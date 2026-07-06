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
