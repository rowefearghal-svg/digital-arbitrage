# digital-arbitrage

> Research and engineering project exploring digital arbitrage opportunities.
> This repository currently contains the **engineering foundation only** - no
> arbitrage logic is implemented yet.

[![CI](https://github.com/rowefearghal-svg/digital-arbitrage/actions/workflows/ci.yml/badge.svg)](https://github.com/rowefearghal-svg/digital-arbitrage/actions/workflows/ci.yml)
[![status](https://img.shields.io/badge/status-bootstrapping-blue)](docs/ROADMAP.md)

## Overview

`digital-arbitrage` is a long-lived Python project. This initial commit
establishes a clean, professional structure so that future development has a
solid base: packaging, tests, configuration, documentation, and a backlog.

_A concise product description will be added as scope firms up (see
[`docs/VISION.md`](docs/VISION.md))._

## Modules

- **`product_scanner`** - searches marketplaces through a common provider
  interface and returns unified `Listing` objects (currently mocked providers:
  eBay, Facebook Marketplace, Adverts.ie, DoneDeal).
- **`normalization`** - converts raw `Listing` objects into a consistent
  internal `NormalizedListing` via a configurable, provider-agnostic pipeline
  (unicode + text/whitespace/title cleanup, currency/condition/location
  normalization). No pricing, FX, or AI.
- **`classification`** - deterministic, **title-only** classifier that labels
  each listing `COMPLETE_PRODUCT / ACCESSORY / PART / UNKNOWN / REJECTED` with a
  0-100 `match_confidence` and a human-readable reason, so cables, adapters,
  spare fans, and unrelated keyword matches are told apart from the real
  product. Driven by a marketplace-independent `SearchProfile`
  (required / excluded / accessory / part terms); matching is case/spacing/
  hyphen-insensitive. Additive: it annotates `NormalizedListing.classification`
  and removes nothing. No images, LLMs, or external services (ADR-022).
- **`product_matching`** - deterministic engine estimating whether two
  `NormalizedListing`s are the same product, via token similarity + brand/model
  heuristics with configurable thresholds. Returns an explained `MatchResult`
  (`score`, `decision`, `reasons`, matched/unmatched tokens). No AI or pricing.
- **`deduplication`** - groups duplicate/near-duplicate listings across
  providers (reusing `product_matching`), selecting one canonical listing per
  group and a deterministic fingerprint. Lossless (every input preserved) and
  toggleable via config. No pricing, scraping, or AI.
- **`market_pricing`** - estimates the market price of a product from comparable
  listings using deterministic, swappable strategies (median, trimmed mean,
  weighted average) with IQR outlier removal. Returns a `MarketPrice`
  (estimate, confidence, comparable count, min/max/median/mean). No AI/ML.
- **`opportunity`** - turns an asking price + `MarketPrice` into a scored
  arbitrage `Opportunity`: an itemized `CostBreakdown` (marketplace/payment/
  shipping/packaging/buffer/tax), a `ProfitEstimate` (gross/net profit, ROI %,
  margin %), and a `STRONG_BUY / BUY / WATCH / REJECT` recommendation with
  reasons. Conservative by default, configurable. No scraping, AI, or APIs.
- **`opportunity.scoring`** - a configurable `RecommendationScorer` that blends
  ROI, net profit, confidence, and risk into a single deterministic **0-100
  recommendation score** for ranking opportunities. All weights and reference
  points live in one `ScoringConfig`. No AI/ML (see below).
- **`pipeline`** - end-to-end orchestrator wiring every stage into
  `ArbitragePipeline.analyze(query)`, returning a `PipelineResult` of
  `PipelineItemResult`s ranked by recommendation, then ROI, then confidence
  (each item also carries its 0-100 `score`). Ships the `arb` CLI.
  Deterministic; mock providers only.
- **`persistence`** - a standard-library `sqlite3` `ResultStore` that saves each
  `PipelineResult` as a run plus its ranked opportunity snapshots, and reads them
  back as `StoredRun` / `StoredOpportunity`. Powers `arb scan --save`,
  `arb history`, and `arb show`. No external dependencies (ADR-013).
- **`comparison`** - `compare_runs(...)` diffs two saved runs into a
  `RunComparison`, matching opportunities by a stable identity key (provider +
  normalized title) and categorising each as **new / disappeared / unchanged /
  improved / worsened** from recommendation score, ROI, net profit, confidence,
  and risk. Powers `arb compare`. Deterministic; standard library only
  (ADR-014).
- **`providers.live`** - a production-quality **framework** for onboarding real
  marketplaces (no scraping yet). Provides a `LiveProvider` base (a strict
  superset of the mock `Provider`) plus reusable infrastructure: an `HttpClient`
  over a swappable `Transport` (stdlib `urllib`), a `RetryPolicy` with
  exponential backoff + jitter, a `TokenBucketRateLimiter`, a typed
  `ProviderError` hierarchy, declarative `ProviderCapabilities`, response
  validation helpers, generic `paginate`, and structured logging. Pluggable
  `AuthProvider` strategies (none / static bearer / OAuth client-credentials)
  and a config-aware factory (`create_live_provider`) support authenticated
  providers. Standard library only; existing mock providers are untouched
  (ADR-015, ADR-017).

Pipeline order: **Scanner -> Normalization -> Classification -> Product Matching
-> Deduplication -> Market Pricing -> Opportunity.** Classification is currently
annotate-only; it does not yet influence deduplication, pricing, or scoring.

```python
from digital_arbitrage.pipeline import ArbitragePipeline

result = ArbitragePipeline().analyze("rtx 4090")
for item in result.items:
    print(item.recommendation, item.title, item.roi_percentage, item.confidence_score)
```

### CLI

The `arb` command runs the whole pipeline (installed via `pip install -e .`):

```bash
arb scan "rtx 4090"                 # fixed-width table (default)
arb scan "rtx 4090" --format json   # table | json | csv | markdown
arb scan "rtx 4090" --limit 5       # cap results per provider
arb scan "rtx 4090" --config configs/default.toml   # load stage config from TOML
arb scan "rtx 4090" --provider ebay_browse          # scan one provider (repeatable; live eBay needs creds)
```

By default `arb scan` queries the mock providers only. `--provider NAME`
(repeatable) overrides the configured provider list for a single scan; passing a
live provider such as `ebay_browse` runs a real API search - see
[Local live eBay scanning](#local-live-ebay-scanning) below.

**Filter, sort, and export.** Filters combine with AND; `--sort` reorders the
displayed rows; four output formats are supported:

```bash
arb scan "rtx 4090" --actionable-only              # only BUY / STRONG_BUY
arb scan "rtx 4090" --min-recommendation watch     # watch | buy | strong_buy | reject
arb scan "rtx 4090" --min-roi 15 --min-net-profit 50
arb scan "rtx 4090" --sort score --format csv      # sort: recommendation | score | roi | net_profit | confidence
arb scan "rtx 4090" --format markdown > report.md
arb scan "rtx 4090" --debug                        # full traceback on error (clean message otherwise)
```

Every opportunity carries a **0-100 recommendation score** (the `SCORE` column /
`recommendation_score` field), a single ranking number that blends ROI, net
profit, confidence, and risk - use `--sort score` for the most holistic order.

**Save and review history.** `--save` persists the full scan (all items, before
display filters) to a SQLite database; `arb history` lists past runs and
`arb show <run_id>` replays a run's opportunities. The database defaults to
`~/.digital_arbitrage/history.db`; override it with `--db`:

```bash
arb scan "rtx 4090" --save                     # store this run
arb scan "rtx 4090" --save --db runs.db        # ... in a specific database
arb history                                     # list runs (table | json)
arb show 3                                       # view run #3 (table | json | csv)
```

Persistence uses only the standard-library `sqlite3` module - no ORM, no new
dependencies. The schema is two small, additive tables (`runs`,
`opportunities`); see [ADR-013](docs/DECISIONS.md).

**Compare two runs.** `arb compare <old_run_id> <new_run_id>` diffs a query over
time. Opportunities are matched by identity key (**provider + normalized title**)
and each is categorised **new / disappeared / unchanged / improved / worsened**;
metric columns show the new-minus-old delta:

```bash
arb compare 1 2                       # table (default)
arb compare 1 2 --format markdown     # table | json | csv | markdown
```

A pair is *improved* / *worsened* by the first metric that changed, in priority
order: recommendation score -> ROI -> net profit -> confidence -> risk (risk
inverted, since lower is better); if none changed it is *unchanged*. Ordering is
deterministic (new, improved, worsened, unchanged, disappeared, then by key). See
[ADR-014](docs/DECISIONS.md) for the identity-key assumptions.

Every stage is configurable from one TOML file (`--config`), with one table per
stage; each table and key is optional and falls back to its code default.
Unknown tables/keys or wrong types fail at load with a clear, section-prefixed
error. `--limit` overrides `[pipeline].scan_limit`. See
[`configs/default.toml`](configs/default.toml) for the full, documented example:

```toml
[pipeline]
scan_limit = 10

[scanner]
providers = ["ebay", "donedeal"]

[market_pricing]
strategy = "median"      # median | trimmed_mean | weighted_average

[opportunity]
buy_roi = 0.15           # thresholds and the full fee/cost model
```

```python
from digital_arbitrage.pipeline import ArbitragePipeline, load_pipeline_config

config = load_pipeline_config("configs/default.toml")
result = ArbitragePipeline(config).analyze("rtx 4090")
```

### Recommendation scoring

The `Recommendation` (STRONG_BUY / BUY / WATCH / REJECT) is a *categorical*
verdict; the **recommendation score** is a *continuous* 0-100 quality number for
ranking. `RecommendationScorer` normalizes four signals to `[0, 1]` and combines
them with weights from a single `ScoringConfig`:

- **ROI** - `roi_percentage / roi_reference` (default reference 30%).
- **Net profit** - `net_profit / net_profit_reference` (default 200).
- **Confidence** - the market-price confidence, used directly.
- **Risk** (a *penalty*) - derived from the market price: wide price spread
  (`(max - min) / median`) and thin comparable coverage both raise it; an
  unpriced product is maximally risky.

```text
weighted = w_roi*roi + w_profit*profit + w_conf*confidence - w_risk*risk
score    = 100 * (weighted + w_risk) / (w_roi + w_profit + w_conf + w_risk)
```

The shift/normalize maps the worst case (no upside, full risk) to 0 and the best
case (full upside, no risk) to 100. It is fully deterministic - identical inputs
always yield an identical score - with no AI/ML. Tune it via `[scoring]` in a
config file or `ScoringConfig` in code:

```python
from digital_arbitrage.opportunity import RecommendationScorer, ScoringConfig

scorer = RecommendationScorer(ScoringConfig(roi_weight=0.5, risk_weight=0.2))
breakdown = scorer.score(opportunity, market_price)
print(breakdown.score, breakdown.risk_signal)
```

### Live provider framework

`digital_arbitrage.providers.live` is the infrastructure for *real* marketplace
integrations, and now ships the first concrete one: the read-only
[eBay Browse provider](#ebay-browse-provider). Standard library only, no scraping,
no new dependencies, and **no live API call in automated tests**. A new provider
is added by subclassing `LiveProvider` and implementing two small hooks:

```python
from digital_arbitrage.providers.live import (
    HttpClient, HttpRequest, HttpResponse, LiveProvider, LiveProviderConfig,
    Page, ProviderCapabilities, ensure_mapping, parse_json, require, resolve_url,
)
from digital_arbitrage.product_scanner.models import Listing


class ExampleProvider(LiveProvider):
    name = "example"
    capabilities = ProviderCapabilities(supports_pagination=True, max_page_size=50)

    def build_request(self, query, *, page, page_size):
        return HttpRequest(
            method="GET",
            url=resolve_url(self.config.base_url, "/search"),
            params={"q": query, "page": str(page), "size": str(page_size)},
        )

    def parse_response(self, response, *, query):
        payload = ensure_mapping(parse_json(response, provider=self.name))
        items = tuple(
            Listing(
                listing_id=require(it, "id", str),
                title=require(it, "title", str),
                provider=self.name,
                url=require(it, "url", str),
                price=float(it["price"]),
                currency=self.config.default_currency,
            )
            for it in payload["items"]  # validated in real code
        )
        return Page(items=items, has_more=bool(payload.get("has_more")))


provider = ExampleProvider(LiveProviderConfig(base_url="https://api.example.com"))
listings = provider.search("rtx 4090", limit=25)  # same Provider contract as mocks
```

The base class handles the production concerns so providers stay declarative:

- **HTTP** - `HttpClient` composes a swappable `Transport` (the stdlib
  `UrllibTransport`; fakes are trivial in tests) with default headers,
  auth, timeouts, retries, and rate limiting.
- **Retries** - `RetryPolicy` retries only transient failures (timeouts,
  connection errors, and configurable 5xx/429 statuses) with **exponential
  backoff + equal jitter**, honouring a `Retry-After` hint when present.
- **Rate limiting** - `TokenBucketRateLimiter` smooths outbound request rate to
  a provider's quota (sustained rate + burst); the clock and sleep are
  injectable for deterministic tests.
- **Pagination** - `paginate` drives page fetching up to `max_results`, stopping
  when a `Page` reports no more results (used only if the provider's
  `capabilities` advertise pagination).
- **Capabilities** - `ProviderCapabilities` declares what a provider supports
  (pagination, price/condition filters, sorting, api-key requirement, page/result
  caps, currencies) so the framework adapts without provider-specific branching.
- **Errors** - a typed `ProviderError` hierarchy
  (`ProviderConfigError`, `ProviderTimeoutError`, `ProviderConnectionError`,
  `ProviderHTTPError`, `ProviderRateLimitError`, `ProviderResponseError`) lets
  callers react precisely; each carries the provider name for logs.
- **Validation** - small helpers (`parse_json`, `ensure_mapping/list`, `require`,
  `require_number`, `optional`) turn untrusted JSON into typed values, failing
  with a context-prefixed `ProviderResponseError`.
- **Logging** - structured `key=value` fields under the
  `digital_arbitrage.providers` namespace.

`LiveProvider` subclasses `product_scanner.providers.Provider`, so live providers
are drop-in compatible with the existing scanner and registry. See ADR-015.

#### Authentication

Auth is pluggable via an `AuthProvider`, which supplies the `Authorization`
header per request. Three strategies ship (ADR-017):

- **`NoAuthProvider`** - public endpoints (no header).
- **`StaticBearerTokenAuthProvider`** - a fixed, pre-issued token.
- **`OAuthClientCredentialsAuthProvider`** - mints an *application* token via the
  OAuth 2.0 client-credentials grant, then **caches and refreshes it safely
  before expiry** (as required by e.g. the eBay Browse API). Credentials are
  never logged; token minting failures raise a typed `ProviderAuthError`.

```python
from digital_arbitrage.providers.live import (
    LiveProviderConfig, OAuthClientCredentialsAuthProvider, create_live_provider,
)

auth = OAuthClientCredentialsAuthProvider(
    client_id=os.environ["EBAY_CLIENT_ID"],       # from a secret, never the repo
    client_secret=os.environ["EBAY_CLIENT_SECRET"],
    token_url="https://api.ebay.com/identity/v1/oauth2/token",
    scope="https://api.ebay.com/oauth/api_scope",
)
config = LiveProviderConfig(base_url="https://api.ebay.com")
provider = create_live_provider("ebay_browse", config, auth=auth)  # once registered
```

When no `AuthProvider` is given, the client falls back to a static
`config.api_key` as a `Bearer` token (backward compatible).

#### eBay Browse provider

`EbayBrowseProvider` (`"ebay_browse"`) is the first real, **read-only** provider
(ADR-018). It calls the officially supported eBay Browse API
(`GET /buy/browse/v1/item_summary/search`) with an application OAuth token and
maps each item summary onto the shared `Listing` model. The core fields
(`price`, `currency`, `condition`, `location`, ...) populate `Listing` directly;
every other useful Browse field is preserved in the flat `Listing.extra`
(`dict[str, str]`) metadata map so it is available for market analysis and future
ML without touching the core model or the opportunity calculations (ADR-021).
Credentials come only from the `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET`
environment variables and are never committed or logged.

Fields mapped into `Listing.extra` when present (only non-empty values are added,
so listings stay lean and the mapping is backwards compatible):

| Group | `extra` keys |
| --- | --- |
| Images | `image_url`, `thumbnail_image_urls`, `additional_image_urls` |
| Buying | `buying_options`, `current_bid_price`, `current_bid_currency`, `bid_count` |
| Condition | `condition_id`, `condition_text` |
| Seller | `seller`, `seller_feedback_percentage`, `seller_feedback_score`, `seller_account_type` |
| Shipping | `shipping_cost`, `shipping_currency`, `shipping_cost_type`, `shipping_type`, `shipping_carrier`, `shipping_min_delivery`, `shipping_max_delivery`, `shipping_guaranteed_delivery` |
| Location | `item_city`, `item_state`, `item_postal_code`, `item_country` |
| Category | `category_id`, `category_name`, `leaf_category_ids` |
| Timing | `item_creation_date`, `item_end_date` |
| Pricing | `original_price`, `original_price_currency`, `discount_percentage`, `discount_amount`, `discount_amount_currency`, `price_treatment`, `unit_price`, `unit_price_currency`, `unit_pricing_measure` |
| Popularity | `watch_count` |
| Identifiers / misc | `epid`, `legacy_item_id`, `item_href`, `item_affiliate_web_url`, `item_group_type`, `subtitle`, `short_description`, `listing_marketplace_id`, `qualified_programs`, `adult_only`, `available_coupons`, `top_rated_buying_experience`, `priority_listing` |

Numbers are stringified (integral floats lose the trailing `.0`), booleans become
`"true"`/`"false"`, lists are comma-joined, and eBay amount objects are split into
`*_price`/`*_currency` (or `*_cost`/`*_currency`) pairs. Watch count is only
present on marketplaces/queries where eBay returns it.

```python
import os
from digital_arbitrage.providers.live import (
    EbayBrowseConfig, build_ebay_browse_provider_from_env,
)

config = EbayBrowseConfig(base_url="https://api.ebay.com", marketplace_id="EBAY_IE")
provider = build_ebay_browse_provider_from_env(config)  # reads EBAY_CLIENT_ID/SECRET
listings = provider.search("rtx 4090", limit=50)  # same Provider contract as mocks
```

See `configs/ebay_browse.example.toml` for a documented, secret-free config
(loadable via `EbayBrowseConfig.from_dict`). The provider registers itself in the
live registry, so it can also be built by name:

```python
from digital_arbitrage.providers.live import create_live_provider
provider = create_live_provider("ebay_browse", config, auth=auth)
```

The entire request/response/pagination/OAuth flow is unit-tested against
sanitised JSON fixtures through a fake `Transport` - no network, no secrets in
CI. There is no live smoke test in the automated suite by design.

Because a `LiveProvider` needs a config (and usually auth), it cannot be built by
the mock registry's zero-arg `create_provider`. A **separate, config-aware**
registry (`LIVE_PROVIDER_REGISTRY` + `register_live_provider`) and factory
(`create_live_provider(name, config, *, auth=...)`, or
`LiveProvider.create(config, *, auth=...)`) handle this. The mock registry is
unchanged; the live registry holds the `ebay_browse` provider (ADR-018).

#### Local live eBay scanning

`arb scan` can run a real eBay Browse search locally against your own eBay
developer credentials, driving the **entire pipeline** (Scanner -> Normalization
-> Matching -> Deduplication -> Market Pricing -> Opportunity) on live listings
(ADR-019/ADR-020). It stays **opt-in**: the default scan is mock-only, and a live
provider runs only when you select it. No secrets are ever committed and CI makes
no live calls.

**1. Get eBay application credentials.** Create an application in the
[eBay Developer Program](https://developer.ebay.com/) and copy its OAuth
*client ID* and *client secret* (App ID / Cert ID). The `ebay_browse` provider
uses the OAuth **client-credentials** grant, so no user login is required.

**2. Export them as environment variables** (never put secrets in a file):

```bash
export EBAY_CLIENT_ID="your-app-client-id"
export EBAY_CLIENT_SECRET="your-app-client-secret"
```

**3. Run a live scan** with the ready-to-use sample config
[`configs/ebay_browse.toml`](configs/ebay_browse.toml):

```bash
arb scan "rtx 4090" --provider ebay_browse --config configs/ebay_browse.toml
```

The sample already lists `ebay_browse` in `[scanner].providers`, so `--config`
alone runs the same live scan; `--provider` selects it explicitly and can be
repeated to mix in mock providers:

```bash
arb scan "rtx 4090" --config configs/ebay_browse.toml          # config selects ebay_browse
arb scan "rtx 4090" --provider ebay_browse                     # no config: built-in defaults
arb scan "rtx 4090" --provider ebay_browse --provider ebay     # live + a mock, together
```

If the credentials are missing (or invalid) the scan fails fast with a clear
`EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set` error and a non-zero exit
code - nothing partial is written.

**Enable/disable from config instead of the CLI.** Add `ebay_browse` to
`[scanner].providers` and configure it under a `[providers.ebay_browse]` table in
your pipeline config (see `configs/ebay_browse.example.toml` for every key). The
`enabled` flag toggles the live provider without editing the provider list:

```toml
[scanner]
providers = ["ebay", "ebay_browse"]

[providers.ebay_browse]
enabled = true                 # set false to keep this config but skip the provider
marketplace_id = "EBAY_IE"     # EBAY_IE, EBAY_GB, EBAY_US, EBAY_DE, ...
page_size = 100
max_results = 200
```

```bash
arb scan "rtx 4090" --config configs/my-live.toml
```

Everything but the credentials lives in config; the credentials come only from
the environment. Use the eBay **sandbox** hosts (`base_url` /
`oauth_token_url`) while developing to avoid touching production quota.

## Repository Layout

```
digital-arbitrage/
|-- src/digital_arbitrage/   # importable Python package (application code)
|-- tests/                   # test suite (pytest)
|-- configs/                 # non-secret configuration + examples
|-- scripts/                 # helper / operational scripts
|-- docs/                    # project documentation
|   |-- VISION.md            # why this project exists, long-term direction
|   |-- ROADMAP.md           # planned milestones
|   `-- DECISIONS.md         # architecture decision log
|-- BACKLOG.md               # initial issue list / work items
|-- pyproject.toml           # project metadata + tooling config
|-- requirements.txt         # pinned developer tooling
|-- .gitignore
|-- .gitattributes
`-- LICENSE                  # placeholder - license TBD
```

## Getting Started

> Requires Python 3.12+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# macOS/Linux:  source .venv/bin/activate

# 2. Install the package (editable) plus dev tooling
pip install -r requirements.txt

# 3. Copy the example config and fill in values
#    (Linux/macOS shown; on Windows use Copy-Item)
cp configs/config.example.toml configs/config.toml

# 4. Run the checks
ruff check .
pytest
```

## Development

### Local checks

Run these before pushing - they mirror exactly what CI runs:

```bash
ruff check .            # lint
ruff format --check .   # formatting (use `ruff format .` to fix)
mypy src                # type check
pytest -q               # tests
```

### Continuous integration

Every `push` and `pull_request` is validated by GitHub Actions
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) on **Python 3.12**.
The pipeline fails if any of the four checks above fail, so a PR must be green
before it is merged.

### Workflow

1. Branch off `main` (`feature/*`, `fix/*`, `infrastructure/*`, `docs/*`).
2. Make focused commits; run the local checks above.
3. Open a pull request - CI runs automatically.
4. Merge only when CI is green (squash-merge, linear history, protected `main`).

Trunk-based: short-lived branches, a PR for every change, no direct pushes to
`main`. See the workspace standards in the `ai-infrastructure` repository.

## Configuration

Runtime configuration lives in `configs/`. Never commit secrets - copy
`config.example.toml` to `config.toml` (gitignored) and keep secrets in a local
`.env` (see `.env` handling in `.gitignore`).

### Provider credentials (`.env`)

External-provider credentials are read **only from the environment** - never
from a config file, the repository, or CI. To set them up locally, copy the
tracked template to a local, gitignored `.env` and fill in real values:

```bash
cp .env.example .env
# edit .env, then load it into your shell before running a live scan:
set -a; source .env; set +a
```

Supported credential variables:

| Provider     | Environment variables                                             |
| ------------ | ----------------------------------------------------------------- |
| eBay Browse  | `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`                            |
| StockX       | `STOCKX_API_KEY`, `STOCKX_CLIENT_ID`, `STOCKX_CLIENT_SECRET`      |

The StockX credentials are loaded via `StockXCredentials.from_env()`
(`digital_arbitrage.providers.live`), mirroring the eBay pattern: all three
values are required and a missing one fails fast with a clear
`... must be set` error. Secrets are never logged (`repr` is redacted).

`.env` and `*.key` / `*.pem` are already gitignored; **never commit real
credentials**.

## Data & Models

Datasets, models, and checkpoints are **not** stored in Git. Keep them in a
local `data/` directory (gitignored) or external object storage. See the
`ai-infrastructure` GitHub architecture notes.

## Documentation

- [`docs/VISION.md`](docs/VISION.md) - long-term direction and principles.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - planned milestones.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) - architecture decision log (ADR).
- [`BACKLOG.md`](BACKLOG.md) - initial work items.

## License

License is **TBD** - see [`LICENSE`](LICENSE). Do not assume an open-source
license until one is chosen.

---

_Last updated: Sprint 9 (CI). This README will grow as the project takes shape._
