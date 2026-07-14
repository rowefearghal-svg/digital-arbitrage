"""Tests for the eBay Browse API provider (Sprint 24).

All tests are hermetic: a fake :class:`Transport` replays sanitised, committed
JSON fixtures, so **no network call and no secret is ever used**. Coverage spans
request construction, response -> :class:`Listing` mapping (condition table,
price/currency/``None`` price, location, ``extra``), pagination, empty results,
error mapping, config validation, the config-aware live registry, and the OAuth
client-credentials wiring (mint + cache) through an injected token transport.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.product_scanner.models import Condition, Listing
from digital_arbitrage.product_scanner.providers.base import PROVIDER_REGISTRY
from digital_arbitrage.providers.live import (
    LIVE_PROVIDER_REGISTRY,
    EbayBrowseConfig,
    EbayBrowseProvider,
    HttpClient,
    HttpRequest,
    HttpResponse,
    LiveProviderConfig,
    ProviderConfigError,
    ProviderHTTPError,
    ProviderRateLimitError,
    ProviderResponseError,
    RetryPolicy,
    StaticBearerTokenAuthProvider,
    Transport,
    build_ebay_browse_provider,
    build_ebay_browse_provider_from_env,
    create_live_provider,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "ebay"


def _fixture_bytes(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


def _response(status: int, body: bytes, headers: dict[str, str] | None = None) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers=headers or {},
        body=body,
        url="https://api.ebay.com/buy/browse/v1/item_summary/search",
    )


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #


class _SearchTransport(Transport):
    """Replays search fixtures keyed by the request's ``offset`` parameter."""

    def __init__(self, by_offset: dict[str, HttpResponse]) -> None:
        self._by_offset = by_offset
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        offset = dict(request.params).get("offset", "0")
        return self._by_offset[offset]


class _StaticTransport(Transport):
    """Returns one response (or raises one error) for every request."""

    def __init__(self, action: HttpResponse | Exception) -> None:
        self._action = action
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if isinstance(self._action, Exception):
            raise self._action
        return self._action


def _config(**overrides: object) -> EbayBrowseConfig:
    params: dict[str, object] = {
        "base_url": "https://api.ebay.com",
        "marketplace_id": "EBAY_IE",
        "page_size": 2,
        "max_results": 50,
        "default_currency": "EUR",
    }
    params.update(overrides)
    return EbayBrowseConfig(**params)  # type: ignore[arg-type]


def _provider(
    transport: Transport, *, config: EbayBrowseConfig | None = None
) -> EbayBrowseProvider:
    cfg = config or _config()
    auth = StaticBearerTokenAuthProvider("test-token")
    client = HttpClient(
        cfg,
        provider=EbayBrowseProvider.name,
        transport=transport,
        auth=auth,
        sleep=lambda _s: None,
        random_fn=lambda: 0.0,
    )
    return EbayBrowseProvider(cfg, http_client=client, auth=auth)


def _page1_provider() -> tuple[EbayBrowseProvider, _SearchTransport]:
    transport = _SearchTransport({"0": _response(200, _fixture_bytes("search_page1.json"))})
    return _provider(transport), transport


# --------------------------------------------------------------------------- #
# Request construction
# --------------------------------------------------------------------------- #


def test_build_request_shape_offset_and_marketplace_header() -> None:
    provider = _provider(_SearchTransport({}))
    request = provider.build_request("rtx 4090", page=3, page_size=50)
    assert request.method == "GET"
    assert request.url == "https://api.ebay.com/buy/browse/v1/item_summary/search"
    params = dict(request.params)
    assert params["q"] == "rtx 4090"
    assert params["limit"] == "50"
    assert params["offset"] == "100"  # (page 3 - 1) * 50
    assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_IE"


def test_build_request_truncates_query_to_100_chars() -> None:
    provider = _provider(_SearchTransport({}))
    request = provider.build_request("x" * 250, page=1, page_size=10)
    assert len(dict(request.params)["q"]) == 100


def test_marketplace_id_is_configurable() -> None:
    provider = _provider(_SearchTransport({}), config=_config(marketplace_id="EBAY_GB"))
    request = provider.build_request("q", page=1, page_size=10)
    assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"


# --------------------------------------------------------------------------- #
# Response mapping
# --------------------------------------------------------------------------- #


