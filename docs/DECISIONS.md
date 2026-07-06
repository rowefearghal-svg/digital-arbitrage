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
