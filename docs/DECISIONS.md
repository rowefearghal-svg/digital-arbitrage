# Architecture Decision Log

> A lightweight log of significant decisions (ADR style). Add a new entry
> whenever a choice is made that would be expensive or confusing to reverse.
> Keep entries short. Never delete an entry - supersede it with a newer one.

## Format

```
### ADR-NNN: <title>
- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Superseded by ADR-XXX
- **Context:** why a decision was needed
- **Decision:** what was decided
- **Consequences:** trade-offs / follow-ups
```

---

### ADR-001: Python packaging with a `src/` layout

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Need a standard, import-safe project structure for long-term
  maintainability.
- **Decision:** Use a `src/digital_arbitrage/` package with `pyproject.toml`
  (setuptools build backend); manage the dev environment via `requirements.txt`
  installing `-e .[dev]`.
- **Consequences:** Avoids accidental imports from the working directory;
  standard tooling (ruff, black, mypy, pytest) configured in `pyproject.toml`.

### ADR-002: Trunk-based branching with protected `main`

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Solo founder working with Devin; need a simple, safe workflow.
- **Decision:** Short-lived branches off `main`, a PR for every change,
  squash-merge, linear history, protected `main`. No direct pushes.
- **Consequences:** Every change is reviewable; history stays clean. CI will be
  required to pass before merge once it exists.

### ADR-003: No arbitrage logic during bootstrap

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** The first sprint is explicitly foundation-only.
- **Decision:** Ship structure, packaging, tests, docs, and backlog with no
  domain/trading logic.
- **Consequences:** A clean base to build on; domain logic arrives in later,
  separately-reviewed PRs.

### ADR-004: Normalization as a configurable step pipeline

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Raw listings from different providers vary in casing, unicode,
  punctuation, currency notation, condition wording, and location format. The
  rest of the system needs a single consistent shape.
- **Decision:** Add a `normalization` package that turns a `Listing` into a
  `NormalizedListing` via an ordered pipeline of independent `NormalizationStep`
  objects (unicode -> text cleaning -> whitespace -> title cleanup -> currency
  -> condition -> location). Steps are configurable/replaceable; domain mappings
  (currency/condition/location) are small extensible registries. Normalization
  keeps a reference to the source listing and does no pricing/FX/AI.
- **Consequences:** Behaviour is tunable via `NormalizationConfig` or a custom
  pipeline without touching the `Normalizer`; provider-agnostic; easy to unit
  test each concern in isolation.

### ADR-005: Deterministic product matching before AI matching

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Deciding whether two listings are the same product is central to
  arbitrage. An LLM/embedding matcher is tempting, but the project is early and
  needs a reliable, debuggable baseline first.
- **Decision:** Start with a deterministic `product_matching` engine: token
  similarity (Jaccard blended with the overlap coefficient) plus brand/model
  heuristics and configurable thresholds. Every decision returns explicit
  `reasons` and matched/unmatched tokens. No AI/LLMs, no pricing, no dedup yet.
- **Rationale:**
  - *Explainable & testable* - outcomes are pure functions of the inputs, so
    behaviour is unit-testable and auditable (no opaque model calls).
  - *Deterministic & offline* - no network, no API keys, no cost, no flakiness;
    CI stays fast and stable.
  - *A measurable baseline* - future AI/embedding matching can be evaluated
    against this, and can slot in behind the same `match()` API.
  - *Cheap to tune* - thresholds/weights live in `MatchConfig`; brands are an
    extensible set.
- **Consequences:** Matching quality is bounded by heuristics (e.g. synonyms,
  spelling variants, missing brand tokens). Accepted for now; an AI matcher is a
  later, separately-reviewed enhancement layered on the same interface.

### ADR-006: Lossless, deterministic cross-provider deduplication

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** The same product is listed on multiple marketplaces; downstream
  logic needs a de-duplicated view without losing any source listing.
- **Decision:** Add a `deduplication` stage (last in the pipeline: Scanner ->
  Normalization -> Product Matching -> Deduplication). `Deduplicator` clusters
  `NormalizedListing`s by reusing `ProductMatcher` (SAME_PRODUCT, optionally
  POSSIBLE_MATCH), producing `DuplicateGroup`s each with one `canonical` listing
  and a deterministic fingerprint. It is **lossless** (every input preserved in
  exactly one group), **deterministic** (input sorted by a stable key; a frozen
  invariant asserts no listings are lost), and **toggleable** (`enabled=False`
  makes it a no-op of singleton groups).
- **Rationale:**
  - *Reuse over reinvention* - grouping is driven by the existing, tested,
    explainable matcher rather than a second similarity implementation.
  - *Lossless by construction* - `DeduplicationResult` refuses to be built if the
    grouped count differs from the input count, so a bug cannot silently drop
    listings. Canonicals are a view, not a destructive filter.
  - *Deterministic* - stable ordering + content-derived fingerprints make output
    reproducible across runs, machines, and input orderings.
- **Consequences:** Greedy clustering compares each listing against a cluster
  representative, so it favours simplicity over perfect transitive grouping;
  adequate for current volumes. Canonical selection prefers the richest title
  (and an optional provider priority); price-aware selection is deferred to the
  future pricing layer.

### ADR-007: Deterministic statistical market pricing (no ML)

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** After deduplication we need a single market-price estimate per
  product from its comparable listings. A regression/ML valuation model is
  possible but premature and hard to trust or debug this early.
