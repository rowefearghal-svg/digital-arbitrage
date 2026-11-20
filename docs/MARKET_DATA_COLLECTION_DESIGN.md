# Market-Data Collection & Storage Layer — Implementation-Ready Design

**Status:** Design only. No code changes in this document.
**Scope:** Existing live providers only (`ebay_browse`, `stockx`), a configurable
product-family query manifest, and a new append-only store. The scan pipeline,
scoring, `history.db`, `pue_shadow.db` and the live-shadow trial are unchanged.

> Verified against the current branch (commit `e013167`) and against the
> published OpenAPI specs for eBay Browse `v1.19.7` and the StockX Public API
> `v2.0.0` on 2026-09-19. Every capability claim below is marked **[verified]**
> (present in the official spec/our fixture) or **[assumption]** (needs a live
> check before we rely on it).

---

## 1. Data coverage

### 1.1 eBay Browse (`ebay_browse`)

Auth: application OAuth token (client-credentials), `X-EBAY-C-MARKETPLACE-ID`
header. Documented budget: ~5,000 calls/day shared across Browse methods
(repo plan doc; verify at runtime via the Analytics `getRateLimits` API).

**Currently requested:** `GET /buy/browse/v1/item_summary/search` with `q`,
`limit`, `offset` only (`EbayBrowseProvider.build_request`).

**Returned today & mapped onto `Listing` / `Listing.extra`**
(`ebay_browse.py::_to_listing`, `_build_extra`; all [verified] in the spec):

| Group | Fields captured |
|---|---|
| Identity | `itemId` → `listing_id`, `legacyItemId`, `itemHref`, `epid`, `itemGroupType` |
| Content | `title`, `subtitle`, `shortDescription`, `itemWebUrl`, `itemAffiliateWebUrl`, `listingMarketplaceId`, `image`/`thumbnailImages`/`additionalImages` URLs |
| Price | `price.{value,currency}`, `marketingPrice` (original/discount/treatment), `unitPrice`, `unitPricingMeasure`, `currentBidPrice`, `bidCount` |
| Condition | `conditionId` → `Condition`, raw `condition` text |
| Seller | `seller.username`, `feedbackPercentage`, `feedbackScore`, `sellerAccountType` |
| Shipping | first `shippingOptions[]`: cost/currency/type/carrier/min/max delivery/guaranteed |
| Location | `itemLocation.{city,stateOrProvince,postalCode,country}` |
| Category | `categories[0].{categoryId,categoryName}`, `leafCategoryIds` |
| Lifecycle | `itemCreationDate`, `itemEndDate` |
| Demand/flags | `watchCount`, `buyingOptions`, `qualifiedPrograms`, `adultOnly`, `availableCoupons`, `topRatedBuyingExperience`, `priorityListing` |

**Retained in memory vs persisted:**

| Where | What survives |
|---|---|
| `Listing` in memory | Everything above during the scan |
| `history.db` (`runs`, `opportunities`) | Only ranked-opportunity snapshots: title, provider, asking price, estimates. **No listing id, URL, extras, or per-listing history.** |
| `pue_shadow.db` (`pue_cases`) | Full `reasoning_record_json` including the observation's `raw_attributes` (= `Listing.extra`) — shadow-mode only, keyed by case, not by listing over time |
| Raw API response | **Not persisted anywhere** — `parse_response` discards the JSON after mapping |

**Additional fields accessible with our existing access** (verified in the
`item_summary/search` OpenAPI — no extra permission needed, but **not currently
requested**):

| Field / parameter | Value for demand work |
|---|---|
| `filter=buyingOptions:{AUCTION|FIXED_PRICE}` | **Auctions are excluded by default today.** With the filter we get `bidCount`, `currentBidPrice`, `uniqueBidderCount` (detail) — real demand signals |
| `fieldgroups=EXTENDED` | Adds `shortDescription` and `itemLocation.city` (we already map both but never request the group) |
| `fieldgroups=ASPECT_REFINEMENTS` / `CONDITION_REFINEMENTS` / `CATEGORY_REFINEMENTS` / `BUYING_OPTION_REFINEMENTS` | Market-composition histograms per query (matchCount per aspect/condition) — cheap market-structure context |
| `sort=newlyListed` / `endingSoonest` / `price` | Alternative sampling windows; `priorityListing` is only returned under Best Match sort |
| `epid`, `gtin`, `category_ids` query params | Product-identity queries; `category_ids` scoping for family manifests |
| `filter=` (price range, conditions, sellers, deliveryCountry, itemLocationCountry) | Scoped samples; every filter used must be recorded as a coverage limit |
| `X-EBAY-C-ENDUSERCTX` (contextualLocation) | More accurate shipping/delivery estimates |

