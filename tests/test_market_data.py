"""Tests for the market-data collection & storage layer.

All tests are hermetic: providers are built with scripted fake transports and
fake credentials; no network call and no real secret is used. Live behaviour
is verified separately via ``scripts/verify_live_capabilities.py`` and bounded
``arb collect`` runs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.market_data.collector import CollectionConfig, CollectionRunner
from digital_arbitrage.market_data.manifest import (
    CollectionManifest,
    CollectionQuery,
    ManifestError,
    load_collection_manifest,
)
from digital_arbitrage.market_data.redaction import (
    redact_payload,
    redact_request,
    seller_pseudonym,
)
from digital_arbitrage.market_data.report import build_report
from digital_arbitrage.market_data.store import MarketDataStore
from digital_arbitrage.providers.live.ebay_browse import (
    EbayBrowseConfig,
    build_ebay_browse_provider,
)
from digital_arbitrage.providers.live.errors import (
    ProviderConnectionError,
)
from digital_arbitrage.providers.live.http import HttpRequest, HttpResponse, Transport
from digital_arbitrage.providers.live.stockx_provider import (
    StockXConfig,
    build_stockx_provider,
)

_FIXTURES = Path(__file__).parent / "fixtures"
EBAY_DIR = _FIXTURES / "ebay"
STOCKX_DIR = _FIXTURES / "stockx"

EBAY_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

_EBAY_DETAIL = {
    "itemId": "v1|110000000001|0",
    "title": "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
    "price": {"value": "2999.99", "currency": "USD"},
    "condition": "New",
    "description": "<p>Brand new sealed RTX 4090.</p>",
    "estimatedAvailabilities": [
        {
            "deliveryOptions": ["SHIP_TO_HOME"],
            "estimatedAvailabilityStatus": "IN_STOCK",
            "estimatedAvailableQuantity": 2,
            "estimatedSoldQuantity": 3,
            "estimatedRemainingQuantity": 2,
        }
    ],
    "localizedAspects": [
        {"name": "Brand", "type": "STRING", "value": "NVIDIA"},
        {"name": "Chipset/GPU Model", "type": "STRING", "value": "RTX 4090"},
    ],
    "sellerItemRevision": "3",
    "uniqueBidderCount": 0,
    "gtin": "0812784023524",
    "mpn": "900-1G136-2515-000",
    "brand": "NVIDIA",
    "seller": {"username": "real_seller_name", "feedbackPercentage": "99.6", "feedbackScore": 100},
}

_STOCKX_VARIANTS = [
    {
        "productId": "prod-1",
        "variantId": "var-1a",
        "variantName": "Product One:0",
        "variantValue": "9",
        "sizeChart": {"defaultConversion": {"size": "9", "type": "us m"}},
        "gtins": [{"identifier": "0194817794556", "type": "UPC"}],
        "isFlexEligible": True,
        "isDirectEligible": True,
    },
    {
        "productId": "prod-1",
        "variantId": "var-1b",
        "variantName": "Product One:1",
        "variantValue": "9.5",
        "sizeChart": {"defaultConversion": {"size": "9.5", "type": "us m"}},
        "gtins": [],
        "isFlexEligible": False,
        "isDirectEligible": True,
    },
]

_EBAY_SINGLE_PAGE = {
    "href": EBAY_SEARCH_URL,
    "total": 1,
    "limit": 1,
    "offset": 0,
    "itemSummaries": [
        {
            "itemId": "v1|110000000001|0",
            "title": "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
            "price": {"value": "2999.99", "currency": "USD"},
            "condition": "New",
            "conditionId": "1000",
            "itemWebUrl": "https://www.ebay.ie/itm/110000000001",
            "itemCreationDate": "2026-09-01T09:00:00.000Z",
            "itemOriginDate": "2026-09-01T09:00:00.000Z",
            "listingMarketplaceId": "EBAY_IE",
            "buyingOptions": ["FIXED_PRICE"],
            "seller": {"username": "seller_one", "feedbackPercentage": "99.0", "feedbackScore": 55},
        }
    ],
}

_EBAY_EMPTY_PAGE = {"href": EBAY_SEARCH_URL, "total": 0, "limit": 50, "offset": 0}


class _ScriptedTransport(Transport):
    """Routes requests to canned responses by URL path substring.

    ``routes`` maps a substring of the request URL to an :class:`HttpResponse`
    or a callable producing one (or raising a provider error).
    """

    def __init__(self, routes: dict[str, object]) -> None:
        self._routes = routes
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        for needle, outcome in self._routes.items():
            if needle in request.url:
                if callable(outcome):
                    return outcome(request)
                assert isinstance(outcome, HttpResponse)
                return outcome
        raise ProviderConnectionError(f"no route for {request.url}", provider="test")


def _json_response(status: int, payload: object, url: str) -> HttpResponse:
    return HttpResponse(
        status=status, headers={}, body=json.dumps(payload).encode("utf-8"), url=url
    )


def _token_transport() -> Transport:
    token_body = (EBAY_DIR / "oauth_token.json").read_bytes()
    return _ScriptedTransport(
        {
            "oauth2/token": HttpResponse(200, {}, token_body, "https://api.ebay.com/token"),
            "oauth/token": HttpResponse(200, {}, token_body, "https://accounts.stockx.com/token"),
        }
    )


def _ebay_factory(routes: dict[str, object]):
    def factory(transport: Transport):
        config = EbayBrowseConfig.from_dict(
            {
                "base_url": "https://api.ebay.com",
                "marketplace_id": "EBAY_IE",
                "rate_limit_per_second": 1000.0,
                "timeout": 5,
            }
        )
        return build_ebay_browse_provider(
            config,
            client_id="fake-id",
            client_secret="fake-secret",
            transport=transport,
            token_transport=_token_transport(),
        )

    return factory


def _stockx_factory(routes: dict[str, object]):
    def factory(transport: Transport):
        config = StockXConfig.from_dict(
            {
                "base_url": "https://api.stockx.com",
                "rate_limit_per_second": 1000.0,
                "timeout": 5,
            }
        )
        return build_stockx_provider(
            config,
            refresh_token="fake-refresh",
            client_id="fake-id",
            client_secret="fake-secret",
            api_key="fake-key",
            transport=transport,
            token_transport=_token_transport(),
        )

    return factory


def _ebay_routes(
    search: dict | None = None,
    *,
    detail: dict | None = None,
    search_override=None,
) -> dict[str, object]:
    payload = search if search is not None else _EBAY_SINGLE_PAGE
    routes: dict[str, object] = {
        "item_summary/search": search_override or _json_response(200, payload, EBAY_SEARCH_URL),
        "/item/v1%7C": _json_response(200, detail or _EBAY_DETAIL, "https://api.ebay.com/item"),
    }
    return routes


def _stockx_routes(*, with_variants: bool = True) -> dict[str, object]:
    md_fixture = json.loads((STOCKX_DIR / "market_data.json").read_text())

    def market_data(request: HttpRequest) -> HttpResponse:
        # Per-product variant ids so sibling products don't share variants.
        product_id = request.url.split("/products/")[1].split("/")[0]
        entries = []
        for entry in md_fixture:
            e = dict(entry)
            e["productId"] = product_id
            e["variantId"] = f"{e['variantId']}-{product_id}"
            entries.append(e)
        return _json_response(200, entries, request.url)

    routes: dict[str, object] = {
        "catalog/search": _json_response(
            200,
            json.loads((STOCKX_DIR / "search.json").read_text()),
            "https://api.stockx.com/v2/catalog/search",
        ),
        "market-data": market_data,
    }
    if with_variants:

        def variants(request: HttpRequest) -> HttpResponse:
            product_id = request.url.split("/products/")[1].split("/")[0]
            # The variants endpoint returns the same variantIds as market-data.
            entries = [
                dict(
                    v,
                    productId=product_id,
                    variantId=f"{md_fixture[i]['variantId']}-{product_id}",
                )
                for i, v in enumerate(_STOCKX_VARIANTS)
            ]
            return _json_response(200, entries, request.url)

        routes["/variants"] = variants
    return routes


def _manifest(*queries: CollectionQuery) -> CollectionManifest:
    return CollectionManifest(manifest_id="test-manifest", version="0.0.1", queries=tuple(queries))


def _ebay_query(**kwargs) -> CollectionQuery:
    return CollectionQuery(
        query_id="q1",
        search_text="RTX 4090",
        providers=("ebay_browse",),
        max_results_per_provider=kwargs.pop("max_results", 50),
        detail_top_n=kwargs.pop("detail_top_n", 5),
        **kwargs,
    )


def _runner(
    store: MarketDataStore,
    routes: dict[str, dict[str, object]],
    *,
    config: CollectionConfig | None = None,
) -> CollectionRunner:
    transports = {name: _ScriptedTransport(r) for name, r in routes.items()}
    factories = {}
    if "ebay_browse" in routes:
        factories["ebay_browse"] = _ebay_factory(routes["ebay_browse"])
    if "stockx" in routes:
        factories["stockx"] = _stockx_factory(routes["stockx"])
    runner = CollectionRunner(
        store,
        config
        or CollectionConfig(
            rate_limit_per_second={"ebay_browse": 1000.0, "stockx": 1000.0},
            detail_fetch_top_n=150,
            fetch_stockx_variants=True,
        ),
        provider_factories=factories,
        transport_factory=lambda name: transports[name],
    )
    runner._test_transports = transports  # type: ignore[attr-defined]
    return runner


@pytest.fixture()
def store(tmp_path: Path) -> MarketDataStore:
    s = MarketDataStore(tmp_path / "market_data.db")
    yield s
    s.close()


# --------------------------------------------------------------------------- #
# Field preservation + entity separation
# --------------------------------------------------------------------------- #


def test_ebay_search_preserves_all_summary_fields(store: MarketDataStore) -> None:
    runner = _runner(store, {"ebay_browse": _ebay_routes()})
    runner.collect(_manifest(_ebay_query(detail_top_n=0)))

    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    assert entity is not None
    assert entity["entity_type"] == "listing"
    assert entity["seller_key"].startswith("sel_")
    assert "seller_one" not in entity["seller_key"]

    obs = store.observations_for_entity(entity["entity_id"])
    assert len(obs) == 1
    attrs = json.loads(obs[0]["attributes_json"])
    # Every summary field lands in attributes, including ones the old pipeline
    # never mapped (itemOriginDate).
    for key in _EBAY_SINGLE_PAGE["itemSummaries"][0]:
        if key == "itemAffiliateWebUrl":
            assert key not in attrs
            continue
        assert key in attrs, key
    assert attrs["itemOriginDate"] == "2026-09-01T09:00:00.000Z"
    # seller username is pseudonymised in attributes too
    assert "username" not in attrs["seller"]
    assert attrs["seller"]["seller_key"] == entity["seller_key"]
    # price is an ask, never a sold price
    assert obs[0]["price_kind"] == "ask"
    assert obs[0]["price_amount"] == 2999.99
    # unknown quantities stay NULL, not zero
    assert obs[0]["quantity_available"] is None
    assert obs[0]["quantity_sold_estimate"] is None
    # raw payload persisted, redacted
    payload = store._conn.execute("SELECT payload_json FROM raw_payloads").fetchone()
    assert "seller_one" not in payload["payload_json"]


def test_ebay_detail_captures_estimate_fields(store: MarketDataStore) -> None:
    runner = _runner(store, {"ebay_browse": _ebay_routes()})
    runner.collect(_manifest(_ebay_query(detail_top_n=5)))

    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    obs = [
        o
        for o in store.observations_for_entity(entity["entity_id"])
        if o["source_kind"] == "detail"
    ]
    assert len(obs) == 1
    o = obs[0]
    assert o["quantity_sold_estimate"] == 3  # provider estimate, not a sale count
    assert o["quantity_available"] == 2
    assert o["description"].startswith("<p>Brand new")
    attrs = json.loads(o["attributes_json"])
    assert attrs["localized_aspects"]["Chipset/GPU Model"] == "RTX 4090"
    assert attrs["seller_item_revision"] == "3"
    assert attrs["gtin"] == "0812784023524"
    assert attrs["sold_estimate_delta"] is None  # first detail observation


def test_stockx_entities_keep_types_distinct(store: MarketDataStore) -> None:
    runner = _runner(store, {"stockx": _stockx_routes()})
    runner.collect(
        _manifest(
            CollectionQuery(
                query_id="q1",
                search_text="nike dunk",
                providers=("stockx",),
                max_results_per_provider=10,
            )
        )
    )
    rows = store._conn.execute(
        "SELECT entity_type, COUNT(*) AS n FROM provider_entities GROUP BY entity_type"
    ).fetchall()
    counts = {r["entity_type"]: r["n"] for r in rows}
    assert counts["catalogue_product"] == 2
    # each fixture product has 2 market-data variants
    assert counts["variant"] == 4
    product = store.get_entity(
        "stockx", "catalogue_product", "5e6a1e57-1c7d-435a-82bd-5666a13560fe"
    )
    variant = store.get_entity(
        "stockx",
        "variant",
        "55da4110-5983-439f-9ae4-d7d054f67723-5e6a1e57-1c7d-435a-82bd-5666a13560fe",
    )
    assert product is not None and variant is not None
    assert variant["parent_entity_id"] == product["entity_id"]

    obs = [
        o
        for o in store.observations_for_entity(variant["entity_id"])
        if o["source_kind"] == "market_data"
    ]
    assert obs, "variant market data must be stored"
    attrs = json.loads(obs[0]["attributes_json"])
    # previously discarded fields are now retained
    for key in (
        "sellFasterAmount",
        "earnMoreAmount",
        "standardMarketData",
        "flexMarketData",
        "directMarketData",
    ):
        assert key in attrs
    # variants endpoint data lands in its own observation kind
    var_obs = [
        o
        for o in store.observations_for_entity(variant["entity_id"])
        if o["source_kind"] == "variants"
    ]
    assert var_obs
    vattrs = json.loads(var_obs[0]["attributes_json"])
    assert vattrs["variantValue"] == "9"
    assert vattrs["gtins"][0]["identifier"] == "0194817794556"


def test_entities_never_merge_across_providers(store: MarketDataStore) -> None:
    runner = _runner(
        store,
        {"ebay_browse": _ebay_routes(), "stockx": _stockx_routes()},
    )
    runner.collect(
        _manifest(
            CollectionQuery(
                query_id="q1",
                search_text="RTX 4090",
                providers=("ebay_browse", "stockx"),
                detail_top_n=0,
            )
        )
    )
    providers = {
        r["provider"] for r in store._conn.execute("SELECT provider FROM provider_entities")
    }
    assert providers == {"ebay_browse", "stockx"}


# --------------------------------------------------------------------------- #
# History + idempotency
# --------------------------------------------------------------------------- #


def test_two_runs_preserve_observation_history(store: MarketDataStore) -> None:
    runner = _runner(store, {"ebay_browse": _ebay_routes()})
    manifest = _manifest(_ebay_query(detail_top_n=0))
    runner.collect(manifest)
    runner.collect(manifest)

    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    assert entity["times_seen"] == 2
    obs = store.observations_for_entity(entity["entity_id"])
    # same content, different runs -> two retained rows
    assert len(obs) == 2
    assert obs[0]["collection_run_id"] != obs[1]["collection_run_id"]
    runs = store._conn.execute("SELECT run_id FROM collection_runs").fetchall()
    assert len(runs) == 2


def test_price_change_creates_new_observation(store: MarketDataStore) -> None:
    changed = json.loads(json.dumps(_EBAY_SINGLE_PAGE))
    changed["itemSummaries"][0]["price"]["value"] = "2599.00"
    transport_routes = {"ebay_browse": _ebay_routes()}
    runner = _runner(store, transport_routes)
    runner.collect(_manifest(_ebay_query(detail_top_n=0)))

    # second run over the changed price
    runner2 = _runner(store, {"ebay_browse": _ebay_routes(search=changed)})
    runner2.collect(_manifest(_ebay_query(detail_top_n=0)))

    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    obs = store.observations_for_entity(entity["entity_id"])
    prices = {o["price_amount"] for o in obs}
    assert prices == {2999.99, 2599.00}


def test_task_retry_does_not_duplicate_observations(store: MarketDataStore) -> None:
    runner = _runner(store, {"ebay_browse": _ebay_routes()})
    run_id = runner.collect(_manifest(_ebay_query(detail_top_n=0)))
    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    before = len(store.observations_for_entity(entity["entity_id"]))
    # simulate a retry of the same ingest within the same run
    runner._ingest_ebay_summary(_EBAY_SINGLE_PAGE["itemSummaries"][0], task_id=1, run_id=run_id)
    after = len(store.observations_for_entity(entity["entity_id"]))
    assert after == before  # INSERT OR IGNORE deduped


def test_partial_response_does_not_erase_fields(store: MarketDataStore) -> None:
    runner = _runner(store, {"ebay_browse": _ebay_routes()})
    runner.collect(_manifest(_ebay_query(detail_top_n=5)))
    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    obs = store.observations_for_entity(entity["entity_id"])
    # detail obs missing localizedAspects but search obs still carries summary fields
    detail = [o for o in obs if o["source_kind"] == "detail"][0]
    search = [o for o in obs if o["source_kind"] == "search"][0]
    s_attrs = json.loads(search["attributes_json"])
    assert "seller" in s_attrs
    assert detail["price_amount"] == 2999.99
    # detail obs has its own attributes; search obs untouched by detail failure paths


# --------------------------------------------------------------------------- #
# Pagination, budgets, partial failures
# --------------------------------------------------------------------------- #


def test_two_page_pagination_records_tasks(store: MarketDataStore) -> None:
    page1 = json.loads((EBAY_DIR / "search_page1.json").read_text())
    page2 = json.loads((EBAY_DIR / "search_page2.json").read_text())

    def search(request: HttpRequest) -> HttpResponse:
        offset = dict(request.params).get("offset", "0")
        return _json_response(200, page1 if offset == "0" else page2, EBAY_SEARCH_URL)

    runner = _runner(store, {"ebay_browse": _ebay_routes(search_override=search)})
    run_id = runner.collect(_manifest(_ebay_query(detail_top_n=0)))
    tasks = [t for t in store.tasks_for_run(run_id) if t["endpoint"] == "item_summary/search"]
    assert len(tasks) == 2
    assert all(t["status"] == "done" for t in tasks)
    assert tasks[0]["has_more"] == 1
    assert tasks[1]["has_more"] == 0
    assert tasks[0]["reported_total"] == 4


def test_page_failure_leaves_partial_run(store: MarketDataStore) -> None:
    page1 = json.loads((EBAY_DIR / "search_page1.json").read_text())
    calls = {"n": 0}

    def search(request: HttpRequest) -> HttpResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return _json_response(200, page1, EBAY_SEARCH_URL)
        raise ProviderConnectionError("boom", provider="ebay_browse")

    runner = _runner(store, {"ebay_browse": _ebay_routes(search_override=search)})
    run_id = runner.collect(_manifest(_ebay_query(detail_top_n=0)))
    run = store.run_row(run_id)
    assert run["status"] == "PARTIAL_SUCCESS"
    # page-1 entities retained
    entities = store._conn.execute("SELECT COUNT(*) AS n FROM provider_entities").fetchone()
    assert entities["n"] == 2
    failed = [t for t in store.tasks_for_run(run_id) if t["status"] == "failed"]
    assert failed and failed[0]["error_category"] == "ProviderConnectionError"


def test_budget_exhaustion_stops_provider(store: MarketDataStore) -> None:
    config = CollectionConfig(
        rate_limit_per_second={"ebay_browse": 1000.0},
        daily_request_budget={"ebay_browse": 1},
        detail_fetch_top_n=0,
    )
    runner = _runner(store, {"ebay_browse": _ebay_routes()}, config=config)
    runner.collect(_manifest(_ebay_query(detail_top_n=0)))
    # first send succeeds, second is refused by the budget guard
    used = store.requests_used("ebay_browse", day=runner._budget.day)
    assert used == 1


def test_sold_estimate_decrease_flagged(store: MarketDataStore) -> None:
    detail_v2 = json.loads(json.dumps(_EBAY_DETAIL))
    detail_v2["estimatedAvailabilities"][0]["estimatedSoldQuantity"] = 1
    runner = _runner(store, {"ebay_browse": _ebay_routes()})
    runner.collect(_manifest(_ebay_query(detail_top_n=5)))
    runner2 = _runner(store, {"ebay_browse": _ebay_routes(detail=detail_v2)})
    runner2.collect(_manifest(_ebay_query(detail_top_n=5)))

    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    detail_obs = [
        o
        for o in store.observations_for_entity(entity["entity_id"])
        if o["source_kind"] == "detail"
    ]
    assert len(detail_obs) == 2
    attrs2 = json.loads(detail_obs[1]["attributes_json"])
    assert attrs2["sold_estimate_delta"] == -2
    assert attrs2["sold_estimate_flag"] == "decrease"


def test_disappearance_not_marked_as_sale(store: MarketDataStore) -> None:
    # run 1: complete coverage with the item
    _runner(store, {"ebay_browse": _ebay_routes()}).collect(_manifest(_ebay_query(detail_top_n=0)))
    # run 2: complete coverage, empty result -> disappeared, never confirmed_sale
    _runner(store, {"ebay_browse": _ebay_routes(search=_EBAY_EMPTY_PAGE)}).collect(
        _manifest(_ebay_query(detail_top_n=0))
    )
    entity = store.get_entity("ebay_browse", "listing", "v1|110000000001|0")
    assert entity["latest_state"] == "disappeared"
    states = {o["state"] for o in store.observations_for_entity(entity["entity_id"])}
    assert "disappeared" in states
    assert "confirmed_sale" not in states


# --------------------------------------------------------------------------- #
# Secrets + retention
# --------------------------------------------------------------------------- #


def test_request_headers_never_stored() -> None:
    request = HttpRequest(
        method="GET",
        url="https://api.ebay.com/buy/browse/v1/item_summary/search",
        params={"q": "rtx", "access_token": "should-be-masked"},
        headers={"Authorization": "Bearer super-secret-token"},
    )
    safe = redact_request(request)
    assert "Authorization" not in json.dumps(safe)
    assert "super-secret-token" not in json.dumps(safe)
    assert "access_token=%3Credacted%3E" in safe["url"] or "redacted" in safe["url"]


def test_payload_redaction_scrubs_secrets_and_sellers() -> None:
    payload = {
        "seller": {"username": "real_name", "feedbackScore": 5},
        "access_token": "ABC123",
        "note": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
        "itemAffiliateWebUrl": "https://ebay.com/track?mkcid=1",
    }
    out = redact_payload(json.dumps(payload), provider="ebay_browse")
    assert "real_name" not in out and "sel_" in out
    assert "ABC123" not in out
    assert "eyJhbGci" not in out
    assert "mkcid" not in out
    parsed = json.loads(out)
    assert parsed["seller"]["feedbackScore"] == 5


def test_pseudonym_is_stable() -> None:
    assert seller_pseudonym("ebay_browse", "Name") == seller_pseudonym("ebay_browse", "  name ")
    assert seller_pseudonym("ebay_browse", "a") != seller_pseudonym("stockx", "a")


def test_raw_payload_retention_gc(store: MarketDataStore) -> None:
    store.start_run("r1", manifest_id="m", manifest_hash="h", config_json="{}")
    old_id = store.record_payload(
        collection_run_id="r1",
        task_id=None,
        endpoint="x",
        request_url="https://a",
        http_status=200,
        payload_json='{"a":1}',
        payload_sha256="sha-old",
    )
    store._conn.execute(
        "UPDATE raw_payloads SET first_retrieved_at = '2020-01-01T00:00:00+00:00' "
        "WHERE payload_id = ?",
        (old_id,),
    )
    store._conn.commit()
    removed = store.gc_raw_payloads(older_than_days=90)
    assert removed == 1
    assert store._conn.execute("SELECT COUNT(*) AS n FROM raw_payloads").fetchone()["n"] == 0


def test_identical_payload_deduped_across_runs(store: MarketDataStore) -> None:
    for run in ("r1", "r2"):
        store.start_run(run, manifest_id="m", manifest_hash="h", config_json="{}")
        store.record_payload(
            collection_run_id=run,
            task_id=None,
            endpoint="x",
            request_url="https://a",
            http_status=200,
            payload_json='{"a":1}',
            payload_sha256="same-sha",
        )
    bodies = store._conn.execute("SELECT COUNT(*) AS n FROM raw_payloads").fetchone()["n"]
    captures = store._conn.execute("SELECT COUNT(*) AS n FROM payload_captures").fetchone()["n"]
    assert bodies == 1
    assert captures == 2


# --------------------------------------------------------------------------- #
# Manifest + report
# --------------------------------------------------------------------------- #


def test_manifest_validation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"manifest_id": "x", "version": "1", "queries": []}))
    with pytest.raises(ManifestError):
        load_collection_manifest(bad)


def test_report_shape(store: MarketDataStore) -> None:
    runner = _runner(store, {"ebay_browse": _ebay_routes(), "stockx": _stockx_routes()})
    run_id = runner.collect(
        _manifest(
            CollectionQuery(
                query_id="q1",
                search_text="RTX 4090",
                providers=("ebay_browse", "stockx"),
                detail_top_n=5,
            )
        )
    )
    report = build_report(store, run_id)
    assert report["counters"]["stored"] > 0
    cov = {c["provider"]: c for c in report["coverage"]}
    assert cov["ebay_browse"]["coverage"] == "COMPLETE"
    assert cov["stockx"]["coverage"] == "COMPLETE"
    ebay_fields = report["missing_fields"]["ebay_browse"]["search"]["fields"]
    assert ebay_fields["watchCount"]["status"] == "restricted"
    assert ebay_fields["soldPrice"]["status"] == "not_in_api"
    stockx_fields = report["missing_fields"]["stockx"]["market_data"]["fields"]
    assert stockx_fields["lastSalePrice"]["status"] == "not_in_api"
    assert report["errors"] == []
    assert report["states"]["active"] > 0
    assert report["raw_payloads"]["captures"] > 0