- **Decision:** Add a `market_pricing` stage (Scanner -> Normalization ->
  Product Matching -> Deduplication -> Market Pricing). `MarketPriceEstimator`
  turns comparables (from a `DuplicateGroup`, normalized listings, or explicit
  `ComparableListing`s) into a `MarketPrice` using a pluggable `PricingStrategy`
  (median / trimmed mean / weighted average), with optional IQR outlier removal
  and a deterministic confidence score derived from comparable count and price
  dispersion. Strategies are swappable via name or instance in
  `MarketPricingConfig`.
- **Rationale:**
  - *Explainable & deterministic* - the estimate is a documented statistic over
    the inputs; the result carries min/max/median/mean, outlier count, and
    confidence so it is fully auditable.
  - *Robust by default* - median plus IQR trimming resist scam/typo prices
    without any training data.
  - *Replaceable* - the `PricingStrategy` seam lets an ML valuation slot in
    later behind the same `estimate()` API and be benchmarked against this
    baseline.
- **Consequences:** Cross-currency comparables are reduced to the dominant (or a
  configured) currency rather than converted - FX conversion and profit
  calculations remain out of scope. Confidence is a heuristic, not a calibrated
  probability.

### ADR-008: Deterministic, conservative profit/opportunity scoring

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** The pipeline can now estimate a product's market price; the next
  step is to decide whether a *specific* listing is a buy. This needs an
  explicit, auditable cost and profit model - not a black box.
- **Decision:** Add an `opportunity` stage (Scanner -> ... -> Market Pricing ->
  Opportunity). `OpportunityAnalyzer.analyze(listing, market_price)` returns an
  `Opportunity` containing a `ProfitEstimate` (gross/net profit, ROI %,
  margin %) built from an itemized `CostBreakdown` (marketplace fee, payment fee,
  shipping, packaging, risk buffer, VAT/tax placeholder) and a `Recommendation`
  in {STRONG_BUY, BUY, WATCH, REJECT}. Recommendation is a pure function of ROI
  thresholds gated by the market-price confidence; every result carries the
  `reasons` behind it. All costs/thresholds live in `OpportunityConfig`.
- **Rationale:**
  - *Conservative by default* - default fees, a risk buffer, and confidence
    gating bias toward REJECT/WATCH so marginal deals are not over-sold. A
    positive recommendation must clear real, itemized costs.
  - *Explainable & deterministic* - the decision is arithmetic over declared
    inputs; `reasons` make each recommendation auditable, and identical inputs
    always yield identical output.
  - *No FX / no external calls* - listings whose currency differs from the market
    estimate are rejected rather than silently converted, consistent with
    ADR-007. VAT is a configurable placeholder (fraction of gross profit),
    defaulting off.
- **Consequences:** ROI is computed against the asking price (capital deployed);
  the tax model is a simplified margin-scheme placeholder, not tax advice.
  Actual marketplace/payment schedules and multi-currency handling are future
  enhancements layered on the same `OpportunityConfig` seam.

### ADR-009: Single orchestrator + thin CLI over the module stack

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Six independent stages now exist but had to be wired by hand.
  Users and demos need one entry point, and the system needs a place for
  run-level configuration.
- **Decision:** Add a `pipeline` package. `ArbitragePipeline.analyze(query)`
  composes the stages in order (Scanner -> Normalization -> Product Matching ->
  Deduplication -> Market Pricing -> Opportunity) and returns a `PipelineResult`
  of `PipelineItemResult`s sorted by `(recommendation, ROI, confidence)`.
  `PipelineConfig` nests each stage's config so everything is tunable from one
  object. A thin `arb` CLI (`arb scan "<query>" --format table|json`) renders
  the result; it is a `[project.scripts]` console entry point.
- **Rationale:**
  - *Composition, not reimplementation* - the orchestrator only sequences and
    ranks; all logic stays in the tested stage modules. The CLI is a pure view
    over `PipelineResult`.
  - *Deterministic & offline* - built on the existing mock providers with stable
    sorting (ties broken by `listing_id`), so runs are reproducible and
    `to_dict()` output is stable for JSON snapshots.
  - *Clean error handling* - provider failures are already isolated in the
    scanner; the CLI additionally catches unexpected errors, prints to stderr,
    and returns a non-zero exit code.
- **Consequences:** Ranking currently treats unpriced/rejected items as lowest
  (ROI `-inf`); richer filtering (e.g. `--min-recommendation`), result
  persistence, and async scanning are future additions on the same seam. The
  CLI intentionally has no third-party dependencies (stdlib `argparse` + manual
  table rendering).

### ADR-010: TOML configuration files for the pipeline

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Fee models and thresholds were only settable in code. Operators
  need to tune the run (providers, strategy, cost assumptions) without editing
  Python, and to keep tuned profiles under version control.
- **Decision:** Add `load_pipeline_config(path) -> PipelineConfig` (stdlib
  `tomllib`, no new deps) plus `arb scan ... --config file.toml`. The file has
  one table per stage (`[pipeline]`, `[scanner]`, `[normalization]`,
  `[matching]`, `[deduplication]`, `[market_pricing]`, `[opportunity]`); the
  `[matching]` table nests into the deduplicator's `match_config`. A documented
  `configs/default.toml` mirrors the code defaults. `--limit` overrides
  `[pipeline].scan_limit`.