**Accessible via the `item` resource with the same token**
(`GET /buy/browse/v1/item/{item_id}`, verified in spec):

| Field | Demand relevance |
|---|---|
| `estimatedAvailabilities[].estimatedSoldQuantity` | **Cumulative estimated units sold per listing — the only sold-quantity signal we can get.** Estimated, not exact |
| `estimatedAvailabilities[].estimatedAvailableQuantity` / `estimatedRemainingQuantity` / `estimatedAvailabilityStatus` (`IN_STOCK`/`LIMITED_STOCK`/`OUT_OF_STOCK`) | Stock level + a defensible "no longer purchasable" signal |
| `description`, `localizedAspects` (all item specifics: brand/model/size/MPN/GTIN...) | Rich attributes for matching + features |
| `gtin`, `epid`, `product` container (`fieldgroups=PRODUCT`) | Product identity for linking |
| `bidCount`, `uniqueBidderCount`, `minimumPriceToBid`, `reservePriceMet` | Auction demand |
| `sellerItemRevision` + `fieldgroups=COMPACT` | Cheap change-detection probe for tracked listings |
| `returnTerms`, `shipToLocations`, `taxes`, `quantityLimitPerBuyer`, `immediatePay` | Saleability features |
| `seller.userId` (`fieldgroups=ADDITIONAL_SELLER_DETAILS`) | Stable seller key |

**Missing or restricted:**

| Want | Status |
|---|---|
| Confirmed sale price / sale date / completed listings | **Marketplace Insights `item_sales/search` — Limited Release, restricted, documented as not open to new users. Do NOT design assuming access.** Web sold-view now requires login and scraping is out of scope anyway |
| `watchCount` | Field exists in search response **but restricted — requires an App Check grant**; currently not returned to us |
| `getItems` (batch ≤20 item ids) | **Limited Release — partners only**; assume unavailable |
| Exact quantity sold / sell-through rate | Only the *estimate* above, via `getItem` |
| Listing date on summaries | `itemCreationDate` **is** returned (already captured); `itemEndDate` absent for Good-'Til-Cancelled listings |

### 1.2 StockX (`stockx`)

Auth: OAuth2 authorization-code JWT + `x-api-key`. Documented budget:
~25,000 requests/rolling-24h and ~1 request/second (verify; HTTP 429 on breach).

**Currently requested:** `GET /v2/catalog/search` (query, pageNumber, pageSize≤50)
+ one `GET /v2/catalog/products/{id}/market-data?currencyCode=…` per product
(N+1 calls per page).

**Returned today & mapped** (`stockx_provider.py`): `productId` → `listing_id`,
`title`, `urlKey` → URL, min `lowestAskAmount` across variants → `price`,
`currency_code`, `Condition.NEW` (constant), `extra` = styleId, productType,
brand, colorway, gender, releaseDate, retailPrice, variant_count, lowest_ask,
highest_bid.

**Retained:** identical situation to eBay — nothing is persisted except the
ranked-opportunity snapshot and PUE case JSON. The per-variant market-data
payload (variantId, per-variant ask/bid, sellFaster/earnMore, flex/direct
market splits) is **fetched and then discarded** except for min/max.

**Additional endpoints accessible with existing credentials** (verified in the
v2 OpenAPI):

