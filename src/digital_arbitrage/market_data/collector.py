"""Manifest-driven collection runner.

Fetches bounded pages from the live providers through a
:class:`RecordingTransport` (raw payloads + request usage), upserts
provider-native entities, and appends timestamped observations. Never merges
entity types, never treats disappearance as a sale, and records the exact
sampling frame (query, filters, page coverage) on every task.

The collector issues its own request profile (configured via
:dataclass:`CollectionConfig`) - it does not alter ``arb scan`` or any existing
scoring/PUE behaviour.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..providers.live.ebay_browse import (
    EbayBrowseConfig,
    EbayBrowseProvider,
    build_ebay_browse_provider_from_env,
)
from ..providers.live.errors import ProviderError
from ..providers.live.factory import build_live_provider_from_env
from ..providers.live.http import Transport, UrllibTransport
from ..providers.live.stockx_provider import (
    StockXConfig,
    StockXProvider,
    build_stockx_provider_from_env,
)
from .capture import BudgetExhaustedError, PayloadSink, RecordingTransport, RequestBudget
from .manifest import CollectionManifest, CollectionQuery
from .models import (
    EBAY_PARSER_VERSION,
    STOCKX_PARSER_VERSION,
    CollectionTask,
    EntityType,
    Observation,
    ObservationState,
    PriceKind,
    ProviderEntity,
    RunStatus,
    SourceKind,
    TaskStatus,
)
from .redaction import seller_pseudonym
from .store import MarketDataStore, content_hash

_log = logging.getLogger("market_data.collector")

_EBAY = "ebay_browse"
_STOCKX = "stockx"

#: Default location for the market-data database (override via config/--db).
DEFAULT_MARKET_DB = Path.home() / ".digital_arbitrage" / "market_data.db"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _endpoint_for(provider: str, url: str) -> str:
    path = urllib.parse.urlsplit(url).path
    if "item_summary/search" in path:
        return "item_summary/search"
    if path.endswith("/market-data"):
        return "market-data"
    if path.endswith("/variants"):
        return "variants"
    if "/item/" in path:
        return "item/detail"
    if "/catalog/search" in path:
        return "catalog/search"
    if "/catalog/products/" in path:
        return "catalog/product"
    return path


@dataclass(slots=True)
class CollectionConfig:
    """Collector settings. All defaults preserve existing behaviour elsewhere."""

    page_size_ebay: int = 200
    page_size_stockx: int = 50
    max_pages: int = 10  # hard pagination safety ceiling
    detail_fetch_top_n: int = 150  # eBay getItem calls per run
    fetch_stockx_variants: bool = False  # +1 call per product when on
    raw_retention_days: int = 90
    stale_after_hours: int = 48
    keep_seller_usernames: bool = False  # pseudonymous seller_key by default
    ebay_search_filter: str | None = "buyingOptions:{AUCTION|FIXED_PRICE}"
    ebay_search_fieldgroups: str | None = "EXTENDED"
    ebay_search_sort: str | None = None
    ebay_marketplace_id: str = "EBAY_IE"
    ebay_base_url: str = "https://api.ebay.com"
    stockx_base_url: str = "https://api.stockx.com"
    stockx_currency_code: str = "USD"
    rate_limit_per_second: dict[str, float] = field(
        default_factory=lambda: {_EBAY: 2.0, _STOCKX: 1.0}
    )
    daily_request_budget: dict[str, int] = field(
        default_factory=lambda: {_EBAY: 4500, _STOCKX: 20000}
    )
    request_timeout: float = 30.0


class CollectionRunner:
    """Runs a bounded collection over a manifest into a :class:`MarketDataStore`."""

    def __init__(
        self,
        store: MarketDataStore,
        config: CollectionConfig | None = None,
        *,
        env: dict[str, str] | None = None,
        transport_factory: Callable[[str], Transport] | None = None,
        provider_factories: dict[str, Callable[[Transport], Any]] | None = None,
    ) -> None:
        self._store = store
        self._config = config or CollectionConfig()
        self._env = env
        #: ``provider_name -> raw Transport``; default is a fresh urllib transport.
        self._transport_factory = transport_factory or (lambda _name: UrllibTransport())
        #: Optional ``name -> (recording_transport) -> provider`` overrides.
        #: Tests inject fully built providers (fake transports, fake creds);
        #: production falls back to the ``*_from_env`` builders below.
        self._provider_factories = provider_factories or {}
        self._providers: dict[str, tuple[Any, PayloadSink]] = {}
        self._budget: RequestBudget | None = None
        self._run_id: str = ""
        self._detail_budget_used = 0
        self._budget_exhausted: set[str] = set()

    # -- provider construction -------------------------------------------- #
    def _provider(self, name: str) -> tuple[Any, PayloadSink]:
        if name in self._providers:
            return self._providers[name]
        assert self._budget is not None
        sink = PayloadSink(
            self._store,
            self._run_id,
            name,
            endpoint_resolver=lambda url: _endpoint_for(name, url),
            keep_seller_usernames=self._config.keep_seller_usernames,
            budget=self._budget,
        )
        transport = RecordingTransport(
            self._transport_factory(name), sink, provider=name, budget=self._budget
        )
        rps = self._config.rate_limit_per_second.get(name, 1.0)
        factory = self._provider_factories.get(name)
        if factory is not None:
            provider = factory(transport)
        elif name == _EBAY:
            ebay_config = cast(
                EbayBrowseConfig,
                EbayBrowseConfig.from_dict(
                    {
                        "base_url": self._config.ebay_base_url,
                        "marketplace_id": self._config.ebay_marketplace_id,
                        "rate_limit_per_second": rps,
                        "timeout": self._config.request_timeout,
                        "search_filter": self._config.ebay_search_filter,
                        "search_fieldgroups": self._config.ebay_search_fieldgroups,
                        "search_sort": self._config.ebay_search_sort,
                    }
                ),
            )
            provider = build_ebay_browse_provider_from_env(
                ebay_config, env=self._env, transport=transport
            )
        elif name == _STOCKX:
            stockx_config = cast(
                StockXConfig,
                StockXConfig.from_dict(
                    {
                        "base_url": self._config.stockx_base_url,
                        "currency_code": self._config.stockx_currency_code,
                        "rate_limit_per_second": rps,
                        "timeout": self._config.request_timeout,
                    }
                ),
            )
            provider = build_stockx_provider_from_env(
                stockx_config, env=self._env, transport=transport
            )
        else:
            provider = build_live_provider_from_env(name, {}, env=self._env, transport=transport)
        self._providers[name] = (provider, sink)
        return self._providers[name]

    # -- public entry point -------------------------------------------------- #
    def collect(
        self,
        manifest: CollectionManifest,
        *,
        providers_filter: set[str] | None = None,
        run_id: str | None = None,
    ) -> str:
        """Run one collection. Returns the ``run_id``."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._run_id = run_id or f"collect-{stamp}-{uuid.uuid4().hex[:8]}"
        self._budget = RequestBudget(
            self._config.daily_request_budget,
            lambda p: self._store.requests_used(p, day=self._budget.day) if self._budget else 0,
        )
        self._store.start_run(
            self._run_id,
            manifest_id=manifest.manifest_id,
            manifest_hash=manifest.manifest_hash,
            config_json=json.dumps(
                {
                    "detail_fetch_top_n": self._config.detail_fetch_top_n,
                    "fetch_stockx_variants": self._config.fetch_stockx_variants,
                    "ebay_search_filter": self._config.ebay_search_filter,
                    "ebay_search_fieldgroups": self._config.ebay_search_fieldgroups,
                    "ebay_search_sort": self._config.ebay_search_sort,
                    "ebay_marketplace_id": self._config.ebay_marketplace_id,
                    "max_pages": self._config.max_pages,
                    "daily_request_budget": self._config.daily_request_budget,
                    "raw_retention_days": self._config.raw_retention_days,
                },
                sort_keys=True,
            ),
        )

        for query in manifest.queries:
            for provider_name in query.providers:
                if providers_filter and provider_name not in providers_filter:
                    continue
                if provider_name in self._budget_exhausted:
                    continue
                try:
                    provider, sink = self._provider(provider_name)
                except ProviderError as err:
                    _log.warning("provider build failed: %s", err)
                    continue
                try:
                    if provider_name == _EBAY:
                        self._collect_ebay(provider, sink, query)
                    elif provider_name == _STOCKX:
                        self._collect_stockx(provider, sink, query)
                    else:
                        self._collect_generic(provider, sink, query)
                except BudgetExhaustedError:
                    _log.warning("daily budget exhausted for %s", provider_name)
                    self._budget_exhausted.add(provider_name)
                except ProviderError as err:
                    _log.warning("collection failed for %s: %s", provider_name, err)

        counters = self._run_counters()
        tasks_failed = counters["tasks_failed"] > 0
        if counters["tasks_done"] > 0 and not tasks_failed:
            status = RunStatus.SUCCESS.value
        elif counters["tasks_done"] > 0 or counters["stored"] > 0:
            status = RunStatus.PARTIAL_SUCCESS.value
        else:
            status = RunStatus.FAILURE.value
        self._store.finish_run(self._run_id, status=status, counters=counters)
        purged = self._store.gc_raw_payloads(older_than_days=self._config.raw_retention_days)
        if purged:
            _log.info("raw payload GC removed %d rows", purged)
        return self._run_id

    def _run_counters(self) -> dict[str, Any]:
        tasks = self._store.tasks_for_run(self._run_id)
        fetched = sum(t["items_returned"] for t in tasks)
        stored = sum(t["items_stored"] for t in tasks)
        rejected = sum(t["items_rejected"] for t in tasks)
        reported = [t["reported_total"] for t in tasks if t["reported_total"] is not None]
        counts = self._store.observation_counts(self._run_id)
        return {
            "tasks": len(tasks),
            "tasks_done": sum(1 for t in tasks if t["status"] == TaskStatus.DONE.value),
            "tasks_failed": sum(1 for t in tasks if t["status"] == TaskStatus.FAILED.value),
            "requested": fetched,  # records we asked for and got back
            "reported_market_total": sum(reported) if reported else None,
            "fetched": fetched,
            "stored": stored,
            "rejected": rejected,
            "entities": counts["entities"],
            "observations": counts["observations"],
            "requests_used_today": (
                {
                    name: self._store.requests_used(name, day=self._budget.day)
                    for name in {_EBAY, _STOCKX}
                }
                if self._budget
                else {}
            ),
        }

    # -- shared task plumbing ------------------------------------------------ #
    def _new_task(
        self,
        provider_name: str,
        query: CollectionQuery,
        endpoint: str,
        page: int,
        offset: int,
        filters: dict[str, Any],
        marketplace: str | None,
    ) -> tuple[CollectionTask, int]:
        task = CollectionTask(
            provider=provider_name,
            query_id=query.query_id,
            query_text=query.search_text,
            endpoint=endpoint,
            page_number=page,
            offset=offset,
            filters_json=json.dumps(filters, sort_keys=True),
            marketplace=marketplace,
        )
        return task, self._store.record_task(self._run_id, task)

    def _fail_task(self, task: CollectionTask, task_id: int, err: BaseException) -> None:
        task.status = TaskStatus.FAILED
        task.error_category = type(err).__name__
        self._store.finish_task(task_id, task)

    # -- eBay ---------------------------------------------------------------- #
    def _collect_ebay(
        self, provider: EbayBrowseProvider, sink: PayloadSink, query: CollectionQuery
    ) -> bool:
        cfg = self._config
        max_results = query.max_results_per_provider or cfg.page_size_ebay
        page_size = min(cfg.page_size_ebay, max_results)
        filters = {
            "filter": cfg.ebay_search_filter,
            "fieldgroups": cfg.ebay_search_fieldgroups,
            "sort": cfg.ebay_search_sort,
        }
        filters = {k: v for k, v in filters.items() if v}
        complete = False
        fetched = 0
        entity_pairs: list[tuple[int, str]] = []  # (entity_id, provider item id)

        page = 1
        while True:
            task, task_id = self._new_task(
                _EBAY,
                query,
                "item_summary/search",
                page,
                (page - 1) * page_size,
                {**filters, "limit": page_size},
                cfg.ebay_marketplace_id,
            )
            sink.begin_task(task_id)
            started = time.monotonic()
            try:
                request = provider.build_request(query.search_text, page=page, page_size=page_size)
                response = provider.http.send(request)
                task.http_status = response.status
                page_obj = provider.parse_response(response, query=query.search_text)
                payload = json.loads(response.body.decode("utf-8"))
            except BudgetExhaustedError:
                self._fail_task(task, task_id, BudgetExhaustedError(_EBAY, "", 0))
                raise
            except ProviderError as err:
                self._fail_task(task, task_id, err)
                return fetched > 0
            task.duration_ms = round((time.monotonic() - started) * 1000)
            task.attempts = sink.attempts

            summaries = payload.get("itemSummaries") or []
            task.items_returned = len(summaries)
            for summary in summaries:
                eid = self._ingest_ebay_summary(summary, task_id=task_id, run_id=self._run_id)
                if eid is None:
                    task.items_rejected += 1
                else:
                    task.items_stored += 1
                    entity_pairs.append((eid, str(summary.get("itemId"))))
            task.reported_total = payload.get("total")
            task.has_more = page_obj.has_more
            task.status = TaskStatus.DONE
            self._store.finish_task(task_id, task)
            fetched += len(summaries)

            if not page_obj.has_more:
                complete = True
                break
            if fetched >= max_results or page >= self._config.max_pages:
                break  # capped: coverage stays SAMPLE, no disappearance marking
            page += 1

        if complete:
            self._mark_disappeared(_EBAY, query)
        self._enrich_ebay(entity_pairs, query, sink)
        return fetched > 0

    def _enrich_ebay(
        self,
        entity_pairs: list[tuple[int, str]],
        query: CollectionQuery,
        sink: PayloadSink,
    ) -> None:
        remaining = self._config.detail_fetch_top_n - self._detail_budget_used
        quota = remaining if query.detail_top_n is None else min(remaining, query.detail_top_n)
        if quota <= 0:
            return
        for ordinal, (entity_id, item_id) in enumerate(entity_pairs[:quota], start=1):
            task, task_id = self._new_task(
                _EBAY,
                query,
                "item/detail",
                ordinal,
                0,
                {"item_id": item_id},
                self._config.ebay_marketplace_id,
            )
            sink.begin_task(task_id)
            started = time.monotonic()
            try:
                item = self._providers[_EBAY][0].get_item(item_id)
                task.http_status = 200
            except BudgetExhaustedError:
                self._fail_task(task, task_id, BudgetExhaustedError(_EBAY, "", 0))
                raise
            except ProviderError as err:
                self._fail_task(task, task_id, err)
                continue
            task.duration_ms = round((time.monotonic() - started) * 1000)
            task.attempts = sink.attempts
            stored = self._ingest_ebay_detail(entity_id, item, task_id)
            task.items_returned = 1
            task.items_stored = stored
            task.status = TaskStatus.DONE
            self._store.finish_task(task_id, task)
            self._detail_budget_used += 1

    def _ingest_ebay_summary(
        self, summary: dict[str, Any], *, task_id: int, run_id: str
    ) -> int | None:
        item_id = summary.get("itemId")
        title = summary.get("title")
        if not isinstance(item_id, str) or not item_id or not title:
            return None
        now = _utc_now()

        parent_id = None
        group_href = summary.get("itemGroupHref")
        if summary.get("itemGroupType") and isinstance(group_href, str):
            # itemGroupHref is a get_items_by_item_group URL carrying
            # ?item_group_id=<id> - extract the param, not the path tail.
            group_id = urllib.parse.parse_qs(urllib.parse.urlsplit(group_href).query).get(
                "item_group_id", [group_href.rsplit("/", 1)[-1]]
            )[0]
            parent_id = self._store.upsert_entity(
                ProviderEntity(
                    provider=_EBAY,
                    entity_type=EntityType.ITEM_GROUP,
                    provider_entity_id=group_id,
                    marketplace=summary.get("listingMarketplaceId"),
                    canonical_url=group_href,
                ),
                run_id=run_id,
                observed_at=now,
                state=ObservationState.ACTIVE,
            )

        seller = summary.get("seller") or {}
        username = seller.get("username")
        seller_key = seller_pseudonym(_EBAY, username) if isinstance(username, str) else None
        entity_id = self._store.upsert_entity(
            ProviderEntity(
                provider=_EBAY,
                entity_type=EntityType.LISTING,
                provider_entity_id=item_id,
                parent_entity_id=parent_id,
                marketplace=summary.get("listingMarketplaceId"),
                canonical_url=summary.get("itemWebUrl"),
                title=str(title),
                seller_key=seller_key,
            ),
            run_id=run_id,
            observed_at=now,
            state=ObservationState.ACTIVE,
        )

        attrs = dict(summary)
        attrs.pop("itemAffiliateWebUrl", None)
        if isinstance(attrs.get("seller"), dict):
            seller_attrs = dict(attrs["seller"])
            seller_attrs.pop("username", None)
            if seller_key:
                seller_attrs["seller_key"] = seller_key
            attrs["seller"] = seller_attrs

        price = summary.get("price") or {}
        amount = _float_or_none(price.get("value"))
        attributes_json = json.dumps(attrs, sort_keys=True, default=str)
        self._store.insert_observation(
            Observation(
                entity_id=entity_id,
                collection_run_id=run_id,
                task_id=task_id,
                observed_at=now,
                source_event_time=summary.get("itemCreationDate"),
                source_kind=SourceKind.SEARCH,
                state=ObservationState.ACTIVE,
                price_amount=amount,
                price_currency=price.get("currency"),
                price_kind=PriceKind.ASK,
                condition=summary.get("condition"),
                attributes_json=attributes_json,
                content_hash=content_hash(
                    attributes_json,
                    state=ObservationState.ACTIVE.value,
                    price=amount,
                    currency=price.get("currency"),
                ),
                parser_version=EBAY_PARSER_VERSION,
            )
        )
        return entity_id

    def _ingest_ebay_detail(self, entity_id: int, item: dict[str, Any], task_id: int) -> int:
        now = _utc_now()
        availabilities = item.get("estimatedAvailabilities") or []
        avail = availabilities[0] if availabilities else {}
        qty_available = avail.get("estimatedAvailableQuantity")
        qty_sold = avail.get("estimatedSoldQuantity")
        status = avail.get("estimatedAvailabilityStatus")

        # Flag provider-estimate decreases/resets; a zero change is not "no sales".
        prev = self._store.latest_observation(entity_id, source_kind=SourceKind.DETAIL)
        sold_delta = None
        sold_flag = None
        if (
            prev is not None
            and prev.get("quantity_sold_estimate") is not None
            and isinstance(qty_sold, int)
        ):
            sold_delta = qty_sold - prev["quantity_sold_estimate"]
            if sold_delta < 0:
                sold_flag = "reset" if qty_sold == 0 else "decrease"

        aspects = {
            a["name"]: a.get("value")
            for a in (item.get("localizedAspects") or [])
            if isinstance(a, dict) and a.get("name")
        }
        bid_price = (item.get("currentBidPrice") or {}).get("value")
        attrs = {
            "estimated_availabilities": availabilities,
            "localized_aspects": aspects,
            "seller_item_revision": item.get("sellerItemRevision"),
            "unique_bidder_count": item.get("uniqueBidderCount"),
            "bid_count": item.get("bidCount"),
            "current_bid_price": _float_or_none(bid_price),
            "minimum_price_to_bid": _float_or_none(
                (item.get("minimumPriceToBid") or {}).get("value")
            ),
            "reserve_price_met": item.get("reservePriceMet"),
            "gtin": item.get("gtin"),
            "epid": item.get("epid"),
            "mpn": item.get("mpn"),
            "brand": item.get("brand"),
            "category_id": item.get("categoryId"),
            "category_path": item.get("categoryPath"),
            "return_terms": item.get("returnTerms"),
            "ship_to_locations": item.get("shipToLocations"),
            "taxes": item.get("taxes"),
            "quantity_limit_per_buyer": item.get("quantityLimitPerBuyer"),
            "immediate_pay": item.get("immediatePay"),
            "eligible_for_inline_checkout": item.get("eligibleForInlineCheckout"),
            "enabled_for_guest_checkout": item.get("enabledForGuestCheckout"),
            "lot_size": item.get("lotSize"),
            "payment_methods": item.get("paymentMethods"),
            "condition_description": item.get("conditionDescription"),
            "sold_estimate_delta": sold_delta,
            "sold_estimate_flag": sold_flag,
        }
        state = ObservationState.ENDED if status == "OUT_OF_STOCK" else ObservationState.ACTIVE
        price = item.get("price") or {}
        amount = _float_or_none(price.get("value"))
        attributes_json = json.dumps(attrs, sort_keys=True, default=str)
        self._store.insert_observation(
            Observation(
                entity_id=entity_id,
                collection_run_id=self._run_id,
                task_id=task_id,
                observed_at=now,
                source_event_time=item.get("itemCreationDate"),
                source_kind=SourceKind.DETAIL,
                state=state,
                price_amount=amount,
                price_currency=price.get("currency"),
                price_kind=PriceKind.ASK,
                quantity_available=qty_available if isinstance(qty_available, int) else None,
                quantity_sold_estimate=qty_sold if isinstance(qty_sold, int) else None,
                condition=item.get("condition"),
                description=item.get("description"),
                attributes_json=attributes_json,
                content_hash=content_hash(
                    attributes_json,
                    state=state.value,
                    price=amount,
                    currency=price.get("currency"),
                ),
                parser_version=EBAY_PARSER_VERSION,
            )
        )
        if state == ObservationState.ENDED:
            self._store.set_entity_state(entity_id, ObservationState.ENDED)
        return 1

    # -- StockX -------------------------------------------------------------- #
    def _collect_stockx(
        self, provider: StockXProvider, sink: PayloadSink, query: CollectionQuery
    ) -> bool:
        cfg = self._config
        max_results = query.max_results_per_provider or cfg.page_size_stockx
        page_size = min(cfg.page_size_stockx, max_results)
        complete = False
        fetched = 0
        product_entities: list[tuple[int, str]] = []  # (entity_id, productId)

        page = 1
        while True:
            task, task_id = self._new_task(
                _STOCKX,
                query,
                "catalog/search",
                page,
                (page - 1) * page_size,
                {"pageSize": page_size},
                "stockx.com",
            )
            sink.begin_task(task_id)
            started = time.monotonic()
            try:
                request = provider.build_request(query.search_text, page=page, page_size=page_size)
                response = provider.http.send(request)
                task.http_status = response.status
                page_obj = provider.parse_response(response, query=query.search_text)
                payload = json.loads(response.body.decode("utf-8"))
            except BudgetExhaustedError:
                self._fail_task(task, task_id, BudgetExhaustedError(_STOCKX, "", 0))
                raise
            except ProviderError as err:
                self._fail_task(task, task_id, err)
                return fetched > 0
            task.duration_ms = round((time.monotonic() - started) * 1000)
            task.attempts = sink.attempts

            products = payload.get("products") or []
            task.items_returned = len(products)
            for product in products:
                eid = self._ingest_stockx_product(product, task_id=task_id, run_id=self._run_id)
                if eid is None:
                    task.items_rejected += 1
                else:
                    task.items_stored += 1
                    product_entities.append((eid, str(product.get("productId"))))
            task.reported_total = payload.get("count")
            task.has_more = page_obj.has_more
            task.status = TaskStatus.DONE
            self._store.finish_task(task_id, task)
            fetched += len(products)

            if not page_obj.has_more:
                complete = True
                break
            if fetched >= max_results or page >= self._config.max_pages:
                break
            page += 1

        if complete:
            self._mark_disappeared(_STOCKX, query)

        # Per-product enrichment: market data (per-variant quotes) + optional
        # variant identity calls. Each is its own task row for accounting.
        for ordinal, (entity_id, product_id) in enumerate(product_entities, start=1):
            self._stockx_market_data(provider, sink, query, entity_id, product_id, ordinal=ordinal)
            if self._config.fetch_stockx_variants:
                self._stockx_variants(provider, sink, query, entity_id, product_id, ordinal=ordinal)
        return fetched > 0

    def _stockx_market_data(
        self,
        provider: StockXProvider,
        sink: PayloadSink,
        query: CollectionQuery,
        product_entity_id: int,
        product_id: str,
        *,
        ordinal: int,
    ) -> None:
        task, task_id = self._new_task(
            _STOCKX,
            query,
            "market-data",
            ordinal,
            0,
            {"product_id": product_id},
            "stockx.com",
        )
        sink.begin_task(task_id)
        started = time.monotonic()
        try:
            entries = provider.get_product_market_data(product_id)
            task.http_status = 200
        except BudgetExhaustedError:
            self._fail_task(task, task_id, BudgetExhaustedError(_STOCKX, "", 0))
            raise
        except ProviderError as err:
            self._fail_task(task, task_id, err)
            return
        task.duration_ms = round((time.monotonic() - started) * 1000)
        task.attempts = sink.attempts
        task.items_returned = len(entries)
        for entry in entries:
            if self._ingest_stockx_market_variant(entry, product_entity_id, task_id=task_id):
                task.items_stored += 1
            else:
                task.items_rejected += 1
        task.status = TaskStatus.DONE
        self._store.finish_task(task_id, task)

    def _stockx_variants(
        self,
        provider: StockXProvider,
        sink: PayloadSink,
        query: CollectionQuery,
        product_entity_id: int,
        product_id: str,
        *,
        ordinal: int,
    ) -> None:
        task, task_id = self._new_task(
            _STOCKX,
            query,
            "variants",
            ordinal,
            0,
            {"product_id": product_id},
            "stockx.com",
        )
        sink.begin_task(task_id)
        started = time.monotonic()
        try:
            variants = provider.get_product_variants(product_id)
            task.http_status = 200
        except BudgetExhaustedError:
            self._fail_task(task, task_id, BudgetExhaustedError(_STOCKX, "", 0))
            raise
        except ProviderError as err:
            self._fail_task(task, task_id, err)
            return
        task.duration_ms = round((time.monotonic() - started) * 1000)
        task.attempts = sink.attempts
        task.items_returned = len(variants)
        for variant in variants:
            if self._ingest_stockx_variant(variant, product_entity_id, task_id=task_id):
                task.items_stored += 1
            else:
                task.items_rejected += 1
        task.status = TaskStatus.DONE
        self._store.finish_task(task_id, task)

    def _ingest_stockx_product(
        self, product: dict[str, Any], *, task_id: int, run_id: str
    ) -> int | None:
        product_id = product.get("productId")
        title = product.get("title")
        if not isinstance(product_id, str) or not product_id or not title:
            return None
        now = _utc_now()
        url_key = product.get("urlKey")
        url = (
            f"https://stockx.com/{url_key}"
            if isinstance(url_key, str)
            else f"https://stockx.com/{product_id}"
        )
        entity_id = self._store.upsert_entity(
            ProviderEntity(
                provider=_STOCKX,
                entity_type=EntityType.CATALOGUE_PRODUCT,
                provider_entity_id=product_id,
                marketplace="stockx.com",
                canonical_url=url,
                title=str(title),
            ),
            run_id=run_id,
            observed_at=now,
            state=ObservationState.ACTIVE,
        )
        attributes_json = json.dumps(product, sort_keys=True, default=str)
        self._store.insert_observation(
            Observation(
                entity_id=entity_id,
                collection_run_id=run_id,
                task_id=task_id,
                observed_at=now,
                source_kind=SourceKind.SEARCH,
                state=ObservationState.ACTIVE,
                price_kind=PriceKind.UNKNOWN,
                attributes_json=attributes_json,
                content_hash=content_hash(
                    attributes_json,
                    state=ObservationState.ACTIVE.value,
                    price=None,
                    currency=None,
                ),
                parser_version=STOCKX_PARSER_VERSION,
            )
        )
        return entity_id

    def _ingest_stockx_market_variant(
        self, entry: dict[str, Any], product_entity_id: int, *, task_id: int
    ) -> int | None:
        variant_id = entry.get("variantId")
        if not isinstance(variant_id, str) or not variant_id:
            return None
        now = _utc_now()
        entity_id = self._store.upsert_entity(
            ProviderEntity(
                provider=_STOCKX,
                entity_type=EntityType.VARIANT,
                provider_entity_id=variant_id,
                parent_entity_id=product_entity_id,
                marketplace="stockx.com",
            ),
            run_id=self._run_id,
            observed_at=now,
            state=ObservationState.ACTIVE,
        )
        ask = _float_or_none(entry.get("lowestAskAmount"))
        attributes_json = json.dumps(entry, sort_keys=True, default=str)
        self._store.insert_observation(
            Observation(
                entity_id=entity_id,
                collection_run_id=self._run_id,
                task_id=task_id,
                observed_at=now,
                source_kind=SourceKind.MARKET_DATA,
                state=ObservationState.ACTIVE,
                price_amount=ask,
                price_currency=entry.get("currencyCode"),
                price_kind=PriceKind.ASK,
                attributes_json=attributes_json,
                content_hash=content_hash(
                    attributes_json,
                    state=ObservationState.ACTIVE.value,
                    price=ask,
                    currency=entry.get("currencyCode"),
                ),
                parser_version=STOCKX_PARSER_VERSION,
            )
        )
        return entity_id

    def _ingest_stockx_variant(
        self, variant: dict[str, Any], product_entity_id: int, *, task_id: int
    ) -> int | None:
        variant_id = variant.get("variantId")
        if not isinstance(variant_id, str) or not variant_id:
            return None
        now = _utc_now()
        entity_id = self._store.upsert_entity(
            ProviderEntity(
                provider=_STOCKX,
                entity_type=EntityType.VARIANT,
                provider_entity_id=variant_id,
                parent_entity_id=product_entity_id,
                marketplace="stockx.com",
                title=variant.get("variantName"),
            ),
            run_id=self._run_id,
            observed_at=now,
            state=ObservationState.ACTIVE,
        )
        attributes_json = json.dumps(variant, sort_keys=True, default=str)
        self._store.insert_observation(
            Observation(
                entity_id=entity_id,
                collection_run_id=self._run_id,
                task_id=task_id,
                observed_at=now,
                source_kind=SourceKind.VARIANTS,
                state=ObservationState.ACTIVE,
                price_kind=PriceKind.UNKNOWN,
                attributes_json=attributes_json,
                content_hash=content_hash(
                    attributes_json,
                    state=ObservationState.ACTIVE.value,
                    price=None,
                    currency=None,
                ),
                parser_version=STOCKX_PARSER_VERSION,
            )
        )
        return entity_id

    # -- generic fallback ------------------------------------------------------ #
    def _collect_generic(self, provider: Any, sink: PayloadSink, query: CollectionQuery) -> bool:
        """Search-only ingestion for any other registered live provider."""
        task, task_id = self._new_task(provider.name, query, "search", 1, 0, {}, None)
        sink.begin_task(task_id)
        try:
            request = provider.build_request(query.search_text, page=1, page_size=50)
            response = provider.http.send(request)
            task.http_status = response.status
        except ProviderError as err:
            self._fail_task(task, task_id, err)
            return False
        task.status = TaskStatus.DONE
        self._store.finish_task(task_id, task)
        return True

    # -- disappearance --------------------------------------------------------- #
    def _mark_disappeared(self, provider_name: str, query: CollectionQuery) -> None:
        """Mark entities absent from a *complete* re-run as ``disappeared``.

        Never called when coverage was capped - absence under sampling means
        nothing. A disappeared listing is explicitly NOT evidence of a sale.
        """
        now = _utc_now()
        for entity_id in self._store.entities_seen_for_query(
            provider_name, query.search_text, before_run_id=self._run_id
        ):
            attrs = json.dumps(
                {
                    "reason": "absent_from_complete_coverage",
                    "query_text": query.search_text,
                },
                sort_keys=True,
            )
            self._store.insert_observation(
                Observation(
                    entity_id=entity_id,
                    collection_run_id=self._run_id,
                    observed_at=now,
                    source_kind=SourceKind.SEARCH,
                    state=ObservationState.DISAPPEARED,
                    attributes_json=attrs,
                    content_hash=content_hash(
                        attrs,
                        state=ObservationState.DISAPPEARED.value,
                        price=None,
                        currency=None,
                    ),
                    parser_version="coverage-diff-0.1.0",
                )
            )
            self._store.set_entity_state(entity_id, ObservationState.DISAPPEARED)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
