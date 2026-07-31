# PUE data artifacts

Hand-authored, version-controlled knowledge artifacts for the Product
Understanding Engine (see `src/digital_arbitrage/pue/` and
`docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md`). These are
source, not generated output, and are intentionally excluded from the
repository's general `data/` gitignore rule (see `.gitignore`).

## `catalogues/gpu_seed_v0.1.json`

- **Knowledge version:** `gpu-seed-0.1.0`.
- **~36 hand-seeded records** covering NVIDIA RTX 30/40-series, AMD RX
  6000/7000-series, Intel Arc, board-partner variants, a mobile GPU, water
  blocks, replacement parts, packaging, accessories, and a bundle concept.
- Every record carries a `attributes.provenance` block: `source_description`,
  `source_url`, `license`, and a `synthetic` flag. Records marked
  `"synthetic": true` are illustrative concepts (e.g. a competitor mobile-GPU
  concept, several generic accessories, a bundle) - **not** verified retail
  SKUs, and must never be treated as production data.
- This is an evaluation instrument for Sprint 1, not a production catalogue
  (spec section 12.1/24.5). Re-verify any manufacturer part number before
  commercial use; a future production catalogue may replace this file
  entirely behind the same `CandidateRepository` interface
  (`pue/catalogue.py`).

## `knowledge/gpu_terms_v0.1.json`

- **Term version:** `gpu-terms-0.1.1`.
- Deterministic term groups used by `pue/evidence.py`: brand aliases,
  chipset-manufacturer aliases, family/model aliases, product-type terms,
  accessory/component terms (mapped to `ProductForm`), packaging terms,
  box-included terms, compatibility phrases, exclusion terms, bundle terms,
  and condition terms.
- These are versioned Knowledge Artifacts, not permanent truths (spec 9.2):
  expect this file to grow as new listing phrasing patterns are observed and
  added to the regression suite.

## `releases/`

Sprint 3 versioned, immutable release manifests
(`digital_arbitrage.pue.release`), each binding capability/policy/
knowledge/schema/comparison-schema versions, the benchmark dataset id+hash,
the catalogue file hash, and the policy/code Git commit to one release
benchmark report. `pue_v0.1.0.json` is the first release manifest;
`pue_v0.1.0_benchmark_report.{json,md}` is its bound report. Regenerate via
`python scripts/gen_pue_release_v0_1_0.py` - it (like
`digital_arbitrage.pue.release.save_release_manifest`) refuses to overwrite
an existing manifest file; a new release requires a new `release_id`/path.

## Versioning

Bump `knowledge_version` / `term_version` (and the corresponding constant in
`pue/version.py`) whenever these files change in a way that could alter a
Decision, so persisted Reasoning Records remain traceable to the exact
knowledge state that produced them (spec section 7.3).
