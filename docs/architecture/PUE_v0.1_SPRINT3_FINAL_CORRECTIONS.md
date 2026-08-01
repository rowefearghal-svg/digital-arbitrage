# PUE v0.1 Sprint 3 — Final Release-Integrity Correction

Second corrections pass on `feature/pue-v0.1-sprint3`, following
`docs/architecture/PUE_v0.1_SPRINT3_PREMERGE_CORRECTIONS.md`. Addresses eight further
release-integrity gaps identified in review. Not merged; Sprint 4 not started.

## 1. Removed remaining unconditional release-gate `passed=True`

`evaluate_release_gate` (`src/digital_arbitrage/pue/benchmark_report.py`) had two checks that were
`GateCheck(..., True, ...)` regardless of any data:

- **`retrieval_and_decision_quality_reported_independently`** is now derived from the actual
  `ProductMetrics`: it verifies `candidate_recall_at_1/5/10` (retrieval) and
  `exact_identification_accuracy`/`hierarchical_identification_accuracy` (decision quality) are
  each structurally valid (`0 <= numerator <= denominator`) *and* that both categories actually
  measured real data (`denominator > 0` for at least one metric in each group) - a genuine,
  potentially-failing structural check, not a re-statement of fact.
- **`every_harmful_result_individually_listed`** now compares every case with `harmful_errors`
  against the independent `CaseFailure` adjudication trail produced by `classify_failure` (the
  same mechanism `every_wrong_decision_has_a_traceable_failure_stage` already checks) - a harmful
  result with no corresponding `CaseFailure` entry now genuinely fails this check. Zero harmful
  results still passes trivially, with an explicit "0 harmful case(s) - zero-count trivially
  satisfies adjudication" detail string.

**Negative tests** added: `tests/pue/test_benchmark_metrics.py`'s
`test_release_gate_mandatory_checks_pass_when_given_passing_evidence` was narrowed to check only
the checks genuinely derived from its own arguments (mandatory acceptance/replay/versions),
decoupling it from the real dataset's own data-derived outcome; `test_release_gate_fails_when_a_mandatory_check_fails`/`test_release_gate_fails_on_replay_non_equivalence` already exercised
real failure paths and continue to pass.

**A previously-masked, genuine finding was surfaced, then fixed at its root cause**: this
correction initially revealed `every_abstention_classified_justified_or_avoidable` failing on
`compat_01_case_fits_rtx4090` ("PC Case - fits RTX 4090 and other large graphics cards"), which
reached `ABSTAINED` despite that not even being in its own `allowed_decision_types`. Root-caused
to an unconditional `ABSTAINED` return in `pue/decisions.py`'s `form_decision` whenever a single
hypothesis resolved to `ProductForm.COMPATIBLE_ITEM` (a "compatible with `<family>`" phrase with
no accompanying sold-item noun) - contrary to that spec-documented product form's own purpose (see
the Sprint 3 final *narrow* correction below, addressing this at the source rather than leaving it
as an accepted gap). `report.gate.passed` on the real dataset is now honestly **`True`**.

## 2. Explicit search/comparison context — never `build_search_profile(case.title)`

`benchmark_runner.py` built the classifier's `SearchProfile` from the listing's own title
(`build_search_profile(case.title)`), making "does this listing match the search" tautologically
true for every case — a real product-form mismatch between what was searched for and what was
found could never be revealed this way.

`BenchmarkCase` gained `search_query`, `searched_product_form`, `searched_family` (all optional).
`benchmark_runner.py` now builds the classifier's `SearchProfile` from `case.search_query` only;
a case with no `search_query` produces no comparison at all (`comparison=None`, excluded from
every classifier/differential metric) rather than an implicit or synthesized one.

