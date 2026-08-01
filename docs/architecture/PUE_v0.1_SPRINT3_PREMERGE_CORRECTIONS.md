# PUE v0.1 Sprint 3 — Pre-Merge Benchmark Integrity Corrections

Companion to `docs/architecture/PUE_v0.1_SPRINT3_BENCHMARK_REPORT.md` (unchanged narrative sections remain valid). This document records the six pre-merge integrity corrections applied on `feature/pue-v0.1-sprint3` before merge, the real evidence each now produces, and the corrected metrics.

## 1. Release-gate evidence is now real, not hardcoded

`src/digital_arbitrage/pue/release_pipeline.py` (new module) replaces the previous hardcoded `mandatory_acceptance_pass=True, replay_equivalent=True`:

- `verify_mandatory_acceptance()` actually runs `python -m pytest -q tests/pue/test_acceptance.py tests/pue/test_golden.py tests/pue/test_invariants.py` as a subprocess and returns the real exit code + output tail. `test_invariants.py` (the structural no-commercial-data check) is included, so `no_commercial_data_in_product_identity_reasoning` is now derived from the same real, executed evidence rather than an independent hardcoded `True`.
- `verify_replay_equivalence()` actually persists 3 sample listings through the real orchestration path into a throwaway SQLite database, then replays each through the real, unmodified `pue/replay.py::replay_case` and requires every one to report `equivalent=True`.
- `versions_identified_in_manifest` is now derived by checking the four version strings are actually non-empty, not hardcoded `True`.
- `run_release_pipeline()` raises `PueValidationError` **before running the benchmark or writing anything** if either check fails.

Real evidence from the current release (`data/pue/releases/pue-v0.1.0_benchmark_report.json`):

```
all_mandatory_acceptance_cases_pass: "pytest -q tests/pue/test_acceptance.py tests/pue/test_golden.py tests/pue/test_invariants.py -> exit code 0"
deterministic_replay_equivalent: "release-replay-verify-00000001: equivalent=True; release-replay-verify-00000043: equivalent=True; release-replay-verify-00000078: equivalent=True"
```

**Negative tests** (`tests/pue/test_release_pipeline.py`) prove generation fails on real evidence, not a flag:
- `test_run_release_pipeline_refuses_when_acceptance_fails` — an injected pytest-subprocess-replacement returning a real failing exit code causes a real `PueValidationError`.
- `test_run_release_pipeline_refuses_when_replay_fails` — a genuinely different `replay_policy` forces a real version mismatch through the actual, unmodified `replay_case` code path, causing a real `PueValidationError`.

## 2. Classifier/PUE differential is now gold-grounded, not agreement-based

`benchmark_metrics.classifier_gold_correct(case, classifier_label)` grades the classifier independently against the benchmark's gold labels — product-form bucket (complete vs. accessory/part) and declined/non-declined semantics (misleading-similarity/unsupported-domain cases must be `REJECTED`/`UNKNOWN`) — never `ComparisonCategory.AGREEMENT`, which only describes an observable difference (see `comparison.py`'s own docstring: "None of the categories claim correctness").

`DifferentialMetrics` now reports `both_correct`, `both_wrong`, `pue_corrects_classifier`, `classifier_correct_pue_worsens` from **independent** gold grading of each system, plus `classifier_gradable`/`classifier_ungradable` (cases with no clear classifier-gradable judgment, e.g. packaging/bundle, are excluded from every quadrant rather than silently counted).

**Constructed tests** (`tests/pue/test_classifier_differential.py`) prove all 5 required scenarios, each built by taking one real `CaseResult` and replacing only `comparison.category`/`classifier_label`/`correct` — never re-deriving correctness from the category itself:
1. `test_scenario_both_agree_and_both_wrong` — `category=AGREEMENT`, both graded wrong.
2. `test_scenario_both_agree_and_both_correct` — `category=AGREEMENT`, both graded correct.
3. `test_scenario_pue_corrects_classifier` — classifier wrong, PUE correct.
4. `test_scenario_classifier_correct_pue_worsens` — classifier correct, PUE wrong.
5. `test_scenario_both_differ_and_both_wrong` — `category=PRODUCT_FORM_DISAGREEMENT`, both graded wrong.

Real result on the corrected dataset: **`both_wrong: 0`**, `both_correct: 42`, `pue_corrects_classifier: 5`, `classifier_correct_pue_worsens: 4`, out of `classifier_gradable: 51` (of `total_compared: 117`; `classifier_ungradable: 66`).

## 3. Identity metrics now use the Decision's selection, never Candidate rank

