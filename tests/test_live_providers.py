"""Tests for the live-provider framework (Sprint 21).

Covers the reusable infrastructure - errors, retry policy + backoff, token-bucket
rate limiting, HTTP client, response validation, pagination, capability metadata,
config, and the ``LiveProvider`` base - plus a localhost integration test that
exercises the real ``UrllibTransport`` over loopback (no external network).
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from digital_arbitrage.product_scanner import build_scanner
from digital_arbitrage.product_scanner.models import Listing
from digital_arbitrage.product_scanner.providers.base import Provider
from digital_arbitrage.providers.live import (
    HttpClient,
    HttpRequest,
    HttpResponse,
    LiveProvider,
    LiveProviderConfig,
    Page,
    ProviderCapabilities,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTimeoutError,
    RetryPolicy,
    TokenBucketRateLimiter,
    Transport,
    ensure_list,
    ensure_mapping,
    optional,
    paginate,
    parse_json,
    require,
    require_number,
    resolve_url,
    run_with_retries,
)

# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


def _json_response(status: int, obj: object, headers: dict[str, str] | None = None) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers=headers or {},
        body=json.dumps(obj).encode(),
        url="http://test.local/x",
    )


class _ScriptTransport(Transport):
    """Returns responses / raises errors from a scripted sequence."""

    def __init__(self, actions: list[HttpResponse | Exception]) -> None:
        self._actions = list(actions)
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        action = self._actions.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


class _PagingTransport(Transport):
    """Serves a fixed list of pages keyed by the ``page`` query param."""

    def __init__(self, pages: list[HttpResponse]) -> None:
        self._pages = pages
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        page = int(dict(request.params).get("page", "1"))
        return self._pages[page - 1]


class _DemoProvider(LiveProvider):
    """Minimal live provider used only for tests (not registered globally)."""

    name = "demo_market"
    capabilities = ProviderCapabilities(supports_pagination=True, max_page_size=2)

    def build_request(self, query: str, *, page: int, page_size: int) -> HttpRequest:
        return HttpRequest(
            method="GET",
            url=resolve_url(self.config.base_url, "/search"),
            params={"q": query, "page": str(page), "size": str(page_size)},
        )

    def parse_response(self, response: HttpResponse, *, query: str) -> Page[Listing]:
        payload = ensure_mapping(parse_json(response, provider=self.name), provider=self.name)
        raw_items = ensure_list(payload.get("items"), context="items", provider=self.name)
        listings: list[Listing] = []
        for raw in raw_items:
            obj = ensure_mapping(raw, context="items[]", provider=self.name)
            listings.append(
                Listing(
                    listing_id=require(obj, "id", str, provider=self.name),
                    title=require(obj, "title", str, provider=self.name),
                    provider=self.name,
                    url=require(obj, "url", str, provider=self.name),
                    price=require_number(obj, "price", provider=self.name),
                    currency=self.config.default_currency,
                )
            )
        return Page(items=tuple(listings), has_more=bool(payload.get("has_more", False)))


def _demo(
    transport: Transport,
    *,
    config: LiveProviderConfig | None = None,
) -> _DemoProvider:
    cfg = config or LiveProviderConfig(
        base_url="http://api.test.local", max_results=50, page_size=2
    )
    client = HttpClient(
        cfg,
        provider="demo_market",
        transport=transport,
        sleep=lambda _s: None,
        random_fn=lambda: 0.0,
    )
    return _DemoProvider(cfg, http_client=client)


def _page_body(ids: list[int], *, has_more: bool) -> dict[str, object]:
    return {
        "items": [
            {"id": str(i), "title": f"Item {i}", "url": f"http://x/{i}", "price": float(i)}
            for i in ids
        ],
        "has_more": has_more,
    }


# --------------------------------------------------------------------------- #
# Error hierarchy
# --------------------------------------------------------------------------- #


def test_error_str_includes_provider() -> None:
    err = ProviderHTTPError("boom", status_code=500, provider="ebay")
    assert str(err) == "[ebay] boom"
    assert ProviderResponseError("bad").__str__() == "bad"


def test_retry_policy_classifies_retryable_errors() -> None:
    policy = RetryPolicy()
    assert policy.is_retryable(ProviderTimeoutError("t"))
    assert policy.is_retryable(ProviderConnectionError("c"))
    assert policy.is_retryable(ProviderRateLimitError("r"))  # 429
    assert policy.is_retryable(ProviderHTTPError("s", status_code=503))
    assert not policy.is_retryable(ProviderHTTPError("nf", status_code=404))
    assert not policy.is_retryable(ProviderResponseError("bad"))


# --------------------------------------------------------------------------- #
# Retry policy + backoff
# --------------------------------------------------------------------------- #


def test_backoff_delay_is_exponential_and_capped() -> None:
    policy = RetryPolicy(backoff_base=1.0, backoff_factor=2.0, max_backoff=5.0, jitter=False)
    assert policy.backoff_delay(1) == 1.0
    assert policy.backoff_delay(2) == 2.0
    assert policy.backoff_delay(3) == 4.0
    assert policy.backoff_delay(4) == 5.0  # capped


def test_backoff_jitter_stays_within_equal_jitter_band() -> None:
    policy = RetryPolicy(backoff_base=2.0, backoff_factor=1.0, jitter=True)
    assert policy.backoff_delay(1, random_fn=lambda: 0.0) == pytest.approx(1.0)  # 0.5 * 2
    assert policy.backoff_delay(1, random_fn=lambda: 1.0) == pytest.approx(2.0)  # 1.0 * 2


def test_backoff_invalid_attempt_raises() -> None:
    with pytest.raises(ValueError):
        RetryPolicy().backoff_delay(0)


def test_retry_policy_validates_fields() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_factor=0.5)


def test_run_with_retries_succeeds_first_try_without_sleeping() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def op() -> str:
        calls["n"] += 1
        return "ok"

    result = run_with_retries(op, RetryPolicy(), sleep=sleeps.append)
    assert result == "ok"
    assert calls["n"] == 1
    assert sleeps == []


def test_run_with_retries_retries_then_succeeds() -> None:
    sleeps: list[float] = []
    retries: list[int] = []
    seq: list[ProviderError | str] = [ProviderTimeoutError("t"), ProviderTimeoutError("t"), "done"]

    def op() -> str:
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    result = run_with_retries(
        op,
        RetryPolicy(max_attempts=3, backoff_base=1.0, backoff_factor=2.0, jitter=False),
        sleep=sleeps.append,
        on_retry=lambda attempt, _e, _d: retries.append(attempt),
    )
    assert result == "done"
    assert sleeps == [1.0, 2.0]
    assert retries == [1, 2]


def test_run_with_retries_gives_up_and_sets_attempts() -> None:
    def op() -> str:
        raise ProviderTimeoutError("t", url="http://x")

    with pytest.raises(ProviderTimeoutError) as excinfo:
        run_with_retries(op, RetryPolicy(max_attempts=3, jitter=False), sleep=lambda _s: None)
    assert excinfo.value.attempts == 3


def test_run_with_retries_does_not_retry_non_retryable() -> None:
    calls = {"n": 0}

    def op() -> str:
        calls["n"] += 1
        raise ProviderHTTPError("nf", status_code=404)

    with pytest.raises(ProviderHTTPError):
        run_with_retries(op, RetryPolicy(max_attempts=5), sleep=lambda _s: None)
    assert calls["n"] == 1


def test_run_with_retries_honours_retry_after_floor() -> None:
    sleeps: list[float] = []
    seq: list[ProviderError | str] = [ProviderRateLimitError("r", retry_after=10.0), "ok"]

    def op() -> str:
        item = seq.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    run_with_retries(
        op,
        RetryPolicy(max_attempts=2, backoff_base=1.0, jitter=False),
        sleep=sleeps.append,
    )
    assert sleeps == [10.0]  # retry_after (10) beats the 1s backoff


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_rate_limiter_try_acquire_consumes_burst_then_fails() -> None:
    clock = _FakeClock()
    limiter = TokenBucketRateLimiter(1.0, capacity=2, monotonic=clock.monotonic, sleep=clock.sleep)
    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert not limiter.try_acquire()  # burst exhausted, no time passed


def test_rate_limiter_acquire_waits_for_refill() -> None:
    clock = _FakeClock()
    limiter = TokenBucketRateLimiter(2.0, capacity=1, monotonic=clock.monotonic, sleep=clock.sleep)
    assert limiter.acquire() == 0.0  # first token from the initial burst
    waited = limiter.acquire()  # must wait for one token at 2/sec -> 0.5s
    assert waited == pytest.approx(0.5)
    assert clock.now == pytest.approx(0.5)


def test_rate_limiter_refills_over_time() -> None:
    clock = _FakeClock()
    limiter = TokenBucketRateLimiter(1.0, capacity=1, monotonic=clock.monotonic, sleep=clock.sleep)
    assert limiter.try_acquire()
    clock.now += 1.0  # one second -> one token refilled
    assert limiter.try_acquire()


def test_rate_limiter_validates_arguments() -> None:
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(0)
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(1.0, capacity=0)
    limiter = TokenBucketRateLimiter(1.0, capacity=1)
    with pytest.raises(ValueError):
        limiter.acquire(5)  # exceeds capacity
    with pytest.raises(ValueError):
        limiter.try_acquire(0)


# --------------------------------------------------------------------------- #
# HTTP client (with fake transport)
# --------------------------------------------------------------------------- #


def test_http_client_sets_default_headers_and_auth() -> None:
    transport = _ScriptTransport([_json_response(200, {"ok": True})])
    cfg = LiveProviderConfig(base_url="http://api.test.local", api_key="secret", user_agent="ua/1")
    client = HttpClient(cfg, provider="demo", transport=transport)
    client.get("/path", params={"q": "x"})
    sent = transport.requests[0]
    assert sent.headers["User-Agent"] == "ua/1"
    assert sent.headers["Accept"] == "application/json"
    assert sent.headers["Authorization"] == "Bearer secret"
    assert sent.full_url() == "http://api.test.local/path?q=x"
    assert sent.timeout == cfg.timeout


def test_http_client_retries_transport_failures() -> None:
    transport = _ScriptTransport(
        [ProviderConnectionError("reset"), _json_response(200, {"ok": True})]
    )
    cfg = LiveProviderConfig(base_url="http://api.test.local")
    client = HttpClient(
        cfg, provider="demo", transport=transport, sleep=lambda _s: None, random_fn=lambda: 0.0
    )
    resp = client.get("/x")
    assert resp.status == 200
    assert len(transport.requests) == 2


def test_http_client_invokes_rate_limiter_per_request() -> None:
    transport = _ScriptTransport([_json_response(200, {}), _json_response(200, {})])

    class _SpyLimiter(TokenBucketRateLimiter):
        def __init__(self) -> None:
            super().__init__(1000.0, capacity=1000)
            self.acquired = 0

        def acquire(self, tokens: float = 1.0) -> float:
            self.acquired += 1
            return 0.0

    limiter = _SpyLimiter()
    cfg = LiveProviderConfig(base_url="http://api.test.local")
    client = HttpClient(cfg, provider="demo", transport=transport, rate_limiter=limiter)
    client.get("/a")
    client.get("/b")
    assert limiter.acquired == 2


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_parse_json_rejects_invalid_body() -> None:
    resp = HttpResponse(status=200, headers={}, body=b"not json", url="http://x")
    with pytest.raises(ProviderResponseError):
        parse_json(resp, provider="demo")


def test_ensure_helpers_reject_wrong_types() -> None:
    with pytest.raises(ProviderResponseError):
        ensure_mapping([1, 2], provider="demo")
    with pytest.raises(ProviderResponseError):
        ensure_list({"a": 1}, provider="demo")


def test_require_missing_and_type_mismatch() -> None:
    mapping: dict[str, object] = {"title": "X", "count": 3}
    assert require(mapping, "title", str) == "X"
    with pytest.raises(ProviderResponseError, match="missing required field 'url'"):
        require(mapping, "url", str)
    with pytest.raises(ProviderResponseError, match="expected str"):
        require(mapping, "count", str)


def test_require_rejects_bool_for_int() -> None:
    with pytest.raises(ProviderResponseError):
        require({"flag": True}, "flag", int)


def test_require_number_coerces_int_rejects_bool_and_text() -> None:
    assert require_number({"price": 5}, "price") == 5.0
    assert require_number({"price": 1.5}, "price") == 1.5
    with pytest.raises(ProviderResponseError):
        require_number({"price": True}, "price")
    with pytest.raises(ProviderResponseError):
        require_number({"price": "10"}, "price")


def test_optional_returns_default_for_missing_or_null() -> None:
    assert optional({}, "x", str, default="d") == "d"
    assert optional({"x": None}, "x", str, default="d") == "d"
    assert optional({"x": "v"}, "x", str) == "v"


# --------------------------------------------------------------------------- #
# Capabilities
# --------------------------------------------------------------------------- #


def test_capabilities_defaults_and_serialisation() -> None:
    caps = ProviderCapabilities(supports_pagination=True, max_page_size=25)
    data = caps.to_dict()
    assert data["supports_pagination"] is True
    assert data["max_page_size"] == 25
    assert data["supported_currencies"] == []


def test_capabilities_validation() -> None:
    with pytest.raises(ValueError):
        ProviderCapabilities(max_page_size=0)
    with pytest.raises(ValueError):
        ProviderCapabilities(max_results=0)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


def test_config_rejects_bad_base_url() -> None:
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url="ftp://nope")
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url="not-a-url")


def test_config_validates_numeric_fields() -> None:
    base = "http://x.test"
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url=base, timeout=0)
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url=base, page_size=0)
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url=base, max_results=0)
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url=base, rate_limit_per_second=0)
    with pytest.raises(ProviderConfigError):
        LiveProviderConfig(base_url=base, rate_limit_burst=0)


def test_config_from_dict_maps_nested_retry() -> None:
    cfg = LiveProviderConfig.from_dict(
        {
            "base_url": "http://api.test.local",
            "timeout": 5.0,
            "retry": {"max_attempts": 5, "retry_on_status": [500, 503]},
        }
    )
    assert cfg.timeout == 5.0
    assert cfg.retry.max_attempts == 5
    assert cfg.retry.retry_on_status == frozenset({500, 503})


def test_config_from_dict_rejects_unknown_keys() -> None:
    with pytest.raises(ProviderConfigError, match="unknown config key"):
        LiveProviderConfig.from_dict({"base_url": "http://x.test", "bogus": 1})
    with pytest.raises(ProviderConfigError, match="unknown retry config key"):
        LiveProviderConfig.from_dict({"base_url": "http://x.test", "retry": {"nope": 1}})


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #


def test_paginate_stops_when_no_more() -> None:
    pages = [Page(items=(1, 2), has_more=False)]
    result = paginate(lambda _p: pages[0], max_results=10)
    assert result == [1, 2]


def test_paginate_walks_pages_until_exhausted() -> None:
    pages = [
        Page(items=(1, 2), has_more=True),
        Page(items=(3, 4), has_more=True),
        Page(items=(5,), has_more=False),
    ]
    seen: list[int] = []

    def fetch(page: int) -> Page[int]:
        seen.append(page)
        return pages[page - 1]

    assert paginate(fetch, max_results=10) == [1, 2, 3, 4, 5]
    assert seen == [1, 2, 3]


def test_paginate_truncates_to_max_results() -> None:
    pages = [Page(items=(1, 2, 3), has_more=True), Page(items=(4, 5, 6), has_more=True)]
    assert paginate(lambda p: pages[p - 1], max_results=4) == [1, 2, 3, 4]


def test_paginate_respects_max_pages() -> None:
    page = Page(items=(1,), has_more=True)
    calls: list[int] = []

    def fetch(p: int) -> Page[int]:
        calls.append(p)
        return page

    assert paginate(fetch, max_results=100, max_pages=3) == [1, 1, 1]
    assert calls == [1, 2, 3]


def test_paginate_validates_arguments() -> None:
    with pytest.raises(ValueError):
        paginate(lambda _p: Page(items=()), max_results=0)
    with pytest.raises(ValueError):
        paginate(lambda _p: Page(items=()), max_results=1, max_pages=0)


# --------------------------------------------------------------------------- #
# LiveProvider base
# --------------------------------------------------------------------------- #


def test_live_provider_is_a_provider() -> None:
    assert issubclass(LiveProvider, Provider)


def test_live_provider_fetches_and_parses_single_page() -> None:
    transport = _PagingTransport([_json_response(200, _page_body([1, 2], has_more=False))])
    provider = _demo(transport)
    listings = provider.search("rtx 4090", limit=10)
    assert [listing.listing_id for listing in listings] == ["1", "2"]
    assert all(listing.provider == "demo_market" for listing in listings)


def test_live_provider_paginates_up_to_max_results() -> None:
    transport = _PagingTransport(
        [
            _json_response(200, _page_body([1, 2], has_more=True)),
            _json_response(200, _page_body([3, 4], has_more=True)),
            _json_response(200, _page_body([5, 6], has_more=True)),
        ]
    )
    provider = _demo(transport)
    listings = provider.search("q", limit=5)
    assert [listing.listing_id for listing in listings] == ["1", "2", "3", "4", "5"]
    # page_size is 2, so 3 pages fetched to reach 5 results.
    assert len(transport.requests) == 3


def test_live_provider_without_pagination_fetches_one_page() -> None:
    class _NoPaging(_DemoProvider):
        name = "no_paging"
        capabilities = ProviderCapabilities(supports_pagination=False, max_page_size=2)

    transport = _PagingTransport(
        [
            _json_response(200, _page_body([1, 2], has_more=True)),
            _json_response(200, _page_body([3, 4], has_more=True)),
        ]
    )
    cfg = LiveProviderConfig(base_url="http://api.test.local", page_size=2, max_results=10)
    client = HttpClient(cfg, provider="no_paging", transport=transport, sleep=lambda _s: None)
    provider = _NoPaging(cfg, http_client=client)
    listings = provider.search("q", limit=10)
    assert [listing.listing_id for listing in listings] == ["1", "2"]
    assert len(transport.requests) == 1  # capability disables pagination


def test_live_provider_requires_api_key_when_capability_demands_it() -> None:
    class _Keyed(_DemoProvider):
        name = "keyed"
        capabilities = ProviderCapabilities(requires_api_key=True)

    cfg = LiveProviderConfig(base_url="http://api.test.local")
    with pytest.raises(ProviderConfigError, match="requires an api_key"):
        _Keyed(cfg)


def test_live_provider_clamps_limit_to_config_max_results() -> None:
    transport = _PagingTransport([_json_response(200, _page_body([1, 2], has_more=True))] * 5)
    cfg = LiveProviderConfig(base_url="http://api.test.local", page_size=2, max_results=3)
    client = HttpClient(cfg, provider="demo_market", transport=transport, sleep=lambda _s: None)
    provider = _DemoProvider(cfg, http_client=client)
    listings = provider.search("q", limit=100)  # request 100, config caps at 3
    assert len(listings) == 3


def test_live_provider_propagates_response_errors() -> None:
    transport = _PagingTransport([_json_response(200, {"items": "not-a-list"})])
    provider = _demo(transport)
    with pytest.raises(ProviderResponseError):
        provider.search("q", limit=5)


def test_get_capabilities_classmethod() -> None:
    assert _DemoProvider.get_capabilities().supports_pagination is True


# --------------------------------------------------------------------------- #
# Backwards compatibility
# --------------------------------------------------------------------------- #


def test_existing_mock_scanner_still_works() -> None:
    scanner = build_scanner()
    listings = scanner.scan("rtx 4090", limit=2)
    assert listings
    assert all(isinstance(listing, Listing) for listing in listings)


def test_live_framework_does_not_register_providers() -> None:
    from digital_arbitrage.product_scanner.providers.base import PROVIDER_REGISTRY

    assert "demo_market" not in PROVIDER_REGISTRY
    assert set(PROVIDER_REGISTRY) == {"ebay", "facebook_marketplace", "adverts_ie", "donedeal"}


# --------------------------------------------------------------------------- #
# UrllibTransport - localhost integration (loopback only, no external network)
# --------------------------------------------------------------------------- #


class _IntegrationHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:  # silence test server logging
        pass

    def do_GET(self) -> None:  # noqa: N802 - required handler name
        if self.path.startswith("/ok"):
            body = json.dumps(_page_body([1], has_more=False)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/notfound":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"missing")
        elif self.path == "/err500":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"boom")
        elif self.path == "/limited":
            self.send_response(429)
            self.send_header("Retry-After", "2")
            self.end_headers()
            self.wfile.write(b"slow down")
        elif self.path == "/slow":
            time.sleep(0.5)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture()
def live_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _IntegrationHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _client(
    base_url: str, *, retry: RetryPolicy | None = None, timeout: float = 10.0
) -> HttpClient:
    cfg = LiveProviderConfig(base_url=base_url, timeout=timeout, retry=retry or RetryPolicy())
    return HttpClient(cfg, provider="itest", sleep=lambda _s: None, random_fn=lambda: 0.0)


def test_integration_get_ok(live_server: str) -> None:
    resp = _client(live_server).get("/ok")
    assert resp.status == 200
    assert resp.ok
    assert resp.headers["content-type"] == "application/json"
    assert resp.json()["items"][0]["id"] == "1"


def test_integration_404_raises_non_retryable(live_server: str) -> None:
    client = _client(live_server, retry=RetryPolicy(max_attempts=1))
    with pytest.raises(ProviderHTTPError) as excinfo:
        client.request("GET", "/notfound")
    assert excinfo.value.status_code == 404


def test_integration_500_is_retried_then_raised(live_server: str) -> None:
    cfg = LiveProviderConfig(base_url=live_server, retry=RetryPolicy(max_attempts=2, jitter=False))
    client = HttpClient(cfg, provider="itest", sleep=lambda _s: None)
    with pytest.raises(ProviderHTTPError) as excinfo:
        client.get("/err500")
    assert excinfo.value.status_code == 500
    assert excinfo.value.attempts == 2


def test_integration_429_maps_to_rate_limit_with_retry_after(live_server: str) -> None:
    cfg = LiveProviderConfig(base_url=live_server, retry=RetryPolicy(max_attempts=1))
    client = HttpClient(cfg, provider="itest", sleep=lambda _s: None)
    with pytest.raises(ProviderRateLimitError) as excinfo:
        client.get("/limited")
    assert excinfo.value.retry_after == 2.0


def test_integration_timeout_maps_to_timeout_error(live_server: str) -> None:
    cfg = LiveProviderConfig(base_url=live_server, timeout=0.1, retry=RetryPolicy(max_attempts=1))
    client = HttpClient(cfg, provider="itest", sleep=lambda _s: None)
    with pytest.raises(ProviderTimeoutError):
        client.get("/slow")
