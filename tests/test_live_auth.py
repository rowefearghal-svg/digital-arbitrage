"""Tests for the live-provider auth strategies and config-aware factory (Sprint 23).

Mocked transport only - no live network calls, no real secrets. Covers the
``AuthProvider`` implementations (including OAuth token minting/caching/refresh
and typed auth errors), the ``HttpClient`` auth wiring (with backward
compatibility), ``LiveProvider.create``, and the live-provider registry/factory.
"""

from __future__ import annotations

import base64
import json
import logging
import threading

import pytest

from digital_arbitrage.product_scanner.providers.base import (
    PROVIDER_REGISTRY,
    create_provider,
)
from digital_arbitrage.providers.live import (
    LIVE_PROVIDER_REGISTRY,
    AuthProvider,
    HttpClient,
    HttpRequest,
    HttpResponse,
    LiveProvider,
    LiveProviderConfig,
    NoAuthProvider,
    OAuthClientCredentialsAuthProvider,
    Page,
    ProviderAuthError,
    ProviderCapabilities,
    ProviderConfigError,
    ProviderConnectionError,
    StaticBearerTokenAuthProvider,
    Transport,
    create_live_provider,
    register_live_provider,
)

TOKEN_URL = "https://auth.test.local/identity/v1/oauth2/token"
SCOPE = "https://api.test.local/oauth/api_scope"

# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