`CaseResult` gained two fields computed once in `evaluate_case`:
- `selected_product_id` — the catalogue_product_id of the Candidate the Decision actually **selected**.
- `identification_hierarchy_correct` — level-in-gold-set **and** (when the level implies a specific identity) selection-is-acceptable; independent of unrelated checks (evidence count, hard-rejected-candidate assertions).

`exact_identification_accuracy` and `hierarchical_identification_accuracy` in `benchmark_report.py` now read these fields; `top_acceptable_rank` (retrieval rank) is used **only** by `candidate_recall_at_k`.

**Regression test** (`tests/pue/test_identity_metrics.py::test_selecting_a_different_candidate_at_the_same_retrieval_rank_is_incorrect`): takes a real exact-identification case whose acceptable Candidate is retrieved at rank 1, tampers `decision.selected_candidate_instance_id` to point at a *different*, retrieved-but-not-acceptable Candidate, and proves `top_acceptable_rank == 1` while `correct is False` and `identification_hierarchy_correct is False` — the old rank-based metric would have wrongly scored this case correct.

Real (untampered) result: `exact_identification_accuracy: 11/11`, `hierarchical_identification_accuracy: 13/13` — unchanged from before the fix, confirming the bug never manifested on the real dataset, only on the constructed regression case.

## 4. Cross-platform canonical hashing, immutability, and reproducibility

- `pue/canonical.py` (new): `canonical_json_hash`/`canonical_file_hash` parse JSON and re-serialize with sorted keys and no incidental whitespace before hashing — immune to CRLF/LF conversion, editor whitespace, and key reordering.
- `benchmark.dataset_file_hash` and `catalogue.catalogue_file_hash` both now use canonical hashing (previously raw `path.read_bytes()`).
- `benchmark_report.canonical_report_hash`/`report_semantic_dict` hash the report **excluding** `generated_at` (timestamp) and `operational_metrics` (real wall-clock timing) — the only two sections expected to vary between two otherwise-identical regenerations.
- `ReleaseManifest` gained `release_report_hash` (required field).
- `release_pipeline.generate_release_artifacts()` checks **all three** target paths for existence **before writing anything** — a report is never written and then the manifest save fails separately; refusal is atomic across all targets (`tests/pue/test_release_pipeline.py::test_generate_release_artifacts_refuses_if_report_already_exists_without_touching_manifest`).
- `release_pipeline.verify_release_reproducibility()` regenerates a release (optionally into a fresh temp directory via `output_dir`), and checks: `policy_code_git_commit` equals the exact running commit; dataset/catalogue canonical hashes match; the regenerated report's canonical hash matches `release_report_hash`; and (given `committed_report_path`) the regenerated report's semantic content is byte-for-byte identical to the committed report's. `scripts/verify_pue_release.py` and `arb pue release-verify` expose this.
- Reproducibility required making the benchmark run itself deterministic end-to-end: `run_release_pipeline` uses a new production-side `DeterministicSequentialIdFactory` + fixed clock (not a test fixture) for both the benchmark run and the replay-verification sample, so every id in the resulting report — including the replay-evidence detail string — is identical across regenerations.

**Verified from a clean state** (`python scripts/gen_pue_release_v0_1_0.py` then `python scripts/verify_pue_release.py data/pue/releases/pue-v0.1.0.json`):

```
[PASS] policy_code_git_commit_matches_running_code
[PASS] benchmark_dataset_hash_matches
[PASS] catalogue_file_hash_matches
[PASS] release_report_hash_matches
[PASS] release_gate_passed_matches
[PASS] semantic_report_content_matches_committed_report
verification: PASS
```

Cross-process reproducibility was also confirmed directly: two independent Python processes running `run_release_pipeline` produced byte-identical `release_report_hash` values.

