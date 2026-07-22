"""OAuth 2.0 authorization-code authentication for live providers.

This module implements the server-side parts of the OAuth 2.0 authorization-code
flow needed by a CLI tool:

* :class:`TokenCache` - persists a refresh token securely outside the repository.
* :class:`OAuthAuthorizationCodeAuthProvider` - mints access tokens from a saved
  refresh token, caches them in memory, and refreshes them before expiry.

The initial browser-based authorization is intentionally handled by
:class:`digital_arbitrage.providers.live.auth_browser.BrowserTokenExchange`,
which performs the flow inside a real browser context so providers protected by
Cloudflare (such as StockX) can be authenticated without running a local HTTPS
callback server or managing SSL certificates.

Credentials are never logged. All token round trips use an injectable
:class:`Transport` so tests never touch the network.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auth import AuthProvider
from .errors import ProviderAuthError, ProviderConfigError, ProviderError
from .http import HttpRequest, Transport, UrllibTransport
from .logging_utils import format_fields, get_logger

DEFAULT_TOKEN_DIR = Path.home() / ".digital_arbitrage"
DEFAULT_TOKEN_PATH = DEFAULT_TOKEN_DIR / "stockx_tokens.json"


class TokenCache:
    """Secure, repo-external storage for OAuth refresh tokens.

    The file is stored in the user's home directory (``~/.digital_arbitrage/``),
    never in the project repository. It contains only tokens, never client
    secrets. The file is created with restrictive permissions where the OS
    supports it.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else DEFAULT_TOKEN_PATH

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> dict[str, Any]:
        """Return the cached token payload, or an empty dict if none exists."""
        if not self._path.is_file():
            return {}
        try:
            text = self._path.read_text(encoding="utf-8")
        except OSError as err:
            raise ProviderAuthError(
                f"failed to read token cache: {err}", provider="token_cache"
            ) from err
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            raise ProviderAuthError(
                "token cache contains invalid JSON", provider="token_cache"
            ) from err
        if not isinstance(data, dict):
            raise ProviderAuthError(
                "token cache must contain a JSON object", provider="token_cache"
            )
        return data

    def save(self, tokens: Mapping[str, Any]) -> None:
        """Persist ``tokens`` to the cache file atomically.

        Existing token fields (in particular ``refresh_token``) are preserved
        unless the new payload explicitly overwrites them, so a refresh that
        only returns an access token never accidentally wipes the stored
        refresh token.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(self.load())
        merged.update(tokens)
        payload = json.dumps(merged, indent=2)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            # Windows or restricted FS may not support chmod; ignore.
            pass
        tmp.replace(self._path)

    def clear(self) -> None:
        """Remove the cache file."""
        if self._path.is_file():
            self._path.unlink()


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """Normalized response from a token endpoint."""

    access_token: str
    refresh_token: str | None
    expires_in: int
    scope: str | None = None
    token_type: str = "Bearer"


class _TokenEndpointClient:
    """Internal client for the OAuth token endpoint (shared by auth/refresh)."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        provider: str | None = None,
        transport: Transport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not client_id or not client_secret:
            raise ProviderConfigError("client_id and client_secret must not be empty")
        parsed = urllib.parse.urlsplit(token_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ProviderConfigError(f"token_url must be an http(s) URL, got {token_url!r}")
        if timeout <= 0:
            raise ProviderConfigError("timeout must be positive")

        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._provider = provider
        self._transport = transport or UrllibTransport(provider=provider)
        self._timeout = timeout

    def _basic_auth_header(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode()
        return f"Basic {base64.b64encode(raw).decode('ascii')}"

    def _send_token_request(self, form: dict[str, str]) -> TokenResponse:
        request = HttpRequest(
            method="POST",
            url=self._token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body=urllib.parse.urlencode(form).encode("ascii"),
            timeout=self._timeout,
        )
        try:
            response = self._transport.send(request)
        except ProviderError as err:
            status = getattr(err, "status_code", None)
            detail = f" HTTP {status}" if status else ""
            raise ProviderAuthError(
                f"failed to exchange token: {type(err).__name__}{detail}",
                provider=self._provider,
            ) from err

        if not response.ok:
            raise ProviderAuthError(
                f"token endpoint returned HTTP {response.status}",
                provider=self._provider,
            )
        try:
            payload = response.json()
        except ValueError as err:
            raise ProviderAuthError(
                "token endpoint returned invalid JSON", provider=self._provider
            ) from err
        if not isinstance(payload, dict):
            raise ProviderAuthError(
                "token endpoint returned a non-object body", provider=self._provider
            )

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProviderAuthError(
                "token endpoint response missing 'access_token'", provider=self._provider
            )
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise ProviderAuthError(
                "token endpoint response has invalid 'expires_in'", provider=self._provider
            )
        refresh_token = payload.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise ProviderAuthError(
                "token endpoint response has invalid 'refresh_token'", provider=self._provider
            )
        scope = payload.get("scope") if isinstance(payload.get("scope"), str) else None
        token_type = payload.get("token_type")
        token_type = token_type if isinstance(token_type, str) else "Bearer"
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(expires_in),
            scope=scope,
            token_type=token_type,
        )

    def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> TokenResponse:
        """Exchange an authorization code for tokens."""
        form: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            form["code_verifier"] = code_verifier
        return self._send_token_request(form)

    def refresh(self, refresh_token: str) -> TokenResponse:
        """Refresh an access token using a refresh token."""
        return self._send_token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )


class OAuthAuthorizationCodeAuthProvider(AuthProvider):
    """Mint/cache/refresh an OAuth 2.0 authorization-code access token.

    The initial browser-based authorization must already have been completed and
    the resulting refresh token saved to a :class:`TokenCache`. This provider
    reads the refresh token, mints access tokens on demand, and refreshes them
    before expiry. Thread-safe.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        refresh_token: str | None = None,
        scope: str | None = None,
        audience: str | None = None,
        provider: str | None = None,
        transport: Transport | None = None,
        token_cache: TokenCache | None = None,
        browser_exchange: Any | None = None,
        timeout: float = 10.0,
        refresh_leeway: float = 60.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not refresh_token:
            raise ProviderConfigError(
                "refresh_token is required for authorization-code auth",
                provider=provider,
            )
        self._refresh_token = refresh_token
        self._scope = scope
        self._audience = audience
        self._token_cache = token_cache
        self._browser_exchange = browser_exchange
        self._refresh_leeway = refresh_leeway
        self._monotonic = monotonic
        self._log = get_logger(provider or "oauth_auth_code")

        self._client = _TokenEndpointClient(
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            provider=provider,
            transport=transport,
            timeout=timeout,
        )

        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def authorization(self) -> str | None:
        return f"Bearer {self._access_token()}"

    def _access_token(self) -> str:
        with self._lock:
            now = self._monotonic()
            if self._token is None or now >= self._expires_at:
                self._refresh(now)
            assert self._token is not None
            return self._token

    def _refresh(self, now: float) -> None:
        try:
            response = self._client.refresh(self._refresh_token)
            self._log.info(
                "oauth_token_refreshed %s",
                format_fields(
                    provider=self._client._provider,
                    expires_in=response.expires_in,
                    method="http",
                ),
            )
        except ProviderAuthError:
            # Standard HTTP refresh failed (e.g., Cloudflare-blocked token endpoint).
            # Fall back to browser-based exchange if configured.
            if self._browser_exchange is None:
                raise
            self._log.info(
                "oauth_token_refresh_http_failed_fallback_to_browser %s",
                format_fields(provider=self._client._provider),
            )
            response = self._browser_exchange.exchange_refresh_token(self._refresh_token)
            self._log.info(
                "oauth_token_refreshed %s",
                format_fields(
                    provider=self._client._provider,
                    expires_in=response.expires_in,
                    method="browser",
                ),
            )

        self._token = response.access_token
        self._expires_at = now + max(float(response.expires_in) - self._refresh_leeway, 0.0)

        # If a new refresh token was issued, update the cache.
        if response.refresh_token and self._token_cache is not None:
            self._refresh_token = response.refresh_token
            try:
                data = self._token_cache.load()
            except ProviderAuthError:
                data = {}
            data["refresh_token"] = response.refresh_token
            if response.scope:
                data["scope"] = response.scope
            self._token_cache.save(data)