| Endpoint | Adds |
|---|---|
| `GET /v2/catalog/products/{id}` | `sizeChart`, `isFlexEligible`, `isDirectEligible` (+ same attributes as search) |
| `GET /v2/catalog/products/{id}/variants` | Per-variant `variantId`, `variantName`, `variantValue` (size), `gtins[]`, size chart — **true variant identity** |
| `GET /v2/catalog/products/{id}/variants/{vid}` | Single-variant detail |
| `GET /v2/catalog/products/{id}/variants/{vid}/market-data` | Single-variant market data (accounts for our own asks; we have none) |
| `GET /v2/catalog/products/variants/gtins/{gtin}` | GTIN → variant resolution |

**Already returned but discarded:** `sellFasterAmount`, `earnMoreAmount`,
`flexLowestAskAmount`, and `standardMarketData`/`flexMarketData`/
`directMarketData` per variant. `sellFaster`/`earnMore` are guidance prices
"competitive with recent global sales" — a weak, provider-derived demand signal
worth keeping with its provenance labelled.

**Missing or restricted:** no confirmed sale prices, no sale counts, no
quantity sold, no listing dates, no seller identity, no condition split
(everything is effectively "new"), no per-listing location/shipping. StockX
catalog objects are **products**, not listings — the store must keep that
entity type distinct. The seller-side Orders/Listing APIs cover only our own
account activity — not market demand.

---

## 2. Storage design

### 2.1 Placement

New database **`market_data.db`** (default `~/.digital_arbitrage/market_data.db`,
`var/`-overridable), following the per-concern convention already used by
`history.db` and `pue_shadow.db`. Plain `sqlite3`, `PRAGMA user_version`
migration protocol copied from `pue/persistence.py` (transactional DDL,
version detection on shape). Existing stores are untouched.

### 2.2 Entity model — provider identity stays provider-native

```
provider_entities (
  entity_id            INTEGER PK,
  provider             TEXT NOT NULL,          -- 'ebay_browse' | 'stockx'
  entity_type          TEXT NOT NULL,          -- 'listing' | 'catalogue_product' | 'variant' | 'item_group'
  provider_entity_id   TEXT NOT NULL,          -- itemId / productId / variantId / groupId
  parent_entity_id     INTEGER NULL REFERENCES provider_entities(entity_id),
  marketplace          TEXT,                   -- EBAY_IE, stockx.com region, ...
  canonical_url        TEXT,
  title                TEXT,
  first_seen_run_id    TEXT, first_seen_at TEXT,
  last_seen_at         TEXT, times_seen INTEGER DEFAULT 0,
  latest_state         TEXT,                   -- mirrors most recent observation state
  UNIQUE(provider, entity_type, provider_entity_id)
)
```

- eBay `itemId` (`v1|…|0`) → `listing`; `itemGroupType` present → an
  `item_group` entity linked as parent. `legacyItemId`, `epid`, `gtin` are
  **attributes**, not identity.
- StockX `productId` → `catalogue_product`; each `variantId` → `variant` with
  `parent_entity_id` → the product. Nothing collapses a StockX product into an
  eBay listing or vice versa.
- PUE product identity is **never** merged into this table. A separate link
  table records inferred correspondences:

```
entity_links (
  link_id PK, entity_id FK,
  link_kind TEXT,               -- 'pue_case' | 'pue_catalogue_product' | 'cross_provider_candidate' | 'manual'
  target_id TEXT,               -- case_id / catalogue_product_id / other entity key
  match_method TEXT,            -- 'pue-v0.1' | 'epid' | 'manual' | ...
  match_confidence REAL,        -- NULL when unknown — never 0-as-unknown
  status TEXT,                  -- 'candidate' | 'confirmed' | 'rejected'
  created_by TEXT, created_at TEXT,
  UNIQUE(entity_id, link_kind, target_id)
)
```

Uncertain matches persist as `candidate` rows; nothing auto-merges entities.

### 2.3 Observations — append-only history