def test_maps_all_listing_fields_for_first_item() -> None:
    provider, _ = _page1_provider()
    listings = provider.search("rtx 4090", limit=2)
    first = listings[0]
    assert first.listing_id == "v1|110000000001|0"
    assert first.title == "NVIDIA GeForce RTX 4090 Founders Edition 24GB"
    assert first.provider == "ebay_browse"
    assert first.url == "https://www.ebay.ie/itm/110000000001"
    assert first.price == 1799.99
    assert first.currency == "EUR"
    assert first.location == "Dublin, IE"
    assert first.condition is Condition.NEW
    assert first.posted_at is None
    assert first.extra == {
        "image_url": "https://i.ebayimg.com/images/g/example0001/s-l225.jpg",
        "thumbnail_image_urls": "https://i.ebayimg.com/images/g/example0001/s-l64.jpg",
        "additional_image_urls": (
            "https://i.ebayimg.com/images/g/example0001/s-l500-a.jpg,"
            "https://i.ebayimg.com/images/g/example0001/s-l500-b.jpg"
        ),
        "buying_options": "FIXED_PRICE",
        "condition_id": "1000",
        "condition_text": "New",
        "seller": "example_seller_ie",
        "seller_feedback_percentage": "99.5",
        "seller_feedback_score": "4821",
        "seller_account_type": "BUSINESS",
        "shipping_cost": "12.50",
        "shipping_currency": "EUR",
        "shipping_cost_type": "FIXED",
        "shipping_type": "Economy Shipping",
        "shipping_carrier": "AnPost",
        "shipping_min_delivery": "2026-07-16T00:00:00.000Z",
        "shipping_max_delivery": "2026-07-18T00:00:00.000Z",
        "shipping_guaranteed_delivery": "false",
        "item_city": "Dublin",
        "item_state": "Leinster",
        "item_postal_code": "D01",
        "item_country": "IE",
        "category_id": "27386",
        "category_name": "Graphics/Video Cards",
        "leaf_category_ids": "27386",
        "item_creation_date": "2026-07-01T09:00:00.000Z",
        "item_end_date": "2026-08-01T09:00:00.000Z",
        "original_price": "1999.99",
        "original_price_currency": "EUR",
        "discount_percentage": "10",
        "discount_amount": "200.00",
        "discount_amount_currency": "EUR",
        "price_treatment": "STRIKETHROUGH",
        "watch_count": "37",
        "unit_price": "1799.99",
        "unit_price_currency": "EUR",
        "unit_pricing_measure": "1 unit",
        "epid": "24057409123",
        "legacy_item_id": "110000000001",
        "item_href": "https://api.ebay.com/buy/browse/v1/item/v1%7C110000000001%7C0",
        "item_affiliate_web_url": "https://www.ebay.ie/itm/110000000001?mkcid=1",
        "subtitle": "Factory sealed, ships from Ireland",
        "short_description": "Brand new sealed RTX 4090 Founders Edition.",
        "listing_marketplace_id": "EBAY_IE",
        "qualified_programs": "EBAY_PLUS,AUTHENTICITY_GUARANTEE",
        "adult_only": "false",
        "available_coupons": "true",
        "top_rated_buying_experience": "true",
        "priority_listing": "false",
    }


def test_maps_second_item_country_only_location_and_multiple_buying_options() -> None:
    provider, _ = _page1_provider()
    second = provider.search("rtx 4090", limit=2)[1]
    assert second.condition is Condition.REFURBISHED
    assert second.location == "DE"
    assert second.extra["buying_options"] == "FIXED_PRICE,BEST_OFFER"
    assert second.currency == "EUR"


def test_maps_usd_price_and_city_country_location() -> None:
    transport = _SearchTransport({"0": _response(200, _fixture_bytes("search_page2.json"))})
    listings = _provider(transport).search("rtx 4090", limit=2)
    used = listings[0]
    assert used.price == 1350.50
    assert used.currency == "USD"
    assert used.location == "New York, US"
    assert used.condition is Condition.USED


def test_auction_item_without_price_defaults_currency_and_none_price() -> None:
    transport = _SearchTransport({"0": _response(200, _fixture_bytes("search_page2.json"))})
    auction = _provider(transport).search("rtx 4090", limit=2)[1]
    assert auction.price is None
    assert auction.currency == "EUR"  # config default
    assert auction.condition is Condition.UNKNOWN  # no conditionId or text
    assert auction.location == "IE"
    assert auction.extra == {
        "buying_options": "AUCTION",
        "current_bid_price": "999.00",
        "current_bid_currency": "EUR",
        "bid_count": "14",
        "item_country": "IE",
    }
    assert "condition_id" not in auction.extra