- **Rationale:**
  - *Fail loud, fail early* - a validating loader rejects unknown tables/keys,
    wrong types (including `bool`-is-not-`int`), and out-of-range values, always
    with a section-prefixed message. Dataclass `__post_init__` errors are
    re-raised with the same prefix, so one `ConfigError` type covers everything.
  - *Everything optional* - each table/key falls back to the stage default, so
    partial files are valid and only omitted stages stay `None`.
  - *No new surface area* - the loader maps onto the existing per-stage config
    dataclasses rather than introducing a parallel schema; TOML matches the
    stdlib parser and the format already used by `ScannerConfig`.
- **Consequences:** A few rich fields are intentionally not file-configurable
  yet (e.g. `condition_aliases`, custom strategy instances); they remain
  code-only until needed. The file is the source of truth for a run, but CLI
  flags still win for quick overrides.

### ADR-011: CLI ergonomics - filtering, sorting, export, and debug

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** The `arb` CLI could only dump every opportunity as a table or
  JSON. Users need to narrow results, reorder them, export to other tools, and
  see real tracebacks when debugging.
- **Decision:** Extend `arb scan` (no new command):
  - *Filters* (combine with AND, applied to `PipelineResult.items`):
    `--actionable-only`, `--min-recommendation`, `--min-roi` (a percentage,
    matching the ROI% column), `--min-net-profit`.
  - *Sorting*: `--sort {recommendation,roi,net_profit,confidence}`;
    `recommendation` keeps the pipeline's existing ranking, the others sort
    descending with a `listing_id` tie-break (`None` metrics sort last).
  - *Formats*: add `csv` (stdlib `csv`, reasons joined by `;`) and `markdown`
    (GitHub table) alongside `table`/`json`. Renderers take an explicit
    `items` sequence so filtering/sorting is decoupled from the full result;
    `table`/`json`/`markdown` also report `showing N of M`.
  - *Errors*: a single top-level handler in `main` prints a clean
    `error: <message>` by default and a full traceback with `--debug`.
- **Rationale:**
  - *View layer only* - all logic stays in the pipeline; filters/sorts operate
    on the immutable result and renderers are pure functions of
    `(result, items)`, keeping everything deterministic and easy to test.
  - *No new dependencies* - CSV and Markdown use the stdlib and manual string
    building, consistent with the existing table renderer.
  - *Centralised error handling* - moving the try/except to `main` makes
    `--debug` apply uniformly to config and runtime errors.
- **Consequences:** The `counts` and scanned/groups lines always report the full
  run; only the `showing N of M` line and the rendered rows reflect the filtered
  subset, so users still see the whole breakdown. `--min-roi` is a percentage,
  not the fraction used in config thresholds - documented to avoid confusion.

### ADR-012: Deterministic weighted recommendation scoring (pre-ML)

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** The pipeline emitted a categorical `Recommendation` plus separate
  ROI/profit/confidence figures, and ranked by `(recommendation, ROI,
  confidence)`. Comparing opportunities *within* a category (or trading off a
  high-ROI/low-confidence deal against a safe/modest one) required eyeballing
  several columns. We want one continuous, tunable, explainable quality number -
  and a clean seam for a future ML-based scorer - without adding dependencies or
  black-box behaviour.
- **Decision:** Add `opportunity.scoring` with a `RecommendationScorer` that
  produces a 0-100 `ScoreBreakdown` from four signals normalized to `[0, 1]`:
  ROI (`roi_percentage / roi_reference`), net profit
  (`net_profit / net_profit_reference`), confidence (used directly), and a risk
  *penalty* estimated from the market price (price dispersion `(max-min)/median`
  and comparable coverage; unpriced = maximal risk). The combination is
  `100 * (Sum(w_i * s_i) - w_risk*risk + w_risk) / Sum(w)`, i.e. a weighted
  average shifted so worst-case maps to 0 and best-case to 100. Every value -
  the four weights and the reference points - lives in a single `ScoringConfig`
  (also a `[scoring]` TOML table). The pipeline computes and stores `score` (and
  `risk_score`) on each `PipelineItemResult`; the CLI shows a `SCORE` column in
  every format and adds `--sort score`.
- **Rationale:**
  - *Single source of truth for weights* - all tunables are in `ScoringConfig`;
    nothing is hard-coded across the codebase, so re-weighting is one edit.
  - *Deterministic & explainable* - pure arithmetic over declared inputs; the
    `ScoreBreakdown` exposes each normalized signal, so a score is auditable and
    reproducible. No AI/ML, no external state (consistent with ADR-005/007/008).
  - *Extensible toward ML* - `RecommendationScorer.score(opportunity,
    market_price) -> ScoreBreakdown` is a narrow, stable interface. A learned
    model can be dropped in behind it (or selected via config, like the pricing
    strategies) without touching the pipeline, CLI, or result models. The
    normalized `[0, 1]` signals are ready-made features.
  - *Backward compatible* - `score`/`risk_score` default to `0.0` on
    `PipelineItemResult`, the default pipeline ranking is unchanged
    (`--sort score` is opt-in), and the score is additive to `to_dict()`.
- **Consequences:** Weights need not sum to 1 (the score is normalized by their
  total), but at least one must be positive. Risk is intentionally distinct from
  confidence: it is a market-structure signal (dispersion + coverage), and only
  falls back to `1 - confidence` when a scorer is used without a market price.
  ROI/profit references are absolute anchors, so scores are comparable across
  runs but should be re-tuned if the cost model or currency scale changes.

### ADR-013: SQLite persistence for scan history

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Every `arb scan` was ephemeral - results printed and vanished, so
  there was no way to review an earlier run, compare a query over time, or keep a
  record of opportunities. We want lightweight, local persistence that fits the
  project's constraints: standard library only, no external services, no new
  dependencies, deterministic, and simple to extend.