```
observations (
  observation_id    INTEGER PK,
  entity_id         INTEGER NOT NULL REFERENCES provider_entities(entity_id),
  collection_run_id TEXT NOT NULL REFERENCES collection_runs(run_id),
  task_id           INTEGER REFERENCES collection_tasks(task_id),
  observed_at       TEXT NOT NULL,             -- retrieval time (UTC ISO-8601)
  source_event_time TEXT,                      -- provider timestamp (itemCreationDate etc.)
  state             TEXT NOT NULL,             -- see §3
  -- curated columns for the fields that drive demand features
  price_amount      REAL,  price_currency TEXT,
  price_kind        TEXT,                      -- 'ask' | 'bid' | 'sold' | 'retail' | 'guidance' | 'unknown'
  quantity_available INTEGER,                  -- NULL = unknown, never 0
  quantity_sold_estimate INTEGER,              -- eBay estimatedSoldQuantity only
  condition         TEXT,
  attributes_json   TEXT NOT NULL,             -- full flat extra map + nested demand fields
  content_hash      TEXT NOT NULL,             -- sha256 of canonical attributes_json
  parser_version    TEXT NOT NULL,             -- e.g. 'ebay-browse-parser-1.0'
  UNIQUE(entity_id, collection_run_id, content_hash)   -- duplicate-safe ingestion
)
```

- Every fetch produces a row; re-ingesting the same payload within a run is a
  no-op (UNIQUE + `INSERT OR IGNORE`). Price changes are new rows with a new
  `content_hash`; history is never overwritten.
- `attributes_json` carries everything `Listing.extra` holds today plus
  detail-level fields (`estimated_sold_quantity`, `unique_bidder_count`,
  `seller_feedback_score`, variant `sellFaster`/`earnMore`, …). Curated columns
  exist only for hot query fields; the JSON is the lossless projection.
- Missing value = SQL `NULL`. Zero means the source actually said zero.

### 2.4 Raw payloads (permitted, redacted)

```
raw_payloads (
  payload_id        INTEGER PK,
  collection_run_id TEXT NOT NULL, task_id INTEGER,
  endpoint          TEXT NOT NULL,             -- 'item_summary/search' | 'item/{id}' | 'catalog/search' | 'market-data'
  request_url       TEXT NOT NULL,             -- path + query params, never headers
  http_status       INTEGER NOT NULL,
  payload_json      TEXT NOT NULL,             -- response body (or redacted form)
  payload_sha256    TEXT NOT NULL,
  redaction_version TEXT NOT NULL,
  retrieved_at      TEXT NOT NULL
)
```

- Captured at **transport level** (`RecordingTransport` wrapping the provider's
  API transport — never the token transport), so pages, detail calls and error
  bodies are all recorded without changing provider parsing.
- Request **headers are never stored** — that structurally excludes
  `Authorization` bearer tokens, `x-api-key`, cookies. Response bodies contain
  no credentials; a `redaction.py` pass additionally drops a denylist
  (`seller.userId` if we choose not to keep it, any `*token*`/`*secret*` keys)
  and records `redaction_version`.
- Retention is configurable (`raw_payload_retention_days`, default 90; raw rows
  deleted by age, observations kept). Optional `zlib`-compressed storage if
  volume demands it.

### 2.5 Runs, tasks, coverage

```
collection_runs (
  run_id TEXT PK, manifest_id TEXT, manifest_hash TEXT,
  collector_version TEXT, schema_version TEXT,
  started_at TEXT, finished_at TEXT, status TEXT,     -- SUCCESS|PARTIAL_SUCCESS|FAILURE
  config_json TEXT,                                   -- frequency, limits, provider settings (no secrets)
  counters_json TEXT                                  -- requested/fetched/stored/rejected
)

collection_tasks (
  task_id INTEGER PK, collection_run_id TEXT NOT NULL,
  provider TEXT, query_id TEXT, query_text TEXT,
  filters_json TEXT,               -- exact filter/fieldgroups/sort sent — the sample definition
  marketplace TEXT,
  page_number INTEGER, offset INTEGER,
  status TEXT,                     -- 'pending'|'done'|'failed'|'skipped'
  http_status INTEGER, error_category TEXT, attempts INTEGER,
  items_returned INTEGER, items_stored INTEGER, items_rejected INTEGER,
  reported_total INTEGER,          -- eBay 'total' / StockX 'count' (approximate; flagged)
  has_more INTEGER,                -- provider-reported
  duration_ms INTEGER, retrieved_at TEXT,
  UNIQUE(collection_run_id, provider, query_id, page_number)
)
```