@pytest.mark.parametrize(
    ("condition_id", "expected"),
    [
        ("1000", Condition.NEW),
        ("1500", Condition.NEW),
        ("1750", Condition.NEW),
        ("2000", Condition.REFURBISHED),
        ("2010", Condition.REFURBISHED),
        ("2020", Condition.REFURBISHED),
        ("2030", Condition.REFURBISHED),
        ("2500", Condition.REFURBISHED),
        ("3000", Condition.USED),
        ("4000", Condition.USED),
        ("5000", Condition.USED),
        ("6000", Condition.USED),
        ("7000", Condition.USED),
        ("9999", Condition.UNKNOWN),
    ],
)
def test_condition_id_mapping(condition_id: str, expected: Condition) -> None:
    body = {
        "total": 1,
        "limit": 2,
        "offset": 0,
        "itemSummaries": [
            {
                "itemId": "v1|1|0",
                "title": "item",
                "itemWebUrl": "https://www.ebay.ie/itm/1",
                "conditionId": condition_id,
            }
        ],
    }
    transport = _SearchTransport({"0": _response(200, json.dumps(body).encode())})
    listing = _provider(transport).search("q", limit=1)[0]
    assert listing.condition is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Brand New", Condition.NEW),
        ("Seller refurbished", Condition.REFURBISHED),
        ("For parts or not working", Condition.USED),
        ("mystery", Condition.UNKNOWN),
    ],
)
def test_condition_text_fallback_when_id_absent(text: str, expected: Condition) -> None:
    body = {
        "total": 1,
        "limit": 2,
        "offset": 0,
        "itemSummaries": [
            {
                "itemId": "v1|1|0",
                "title": "item",
                "itemWebUrl": "https://www.ebay.ie/itm/1",
                "condition": text,
            }
        ],
    }
    transport = _SearchTransport({"0": _response(200, json.dumps(body).encode())})
    listing = _provider(transport).search("q", limit=1)[0]
    assert listing.condition is expected


# --------------------------------------------------------------------------- #
# Enrichment: Listing.extra field mapping (Sprint 27 / ADR-021)
# --------------------------------------------------------------------------- #


def _extra_for(item: dict[str, object]) -> dict[str, str]:
    """Map a single raw item summary and return its ``Listing.extra``."""
    body = {"total": 1, "limit": 2, "offset": 0, "itemSummaries": [item]}
    transport = _SearchTransport({"0": _response(200, json.dumps(body).encode())})
    return _provider(transport).search("q", limit=1)[0].extra


_MINIMAL_ITEM: dict[str, object] = {
    "itemId": "v1|1|0",
    "title": "bare item",
    "itemWebUrl": "https://www.ebay.ie/itm/1",
}


def test_minimal_item_produces_empty_extra() -> None:
    assert _extra_for(dict(_MINIMAL_ITEM)) == {}


def test_backwards_compatible_extra_keys_preserved() -> None:
    provider, _ = _page1_provider()
    extra = provider.search("rtx 4090", limit=1)[0].extra
    # Keys that existed before Sprint 27 must still be present and unchanged.
    assert extra["image_url"] == "https://i.ebayimg.com/images/g/example0001/s-l225.jpg"
    assert extra["buying_options"] == "FIXED_PRICE"
    assert extra["seller"] == "example_seller_ie"
    assert extra["condition_id"] == "1000"


def test_seller_reputation_fields_mapped() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "seller": {
                "username": "u",
                "feedbackPercentage": "98.7",
                "feedbackScore": 1234,
                "sellerAccountType": "INDIVIDUAL",
            },
        }
    )
    assert extra["seller"] == "u"
    assert extra["seller_feedback_percentage"] == "98.7"
    assert extra["seller_feedback_score"] == "1234"
    assert extra["seller_account_type"] == "INDIVIDUAL"


def test_shipping_uses_primary_option_only() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "shippingOptions": [
                {"shippingCostType": "FIXED", "shippingCost": {"value": "5.00", "currency": "GBP"}},
                {"shippingCostType": "CALCULATED"},
            ],
        }
    )
    assert extra["shipping_cost"] == "5.00"
    assert extra["shipping_currency"] == "GBP"
    assert extra["shipping_cost_type"] == "FIXED"