Applied to 47 cases spanning exact-identification, board-partner-ambiguity, family-only,
mobile-vs-desktop, water-block, unsupported-domain, and misleading-similarity coverage — including
the brief's own example: `waterblock_01_ek_quantum_vector2` (listing title "EK Quantum Vector2 RTX
4090 Water Block Full Cover") now carries `search_query="RTX 4090"`, `searched_product_form=
"complete_product"` — a buyer looking for a graphics card shown a water-block accessory instead.

## 3. Removed implementation-derived comparability gold labels

The Sprint 3 pre-merge correction's `_derive_expected_comparability()` (in
`scripts/gen_pue_benchmark_dataset.py`) walked exactly the same dispatch variables
(`allowed_decision_types`, `expected_product_form`) `pue/decisions.py` itself switches on to
compute `ComparabilityStatus` — a table that trivially guarantees agreement with the
implementation's *branch structure*, independent of whether the underlying real-world semantic
mapping is correct. **Removed entirely.**

Replaced with hand-adjudicated, per-stratum labels dispatched only on pure annotation metadata
(`case_tags`, `catalogue_gap`, `unsupported_domain`) or case-specific reasoning written directly
in each case's authoring block — never on `pue/decisions.py`'s own output variables:

- accessory/component/replacement-part/packaging-only/water-block/compatible-item →
  `not_comparable_product_form` (categorically a different product from a complete GPU).
- bundle → `not_comparable_bundle` (aggregate value differs materially from a standalone GPU).
- misleading-similarity merchandise → `not_comparable_product_form` (not a GPU at all).
- catalogue-gap → `not_assessed` (no reference product exists in the tested knowledge version at
  all — an epistemic-limitation statement about this system's own catalogue coverage, not about
  the underlying decision path).
- unsupported-domain → `not_assessed` (not in the GPU product category at all).
- exact-identification cases → `directly_comparable` (MPN-bearing) or
  `[directly_comparable, comparable_at_broader_level]` (canonical-title-only — the annotator
  cannot know a priori which specificity of evidence a title carries).
- family/model-only and board-partner-ambiguity cases → `comparable_at_broader_level` (a real,
  complete GPU, comparable at that broader level regardless of exact SKU).

Cases with no confident, independent real-world judgment remain unlabelled and excluded from
`comparability_accuracy` (grew from 0 hand-adjudicated strata to 8, covering 75 of 118 cases; down
from the previous, illegitimate 118-covering derivation).

**New, genuine findings surfaced** (previously hidden by the code-mirroring derivation, which
could never disagree with the code by construction): `bracket_02_riser_cable`,
`adapter_03_riser_cable_variant`, `bundle_02_rtx4090_with_waterblock`, `bundle_03_gpu_and_riser`,
`bundle_05_two_cards`, and `gap_05_rtx4090ti` now fail `expected_comparability` — the real
implementation's `ComparabilityStatus` for these cases does not match the hand-adjudicated,
real-world-correct expectation. `bracket_02`/`adapter_03` were already known-wrong
(`decision_type_allowed`); `bundle_02/03/05` and `gap_05` are genuinely new, real, visible
findings for follow-up investigation, not something this correction pass silently fixed or hid.

## 4. Release provenance survives a squash merge

`ReleaseManifest.policy_code_git_commit` alone would necessarily go stale the moment this
feature branch is squash-merged into a single, different commit on `main`.

Added `pue/canonical.py::policy_code_content_hash()` — a deterministic SHA-256 over the content
of every file in `DEFAULT_POLICY_CODE_PATHS` (the reasoning pipeline: `admission.py`,
`claims.py`, `decisions.py`, `enums.py`, `evaluation.py`, `evidence.py`, `hypotheses.py`,
`models.py`, `orchestration.py`, `policies.py`, `retrieval.py`, `validation.py`, plus
`data/pue/knowledge/gpu_terms_v0.1.json`) — computed purely from file *content*, so it is
identical before and after a squash merge (only the Git commit hash changes; the files' content
does not).

`ReleaseManifest` gained `policy_code_content_hash` (the new authoritative, blocking provenance
check) alongside the existing `policy_code_git_commit` (now documented and treated as
informational-only). `GateCheck` gained a `blocking: bool = True` field;
`ReleaseGateReport.passed`/`VerificationReport.passed` now only require `blocking` checks —
`policy_code_git_commit_matches_running_code` is marked `blocking=False` and will no longer fail
overall verification when (correctly) the commit differs after a squash merge, while
`policy_code_content_hash_matches` is blocking and catches a genuine code-content change.

Tests: `test_verify_release_reproducibility_checks_git_commit_matches` now additionally asserts
`result.passed is True` despite the (expected) git-commit mismatch;
`test_verify_release_reproducibility_detects_a_tampered_policy_code_content_hash` proves the new
check is blocking.

## 5. Artifact integrity vs semantic reproducibility

`ReleaseManifest.release_report_hash` conflated two different properties. Split into:

- **`release_report_artifact_hash`** (`canonical_report_artifact_hash`) — hashes the *complete*
  report including `generated_at`/`operational_metrics`. Computed once at generation time;
  verification re-hashes the **exact committed file on disk** (never a fresh regeneration, which
  would always mismatch on real wall-clock timing alone) — detects any post-publication edit to
  *any* field, including a hand-tampered operational metric.
- **`release_report_semantic_hash`** (`canonical_report_semantic_hash`, the old
  `canonical_report_hash` renamed) — excludes volatile fields; compared against a **fresh
  regeneration** to prove reproducibility.

New test `test_verify_release_reproducibility_detects_tampered_operational_metrics` hand-edits a
committed report's `operational_metrics.listings_per_second` and proves
`release_report_artifact_hash_matches_committed_file` fails while
`semantic_report_content_matches_committed_report` (which deliberately excludes
`operational_metrics`) does not.

## 6. Evidence-precision terminology corrected

The previous "evidence precision" metric counted every produced, non-gold-forbidden evidence type
as a true positive — conflating "we did not bother to label this type forbidden" with "this
evidence type is confirmed correct", which is not the same claim without a *complete*
expected/allowed evidence-type enumeration per case (which this benchmark does not have).

`evidence_precision` is now **always** reported unavailable (`Metric(0, 0)`, `value=None`), with
a docstring explaining why. Added `forbidden_evidence_violation_rate` — of cases with an explicit
`forbidden_evidence_types` gold label, the fraction that actually violated it — the rate the
existing sparse negative labels honestly support.

## 7. Explicit abstention classification

`avoidable_if_abstained: bool` (default `False`) meant `is_justified_abstention = is_abstained and
not avoidable_if_abstained` — every case nobody had explicitly marked `avoidable` was silently
treated as `justified` by default, so `every_abstention_classified_justified_or_avoidable` could
never actually catch an unlabelled abstention (every case was, in effect, always pre-classified).

Replaced with `abstention_classification: str | None` — `"justified"` / `"avoidable"` / `None`
(never hand-adjudicated). `CaseResult` gained `is_unlabelled_abstention`. An abstaining case with
`abstention_classification is None` is now neither justified nor avoidable and correctly fails the
release gate (see item 1's `compat_01` finding — the direct, intended consequence of this fix).

Hand-adjudicated `"justified"` for 5 cases whose title/structured-attribute content genuinely does
not support a confident non-abstaining outcome (`abstain_01/02/03`, `conflict_01`,
`edge_01_empty_title`); `"avoidable"` for `exact_02` (a confident MPN-bearing exact match — already
present from the pre-merge pass) and `compat_03_psu_compatible_wattage` (an unambiguous PSU
listing — abstaining on it is excessive caution, a new, genuine finding this correction surfaced:
`compat_03` now fails `avoidable_abstention_did_not_occur`).

## 8. Reconciled generated and narrative reports

Added a superseded-metrics notice to the top of
`docs/architecture/PUE_v0.1_SPRINT3_BENCHMARK_REPORT.md` pointing to this document and the
freshly generated `data/pue/releases/pue-v0.1.0_benchmark_report.json`/`.md` as the single
authoritative, internally consistent source of current Sprint 3 results (the narrative report's
own prose numbers are not automatically regenerated and will drift after every dataset/metric
change — regenerating the machine-readable report via `scripts/gen_pue_release_v0_1_0.py` is the
only way to get current, self-consistent numbers).

## 9. Follow-up narrow correction: `compat_01_case_fits_rtx4090` root cause fixed

Item 1 above surfaced `compat_01_case_fits_rtx4090` reaching `ABSTAINED` although its gold label
(`allowed_decision_types: ["classified", "ambiguous"]`) never permitted that outcome. Root cause:
`pue/decisions.py::form_decision`'s `ProductForm.COMPATIBLE_ITEM` branch unconditionally returned
`ABSTAINED` (`AbstentionReason.INSUFFICIENT_EVIDENCE`) for *every* single-hypothesis
compatibility-only listing (a "compatible with `<family>`" phrase with no accompanying sold-item
noun), regardless of how coherent that one interpretation was - contrary to
`ProductForm.COMPATIBLE_ITEM`'s own documented purpose and to spec section 21 row 22's intent
("compatibility must not become identity" - never "must always abstain").

Fixed by returning `CLASSIFIED` (`ProductForm.COMPATIBLE_ITEM`,
`ComparabilityStatus.NOT_COMPARABLE_PRODUCT_FORM`, no identity fields populated) for this branch,
mirroring the existing accessory/component/replacement-part `CLASSIFIED` pattern immediately above
it in the same function - `AMBIGUOUS` remains available (and correct) whenever genuinely more than
one hypothesis survives (the pre-existing `len(hypotheses) > 1` branch, unchanged). The gold label
itself was **not** changed.

`compat_01_case_fits_rtx4090`'s gold label is preserved unchanged and now passes. Updated spec
section 21 row 22 and three Sprint 1 acceptance fixture cases
(`case_22_compatibility_only_no_sold_item`, `case_31_for_rtx4090_boundary_regression`,
`case_32_fits_rtx4090_boundary_regression`) whose gold labels encoded the old, now-corrected
"ambiguous or abstained only" contract for this exact scenario - a deliberate, reviewed change to
the acceptance contract, not an unrelated one, since they exercise the identical code path.
`case_30_fits_rtx4090_precedence_regression` already permitted `classified` and needed no change.

New regression test: `tests/pue/test_decisions.py::test_compatibility_only_listing_is_classified_not_abstained`
runs the exact real benchmark title through the real `process_one` path and asserts
`CLASSIFIED`/`ProductForm.COMPATIBLE_ITEM` (or, only if genuinely ambiguous, `AMBIGUOUS`), never
`ABSTAINED`.

**Side effect, not scope creep**: `compat_03_psu_compatible_wattage` (an unambiguous PSU listing;
item 7's `"avoidable"` finding) also goes through this exact same `ProductForm.COMPATIBLE_ITEM`
branch and is now correctly `CLASSIFIED` too, resolving that finding at its root cause rather than
merely labelling it. Three existing comparison/publication tests using "Compatible with RTX 4090"
as an ABSTAINED example (`test_category_pue_abstained`,
`test_build_comparison_report_counts_are_deterministic_and_exhaustive`,
`test_publish_result_abstained_case_has_no_identity_claims`) were updated to use a genuinely still-
abstaining input (an empty/whitespace-only title) instead - the same code path they were built to
exercise no longer exists for that specific input, so pinning the same *behaviour* required a
different input, not a changed assertion.

**Explicitly out of scope, unchanged**: `bracket_02_riser_cable` and `adapter_03_riser_cable_variant`
("... Compatible with RTX 4090" riser-cable titles) remain pre-existing, already-documented
`decision_type_allowed` failures - they take a different code path (their "riser cable" phrasing is
not currently recognized as a `product_type_term`) and are unaffected by this narrow correction.

## Verification

```
python -m pytest -q             -> 920 passed
python -m ruff check .          -> All checks passed!
python -m ruff format --check . -> 186 files already formatted
python -m mypy src               -> Success: no issues found in 104 source files
```

Dataset, benchmark report, and release manifest regenerated from a clean checkout via
`python scripts/gen_pue_benchmark_dataset.py` and `python scripts/gen_pue_release_v0_1_0.py`;
verified via `python scripts/verify_pue_release.py data/pue/releases/pue-v0.1.0.json`.

**Release gate on the real dataset is honestly `True`** — following item 9's root-cause fix, every
release-gate check (including `every_abstention_classified_justified_or_avoidable`) genuinely
passes with no remaining known gaps.

Not merged; Sprint 4 not started.
