"""Browser-based OAuth token exchange for providers protected by Cloudflare.

StockX's token endpoint is behind Cloudflare/PerimeterX bot detection and rejects
plain HTTP requests from Python's standard library. This module uses Playwright to
perform the OAuth 2.0 authorization-code flow inside a real browser context, so
the token exchange inherits the browser's cookies and passes Cloudflare's checks.

Playwright is imported lazily so the rest of the provider still works without it
installed (e.g. in CI, or for providers that do not need browser auth). If
Playwright is missing, the caller gets a clear :class:`ProviderConfigError`.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import urllib.parse
from pathlib import Path
from typing import Any

from .auth_code import TokenCache, TokenResponse
from .errors import ProviderAuthError, ProviderConfigError
from .logging_utils import format_fields, get_logger


def _import_playwright() -> Any:
    """Import Playwright lazily; fail with a clear error if not installed."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as err:  # pragma: no cover - optional dependency
        raise ProviderConfigError(
            "Playwright is required for StockX browser authentication. "
            "Install it with: pip install playwright && python -m playwright install chromium"
        ) from err
    return async_playwright


class BrowserTokenExchange:
    """Perform StockX OAuth token exchange through a Playwright browser.

    This class is deliberately isolated from the rest of the provider:
    Playwright is used only to obtain or refresh tokens. After tokens are saved,
    normal API requests go through the standard :class:`HttpClient`.
    """

    _STEALTH_ARGS: tuple[str, ...] = (
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
    )

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        authorization_url: str,
        token_url: str,
        redirect_uri: str,
        scope: str | None = None,
        audience: str | None = None,
        token_cache: TokenCache | None = None,
        storage_state_path: str | Path | None = None,
        headless: bool = False,
        channel: str | None = "msedge",
        provider: str | None = None,
    ) -> None:
        if not all((client_id, client_secret, authorization_url, token_url, redirect_uri)):
            raise ProviderConfigError(
                "client_id, client_secret, authorization_url, token_url, and redirect_uri "
                "are required for browser token exchange"
            )
        self._client_id = client_id
        self._client_secret = client_secret
        self._authorization_url = authorization_url
        self._token_url = token_url
        self._redirect_uri = redirect_uri
        self._scope = scope
        self._audience = audience
        self._token_cache = token_cache or TokenCache()
        self._storage_state_path = (
            Path(storage_state_path)
            if storage_state_path is not None
            else (TokenCache().path.parent / "stockx_playwright_state.json")
        )
        self._headless = headless
        self._channel = channel
        self._log = get_logger(provider or "browser_auth")

    def _build_auth_url(self, state: str, code_challenge: str) -> str:
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if self._scope:
            params["scope"] = self._scope
        if self._audience:
            params["audience"] = self._audience
        return f"{self._authorization_url}?{urllib.parse.urlencode(params)}"

    def _basic_auth(self) -> str:
        raw = f"{self._client_id}:{self._client_secret}".encode("ascii")
        return f"Basic {base64.b64encode(raw).decode('ascii')}"

    def exchange_refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh an access token using Playwright's browser request context.

        Synchronous wrapper around the async implementation so callers do not need
        to manage an event loop. The resulting tokens are saved to the cache.
        """
        response = asyncio.run(self._async_exchange_with_refresh_token(refresh_token))
        self._save_token_response(response)
        return response

    async def _async_exchange_with_refresh_token(self, refresh_token: str) -> TokenResponse:
        async_playwright = _import_playwright()
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel=self._channel,
                headless=self._headless,
                args=list(self._STEALTH_ARGS),
            )
            try:
                storage_state = self._load_storage_state()
                context = await browser.new_context(storage_state=storage_state)
                page = await context.new_page()
                # Visit the StockX domain first to pick up any Cloudflare cookies.
                await page.goto("https://accounts.stockx.com", wait_until="domcontentloaded")
                response = await context.request.post(
                    self._token_url,
                    headers={
                        "Authorization": self._basic_auth(),
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    form={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                )
                body = await response.json()
            finally:
                storage_state = await context.storage_state()
                self._save_storage_state(storage_state)
                await browser.close()
        return self._parse_token_response(body)

    def _load_storage_state(self) -> dict[str, Any] | None:
        """Load a previously saved Playwright storage state, if any."""
        if self._storage_state_path.is_file():
            try:
                return json.loads(self._storage_state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def _save_storage_state(self, state: dict[str, Any]) -> None:
        """Persist Playwright storage state so the next run can reuse cookies."""
        self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _save_token_response(self, response: TokenResponse) -> None:
        data: dict[str, Any] = {
            "access_token": response.access_token,
            "expires_in": response.expires_in,
            "token_type": response.token_type,
        }
        if response.refresh_token:
            data["refresh_token"] = response.refresh_token
        if response.scope:
            data["scope"] = response.scope
        self._token_cache.save(data)

    def run_initial_flow(self, timeout: float = 300.0) -> TokenResponse:
        """Open the browser, authorize, and exchange the code for tokens.

        This is the interactive path: the user must log in to StockX in the
        opened browser. The callback is intercepted by Playwright, so no local
        HTTPS server is required.
        """
        return asyncio.run(self._async_run_initial_flow(timeout))

    async def _async_run_initial_flow(self, timeout: float) -> TokenResponse:
        async_playwright = _import_playwright()
        state = secrets.token_urlsafe(16)
        code_verifier = secrets.token_urlsafe(48)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        auth_url = self._build_auth_url(state, code_challenge)

        parsed_redirect = urllib.parse.urlsplit(self._redirect_uri)
        redirect_pattern = (
            f"{parsed_redirect.scheme}://{parsed_redirect.netloc}{parsed_redirect.path}*"
        )

        code: str | None = None
        auth_error: str | None = None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel=self._channel,
                headless=self._headless,
                args=list(self._STEALTH_ARGS),
            )
            try:
                storage_state = self._load_storage_state()
                context = await browser.new_context(storage_state=storage_state)
                page = await context.new_page()

                async def _handle_route(route, request) -> None:
                    nonlocal code, auth_error
                    url = request.url
                    if url.startswith(self._redirect_uri):
                        parsed = urllib.parse.urlsplit(url)
                        query = urllib.parse.parse_qs(parsed.query)
                        if "code" in query:
                            code = query["code"][0]
                        elif "error" in query:
                            auth_error = query["error"][0]
                        await route.fulfill(
                            status=200,
                            content_type="text/plain",
                            body="Authorization successful. You may close this tab.",
                        )
                        return
                    await route.continue_()

                await page.route(redirect_pattern, _handle_route)

                self._log.info(
                    "browser_auth_opening %s",
                    format_fields(provider=self._log.name),
                )
                await page.goto(auth_url, wait_until="domcontentloaded")

                # Wait for the callback to be intercepted.
                deadline = asyncio.get_event_loop().time() + timeout
                while code is None and auth_error is None:
                    if asyncio.get_event_loop().time() > deadline:
                        raise ProviderAuthError(
                            "browser authorization timed out", provider=self._log.name
                        )
                    await asyncio.sleep(0.5)

                if auth_error:
                    raise ProviderAuthError(
                        f"authorization server returned error: {auth_error}",
                        provider=self._log.name,
                    )
                if code is None:
                    raise ProviderAuthError(
                        "authorization code not captured", provider=self._log.name
                    )

                self._log.info(
                    "browser_auth_code_captured %s",
                    format_fields(provider=self._log.name),
                )

                # Perform the token exchange inside the browser context.
                response = await context.request.post(
                    self._token_url,
                    headers={
                        "Authorization": self._basic_auth(),
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    form={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self._redirect_uri,
                        "code_verifier": code_verifier,
                    },
                )
                body = await response.json()
            finally:
                storage_state = await context.storage_state()
                self._save_storage_state(storage_state)
                await browser.close()

        response = self._parse_token_response(body)
        self._save_token_response(response)
        return response

    def _parse_token_response(self, payload: dict[str, Any]) -> TokenResponse:
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProviderAuthError(
                "token endpoint response missing 'access_token'", provider=self._log.name
            )
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise ProviderAuthError(
                "token endpoint response has invalid 'expires_in'", provider=self._log.name
            )
        refresh_token = payload.get("refresh_token")
        if refresh_token is not None and not isinstance(refresh_token, str):
            raise ProviderAuthError(
                "token endpoint response has invalid 'refresh_token'", provider=self._log.name
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