def test_free_shipping_zero_cost_is_mapped() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "shippingOptions": [
                {"shippingCostType": "FIXED", "shippingCost": {"value": "0.00", "currency": "EUR"}}
            ],
        }
    )
    assert extra["shipping_cost"] == "0.00"


def test_category_takes_first_and_joins_leaf_ids() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "categories": [
                {"categoryId": "111", "categoryName": "Primary"},
                {"categoryId": "222", "categoryName": "Secondary"},
            ],
            "leafCategoryIds": ["111", "333"],
        }
    )
    assert extra["category_id"] == "111"
    assert extra["category_name"] == "Primary"
    assert extra["leaf_category_ids"] == "111,333"


def test_boolean_fields_render_as_true_false_strings() -> None:
    extra = _extra_for({**_MINIMAL_ITEM, "adultOnly": True, "topRatedBuyingExperience": False})
    assert extra["adult_only"] == "true"
    assert extra["top_rated_buying_experience"] == "false"


def test_integer_valued_float_number_renders_without_trailing_zero() -> None:
    extra = _extra_for({**_MINIMAL_ITEM, "watchCount": 42.0})
    assert extra["watch_count"] == "42"


def test_non_numeric_watch_count_raises_response_error() -> None:
    with pytest.raises(ProviderResponseError, match="expected a number"):
        _extra_for({**_MINIMAL_ITEM, "watchCount": "lots"})


def test_image_lists_joined_and_skip_malformed_entries() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "thumbnailImages": [{"imageUrl": "https://x/t1.jpg"}, {"noUrl": 1}, "bad"],
            "additionalImages": [
                {"imageUrl": "https://x/a1.jpg"},
                {"imageUrl": "https://x/a2.jpg"},
            ],
        }
    )
    assert extra["thumbnail_image_urls"] == "https://x/t1.jpg"
    assert extra["additional_image_urls"] == "https://x/a1.jpg,https://x/a2.jpg"


def test_marketing_discount_and_current_bid_split_into_value_currency() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "marketingPrice": {
                "originalPrice": {"value": "100.00", "currency": "USD"},
                "discountPercentage": "20",
                "discountAmount": {"value": "20.00", "currency": "USD"},
                "priceTreatment": "MARKDOWN",
            },
            "currentBidPrice": {"value": "50.00", "currency": "USD"},
        }
    )
    assert extra["original_price"] == "100.00"
    assert extra["original_price_currency"] == "USD"
    assert extra["discount_percentage"] == "20"
    assert extra["discount_amount"] == "20.00"
    assert extra["price_treatment"] == "MARKDOWN"
    assert extra["current_bid_price"] == "50.00"
    assert extra["current_bid_currency"] == "USD"


def test_listing_times_and_identifiers_mapped() -> None:
    extra = _extra_for(
        {
            **_MINIMAL_ITEM,
            "itemCreationDate": "2026-07-01T09:00:00.000Z",
            "itemEndDate": "2026-08-01T09:00:00.000Z",
            "epid": "999",
            "legacyItemId": "abc",
        }
    )
    assert extra["item_creation_date"] == "2026-07-01T09:00:00.000Z"
    assert extra["item_end_date"] == "2026-08-01T09:00:00.000Z"
    assert extra["epid"] == "999"
    assert extra["legacy_item_id"] == "abc"


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #


def test_paginates_across_two_pages_via_next_link() -> None:
    transport = _SearchTransport(
        {
            "0": _response(200, _fixture_bytes("search_page1.json")),
            "2": _response(200, _fixture_bytes("search_page2.json")),
        }
    )
    provider = _provider(transport)
    listings = provider.search("rtx 4090", limit=4)
    assert [listing.listing_id for listing in listings] == [
        "v1|110000000001|0",
        "v1|110000000002|0",
        "v1|110000000003|0",
        "v1|110000000004|0",
    ]
    assert [dict(r.params)["offset"] for r in transport.requests] == ["0", "2"]


def test_pagination_stops_after_second_page_without_next() -> None:
    transport = _SearchTransport(
        {
            "0": _response(200, _fixture_bytes("search_page1.json")),
            "2": _response(200, _fixture_bytes("search_page2.json")),
        }
    )
    provider = _provider(transport)
    provider.search("rtx 4090", limit=50)  # far above available results
    assert len(transport.requests) == 2  # page2 has no "next" -> stop