- **Decision:** Add a `persistence` package built on the stdlib `sqlite3` module.
  A `ResultStore(path)` opens (and creates) a database with two additive tables -
  `runs` (one row per scan: query, timestamp, config summary, totals) and
  `opportunities` (one row per ranked item: title, provider, price, estimated
  resale value, ROI, net profit, confidence, risk score, recommendation score,
  recommendation, plus its `rank`). `save_run(result) -> int` persists a
  `PipelineResult` in a single transaction and returns the new run id;
  `list_runs`, `get_run`, and `list_opportunities` read them back as typed
  `StoredRun` / `StoredOpportunity` models. The CLI gains `arb scan --save`
  (persists the *full*, unfiltered result), `arb history` (list runs), and
  `arb show <run_id>` (view a run's opportunities), all honouring `--db` with a
  default of `~/.digital_arbitrage/history.db`. `PRAGMA user_version` records the
  schema version for future migrations.
- **Rationale:**
  - *Zero dependencies* - `sqlite3` ships with Python, so persistence adds no
    install burden and works offline (consistent with the stdlib-only ethos of
    ADR-009/010).
  - *Right tool* - a single-file relational store gives durable, queryable
    history with transactions and referential integrity (`opportunities.run_id`
    -> `runs.id`, `ON DELETE CASCADE`) without a server or ORM.
  - *Snapshots, not references* - opportunity fields are copied into the row, so
    history is a faithful record even as the scoring/cost models evolve; runs
    stay comparable over time.
  - *Typed seam* - reads return dataclasses (never raw `sqlite3.Row`), keeping
    the store's surface consistent with the rest of the codebase and easy to
    render or serialize.
  - *Backward compatible* - persistence is entirely opt-in (`--save`); default
    scan behaviour, output, and the pipeline are unchanged.
- **Consequences:** History accumulates until manually pruned (no retention
  policy or `arb prune` yet - deferred). The stored snapshot is a subset of
  `to_dict()` (the fields worth querying), not the full item, so re-deriving a
  complete `PipelineResult` from history is out of scope. `save_run` records the
  full result regardless of the CLI's display filters, so `arb show` may list
  more rows than the original filtered `arb scan` printed - intentional, as the
  saved run is the complete analysis. `arb compare` (diffing a query across runs)
  is a natural follow-up now that the data is captured.

### ADR-014: Comparing two saved runs

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Persistence (ADR-013) captures runs, but there was no way to see
  *what changed* between two scans of the same query - which opportunities are
  new, which vanished, and which got better or worse. We want a deterministic,
  dependency-free diff over the stored snapshots.
- **Decision:** Add a `comparison` package. `compare_runs(old_run, old_opps,
  new_run, new_opps, config?) -> RunComparison` matches opportunities across the
  two runs by a stable **identity key** and classifies each into a
  `ChangeCategory`: `NEW` (only in the newer run), `DISAPPEARED` (only in the
  older), `UNCHANGED`, `IMPROVED`, or `WORSENED`. Each `OpportunityDelta` carries
  the matched snapshots plus a `MetricDelta` (old, new, signed delta) for every
  key metric, and a human-readable `reason`.
  - *Identity key* - `provider + "|" + normalized(title)`, where the title is
    lower-cased and whitespace-collapsed. This uses the best stable fields a
    snapshot has (there is no cross-provider product id), so the same listing
    matches across runs while genuinely different listings stay distinct.
  - *Improve/worsen decision* - a fixed metric priority is walked in order:
    `recommendation_score` -> `roi_percentage` -> `net_profit` ->
    `confidence_score` -> `risk_score`. The first metric whose change exceeds
    `ComparisonConfig.epsilon` settles the verdict (risk is inverted: a decrease
    is an improvement); the rest act as deterministic tie-breakers. If no metric
    moves, the pair is `UNCHANGED`. `recommendation_score` leads because it
    already blends the other signals (ADR-012).
  - *Deterministic ordering* - deltas are sorted by category (new, improved,
    worsened, unchanged, disappeared) then identity key, so output is stable.
  - *CLI* - `arb compare <old_run_id> <new_run_id>` renders `table`, `json`,
    `csv`, or `markdown` (metric columns show the new-minus-old delta); a missing
    run id prints an error and exits non-zero.
- **Rationale:** Standard library only, reads the existing snapshot schema
  unchanged (no migration), and keeps the policy (identity + classification) in a
  small pure module that is trivial to unit-test. Exposing per-metric deltas
  (not just a verdict) keeps the result auditable and future-proof for a
  weighted/scored diff later.
- **Consequences:** Identity is heuristic: a retitled listing looks like a
  `DISAPPEARED` + `NEW` pair rather than a change, and two distinct listings that
  happen to share a provider+title collapse to one (the best-ranked is kept,
  documented). `None` ROI/net-profit values are coalesced to `0.0` for the delta
  math, so a rejected-then-priced opportunity reads as an improvement. Comparison
  is symmetric only in structure, not meaning - callers pass old and new
  explicitly. A stored, stable product id (if added upstream) would supersede the
  title-based key.

### ADR-015: Live-provider framework (before any live integration)

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** Every provider so far is a deterministic mock. Before wiring the
  first *real* marketplace we need the production concerns a network integration
  demands - HTTP, timeouts, retries, rate limiting, pagination, capability
  metadata, typed errors, and structured logging - built once and shared, so a
  concrete provider is small and declarative. The framework must not add scraping,
  live API calls, or dependencies, and must not disturb the existing mock
  providers or the pipeline.
- **Decision:** Add a `digital_arbitrage.providers.live` package containing the
  reusable infrastructure **only** (no concrete provider ships this sprint):
  - *Two hierarchies, not one* - `LiveProvider` **subclasses** the existing
    `product_scanner.providers.Provider` rather than modifying it. A live provider
    is therefore drop-in compatible with the scanner/registry, but the simple mock
    interface stays free of HTTP/retry/rate-limit noise. Backwards compatibility
    is structural, not just behavioural.
  - *Layered HTTP* - `HttpRequest`/`HttpResponse` DTOs; a `Transport` seam whose
    stdlib implementation is `UrllibTransport` (tests inject fakes - no network);
    and an `HttpClient` that composes transport + retries + rate limiting +
    default headers/auth + logging. Only `urllib`/`http.client` are used.
  - *Resilience as data* - `RetryPolicy` is a frozen config that decides *what* is
    retryable (timeouts, connection errors, and a configurable set of 5xx/429
    statuses) and computes exponential backoff with **equal jitter**;
    `run_with_retries` applies it, honouring a server `Retry-After` as a delay
    floor. `TokenBucketRateLimiter` gates outbound rate (sustained rate + burst).
    Clock, sleep, and jitter sources are all injectable, so every timing path is
    unit-tested deterministically without real waiting.
  - *Declarative capabilities* - `ProviderCapabilities` (frozen) states what a
    provider supports (pagination, filters, sorting, api-key requirement, page/
    result caps, currencies). The base uses these to gate pagination and clamp
    result counts, so the framework adapts without provider-specific branching.
  - *Typed errors* - a `ProviderError` tree
    (`ProviderConfigError`; `ProviderRequestError` ->
    `ProviderTimeoutError`/`ProviderConnectionError`/`ProviderHTTPError` ->
    `ProviderRateLimitError`; `ProviderResponseError`) lets callers react
    precisely and carries the provider name (and url/status/retry-after where
    relevant) for structured logs.
  - *Validation + pagination + logging* - small `validation` helpers turn
    untrusted JSON into typed values with context-prefixed errors; a generic
    `paginate` drives page fetching up to `max_results`; logs use `key=value`
    fields under the `digital_arbitrage.providers` namespace.
  - *Provider hooks* - a concrete provider implements just `build_request(query,
    *, page, page_size)` and `parse_response(response, *, query) -> Page[Listing]`;
    the base handles execution, resilience, pagination, and capping via the
    inherited `Provider.search`/`fetch` contract.
- **Rationale:** Standard library only and additive - no change to existing
  modules, schema, or the mock providers (verified by a test asserting the global
  registry is unchanged and the mock scanner still runs). Dependency injection of
  transport/clock/sleep keeps the suite fast and deterministic while still
  covering real behaviour via a loopback `http.server` integration test for the
  `UrllibTransport` (200/404/500/429/timeout mapping). Splitting policy (config
  dataclasses) from mechanism (client/limiter/pagination) mirrors the conventions
  used elsewhere in the codebase.
- **Consequences:** No live data is fetched yet - this is scaffolding, and the
  first real provider (plus its API-key secret handling and record-parsing) is a
  later sprint. `UrllibTransport` is synchronous and per-request; a connection
  pool or async transport can be added behind the `Transport` seam without
  touching providers. Capabilities are static class attributes (fine for
  compile-time-known providers); a dynamic/discovered capability set would need a
  small extension. The two-hierarchy choice means a future decision may unify
  mock and live providers, but only once a live provider actually exists.

### ADR-016: First real provider — eBay Browse API (research & plan)

- **Date:** 2026-07-07
- **Status:** Accepted (plan only; no provider code this sprint)
- **Context:** With the live-provider framework in place (ADR-015), the first
  real, read-only marketplace integration is the eBay **Browse API**
  (`buy/browse/v1/item_summary/search`). Before implementing, we researched its
  auth, limits, endpoint, pagination, and response shape, and validated the fit
  against the framework. Full detail lives in `docs/EBAY_PROVIDER_PLAN.md`; this
  ADR records the decisions. Constraints unchanged: read-only, no scraping, stdlib
  only, no secrets in repo/CI, mocks untouched.
- **Decision:**
  - *Provider name* — register as **`ebay_browse`**, not `ebay`, because the
    existing mock provider already owns `"ebay"` in `PROVIDER_REGISTRY` and
    `register_provider` rejects duplicates. Distinct name lets mock and live
    coexist during rollout.
  - *API surface* — Browse `item_summary/search` with an **Application** OAuth
    token (client-credentials grant, scope `.../oauth/api_scope`, ~2h TTL). No
    user login. Marketplace selected via `X-EBAY-C-MARKETPLACE-ID` (default
    `EBAY_IE`, EUR). Offset/limit pagination (`limit` ≤ 200, `offset` < 10,000).
  - *Model mapping* — response maps 1:1 onto `Listing` (`itemId`→`listing_id`,
    `title`, `itemWebUrl`→`url`, `price.value`/`price.currency`, `itemLocation`→
    `location`, `condition`/`conditionId`→`Condition`); image/seller/buying
    options/raw condition id go into `Listing.extra`. **No schema change.**
    `posted_at` is unavailable on summaries and stays `None`.
  - *Config & secrets* — an `EbayBrowseConfig(LiveProviderConfig)` adding
    `marketplace_id` + `oauth_token_url`, loaded from `[providers.ebay_browse]`
    TOML; credentials come only from secrets `EBAY_CLIENT_ID` /
    `EBAY_CLIENT_SECRET` (never the file/CI). `requires_api_key=True` fails fast
    when absent.
  - *One framework addition* — a small, additive **`AuthProvider`** seam so
    `HttpClient` can source a *minted, cached, auto-refreshed* bearer token
    (`OAuthClientCredentialsAuth`) instead of today's static `config.api_key`.
    This is the only real gap; existing providers are unaffected.
  - *Tests/CI* — sanitised recorded JSON fixtures replayed through a
    `FixtureTransport`; **CI uses the mocked transport only** (no network, no
    secrets). A live smoke test is opt-in, gated by env-var presence and always
    skipped in CI.
- **Rationale:** Browse is the officially supported, read-only, app-token search
  surface — no scraping, no user consent, and it fits the framework's
  transport/retry/rate-limit/pagination/validation seams almost entirely as-is.
  Keeping credentials in secrets and CI on a mocked transport preserves the "no
  secrets, deterministic CI" posture from prior sprints. Putting eBay-only fields
  on a `LiveProviderConfig` subclass keeps the generic config lean.
- **Consequences:** Implementation is deferred to the next sprint and will need
  the `AuthProvider` seam plus a config-aware registry factory (today's
  `create_provider(name)` calls `cls()` with no args, which cannot construct a
  config-taking `LiveProvider`). The per-second rate limiter does not enforce
  eBay's **5,000 calls/day** quota — a daily budget guard is deferred debt.
  Affiliate/EPN commissions are out of scope (we use the plain `itemWebUrl`).
  Production volume requires accepting the eBay API License Agreement / passing
  the free Application Growth Check.

### ADR-017: Live-provider auth abstraction & config-aware factory

- **Date:** 2026-07-05
- **Status:** Accepted
- **Context:** ADR-016 surfaced two framework gaps blocking a real authenticated
  provider (eBay Browse): (1) auth was a single static `config.api_key` Bearer
  token, but eBay needs a **minted, cached, auto-refreshed** OAuth
  application token; and (2) the provider registry constructs providers with no
  arguments (`create_provider(name)` → `cls()`), which cannot build a
  config-taking `LiveProvider`. This sprint closes both gaps generically — **no
  eBay code, no live calls, no real secrets, stdlib only, fully backward
  compatible.**
- **Decision:**
  - *Auth abstraction* — introduce an `AuthProvider` ABC with a single
    `authorization() -> str | None` method returning the full `Authorization`
    header value (or `None`). `HttpClient` calls it **once per request** in
    `_default_headers`, so caching/refresh is transparent. Three implementations:
    `NoAuthProvider` (no header), `StaticBearerTokenAuthProvider` (fixed token,
    optional scheme), and `OAuthClientCredentialsAuthProvider`.
  - *OAuth provider* — client-credentials grant: POSTs `grant_type=client_credentials`
    (+ optional `scope`) with an HTTP **Basic** header built from
    `client_id:client_secret` to a validated `token_url`, over an **injectable
    `Transport`** (so tests never touch the network). Tokens are cached with a
    monotonic-clock expiry and re-minted once within `refresh_leeway` (default
    60s) of expiry — a request never travels with an about-to-expire token.
    Thread-safe via a lock. Construction validates credentials/URL/timeout.
  - *Typed errors* — add `ProviderAuthError(ProviderError)`. Every token-mint
    failure (non-2xx, invalid/JSON-less body, missing `access_token`, bad
    `expires_in`, wrapped transport error) raises it. It is **not** in the retry
    policy's retryable set, so a bad credential or malformed token response is
    not blindly re-hammered.
  - *No secret logging* — credentials are never logged or placed in exception
    messages; the mint log records only `expires_in`/`refresh_leeway`. Wrapped
    transport errors surface only the error *type name*.
  - *HttpClient wiring* — new optional `auth: AuthProvider | None`. Precedence:
    injected `AuthProvider` → else static `config.api_key` as `Bearer` → else no
    header. With `auth=None` behaviour is byte-identical to before (backward
    compatible).
  - *Config-aware creation* — `LiveProvider` gains an optional `auth` param and a
    `create(config, *, auth=..., transport=..., http_client=...)` classmethod
    that wires auth into the client. A **separate** `LIVE_PROVIDER_REGISTRY` +
    `register_live_provider` + `create_live_provider(name, config, *, auth=...)`
    handle name-based construction. `requires_api_key` is now satisfied by
    *either* an `api_key` *or* an `auth` provider.
- **Rationale:** A one-method `AuthProvider` keeps `HttpClient` agnostic to auth
  mechanics and makes OAuth caching/refresh an implementation detail. Sourcing
  the token round trip through the existing `Transport` seam means the whole
  OAuth flow is unit-tested deterministically with a fake clock — no network, no
  secrets in CI. Keeping the live registry *separate* from the mock registry
  means the zero-arg `create_provider` contract (and every mock provider) is
  untouched, satisfying strict backward compatibility.
- **Consequences:** The framework can now back real authenticated providers; the
  eBay provider (next sprint) just supplies an `OAuthClientCredentialsAuthProvider`
  and registers via `register_live_provider`. Nothing is registered yet, so the
  live factory has no entries. Token refresh is checked per request (not with a
  background timer) and is not re-attempted mid-retry — acceptable for ~2h tokens.
  Auth failures are non-retryable by design; a transient token-endpoint blip
  surfaces immediately rather than being retried.

### ADR-018: eBay Browse provider implementation (`ebay_browse`)

- **Date:** 2026-07-08
- **Status:** Accepted
- **Context:** ADR-016 planned the eBay Browse integration and ADR-017 shipped
  the auth abstraction + config-aware factory it needs. This sprint implements
  the first **real, read-only** provider on that framework. Constraints
  unchanged: stdlib only, no scraping, no live calls in CI, no secrets in the
  repo, mock providers untouched, backward compatible.
- **Decision:**
  - *Shape* — `EbayBrowseProvider(LiveProvider)` registered as **`ebay_browse`**
    in `LIVE_PROVIDER_REGISTRY` (never the mock `PROVIDER_REGISTRY`). It supplies
    only the two declarative hooks; the framework owns HTTP, retries, rate
    limiting, pagination, and logging.
  - *Config* — `EbayBrowseConfig(LiveProviderConfig)` adds `marketplace_id`
    (default `EBAY_IE`), `oauth_token_url`, and `oauth_scope`, validated in
    `__post_init__`. Because `from_dict` keys off `fields(cls)`, the eBay keys are
    accepted transparently and unknown keys still rejected. (An explicit
    `super(EbayBrowseConfig, self)` call is required — `@dataclass(slots=True)`
    rebuilds the class, breaking zero-arg `super()`.)
  - *Auth* — `OAuthClientCredentialsAuthProvider` (ADR-017) mints/caches/refreshes
    the application token. `build_ebay_browse_provider(...)` and
    `build_ebay_browse_provider_from_env(...)` wire it up; credentials come only
    from `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` and are never committed or logged.
  - *Request* — `GET /buy/browse/v1/item_summary/search` with `q` (truncated to
    100 chars), `limit`, and `offset = (page-1)*page_size`, plus the
    `X-EBAY-C-MARKETPLACE-ID` header. Capabilities advertise `max_page_size=200`
    and `max_results=10_000` (eBay's offset ceiling).
  - *Response → `Listing`* — `itemId→listing_id`, `title`, `itemWebUrl→url`,
    `price.value`(+`currency`, defaulting to `default_currency`), a composed
    `itemLocation` string, and a `Condition` derived from `conditionId` (a fixed
    lookup table) with the free-text `condition` as fallback. eBay-only fields
    (`image_url`, `buying_options`, `seller`, `condition_id`) go into
    `Listing.extra`. Auction-only items with no `price` map to `price=None`.
  - *Pagination* — offset-based; `has_more` is true when the payload has a `next`
    link, else when `offset + limit < total`.
  - *Tests* — a fake `Transport` replays sanitised, committed JSON fixtures
    (`tests/fixtures/ebay/`); every path (mapping, condition table, pagination,
    empty, malformed JSON, HTTP/429 errors, config validation, OAuth mint+cache)
    is exercised without network or secrets. A live smoke test is intentionally
    **not** added to CI.
- **Rationale:** Keeping the provider a thin mapping over the framework means the
  hard concerns (resilience, auth, pagination) stay in one tested place and the
  next marketplace is cheap to add. Fixture-driven tests make the whole flow
  deterministic and secret-free, satisfying the "no live calls in CI" constraint.
- **Consequences:** `LIVE_PROVIDER_REGISTRY` now has one entry (`ebay_browse`);
  the mock registry and zero-arg `create_provider` are unchanged. Real end-to-end
  use requires the two eBay secrets in the environment. eBay's daily call quota
  (5,000/day) is not yet enforced by the per-second limiter — deferred as known
  debt (see `docs/EBAY_PROVIDER_PLAN.md`); price/condition **filter** parameters
  and sorting are advertised as capabilities but not yet mapped into the request.

### ADR-019: Local live eBay scanning — wiring `ebay_browse` into the scanner

- **Date:** 2026-07-08
- **Status:** Accepted
- **Context:** ADR-018 shipped the `ebay_browse` provider, but nothing wired it
  into the scanner/pipeline the CLI runs. The scanner built every provider with
  the mock registry's zero-arg `create_provider`, which cannot construct a
  config- and credential-taking `LiveProvider`. Sprint 25 lets a user run a real
  eBay Browse search **locally** with their own credentials, while keeping the
  default scan mock-only. Constraints unchanged: stdlib only, no secrets in the
  repo, no live calls in CI, mock providers untouched, backward compatible.
- **Decision:**
  - *Name-based construction* — two per-provider registries parallel to
    `LIVE_PROVIDER_REGISTRY`: `LIVE_PROVIDER_CONFIG_BUILDERS` (mapping → validated
    `LiveProviderConfig`) and `LIVE_PROVIDER_ENV_BUILDERS` (config + `env` →
    provider). `build_live_provider_from_env(name, config, *, env, transport,
    token_transport)` combines them. `ebay_browse` registers
    `build_ebay_browse_config` (defaults `base_url` to `https://api.ebay.com`,
    reuses `from_dict` validation) and the existing
    `build_ebay_browse_provider_from_env`. This keeps adding a new live provider a
    two-line registration, mirroring the mock/live registry split.
  - *Scanner assembly* — a new `providers.live.scanning.build_scanner_from_config`
    builds each configured name from the **live** registry (via its
    `LiveProviderSetting`) when present, else the **mock** registry — the single
    place that knows a name might be live. The mock path (`create_provider`) is
    byte-for-byte unchanged, and `product_scanner.build_scanner` is left intact.
  - *Enable/disable from TOML* — a new top-level `[providers.<name>]` table in the
    pipeline config carries per-provider config plus an `enabled` boolean
    (default `true`). It is parsed into `PipelineConfig.live_provider_settings`
    (`{name: LiveProviderSetting(enabled, config)}`). A provider runs only when it
    is both listed in `[scanner].providers` (or `--provider`) **and** enabled;
    disabled providers are skipped without needing credentials. Unknown provider
    names, non-boolean `enabled`, and invalid provider config are rejected at
    load, consistent with ADR-010's fail-loud loader.
  - *CLI* — `arb scan … --provider NAME` (repeatable) overrides the configured
    provider list for one scan (`_apply_provider_override` preserves other scanner
    settings and any `[providers.*]` config). `arb scan "rtx 4090" --provider
    ebay_browse` therefore runs a live scan.
  - *Credentials* — read only from `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` at scan
    time via the existing env builder; missing creds fail fast. Secrets never live
    in config files.
  - *Tests* — `tests/test_local_ebay_scan.py` drives the whole path — assembly,
    registries, TOML enable/disable + validation, `--provider` override, and a
    full `arb scan --provider ebay_browse` CLI run — through the ADR-018 fake
    `Transport` and a fake `env`, so no network call and no secret touch CI. The
    injectable `transport`/`token_transport` params thread through purely for this.
- **Rationale:** Reusing the registry pattern keeps the mock path untouched and
  makes "is this name live?" a lookup, not a special case. Putting enable/disable
  in config (not code) and gating on both listing + `enabled` gives an obvious,
  reversible opt-in. Threading injectable transports keeps the integration
  hermetic, honouring "no live API calls in CI".
- **Consequences:** `PipelineConfig` gains `live_provider_settings` (defaults to
  empty, so existing behaviour is identical) and the pipeline builds its scanner
  via `build_scanner_from_config`. The config loader accepts a new `[providers.*]`
  section. Adding a future live provider needs only its two builder registrations.
  The shared `transport`/`token_transport` injection assumes a single live
  provider per scan (true today); per-provider transport wiring is deferred until
  a second live provider exists.

### ADR-020: First live end-to-end scan — pipeline seam, sample config, and tests

- **Date:** 2026-07-08
- **Status:** Accepted
- **Context:** ADR-019 wired `ebay_browse` into the scanner and CLI, so a live
  scan already ran end to end. Sprint 26 makes that first *real* end-to-end scan a
  first-class, documented capability: a copy-and-run config, a proof that live
  listings flow through **every** pipeline stage (Scanner -> Normalization ->
  Matching -> Deduplication -> Market Pricing -> Opportunity) producing real
  opportunities, and hermetic integration tests — all while keeping CI fully
  offline. Constraints unchanged: stdlib only, no scraping, no secrets in the
  repo, no live calls in automated tests, backward compatible, mock path
  untouched.
- **Decision:**
  - *Injectable scanner seam* — `ArbitragePipeline.__init__` gains an optional
    keyword-only `scanner: Scanner | None`. When supplied it is used verbatim;
    otherwise the scanner is built from config as before. This lets the whole
    pipeline be exercised end to end against a `Scanner` wired to a fake
    `Transport` (via the existing `build_scanner_from_config(..., transport=...)`
    seam) without mutating global registries. It is additive and fully backward
    compatible — the default path is byte-for-byte unchanged.
  - *Sample config* — `configs/ebay_browse.toml` is a small, secret-free config
    users copy and run directly. It lists `ebay_browse` in `[scanner].providers`
    and carries a documented `[providers.ebay_browse]` table, so both
    `arb scan "rtx 4090" --provider ebay_browse --config configs/ebay_browse.toml`
    and the same command without `--provider` run the live scan.
    `configs/ebay_browse.example.toml` remains the exhaustive key reference.
  - *No new credential surface* — credentials are still read only from
    `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` at scan time; missing or empty values
    fail fast with the existing helpful message and a non-zero exit code. Nothing
    partial is persisted on failure.
  - *Docs accuracy* — CLI/pipeline docstrings and the `arb` parser description no
    longer claim "mock providers only"; they state that a live provider is an
    opt-in that performs a real, read-only call.
  - *Tests* — `tests/test_live_end_to_end_scan.py` drives the real
    `ArbitragePipeline` end to end through the ADR-018 fake `Transport` + fake
    `env` (asserting listings become scored opportunities, prices/currencies/
    condition and eBay-only `extra` fields survive, and pagination + one token
    mint occur), validates the committed sample config, and runs the exact
    documented CLI command. Sprint 25's `test_local_ebay_scan.py` (assembly,
    registries, TOML parsing) is complementary and unchanged.
- **Rationale:** An injectable scanner is the minimal, enterprise-clean seam for a
  hermetic full-pipeline test — it mirrors the framework's existing preference for
  dependency injection over monkeypatching and keeps test-only transports out of
  production `PipelineConfig`. Shipping a copy-and-run config plus complete README
  steps turns "it can run live" into "here is exactly how", without ever putting a
  secret in the repo.
- **Consequences:** `ArbitragePipeline` has one new optional parameter; all other
  behaviour is identical. There is still, by design, no live smoke test in CI —
  the end-to-end coverage is fixture-driven. Known debt carried from ADR-018/019
  is unchanged: eBay's daily quota is not enforced by the per-second limiter, and
  price/condition filters and sorting are advertised as capabilities but not yet
  mapped into the request.
