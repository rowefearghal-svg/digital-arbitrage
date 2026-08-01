# PUE GPU Release Benchmark Report

- **Dataset:** gpu-release-benchmark-v0.1 (benchmark version gpu-release-benchmark-0.1.0)
- **Dataset file hash (sha256):** `c30c4e547c3bbd9f0a3c7d5ed6799ffc380e2ea2403bea816873d5127c384aa7`
- **Generated:** 2026-08-01T19:36:27.412294
- **Capability version:** pue-0.1.0
- **Policy version:** gpu-policy-0.1.0
- **Knowledge version:** gpu-seed-0.1.0
- **Schema version:** 0.1
- **Total cases:** 118 (102 correct)

## Release gate: PASS

| Gate check | Result | Detail |
|---|---|---|
| all_mandatory_acceptance_cases_pass | PASS | pytest -q tests/pue/test_acceptance.py tests/pue/test_golden.py tests/pue/test_invariants.py -> exit code 0 |
| zero_accessory_to_complete_product_errors | PASS | 0 case(s): [] |
| zero_packaging_to_complete_product_errors | PASS | 0 case(s): [] |
| retrieval_and_decision_quality_reported_independently | PASS | candidate_recall_at_1/5/10=['36/37', '36/37', '36/37']; exact/hierarchical_identification_accuracy=['11/11', '13/13'] |
| every_wrong_decision_has_a_traceable_failure_stage | PASS | untraced: [] |
| every_abstention_classified_justified_or_avoidable | PASS | unclassified: [] |
| every_harmful_result_individually_listed | PASS | 0 harmful case(s) - zero-count trivially satisfies adjudication. |
| deterministic_replay_equivalent | PASS | release-replay-verify-00000001: equivalent=True; release-replay-verify-00000043: equivalent=True; release-replay-verify-00000078: equivalent=True |
| no_commercial_data_in_product_identity_reasoning | PASS | Structural invariant enforced by tests/pue/test_invariants.py::test_invariant_no_commercial_fields (no price/profit/ROI field ever read by pue/claims.py, pue/evaluation.py, or pue/decisions.py); verified by the same mandatory-acceptance pytest run above. |
| versions_identified_in_manifest | PASS | {'capability_version': 'pue-0.1.0', 'policy_version': 'gpu-policy-0.1.0', 'knowledge_version': 'gpu-seed-0.1.0', 'schema_version': '0.1'} |

## Product metrics

| Metric | Value | n / N (excluded) |
|---|---:|---:|
| product_form_accuracy | 1.0 | 48/48 (0) |
| exact_identification_accuracy | 1.0 | 11/11 (0) |
| hierarchical_identification_accuracy | 1.0 | 13/13 (0) |
| candidate_recall_at_1 | 0.973 | 36/37 (7) |
| candidate_recall_at_5 | 0.973 | 36/37 (7) |
| candidate_recall_at_10 | 0.973 | 36/37 (7) |
| harmful_false_match_rate | 0.0 | 0/2 (0) |
| accessory_to_complete_product_error_rate | 0.0 | 0/29 (0) |
| packaging_to_complete_product_error_rate | 0.0 | 0/6 (0) |
| partial_identification_correctness | 0.8167 | 49/60 (0) |
| abstention_rate | 0.0169 | 2/118 (0) |
| avoidable_abstention_rate | 0.0 | 0/2 (0) |
| comparability_accuracy | 0.8667 | 65/75 (0) |
| explanation_faithfulness | 1.0 | 118/118 (0) |

## Pipeline metrics

- **evidence_precision:** None (0/0)
- **forbidden_evidence_violation_rate:** 0.0 (0/9)
- **evidence_recall:** 1.0 (30/30)
- **claim_support_correctness:** 1.0 (1/1)
- **correct_hypothesis_inclusion_rate:** 1.0 (35/35)
- **hard_contradiction_detection_rate:** 1.0 (3/3)
- **classifier_pue_disagreement_rate:** 0.8364 (46/55)
- **candidate_count_mean / median:** 6.39 / 10.0
- **decision_distribution:** {'partially_identified': 59, 'identified': 11, 'classified': 28, 'ambiguous': 5, 'outside_supported_domain': 12, 'abstained': 2, 'processing_failed': 1}

## Operational metrics

- **listings_per_second:** 1304.822
- **median_latency_ms:** 0.5531
- **p95_latency_ms:** 1.3967
- **mean_extraction_ms:** 0.1481
- **mean_retrieval_ms:** 0.221
- **mean_evaluation_ms:** 0.1343
- **mean_decision_explanation_ms:** 0.0528
- **mean_persistence_ms:** None
- **technical_failure_rate:** 0.0085 (1/118)
- **mean_reasoning_record_json_bytes:** 17899.822

## Classifier vs PUE differential

- **total_compared:** 55
- **classifier_gradable:** 45
- **classifier_ungradable:** 10
- **both_correct:** 41
- **both_wrong:** 0
- **pue_corrects_classifier:** 0
- **classifier_correct_pue_worsens:** 4
- **pue_appropriately_abstains:** 0
- **pue_avoidably_abstains:** 0
- **pue_prevents_harmful_comparability:** 0
- **product_form_disagreements:** 0
- **identity_specificity_differences:** 51
- **classifier_declined_pue_classified:** 4

## Error taxonomy counts

| Category | Count |
|---|---:|
| observation_failure | 0 |
| evidence_failure | 0 |
| claim_failure | 0 |
| hypothesis_failure | 0 |
| retrieval_failure | 1 |
| knowledge_failure | 1 |
| evaluation_failure | 0 |
| decision_policy_failure | 14 |
| explanation_failure | 0 |
| runtime_failure | 0 |

## Harmful results (individually reviewed)

_None._

## Wrong / avoidably-abstaining case failures

| Case ID | Primary | Secondary | Explanation |
|---|---|---|---|
| bracket_02_riser_cable | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| not_included_01_case_only | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| compat_02_cooler_compatible | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| bundle_02_rtx4090_with_waterblock | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| bundle_03_gpu_and_riser | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| abstain_01_contradiction | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| misleading_01_mousepad | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| misleading_02_tshirt | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| mobile_04_amd_rx7900m | retrieval_failure |  | An acceptable Candidate exists in the knowledge base but was never retrieved for this case. |
| adapter_03_riser_cable_variant | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| not_included_03_manual_only | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| bundle_05_two_cards | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| gap_05_rtx4090ti | knowledge_failure |  | Gold-labelled catalogue gap (no acceptable Candidate exists in the tested knowledge version 'gpu-seed-0.1.0'); the wrong/avoidable outcome traces to missing knowledge coverage, not a retrieval or evaluation defect. |
| abstain_03_two_families_conflict | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| misleading_03_keychain | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
| misleading_04_sticker_decal | decision_policy_failure |  | Decision Formation reached a gold-disallowed outcome despite an otherwise-unremarkable reasoning trace. |