def test_has_more_from_offset_total_when_next_absent() -> None:
    body = {
        "total": 10,
        "limit": 2,
        "offset": 0,
        "itemSummaries": [
            {"itemId": "v1|1|0", "title": "a", "itemWebUrl": "https://x/1"},
            {"itemId": "v1|2|0", "title": "b", "itemWebUrl": "https://x/2"},
        ],
    }
    provider = _provider(_SearchTransport({}))
    page = provider.parse_response(_response(200, json.dumps(body).encode()), query="q")
    assert page.has_more is True  # offset(0) + limit(2) < total(10)


def test_empty_results_returns_no_listings() -> None:
    transport = _SearchTransport({"0": _response(200, _fixture_bytes("empty.json"))})
    provider = _provider(transport)
    assert provider.search("zzzznomatch", limit=10) == []


# --------------------------------------------------------------------------- #
# Error mapping
# --------------------------------------------------------------------------- #


def test_malformed_json_raises_response_error() -> None:
    transport = _SearchTransport({"0": _response(200, b"not json")})
    with pytest.raises(ProviderResponseError):
        _provider(transport).search("q", limit=2)


def test_non_numeric_price_raises_response_error() -> None:
    body = {
        "total": 1,
        "limit": 2,
        "offset": 0,
        "itemSummaries": [
            {
                "itemId": "v1|1|0",
                "title": "item",
                "itemWebUrl": "https://x/1",
                "price": {"value": "free", "currency": "EUR"},
            }
        ],
    }
    transport = _SearchTransport({"0": _response(200, json.dumps(body).encode())})
    with pytest.raises(ProviderResponseError, match="numeric string"):
        _provider(transport).search("q", limit=1)


def test_item_summaries_not_a_list_raises_response_error() -> None:
    transport = _SearchTransport({"0": _response(200, b'{"itemSummaries": "nope"}')})
    with pytest.raises(ProviderResponseError):
        _provider(transport).search("q", limit=2)


def test_http_error_from_transport_propagates_non_retryable() -> None:
    error = ProviderHTTPError(
        "provider returned HTTP 400",
        status_code=400,
        provider="ebay_browse",
        body=_fixture_bytes("error_12001.json"),
    )
    transport = _StaticTransport(error)
    provider = _provider(transport, config=_config(retry=RetryPolicy(max_attempts=3)))
    with pytest.raises(ProviderHTTPError) as excinfo:
        provider.search("q", limit=2)
    assert excinfo.value.status_code == 400
    assert len(transport.requests) == 1  # 4xx is not retried


def test_rate_limit_error_propagates() -> None:
    error = ProviderRateLimitError("rate limited", provider="ebay_browse", retry_after=2.0)
    transport = _StaticTransport(error)
    provider = _provider(transport, config=_config(retry=RetryPolicy(max_attempts=1)))
    with pytest.raises(ProviderRateLimitError):
        provider.search("q", limit=2)


# --------------------------------------------------------------------------- #
# Capabilities & config
# --------------------------------------------------------------------------- #


def test_capabilities_reflect_browse_api() -> None:
    caps = EbayBrowseProvider.get_capabilities()
    assert caps.supports_pagination is True
    assert caps.requires_api_key is True
    assert caps.max_page_size == 200
    assert caps.max_results == 10_000
    assert caps.supported_currencies == ("EUR", "GBP", "USD")


def test_requires_api_key_without_auth_or_key_fails() -> None:
    with pytest.raises(ProviderConfigError, match="api_key or auth"):
        EbayBrowseProvider(_config())


def test_config_validates_marketplace_and_token_url() -> None:
    with pytest.raises(ProviderConfigError, match="marketplace_id"):
        _config(marketplace_id="")
    with pytest.raises(ProviderConfigError, match="oauth_token_url"):
        _config(oauth_token_url="ftp://nope")
    with pytest.raises(ProviderConfigError, match="oauth_scope"):
        _config(oauth_scope="")


def test_config_from_dict_accepts_ebay_keys_and_nested_retry() -> None:
    cfg = EbayBrowseConfig.from_dict(
        {
            "base_url": "https://api.sandbox.ebay.com",
            "marketplace_id": "EBAY_US",
            "oauth_token_url": "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
            "page_size": 50,
            "retry": {"max_attempts": 5, "retry_on_status": [429, 503]},
        }
    )
    assert isinstance(cfg, EbayBrowseConfig)
    assert cfg.marketplace_id == "EBAY_US"
    assert cfg.retry.max_attempts == 5
    assert cfg.retry.retry_on_status == frozenset({429, 503})


