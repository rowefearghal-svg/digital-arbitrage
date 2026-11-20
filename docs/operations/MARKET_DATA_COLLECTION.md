# Market-data collection runbook

Design: `docs/MARKET_DATA_COLLECTION_DESIGN.md` · Decision: ADR-031.

`arb collect` runs a bounded, read-only collection over a product-family
manifest into `market_data.db`. It is a separate command from `arb scan` —
scoring, PUE and shadow behaviour are unchanged. There is no scheduler; runs
are manual (suggested cadence every ~6h for history building).

## Quick start

```bash
# credentials from the environment (.env): EBAY_CLIENT_ID/SECRET,
# STOCKX_API_KEY/CLIENT_ID/CLIENT_SECRET + cached refresh token
arb collect --manifest configs/collection.gpu.json \
    --db var/market_data/market_data.db

arb collect-report collect-YYYYMMDDTHHMMSSZ-xxxxxxxx \
    --db var/market_data/market_data.db -f markdown
```

Keep databases and reports under `var/market_data/` (gitignored).

## Options

| Flag | Default | Meaning |
|---|---|---|
| `--manifest` | `[collection].manifest` | JSON manifest: `queries[]` with `query_id`, `search_text`, `providers`, `max_results_per_provider`, `detail_top_n` |
| `--config` | – | TOML with a `[collection]` table |
| `--provider NAME` | all in manifest | restrict providers (repeatable) |
| `--db` | `~/.digital_arbitrage/market_data.db` | store location |
| `--detail-budget N` | 150 | max eBay `getItem` calls this run |
| `--no-detail` | off | skip eBay detail enrichment |
| `--stockx-variants` | off | +1 variants call per StockX product |
| `--ebay-marketplace` | EBAY_IE | eBay marketplace header |

`[collection]` TOML keys: `page_size_ebay` (200), `page_size_stockx` (50),
`max_pages` (10), `detail_fetch_top_n` (150), `fetch_stockx_variants` (false),
`raw_retention_days` (90), `stale_after_hours` (48),
`keep_seller_usernames` (false — pseudonymous `sel_` keys by default),
`ebay_search_filter` (`buyingOptions:{AUCTION|FIXED_PRICE}`),
`ebay_search_fieldgroups` (`EXTENDED`), `ebay_search_sort`,
`ebay_marketplace_id`, `request_timeout`, plus
`[collection.daily_request_budget]` and `[collection.rate_limit_per_second]`
provider maps.

## What a run records

- `collection_runs` — manifest id/hash, status, counters.
- `collection_tasks` — one row per request (search page, `getItem`,
  market-data, variants): filters, page/offset, reported total, has_more,
  attempts, errors. Pagination coverage is honest: capped queries report
  `SAMPLE`, never `COMPLETE`.
- `provider_entities` — deduped by (provider, entity_type, native id);
  eBay listings vs item groups vs StockX products vs variants stay distinct.
- `observations` — append-only; identical content re-observed in a later run
  is a new row; task retries dedupe on content hash.
- `raw_payloads`/`payload_captures` — redacted response bodies deduped by
  sha256; request headers are never stored and bodies are content-scrubbed
  (JWT/bearer patterns, `access_token`/`client_secret` keys, seller
  usernames, affiliate tracking URLs).
- `request_usage` — per-day request counts driving the shared daily budget
  (retries count too). Note: requests made by other commands (`arb scan`)
  are not metered here.

## Evidence rules enforced

- `disappeared` = absent from a *complete* re-run; never a sale.
- `ended` only from provider signals (OUT_OF_STOCK, ended item).
- `confirmed_sale` only from a sale-attesting source — none available yet.
- `quantity_sold_estimate` is eBay's `estimatedSoldQuantity`: a provider
  estimate; decreases/resets are flagged, zero change is not "no sales".
- Missing values are NULL, never zero. Asks/bids/guidance are never sold
  prices (`price_kind`).

## Rate/budget guidance

eBay: ~5,000 calls/day documented; a search page costs 1 call/200 items,
each detail 1 call — `--detail-budget` plus `daily_request_budget` keep this
bounded. StockX: ~25,000/day + ~1 req/s; market-data is 1 call per product
(the dominant cost — ~50 calls per 50-product query), variants +1 more.
