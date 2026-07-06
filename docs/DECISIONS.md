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