def test_config_from_dict_rejects_unknown_keys() -> None:
    with pytest.raises(ProviderConfigError, match="unknown config key"):
        EbayBrowseConfig.from_dict({"base_url": "https://api.ebay.com", "bogus": 1})


def test_ebay_config_type_is_enforced() -> None:
    plain = LiveProviderConfig(base_url="https://api.ebay.com", api_key="k")
    provider = EbayBrowseProvider(plain)  # api_key satisfies requires_api_key
    with pytest.raises(ProviderConfigError, match="EbayBrowseConfig"):
        provider.build_request("q", page=1, page_size=10)


# --------------------------------------------------------------------------- #
# Registry (config-aware live factory)
# --------------------------------------------------------------------------- #


def test_registered_in_live_registry_not_mock_registry() -> None:
    assert LIVE_PROVIDER_REGISTRY["ebay_browse"] is EbayBrowseProvider
    assert "ebay_browse" not in PROVIDER_REGISTRY  # mock registry unaffected


def test_create_live_provider_builds_ebay_browse() -> None:
    transport = _SearchTransport({"0": _response(200, _fixture_bytes("empty.json"))})
    provider = create_live_provider(
        "ebay_browse",
        _config(),
        auth=StaticBearerTokenAuthProvider("k"),
        transport=transport,
    )
    assert isinstance(provider, EbayBrowseProvider)
    provider.search("q", limit=1)
    assert transport.requests[0].headers["Authorization"] == "Bearer k"


# --------------------------------------------------------------------------- #
# OAuth wiring (mint + cache through an injected token transport)
# --------------------------------------------------------------------------- #


def test_build_provider_mints_and_reuses_oauth_token() -> None:
    token_transport = _StaticTransport(_response(200, _fixture_bytes("oauth_token.json")))
    search_transport = _SearchTransport(
        {
            "0": _response(200, _fixture_bytes("search_page1.json")),
            "2": _response(200, _fixture_bytes("search_page2.json")),
        }
    )
    provider = build_ebay_browse_provider(
        _config(),
        client_id="test-client-id",
        client_secret="test-client-secret",
        transport=search_transport,
        token_transport=token_transport,
    )
    listings = provider.search("rtx 4090", limit=4)
    assert len(listings) == 4
    # Every search request carries the minted bearer token + marketplace header.
    expected = "Bearer v^1.1#i^1#EXAMPLE-SANITISED-APPLICATION-TOKEN"
    for request in search_transport.requests:
        assert request.headers["Authorization"] == expected
        assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_IE"
    # Token is cached: minted once despite two search calls.
    assert len(token_transport.requests) == 1
    token_request = token_transport.requests[0]
    assert token_request.method == "POST"
    assert token_request.url == "https://api.ebay.com/identity/v1/oauth2/token"
    assert token_request.headers["Authorization"].startswith("Basic ")


def test_build_provider_from_env_reads_credentials() -> None:
    token_transport = _StaticTransport(_response(200, _fixture_bytes("oauth_token.json")))
    search_transport = _SearchTransport({"0": _response(200, _fixture_bytes("empty.json"))})
    provider = build_ebay_browse_provider_from_env(
        _config(),
        env={"EBAY_CLIENT_ID": "cid", "EBAY_CLIENT_SECRET": "secret"},
        transport=search_transport,
        token_transport=token_transport,
    )
    provider.search("q", limit=1)
    assert search_transport.requests[0].headers["Authorization"].startswith("Bearer ")


def test_build_provider_from_env_missing_credentials_fails() -> None:
    with pytest.raises(ProviderConfigError, match="EBAY_CLIENT_ID"):
        build_ebay_browse_provider_from_env(_config(), env={})


# --------------------------------------------------------------------------- #
# Backwards compatibility: mock providers untouched
# --------------------------------------------------------------------------- #


def test_mock_registry_still_has_only_mock_providers() -> None:
    assert set(PROVIDER_REGISTRY) == {"ebay", "facebook_marketplace", "adverts_ie", "donedeal"}


def test_ebay_browse_listing_is_a_listing() -> None:
    provider, _ = _page1_provider()
    listings = provider.search("rtx 4090", limit=1)
    assert isinstance(listings[0], Listing)