- One task row per HTTP page → restartability (resume skips `done` tasks),
  partial-failure accounting, and pagination coverage: a query is
  `coverage_complete` only when the last fetched page had `has_more = 0` and no
  cap (`max_results`, `page_number` ceiling, 10k offset wall) truncated it.
- `filters_json` + `marketplace` + `reported_total` make the sampling frame
  explicit, so a 200-item sample is never mistaken for the whole market.

---

## 3. Evidence quality

`observations.state` (and `provider_entities.latest_state`) uses an explicit
vocabulary:

| State | Meaning | Set by |
|---|---|---|
| `active` | Returned in the latest fetch for its source query | Search/detail fetch |
| `confirmed_sale` | A source that *attests a sale* reported it | Marketplace Insights (if ever granted), verified manual import, own-account order data (deferred) |
| `ended` | Provider signals non-purchasable: `itemEndDate` passed, `estimatedAvailabilityStatus=OUT_OF_STOCK`, or `getItem` 404/`11001` | Detail fetch / scheduled re-probe |
| `disappeared` | Was seen for a query; absent from a **complete-coverage** re-run of that same query | Coverage diff. **Explicitly not a sale** — delisted, revised, sold, expired, or sampling change are indistinguishable |
| `inferred_outcome` | A derived guess, with `match_method` + confidence in `attributes_json` | Later inference job; never presented as fact |
| `unknown` | Insufficient evidence | Default |

Rules enforced by construction:

- Disappearance is never written as `confirmed_sale`; promotion to
  `confirmed_sale` requires a sale-attesting source row.
