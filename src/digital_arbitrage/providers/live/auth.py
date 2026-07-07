"""Authentication strategies for live providers.

An :class:`AuthProvider` supplies the ``Authorization`` header value for each
outbound request. Keeping auth behind a small interface lets the
:class:`~digital_arbitrage.providers.live.http.HttpClient` stay agnostic to *how*
a request is authenticated:

* :class:`NoAuthProvider` - public endpoints (no header).
* :class:`StaticBearerTokenAuthProvider` - a fixed, pre-issued token.
* :class:`OAuthClientCredentialsAuthProvider` - mints an *application* token via
  the OAuth 2.0 client-credentials grant, caches it, and refreshes it safely
  before expiry (as required by e.g. the eBay Browse API).

Standard library only. Credentials are never logged. No live network calls are
made here in tests - the token round trip goes through an injectable
:class:`~digital_arbitrage.providers.live.http.Transport`.
"""

from __future__ import annotations

import base64
import threading
import time
import urllib.parse
from abc import ABC, abstractmethod
from collections.abc import Callable

from .errors import ProviderAuthError, ProviderConfigError, ProviderError
from .http import HttpRequest, Transport, UrllibTransport
from .logging_utils import format_fields, get_logger

_ALLOWED_SCHEMES = frozenset({"http", "https"})


class AuthProvider(ABC):
    """Supplies the ``Authorization`` header value for outbound requests."""

    @abstractmethod
    def authorization(self) -> str | None:
        """Return the full ``Authorization`` header value, or ``None`` for none.

        Called once per request by the HTTP client, so implementations that
        cache/refresh tokens can do so transparently.
        """


class NoAuthProvider(AuthProvider):
    """No authentication: never sets an ``Authorization`` header."""

    def authorization(self) -> str | None:
        return None


class StaticBearerTokenAuthProvider(AuthProvider):
    """A fixed, pre-issued token sent as ``<scheme> <token>`` (default Bearer)."""

    def __init__(self, token: str, *, scheme: str = "Bearer") -> None:
        if not token:
            raise ProviderConfigError("token must not be empty")
        self._value = f"{scheme} {token}" if scheme else token

    def authorization(self) -> str | None:
        return self._value


class OAuthClientCredentialsAuthProvider(AuthProvider):
    """Mint + cache + refresh an OAuth 2.0 client-credentials application token.

    The token is fetched lazily on first use, cached, and re-minted once it is
    within ``refresh_leeway`` seconds of expiry (so a request never travels with
    an about-to-expire token). Thread-safe. The token endpoint round trip uses an
    injectable :class:`Transport`, so tests never touch the network.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        token_url: str,
        scope: str | None = None,
        provider: str | None = None,
        transport: Transport | None = None,
        timeout: float = 10.0,
        refresh_leeway: float = 60.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not client_id or not client_secret:
            raise ProviderConfigError("client_id and client_secret must not be empty")
        parsed = urllib.parse.urlsplit(token_url)
        if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.netloc:
            raise ProviderConfigError(f"token_url must be an http(s) URL, got {token_url!r}")
        if timeout <= 0:
            raise ProviderConfigError("timeout must be positive")
        if refresh_leeway < 0:
            raise ProviderConfigError("refresh_leeway must be non-negative")

        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._scope = scope
        self._provider = provider
        self._transport = transport or UrllibTransport(provider=provider)
        self._timeout = timeout
        self._refresh_leeway = refresh_leeway
        self._monotonic = monotonic
        self._log = get_logger(provider or "oauth")

        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def authorization(self) -> str | None:
        return f"Bearer {self._access_token()}"

    def _access_token(self) -> str:
        with self._lock:
            now = self._monotonic()
            if self._token is None or now >= self._expires_at:
                self._mint(now)
            assert self._token is not None  # noqa: S101 - set by _mint on success
            return self._token

    def _basic_auth_header(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode()
        return f"Basic {base64.b64encode(raw).decode('ascii')}"

    def _mint(self, now: float) -> None:
        form = {"grant_type": "client_credentials"}
        if self._scope:
            form["scope"] = self._scope
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
            # Never leak credentials: surface only the failure kind.
            raise ProviderAuthError(
                f"failed to obtain OAuth token: {type(err).__name__}",
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
                "token endpoint returned invalid JSON",
                provider=self._provider,
            ) from err
        if not isinstance(payload, dict):
            raise ProviderAuthError(
                "token endpoint returned a non-object body",
                provider=self._provider,
            )

        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise ProviderAuthError(
                "token endpoint response missing 'access_token'",
                provider=self._provider,
            )
        expires_in = payload.get("expires_in")
        # bool is an int subclass; reject it explicitly.
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise ProviderAuthError(
                "token endpoint response has invalid 'expires_in'",
                provider=self._provider,
            )

        self._token = token
        self._expires_at = now + max(float(expires_in) - self._refresh_leeway, 0.0)
        self._log.info(
            "oauth_token_minted %s",
            format_fields(
                provider=self._provider,
                expires_in=int(expires_in),
                refresh_leeway=self._refresh_leeway,
            ),
        )
