# PUE test fixtures

## `sprint1_acceptance_v0.1.json`

The 25 mandatory acceptance cases from
`docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md` section 21,
driven by `tests/pue/test_acceptance.py`. Each case is a JSON object with:

| Field | Meaning |
|---|---|
| `case_id` | Stable identifier, also used as the pytest parametrize id. |
| `title` | The (raw) listing title. `null` + `"malformed": true` for case 25. |
| `structured_attributes` | Optional `raw_attributes` dict (e.g. a conflicting `model`). |
| `allowed_decision_types` | Decision types considered a pass. |
| `forbidden_decision_types` | Decision types that must never occur. |
| `forbidden_product_forms` / `expected_product_form` | Product-form assertions. |
| `expected_identification_levels` / `expected_comparability` | Optional exact-match assertions. |
| `expected_abstention_reason` | Required when the case must abstain for a specific reason. |
| `expected_catalogue_product_id` / `forbidden_selected_catalogue_product_ids` | Exact-identity assertions. |
| `required_evidence_types` | Evidence types that must appear (intermediate-reasoning check). |
| `require_hard_rejected_candidate` / `require_contradicted_claim` | Structural reasoning checks beyond the final label. |
| `min_evidence_count` | Sanity floor on the reasoning trace. |
| `difficulty`, `annotation_source`, `annotation_confidence` | Benchmark labelling metadata (spec section 20.3). |

Every case asserts more than the final Decision label, per spec section 21's
closing requirement ("tests must assert not only the final Decision but also
key Evidence, Claims and Candidate contradictions").

## `golden/*.json`

Five complete, serialized `ReasoningRecord`s with deterministic ids/times
(spec section 23.3), covering `IDENTIFIED`, `PARTIALLY_IDENTIFIED`,
`CLASSIFIED`, `ABSTAINED`, and `OUTSIDE_SUPPORTED_DOMAIN`. Regenerate with
`python scripts/gen_pue_golden.py` only after a deliberate, reviewed behavior
change, and review the diff carefully - see `tests/pue/test_golden.py`.