**Inherent self-reference note:** a release manifest's `policy_code_git_commit` necessarily references the commit that contains the code/dataset/catalogue it measured, not the (later) commit that adds the manifest file itself - a file cannot embed the hash of the commit it is part of. This repository therefore commits the manifest as a small follow-up commit referencing its parent (documented in that commit's message). Verifying against literal `HEAD` after that follow-up commit correctly reports a `policy_code_git_commit` mismatch (by exactly one commit) while every content/hash/semantic-content check still passes; verifying at the manifest's own referenced parent commit passes all 6 checks. This is a structural property of self-referential provenance stamping, not a defect in the verification logic - the tool's job (catching a manifest that claims a *different, wrong* commit's code produced it) is unaffected.

## 5. Metric truthfulness and benchmark coverage

- **Evidence precision** (`compute_pipeline_metrics`) no longer reports `1.0` from an unlabelled-false-positive denominator. `BenchmarkCase` gained `forbidden_evidence_types` (a genuine *negative* evidence label — "this evidence type must NOT appear"). Applied to 9 cases where it is structurally guaranteed to be safe (domain cases must never extract `product_family_token`; misleading-similarity titles never contain a real dash-shaped MPN, so `mpn_token` is forbidden). Evidence precision is now genuinely computed: **`20/20 = 1.0`** (previously `null`/unavailable).
- **`expected_comparability`** gold labels were derived from `pue/decisions.py`'s own deterministic, unconditional branches (documented rule table in `scripts/gen_pue_benchmark_dataset.py`) — never from current output — and applied wherever a case's declared `allowed_decision_types`/`expected_product_form` combination resolves unambiguously. Comparability coverage grew from 2 labelled cases to **66**, covering: complete-vs-complete (`directly_comparable`/`comparable_at_broader_level`), complete-vs-accessory/component/replacement-part (`not_comparable_product_form`), complete-vs-packaging (`not_comparable_product_form`), complete-vs-bundle (`not_comparable_bundle`), catalogue-gap (all three code-legitimate outcomes), and misleading-similarity merchandise (`not_comparable_product_form` — the ground-truth-correct answer, which these cases currently fail, exactly matching the already-documented residual risk).
- **Avoidable-abstention coverage**: `exact_02_asus_tuf_rtx4090` (a confident, MPN-bearing exact match) now asserts `avoidable_if_abstained=true` — if this case ever abstains, that is a real regression, not a safe default. Denominator went from `0` (`null`) to `1`; result `0/1` (no abstention occurred).
- **Harmful-false-match coverage**: `mobile_01_rtx4090_laptop_gpu` and `mobile_04_amd_rx7900m` now assert `harmful_false_match` against their existing `forbidden_catalogue_product_ids` (a laptop GPU falsely matched to a specific desktop SKU is a genuinely harmful, not merely wrong, outcome). Denominator went from `0` to `2`; result `0/2`.
- **Claim-correctness coverage**: `conflict_01_title_structured` now asserts `require_contradicted_claim=true` (a title/structured-attribute family conflict is exactly what `decisions.py`'s `contradicted_family_claims` check targets). Result `1/1 = 1.0`.
- **`expected_product_form=incomplete_product`** added to 4 damage/for-parts cases verified to consistently produce that form (one similarly-worded case, `damaged_03`, was left unlabelled since its behaviour genuinely differs and forcing a label would not be honest).

**No labels were changed to fit current output.** Re-running the full 118-case benchmark after every label addition produced the **same 13 wrong cases, by name, as before** (`bracket_02_riser_cable`, `not_included_01/03`, `compat_01/02`, `abstain_01/03`, `misleading_01–04`, `mobile_04_amd_rx7900m`, `adapter_03_riser_cable_variant`) — the stronger labels added diagnostic detail (e.g. `expected_comparability` now also fails on `misleading_01–04` and `abstain_01/03`) to the *same* already-documented residual risks, never a new failure. Total correct: **105/118 (89.0%)**, unchanged.

## 6. Performance diagnostic: bounded latency reservoir, honest memory claim

`pue/performance.py`:
- Replaced the unbounded `latencies_ms: list[float]` (which itself grew O(N) with `count`, confounding the very memory-growth measurement it existed to validate) with a fixed-size (`_MAX_LATENCY_SAMPLES = 2000`), deterministically-seeded reservoir sample. `median_latency_ms`/`p95_latency_ms` are now explicitly documented as reservoir estimates; `latency_sample_size` reports how many observations they are based on.
- The prior conclusion ("checkpoints show roughly linear, non-re-accelerating growth, therefore memory is bounded") was logically backwards — that growth pattern was substantially explained by the diagnostic's own list, not the reasoning pipeline. `possible_memory_growth` now compares only checkpoints taken **after** the reservoir stops growing, flagging (not asserting away) sustained growth beyond a 1.5x ratio as a genuine signal worth investigating.

New tests (`tests/pue/test_performance_diagnostic.py`): bounded sample size for a 5,000-listing run, deterministic reservoir behaviour, and that the growth flag is computed only from post-fill checkpoints.

## Complete CI results

```
python -m pytest -q            -> 916 passed
python -m ruff check .         -> All checks passed!
python -m ruff format --check . -> 183 files already formatted
python -m mypy src              -> Success: no issues found in 104 source files
```

## Not merged

This branch (`feature/pue-v0.1-sprint3`) remains unmerged, per instructions. Sprint 4 was not started.