- `quantity_sold_estimate` NULL ≠ 0; absence of `watchCount` ≠ 0 watchers
  (it's restricted, report as `restricted`, not missing).
- Asking prices are `price_kind='ask'`; StockX `lowestAsk`/`highestBid` are
  order-book quotes, `sellFaster`/`earnMore` are `'guidance'` — none are
  achieved sale prices.
- Absence under **incomplete** coverage marks nothing; the observation is
  simply not refreshed (staleness shows in the completeness report instead).

**Manual sold-comparison imports** (`sold_imports` table, deferred-but-designed):
`source_label` (`manual`/`csv`), `provider`, `provider_entity_id` (nullable →
unresolved queue), `sold_price`, `currency`, `sold_date`, `quantity`,
`evidence_url`, `imported_by`, `imported_at`, `source_file_hash`,
`verification_status` ∈ `unverified | self_reported | cross_checked`,
`raw_row_json`. These land as `confirmed_sale`-grade evidence *only* with
provenance attached; unverified imports stay visibly `self_reported`. They
never overwrite API observations — they are a separate evidence class.

---

## 4. Collection reliability

- **Pagination:** existing `paginate()` + `has_more`; each page is a
  `collection_tasks` row. eBay `total`/StockX `count` recorded as *approximate*
  (eBay documents `total` as an indicator, `next` is authoritative — our code
  already treats it that way).
- **Rate limits:** per-provider `TokenBucketRateLimiter` already exists;
  configured defaults: eBay ~0.05 rps pacing + daily budget counter (the
  existing per-second limiter does not enforce the ~5,000/day cap — a
  `daily_request_budget` counter in `collection_runs.config_json`, cheap and
  honest); StockX 1 rps + 25k/day.
- **Retries:** existing `RetryPolicy` (429/5xx, `Retry-After` honoured).
  `collection_tasks.attempts` records the real count.
- **Partial failures:** provider/query/page granularity — one failure marks its
  task `failed`, the run `PARTIAL_SUCCESS`, nothing rolls back.
- **Restartability:** `run_id` + task unique key; a `--resume <run_id>` flag
  re-reads pending/failed tasks only.
- **Duplicate-safe ingestion:** entity upsert on
  `(provider, entity_type, provider_entity_id)`; observation insert-or-ignore
  on `(entity_id, run_id, content_hash)`; `times_seen`/`last_seen_at` track
  repeated presence without duplicating entities.
- **Stale observation:** `observed_at` vs `datetime.now` beyond
  `stale_after_hours` (config) is *reported*, never treated as ended.

### 4.1 Frequency, volume and storage estimates

Stated assumptions: manifest = 10 GPU-family queries; eBay `page_size=200`,
≤3 pages/query (`max_results=600`); optional `getItem` detail for the newest
≤150 listings/run; StockX ≤25 products/query + market-data (and optionally
variants) each.

| | per run | 4 runs/day |
|---|---|---|
| eBay search pages | ≤30 calls | ≤120 |
| eBay `getItem` detail | ≤150 calls | ≤600 |
| StockX search + market-data | 10 + ~250 calls | ~1,040 |
| StockX variants (optional) | +~250 calls | +~1,040 |
| **Total** | ~440–690 calls | ~1.8k–2.8k — inside both budgets; hourly collection with detail would exceed eBay's ~5k/day, so default cadence is **every 4–6h** (detail on) or hourly (search-only) |

Storage/run: ~40 pages × ~50–80KB raw + ~350 detail/variant payloads × ~2–10KB
+ ~700 curated observation rows ≈ **~3–5 MB**. At 4 runs/day ≈ **15–20 MB/day
→ ~0.5 GB/month**, dominated by raw payloads → the 90-day raw TTL bounds the DB
at roughly ~2 GB worst case; curated observations (~1 KB each) are retained
indefinitely (~0.25 GB/year).

Config (`[collection]` TOML table): `interval_minutes`, `queries_manifest`,
`max_results_per_query`, `detail_fetch_top_n`, `fetch_stockx_variants`,
`raw_payload_retention_days`, `stale_after_hours`, `daily_request_budget`.

---

## 5. Completeness reporting

`arb collect-report <run_id>` (JSON + markdown) built from tasks/observations:

- **Requested / fetched / stored / rejected** per (provider, query, page) and
  in aggregate, with rejection reason (`validation_error`, `duplicate`,
  `missing_required_field`).
- **Missing fields**: a per-provider field-expectation registry
  (`expected_fields.py`) classifies each field as `returned | empty |
  restricted | not_in_api`; e.g. `watchCount → restricted (App Check)`,
  `sold_price → not_in_api`, `itemEndDate → empty (GTC)`.
- **Provider errors & gaps**: error_category histogram, failed tasks, HTTP
  status distribution, token/auth failures isolated from data failures.
- **Stale observations**: entities not re-observed within `stale_after_hours`.
- **Incomplete pagination**: queries where `has_more` was still true at the cap
  or a page failed mid-set — flagged `SAMPLE`, never `COMPLETE`.
- **Coverage framing**: reported_total vs items stored vs caps, so every report
  states the sampling window explicitly.

---

## 6. Future commercial outcomes (identifiers designed now, workflow deferred)

Foreign keys already present for the later layer:

- `observations.observation_id` → the exact evidence a prediction was made
  against; `provider_entities.entity_id` → what was bought/rejected.
- `collection_runs.run_id`/`tasks` → the sampling context any prediction must
  be conditioned on (a prediction made against a capped sample is not a market
  prediction).
- `entity_links` → join provider evidence to PUE identity
  (`pue_cases.case_id`, `catalogue_product_id`) without merging them.

Later tables (not built now) that these IDs already support:
`predictions(prediction_id, entity_id, made_at, model_version, features_hash,
predicted_price, predicted_days_to_sell, uncertainty)`,
`buy_decisions(decision_id, entity_id, prediction_id, decided_at, action)`,
`inventory(item_id, entity_id, bought_at, cost)`, `sales(sale_id, item_id,
sold_price, fees, sold_at)`, `returns`, `unsold_writeoffs`. Timestamps
(`observed_at`, `source_event_time`, `made_at`) already distinguish
evidence-time from decision-time — the property a backtest needs.

---

## 7. Implementation plan

### 7.1 Schema & example records

DDL above is the v1 schema (`SCHEMA_VERSION=1`, `user_version`).

Example `provider_entities` row:

```json
{"entity_id": 101, "provider": "ebay_browse", "entity_type": "listing",
 "provider_entity_id": "v1|110000000001|0", "parent_entity_id": null,
 "marketplace": "EBAY_IE",
 "canonical_url": "https://www.ebay.ie/itm/110000000001",
 "title": "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
 "first_seen_run_id": "run-2026-09-19-a", "first_seen_at": "2026-09-19T10:00:00+00:00",
 "last_seen_at": "2026-09-19T14:00:00+00:00", "times_seen": 2, "latest_state": "active"}
```

Example `observations` row (same entity, price dropped → new row, old kept):

```json
{"observation_id": 9004, "entity_id": 101, "collection_run_id": "run-2026-09-19-b",
 "observed_at": "2026-09-19T14:00:00+00:00",
 "source_event_time": "2026-07-01T09:00:00.000Z",
 "state": "active", "price_amount": 1749.0, "price_currency": "EUR",
 "price_kind": "ask", "quantity_available": null, "quantity_sold_estimate": 3,
 "condition": "new",
 "attributes_json": "{\"buying_options\":\"FIXED_PRICE,BEST_OFFER\",\"seller\":\"example_seller_ie\",\"watch_count\":null,\"estimated_sold_quantity\":3,\"estimated_availability_status\":\"IN_STOCK\"}",
 "content_hash": "…", "parser_version": "ebay-browse-parser-1.0"}
```

StockX variant: `entity_type='variant'`, `provider_entity_id=<variantId>`,
`parent_entity_id → catalogue_product`, `price_kind='ask'`, `attributes_json`
carrying `variant_value`, `highest_bid`, `sell_faster`, `earn_more`, `gtins`.

### 7.2 Modules/files

New package `src/digital_arbitrage/market_data/`:

| File | Contents |
|---|---|
| `models.py` | `EntityType`, `ObservationState`, `PriceKind`, `VerificationStatus` enums; `ProviderEntity`, `ObservationRecord`, `CollectionTask`, `CollectionRun` dataclasses |
| `store.py` | `MarketDataStore` — schema v1 + migrations (copies the `pue/persistence.py` protocol), `upsert_entity`, `insert_observation`, `record_task`, `finish_run`, `mark_disappeared`, coverage/report queries, raw-payload GC |
| `capture.py` | `RecordingTransport(Transport)` — delegates to the real transport, emits `(sanitized_request, response)` to a sink |
| `redaction.py` | header stripping (structural), response denylist, `REDACTION_VERSION` |
| `collector.py` | `CollectionRunner` — manifest → per-(query,provider) page loop → ingest → coverage accounting → disappearance diff |
| `manifest.py` | collection manifest loader (reuse the `live_shadow.py` `QueryManifest` shape; add `filters`, `detail_fetch` per query) |
| `expected_fields.py` | per-provider field registry powering the missing-fields report |
| `report.py` | completeness/coverage report builder |
| `imports.py` | manual sold-comparison CSV import (schema in place; command can land in sprint 2) |

Edits to existing files (all additive, defaults preserve behaviour):

- `providers/live/ebay_browse.py` — `EbayBrowseConfig` gains `search_filter`,
  `search_fieldgroups`, `search_sort`, `enduserctx`; `build_request` emits them;
  new `get_item(item_id)` helper; capability flag `supports_item_detail=True`.
- `providers/live/stockx_provider.py` — `StockXConfig.fetch_variants`;
  `get_product_variants(product_id)` helper.
- `pipeline/cli.py` — `arb collect` (`--manifest`, `--once/--interval`,
  `--resume`, `--db`) and `arb collect-report <run_id>` subcommands.
- `pipeline/config_file.py` — `[collection]` table parsing.
- `docs/DECISIONS.md` — ADR-031 for this layer.
- Tests: `tests/test_market_data_*.py` + fixtures under
  `tests/fixtures/market_data/` (reuse eBay/StockX fixtures).

### 7.3 Compatibility

- `arb scan`, `--save`, `history.db`, `pue_shadow`, `live-shadow`: **zero
  changes**. The collector is a separate command; scoring and PUE behaviour
  are untouched.
- Existing history stays in `history.db`; nothing is migrated. `entity_links`
  can backfill `pue_case` links by matching
  `(provider, provider_listing_id)` against `pue_cases` — optional, read-only.
- No new dependencies; stdlib only; no scraping; read-only API use; secrets
  remain env-only and are structurally excluded from storage.

### 7.4 Ordered implementation

1. `market_data/models.py` + `store.py` schema + `MarketDataStore` CRUD (pure
   SQLite, fully testable offline).
2. `capture.py` + `redaction.py` (RecordingTransport + sink; redaction tests).
3. eBay provider additions (request params + `get_item`), StockX variants
   helper — each behind config flags, tests with fake transports.
4. `collector.py` ingest path (search pages → entities/observations/tasks;
   disappearance diff; duplicate-safe upserts).
5. `manifest.py` + `[collection]` config + `arb collect` CLI.
6. `expected_fields.py` + `report.py` + `arb collect-report`.
7. `imports.py` + `sold_imports` ingestion (can slip to a second sprint).
8. ADR-031 + runbook doc (`docs/operations/MARKET_DATA_COLLECTION.md`).

### 7.5 Acceptance tests

| Test | Asserts |
|---|---|
| Field preservation | Fixture eBay page ingested → every `extra` key present in `attributes_json`; raw payload retrievable byte-identical post-redaction; StockX market-data variant fields (variantId, sellFaster, gtins) all land |
| History | Two runs over a changed fixture → two observations, one entity, price delta preserved, `first_seen_at` < `last_seen_at`, `times_seen=2` |
| Idempotency | Re-ingesting the same run payload → no new entities, `INSERT OR IGNORE` dedupes observations; re-running a completed task marks `skipped` |
| Partial failure | Page 2 transport error → task `failed`, run `PARTIAL_SUCCESS`, page-1 entities retained; `--resume` completes page 2 without duplicates |
| Secret exclusion | Recorded requests contain no `Authorization`/`x-api-key`/cookie values; synthetic secret field in a payload is redacted; `redaction_version` stamped |
| Evidence states | Disappearance under complete coverage → `disappeared`, never `confirmed_sale`; `NULL` quantity never reads as 0; `price_kind='ask'` never reported as sale price; manual import lands with `verification_status` and provenance |
| Coverage framing | Capped query reports `SAMPLE` + `reported_total`; uncapped complete query reports `COMPLETE` |
| PUE separation | `entity_links` candidate row created; entities never merge; StockX product ≠ eBay listing even with identical titles |

### 7.6 Decisions needing your input

1. **Seller usernames**: keep `seller.username` in observations/raw payloads
   (public market data; needed for seller-level demand analysis) — the
   live-shadow runbook currently avoids persisting seller data. Default: keep
   username, drop `seller.userId` unless you say otherwise.
2. **Collector request profile**: default to
   `filter=buyingOptions:{AUCTION|FIXED_PRICE}` + `fieldgroups=EXTENDED`
   (captures auctions + short descriptions; strictly more data, different
   result set than today's scan) vs preserving the exact current query.
   Default: enable both.
3. **`getItem` budget**: detail-fetch the newest N per run (default 150) —
   trades quota for the only quantity-sold signal available. Confirm the
   default, and whether detail fetches should prioritise newly-seen listings.
4. **Retention**: raw payloads 90 days then GC; curated observations
   indefinite. OK?
5. **Access applications**: worth submitting (external, non-code): eBay App
   Check for `watchCount`; Marketplace Insights application (likely refusal,
   documented as not open). Recommend deferring; design assumes neither.
6. **StockX variants fetch**: +1 call per product for true variant identity —
   enable by default given the 25k/day headroom?

### 7.7 What the available data cannot support

- No confirmed sale prices, sale dates, or sold volumes from either provider →
  "will it sell, at what price" can only be estimated from *ask-side* signals
  (price levels/changes, bids, `estimatedSoldQuantity` deltas, stock status,
  manual imports). Achieved-price ground truth requires access we don't have.
- `estimatedSoldQuantity` is an estimate, lumpy, and mostly informative for
  multi-quantity listings.
- StockX gives no time-to-sell, seller, condition, or listing-age data.
- Sampling is capped (10k eBay offset wall, `max_results`, fixed marketplaces)
  — reports carry the sampling frame so this is visible rather than silent.
