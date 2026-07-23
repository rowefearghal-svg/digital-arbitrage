"""Tests for the StockX live provider (Sprint 29).

All tests are hermetic: a fake :class:`Transport` replays committed JSON fixtures,
so no live network call and no real secret is used. Coverage spans request
construction, search -> :class:`Listing` mapping, market-data price extraction,
pagination, error handling, and env-based builder wiring.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.product_scanner.models import Condition, Listing
from digital_arbitrage.providers.live import (
    HttpClient,
    HttpRequest,
    HttpResponse,
    ProviderConfigError,
    ProviderResponseError,
    StockXConfig,
    StockXProvider,
    Transport,
    build_stockx_config,
    build_stockx_provider,
    build_stockx_provider_from_env,
    create_live_provider,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "stockx"


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _response(status: int, body: bytes, headers: dict[str, str] | None = None) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers=headers or {},
        body=body,
        url="https://api.stockx.com/v2/catalog/search",
    )


class _ReplayTransport(Transport):
    """Replays fixtures based on the request URL path."""

    def __init__(
        self,
        search: HttpResponse,
        market_data: dict[str, HttpResponse],
    ) -> None:
        self._search = search
        self._market_data = market_data
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        path = request.full_url().split("?", 1)[0]
        if path.endswith("/market-data"):
            product_id = path.split("/")[-2]
            return self._market_data[product_id]
        return self._search


class _BrokenTransport(Transport):
    """Raises an error for every request after optionally returning one response."""

    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self._responses = list(responses)
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        action = self._responses.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


def _config(**overrides: object) -> StockXConfig:
    params: dict[str, object] = {
        "base_url": "https://api.stockx.com",
        "api_key": "test-api-key",
        "page_size": 2,
        "max_results": 10,
        "default_currency": "USD",
        "currency_code": "USD",
    }
    params.update(overrides)
    return StockXConfig(**params)  # type: ignore[arg-type]


def _provider(transport: Transport, *, config: StockXConfig | None = None) -> StockXProvider:
    cfg = config or _config()
    client = HttpClient(
        cfg,
        provider=StockXProvider.name,
        transport=transport,
        sleep=lambda _s: None,
        random_fn=lambda: 0.0,
    )
    provider = create_live_provider(StockXProvider.name, cfg, http_client=client)
    assert isinstance(provider, StockXProvider)
    return provider


# --------------------------------------------------------------------------- #
# Config and request construction
# --------------------------------------------------------------------------- #


def test_config_defaults_are_valid() -> None:
    config = build_stockx_config({})
    assert config.base_url == "https://api.stockx.com"
    assert config.currency_code == "USD"


def test_config_rejects_bad_oauth_url() -> None:
    with pytest.raises(ProviderConfigError):
        build_stockx_config({"oauth_token_url": "not-a-url"})


def test_build_request_shape() -> None:
    provider = _provider(_ReplayTransport(_response(200, b"{}"), {}))
    request = provider.build_request("nike dunk low", page=2, page_size=25)
    assert request.method == "GET"
    assert request.url == "https://api.stockx.com/v2/catalog/search"
    params = dict(request.params)
    assert params["query"] == "nike dunk low"
    assert params["pageNumber"] == "2"
    assert params["pageSize"] == "25"


def test_build_request_truncates_long_query() -> None:
    provider = _provider(_ReplayTransport(_response(200, b"{}"), {}))
    request = provider.build_request("x" * 250, page=1, page_size=10)
    assert len(dict(request.params)["query"]) == StockXProvider.MAX_QUERY_LENGTH


# --------------------------------------------------------------------------- #
# Response mapping
# --------------------------------------------------------------------------- #


def test_maps_search_and_market_data_to_listings() -> None:
    search = _response(200, _fixture_bytes("search.json"))
    market = _response(200, _fixture_bytes("market_data.json"))
    transport = _ReplayTransport(
        search,
        {
            "5e6a1e57-1c7d-435a-82bd-5666a13560fe": market,
            "e175c189-cf87-4007-bc94-e5b919c4c75c": _response(200, b"[]"),
        },
    )
    provider = _provider(transport)
    listings = provider.search("nike dunk low", limit=2)

    assert len(listings) == 2
    first, second = listings
    assert isinstance(first, Listing)
    assert first.listing_id == "5e6a1e57-1c7d-435a-82bd-5666a13560fe"
    assert first.title == "Nike Dunk Low Retro White Black Panda"
    assert first.provider == "stockx"
    assert first.url == "https://stockx.com/nike-dunk-low-retro-white-black-2021"
    assert first.price == 145.0
    assert first.currency == "USD"
    assert first.condition == Condition.NEW
    assert first.extra["brand"] == "Nike"
    assert first.extra["style_id"] == "DD1391-100"
    assert first.extra["lowest_ask"] == "145"
    assert first.extra["highest_bid"] == "11"
    assert first.extra["variant_count"] == "2"

    assert second.price is None
    assert second.extra.get("variant_count") == "0"


def test_empty_products_returns_empty_page() -> None:
    transport = _ReplayTransport(_response(200, b'{"count": 0, "products": null}'), {})
    provider = _provider(transport)
    listings = provider.search("nike dunk low", limit=5)
    assert listings == []


def test_pagination_uses_has_next_page() -> None:
    page1 = _response(
        200,
        json.dumps(
            {
                "count": 3,
                "pageNumber": 1,
                "pageSize": 2,
                "hasNextPage": True,
                "products": [
                    {
                        "productId": "p1",
                        "title": "Product 1",
                        "urlKey": "product-1",
                        "productType": "sneakers",
                        "brand": "Brand",
                        "productAttributes": {},
                    },
                    {
                        "productId": "p2",
                        "title": "Product 2",
                        "urlKey": "product-2",
                        "productType": "sneakers",
                        "brand": "Brand",
                        "productAttributes": {},
                    },
                ],
            }
        ).encode(),
    )
    page2 = _response(
        200,
        json.dumps(
            {
                "count": 3,
                "pageNumber": 2,
                "pageSize": 2,
                "hasNextPage": False,
                "products": [
                    {
                        "productId": "p3",
                        "title": "Product 3",
                        "urlKey": "product-3",
                        "productType": "sneakers",
                        "brand": "Brand",
                        "productAttributes": {},
                    }
                ],
            }
        ).encode(),
    )
    market_empty = _response(200, b"[]")
    transport = _ReplayTransport(
        page1,
        {"p1": market_empty, "p2": market_empty, "p3": market_empty},
    )
    # Override the second search page by using a transport that returns page1 then page2.
    transport = _ScriptedSearchTransport(
        [page1, page2],
        {"p1": market_empty, "p2": market_empty, "p3": market_empty},
    )
    provider = _provider(transport, config=_config(page_size=2, max_results=3))
    listings = provider.search("q", limit=3)
    assert len(listings) == 3
    assert [listing.listing_id for listing in listings] == ["p1", "p2", "p3"]


class _ScriptedSearchTransport(Transport):
    """Returns scripted search pages and market-data responses by path."""

    def __init__(
        self,
        search_pages: list[HttpResponse],
        market_data: dict[str, HttpResponse],
    ) -> None:
        self._search_pages = search_pages
        self._market_data = market_data
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        path = request.full_url().split("?", 1)[0]
        if path.endswith("/market-data"):
            product_id = path.split("/")[-2]
            return self._market_data[product_id]
        page_number = int(dict(request.params).get("pageNumber", "1"))
        return self._search_pages[page_number - 1]


def test_market_data_failure_keeps_listing_without_price() -> None:
    search = _response(200, _fixture_bytes("search.json"))
    transport = _ReplayTransport(
        search,
        {
            "5e6a1e57-1c7d-435a-82bd-5666a13560fe": ProviderResponseError("boom"),
            "e175c189-cf87-4007-bc94-e5b919c4c75c": _response(200, b"[]"),
        },
    )
    provider = _provider(transport)
    listings = provider.search("nike dunk low", limit=2)
    assert len(listings) == 2
    assert listings[0].price is None


def test_provider_requires_api_key_capability() -> None:
    config = _config()
    config.api_key = None
    config.extra_headers = {}
    with pytest.raises(ProviderConfigError, match="requires an api_key"):
        _provider(_ReplayTransport(_response(200, b"{}"), {}), config=config)


# --------------------------------------------------------------------------- #
# Env builder wiring
# --------------------------------------------------------------------------- #


def test_env_builder_requires_credentials() -> None:
    config = _config()
    with pytest.raises(ProviderConfigError, match="STOCKX_API_KEY"):
        build_stockx_provider_from_env(config, env={})


def test_env_builder_requires_cached_refresh_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config()
    env = {
        "STOCKX_API_KEY": "api-key",
        "STOCKX_CLIENT_ID": "cid",
        "STOCKX_CLIENT_SECRET": "secret",
    }
    monkeypatch.setenv("STOCKX_API_KEY", env["STOCKX_API_KEY"])
    monkeypatch.setenv("STOCKX_CLIENT_ID", env["STOCKX_CLIENT_ID"])
    monkeypatch.setenv("STOCKX_CLIENT_SECRET", env["STOCKX_CLIENT_SECRET"])
    from digital_arbitrage.providers.live.auth_code import TokenCache

    cache = TokenCache(path=tmp_path / "stockx_tokens.json")
    monkeypatch.setattr(
        "digital_arbitrage.providers.live.stockx_provider.TokenCache",
        lambda: cache,
    )
    with pytest.raises(ProviderConfigError, match="No cached StockX refresh token"):
        build_stockx_provider_from_env(config)


def test_build_provider_passes_refresh_token_and_api_key() -> None:
    config = _config()
    provider = build_stockx_provider(
        config,
        refresh_token="refresh",
        client_id="cid",
        client_secret="secret",
        api_key="api-key",
        transport=_ReplayTransport(_response(200, b"{}"), {}),
    )
    assert isinstance(provider, StockXProvider)
    assert provider.http._config.extra_headers.get("x-api-key") == "api-key"
