# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/); dates are UTC.

## [Unreleased]

### Added - PUE v0.1 Sprint 1: Traceable Deterministic GPU Pipeline

- New `digital_arbitrage.pue` package implementing the complete Product
  Understanding Engine v0.1 vertical slice reasoning chain:
  `Observation -> Evidence -> Claim -> ProductHypothesis -> Candidate
  Retrieval -> Candidate Evaluation -> Decision -> Explanation ->
  ReasoningRecord`. See
  `docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md`.
- Hand-seeded, versioned GPU catalogue (`data/pue/catalogues/gpu_seed_v0.1.json`,
  36 records) and term-knowledge artifact
  (`data/pue/knowledge/gpu_terms_v0.1.json`).
- `pue_cases` SQLite table (`digital_arbitrage.pue.persistence.PueCaseStore`)
  for persisting complete Reasoning Records, indexed by listing, source
  fingerprint, and version triple. Historical records are never overwritten.
- Configuration-gated PUE **shadow-mode** execution in the existing pipeline
  (`digital_arbitrage.pipeline.pue_shadow`), disabled by default and never
  altering `PipelineResult`, deduplication, pricing, or scoring.
- 25 mandatory acceptance cases
  (`tests/fixtures/pue/sprint1_acceptance_v0.1.json`) plus unit, integration,
  invariant, and golden-record tests under `tests/pue/`.
- Local synthetic performance diagnostic (`scripts/pue_diagnostic.py`) and
  golden-record regeneration tool (`scripts/gen_pue_golden.py`).
- New runtime dependency: `rapidfuzz` (deterministic fuzzy matching for
  Candidate Retrieval).
- ADR-023 through ADR-030 (`docs/decisions/DECISIONS.md`) covering PUE
  placement, the dataclass object model, catalogue provenance, SQLite JSON
  persistence, the Decision/comparability taxonomy, named uncertainty
  dimensions, the shadow-mode release strategy, and PUE's position relative
  to deduplication/commercial scoring.

### Changed

- `.gitignore`: added a scoped exception (`!data/pue/`) so the hand-authored
  PUE catalogue/knowledge JSON is version-controlled, unlike generated
  data/model artifacts.
- `pyproject.toml`: added `rapidfuzz>=3.6` to `[project.dependencies]`.