class _Clock:
    """A mutable monotonic clock for deterministic expiry tests."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class _MintTransport(Transport):
    """Fake token endpoint: returns a fresh token on each mint."""

    def __init__(self, *, expires_in: float = 7200) -> None:
        self.calls = 0
        self.requests: list[HttpRequest] = []
        self.expires_in = expires_in

    def send(self, request: HttpRequest) -> HttpResponse:
        self.calls += 1
        self.requests.append(request)
        body = {
            "access_token": f"tok-{self.calls}",
            "expires_in": self.expires_in,
            "token_type": "Application Access Token",
        }
        return HttpResponse(200, {}, json.dumps(body).encode(), request.full_url())


class _StaticResultTransport(Transport):
    """Returns a fixed response or raises a fixed error for every request."""

    def __init__(self, result: HttpResponse | Exception) -> None:
        self._result = result
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _EchoTransport(Transport):
    """Records the last request and returns an empty 200 JSON response."""

    def __init__(self) -> None:
        self.last: HttpRequest | None = None

    def send(self, request: HttpRequest) -> HttpResponse:
        self.last = request
        return HttpResponse(200, {}, b"{}", request.full_url())


def _oauth(
    transport: Transport,
    *,
    clock: _Clock | None = None,
    refresh_leeway: float = 60.0,
    scope: str | None = SCOPE,
) -> OAuthClientCredentialsAuthProvider:
    return OAuthClientCredentialsAuthProvider(
        client_id="my-client",
        client_secret="my-secret",
        token_url=TOKEN_URL,
        scope=scope,
        provider="test",
        transport=transport,
        refresh_leeway=refresh_leeway,
        monotonic=clock or _Clock(),
    )


# --------------------------------------------------------------------------- #
# NoAuthProvider / StaticBearerTokenAuthProvider
# --------------------------------------------------------------------------- #


def test_no_auth_provider_returns_none() -> None:
    assert NoAuthProvider().authorization() is None


def test_static_bearer_token_provider() -> None:
    assert StaticBearerTokenAuthProvider("abc").authorization() == "Bearer abc"


def test_static_bearer_custom_scheme() -> None:
    auth = StaticBearerTokenAuthProvider("abc", scheme="Token")
    assert auth.authorization() == "Token abc"


def test_static_bearer_no_scheme() -> None:
    auth = StaticBearerTokenAuthProvider("abc", scheme="")
    assert auth.authorization() == "abc"


def test_static_bearer_empty_token_rejected() -> None:
    with pytest.raises(ProviderConfigError):
        StaticBearerTokenAuthProvider("")


def test_auth_providers_are_auth_provider_instances() -> None:
    assert isinstance(NoAuthProvider(), AuthProvider)
    assert isinstance(StaticBearerTokenAuthProvider("x"), AuthProvider)


# --------------------------------------------------------------------------- #
# OAuthClientCredentialsAuthProvider - happy path, caching, refresh
# --------------------------------------------------------------------------- #


def test_oauth_mints_and_returns_bearer() -> None:
    transport = _MintTransport()
    auth = _oauth(transport)
    assert auth.authorization() == "Bearer tok-1"
    assert transport.calls == 1


def test_oauth_caches_token_until_expiry() -> None:
    transport = _MintTransport(expires_in=7200)
    clock = _Clock(1000.0)
    auth = _oauth(transport, clock=clock)
    assert auth.authorization() == "Bearer tok-1"
    # Well within the token lifetime -> no new mint.
    clock.now = 1000.0 + 7200 - 61
    assert auth.authorization() == "Bearer tok-1"
    assert transport.calls == 1


def test_oauth_refreshes_within_leeway() -> None:
    transport = _MintTransport(expires_in=7200)
    clock = _Clock(1000.0)
    auth = _oauth(transport, clock=clock, refresh_leeway=60.0)
    assert auth.authorization() == "Bearer tok-1"
    # Cross into the refresh leeway window -> re-mint.
    clock.now = 1000.0 + 7200 - 60
    assert auth.authorization() == "Bearer tok-2"
    assert transport.calls == 2


def test_oauth_refreshes_after_expiry() -> None:
    transport = _MintTransport(expires_in=3600)
    clock = _Clock(0.0)
    auth = _oauth(transport, clock=clock, refresh_leeway=0.0)
    assert auth.authorization() == "Bearer tok-1"
    clock.now = 3600.0
    assert auth.authorization() == "Bearer tok-2"
    assert transport.calls == 2


def test_oauth_request_shape() -> None:
    transport = _MintTransport()
    auth = _oauth(transport)
    auth.authorization()
    req = transport.requests[0]
    assert req.method == "POST"
    assert req.url == TOKEN_URL
    expected_basic = base64.b64encode(b"my-client:my-secret").decode()
    assert req.headers["Authorization"] == f"Basic {expected_basic}"
    assert req.headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert req.body is not None
    body = req.body.decode()
    assert "grant_type=client_credentials" in body
    assert "scope=" in body


def test_oauth_omits_scope_when_none() -> None:
    transport = _MintTransport()
    auth = _oauth(transport, scope=None)
    auth.authorization()
    assert transport.requests[0].body is not None
    assert "scope=" not in transport.requests[0].body.decode()


# --------------------------------------------------------------------------- #
# OAuthClientCredentialsAuthProvider - construction validation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kwargs",
    [
        {"client_id": ""},
        {"client_secret": ""},
        {"token_url": "ftp://bad"},
        {"token_url": "not-a-url"},
        {"timeout": 0.0},
        {"refresh_leeway": -1.0},
    ],
)
def test_oauth_construction_validation(kwargs: dict[str, object]) -> None:
    base: dict[str, object] = {
        "client_id": "id",
        "client_secret": "secret",
        "token_url": TOKEN_URL,
    }
    base.update(kwargs)
    with pytest.raises(ProviderConfigError):
        OAuthClientCredentialsAuthProvider(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# OAuthClientCredentialsAuthProvider - error handling
# --------------------------------------------------------------------------- #


def test_oauth_http_error_raises_auth_error() -> None:
    transport = _StaticResultTransport(HttpResponse(401, {}, b"nope", TOKEN_URL))
    auth = _oauth(transport)
    with pytest.raises(ProviderAuthError):
        auth.authorization()


def test_oauth_invalid_json_raises_auth_error() -> None:
    transport = _StaticResultTransport(HttpResponse(200, {}, b"not json", TOKEN_URL))
    with pytest.raises(ProviderAuthError):
        _oauth(transport).authorization()


def test_oauth_non_object_body_raises_auth_error() -> None:
    transport = _StaticResultTransport(HttpResponse(200, {}, b"[1, 2]", TOKEN_URL))
    with pytest.raises(ProviderAuthError):
        _oauth(transport).authorization()


def test_oauth_missing_access_token_raises_auth_error() -> None:
    transport = _StaticResultTransport(
        HttpResponse(200, {}, json.dumps({"expires_in": 100}).encode(), TOKEN_URL)
    )
    with pytest.raises(ProviderAuthError):
        _oauth(transport).authorization()


@pytest.mark.parametrize("expires_in", [True, "3600", None])
def test_oauth_invalid_expires_in_raises_auth_error(expires_in: object) -> None:
    body = json.dumps({"access_token": "t", "expires_in": expires_in}).encode()
    transport = _StaticResultTransport(HttpResponse(200, {}, body, TOKEN_URL))
    with pytest.raises(ProviderAuthError):
        _oauth(transport).authorization()


def test_oauth_transport_error_wrapped_as_auth_error() -> None:
    transport = _StaticResultTransport(
        ProviderConnectionError("boom", provider="test", url=TOKEN_URL)
    )
    with pytest.raises(ProviderAuthError):
        _oauth(transport).authorization()


def test_oauth_never_logs_secrets(caplog: pytest.LogCaptureFixture) -> None:
    transport = _MintTransport()
    auth = _oauth(transport)
    with caplog.at_level(logging.DEBUG, logger="digital_arbitrage.providers"):
        auth.authorization()
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "my-secret" not in text
    assert "tok-1" not in text


# --------------------------------------------------------------------------- #
# OAuth thread safety - only one mint under concurrency
# --------------------------------------------------------------------------- #


def test_oauth_thread_safe_single_mint() -> None:
    transport = _MintTransport()
    auth = _oauth(transport)
    barrier = threading.Barrier(8)
    results: list[str | None] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        value = auth.authorization()
        with lock:
            results.append(value)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)

    assert transport.calls == 1
    assert results == ["Bearer tok-1"] * 8


# --------------------------------------------------------------------------- #
# HttpClient auth wiring + backward compatibility
# --------------------------------------------------------------------------- #


def _client(
    *, api_key: str | None = None, auth: AuthProvider | None = None
) -> tuple[HttpClient, _EchoTransport]:
    transport = _EchoTransport()
    cfg = LiveProviderConfig(base_url="https://api.test.local", api_key=api_key)
    return HttpClient(cfg, provider="t", transport=transport, auth=auth), transport


def test_http_client_uses_auth_provider_header() -> None:
    client, transport = _client(auth=StaticBearerTokenAuthProvider("xyz"))
    client.get("/search")
    assert transport.last is not None
    assert transport.last.headers["Authorization"] == "Bearer xyz"


def test_http_client_auth_overrides_api_key() -> None:
    client, transport = _client(api_key="static-key", auth=StaticBearerTokenAuthProvider("xyz"))
    client.get("/search")
    assert transport.last is not None
    assert transport.last.headers["Authorization"] == "Bearer xyz"


def test_http_client_falls_back_to_api_key() -> None:
    client, transport = _client(api_key="static-key")
    client.get("/search")
    assert transport.last is not None
    assert transport.last.headers["Authorization"] == "Bearer static-key"


def test_http_client_no_auth_no_key_has_no_header() -> None:
    client, transport = _client()
    client.get("/search")
    assert transport.last is not None
    assert "Authorization" not in transport.last.headers


def test_http_client_no_auth_provider_returns_none() -> None:
    client, transport = _client(auth=NoAuthProvider())
    client.get("/search")
    assert transport.last is not None
    assert "Authorization" not in transport.last.headers


def test_http_client_refreshes_token_per_request() -> None:
    mint = _MintTransport(expires_in=3600)
    clock = _Clock(0.0)
    auth = _oauth(mint, clock=clock, refresh_leeway=0.0)
    echo = _EchoTransport()
    cfg = LiveProviderConfig(base_url="https://api.test.local")
    client = HttpClient(cfg, provider="t", transport=echo, auth=auth)

    client.get("/one")
    assert echo.last is not None
    assert echo.last.headers["Authorization"] == "Bearer tok-1"

    clock.now = 3600.0
    client.get("/two")
    assert echo.last.headers["Authorization"] == "Bearer tok-2"


# --------------------------------------------------------------------------- #
# LiveProvider.create + auth-satisfies-requires_api_key
# --------------------------------------------------------------------------- #


class _AuthedProvider(LiveProvider):
    name = "authed_test_provider"
    capabilities = ProviderCapabilities(requires_api_key=True)

    def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
        return HttpRequest(method="GET", url="https://api.test.local/search")

    def parse_response(self, response: HttpResponse, *, query: str) -> Page[object]:
        return Page(items=(), has_more=False)


def test_live_provider_create_wires_auth() -> None:
    echo = _EchoTransport()
    cfg = LiveProviderConfig(base_url="https://api.test.local")
    provider = _AuthedProvider.create(
        cfg, auth=StaticBearerTokenAuthProvider("tok"), transport=echo
    )
    provider.fetch("rtx 4090", limit=5)
    assert echo.last is not None
    assert echo.last.headers["Authorization"] == "Bearer tok"


def test_requires_api_key_satisfied_by_auth() -> None:
    cfg = LiveProviderConfig(base_url="https://api.test.local")
    # No api_key, but an auth provider is supplied -> construction succeeds.
    provider = _AuthedProvider(cfg, auth=StaticBearerTokenAuthProvider("tok"))
    assert isinstance(provider, LiveProvider)


def test_requires_api_key_without_auth_or_key_fails() -> None:
    cfg = LiveProviderConfig(base_url="https://api.test.local")
    with pytest.raises(ProviderConfigError):
        _AuthedProvider(cfg)


# --------------------------------------------------------------------------- #
# Config-aware factory / live registry
# --------------------------------------------------------------------------- #


class _RegistryProvider(LiveProvider):
    name = "registry_test_provider"

    def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
        return HttpRequest(method="GET", url="https://api.test.local/search")

    def parse_response(self, response: HttpResponse, *, query: str) -> Page[object]:
        return Page(items=(), has_more=False)


@pytest.fixture(autouse=True)
def _clean_live_registry() -> object:
    saved = dict(LIVE_PROVIDER_REGISTRY)
    yield
    LIVE_PROVIDER_REGISTRY.clear()
    LIVE_PROVIDER_REGISTRY.update(saved)


def test_register_and_create_live_provider() -> None:
    register_live_provider(_RegistryProvider)
    cfg = LiveProviderConfig(base_url="https://api.test.local")
    echo = _EchoTransport()
    provider = create_live_provider(
        "registry_test_provider", cfg, auth=StaticBearerTokenAuthProvider("k"), transport=echo
    )
    assert isinstance(provider, _RegistryProvider)
    provider.fetch("q", limit=1)
    assert echo.last is not None
    assert echo.last.headers["Authorization"] == "Bearer k"


def test_register_live_provider_is_idempotent() -> None:
    register_live_provider(_RegistryProvider)
    register_live_provider(_RegistryProvider)  # same class, no error
    assert LIVE_PROVIDER_REGISTRY["registry_test_provider"] is _RegistryProvider


def test_register_duplicate_name_rejected() -> None:
    register_live_provider(_RegistryProvider)

    class _Other(_RegistryProvider):
        pass

    with pytest.raises(ValueError, match="already registered"):
        register_live_provider(_Other)


def test_register_empty_name_rejected() -> None:
    class _Nameless(LiveProvider):
        name = ""

        def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
            return HttpRequest(method="GET", url="https://api.test.local")

        def parse_response(self, response: HttpResponse, *, query: str) -> Page[object]:
            return Page(items=(), has_more=False)

    with pytest.raises(ValueError, match="non-empty 'name'"):
        register_live_provider(_Nameless)


def test_create_unknown_live_provider_raises() -> None:
    cfg = LiveProviderConfig(base_url="https://api.test.local")
    with pytest.raises(KeyError, match="unknown live provider"):
        create_live_provider("does_not_exist", cfg)


# --------------------------------------------------------------------------- #
# Backward compatibility: mock registry untouched
# --------------------------------------------------------------------------- #


def test_mock_registry_unaffected_by_live_registry() -> None:
    assert set(PROVIDER_REGISTRY) == {
        "ebay",
        "facebook_marketplace",
        "adverts_ie",
        "donedeal",
    }
    # The two registries are distinct objects.
    assert PROVIDER_REGISTRY is not LIVE_PROVIDER_REGISTRY


def test_create_provider_mock_still_zero_arg() -> None:
    provider = create_provider("ebay")
    listings = provider.search("rtx 4090", limit=3)
    assert len(listings) <= 3
