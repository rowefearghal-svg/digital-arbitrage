"""Tests for exact/hierarchical identification metrics (Sprint 3 pre-merge
correction item 3): correctness must be computed from the Decision's
*selected* Candidate, never from Candidate recall's retrieval rank - a
Candidate can be retrieved at rank 1 and still not be the one selected."""

from __future__ import annotations

import dataclasses

from digital_arbitrage.pue.benchmark import load_benchmark_dataset
from digital_arbitrage.pue.benchmark_metrics import evaluate_case
from digital_arbitrage.pue.benchmark_report import compute_product_metrics
from digital_arbitrage.pue.benchmark_runner import run_benchmark
from digital_arbitrage.pue.enums import IdentificationLevel

DATASET = load_benchmark_dataset()
_RUN = run_benchmark(DATASET, run_classifier=False)


def _exact_case_result_with_multiple_candidates():
    """A real exact-identification result whose retrieval surfaced more
    than one Candidate (so a "different selection at the same rank-1
    retrieval" scenario is constructible)."""
    for r in _RUN.results:
        if (
            r.case.acceptable_catalogue_product_ids
            and "exact_catalogue_product" in set(r.case.expected_identification_levels)
            and r.record.decision.identification_level
            == IdentificationLevel.EXACT_CATALOGUE_PRODUCT
            and len(r.record.candidates) > 1
        ):
            return r
    raise AssertionError("no exact-identification case with >1 retrieved candidate found")


def test_acceptable_candidate_retrieved_at_rank_1_is_a_precondition() -> None:
    base = _exact_case_result_with_multiple_candidates()
    assert base.top_acceptable_rank == 1


def test_selecting_a_different_candidate_at_the_same_retrieval_rank_is_incorrect() -> None:
    """The core regression: rank-1 retrieval must never be conflated with
    a correct selection."""
    base = _exact_case_result_with_multiple_candidates()
    acceptable_ids = set(base.case.acceptable_catalogue_product_ids)
    other_candidate = next(
        c for c in base.record.candidates if c.catalogue_product_id not in acceptable_ids
    )

    tampered_decision = dataclasses.replace(
        base.record.decision,
        selected_candidate_instance_id=other_candidate.candidate_instance_id,
    )
    tampered_record = dataclasses.replace(base.record, decision=tampered_decision)

    result = evaluate_case(base.case, tampered_record)

    # Retrieval rank is unaffected - the acceptable Candidate is still
    # retrieved at rank 1 - but the *selection* is wrong.
    assert result.top_acceptable_rank == 1
    assert result.selected_product_id == other_candidate.catalogue_product_id
    assert result.selected_product_id not in acceptable_ids
    assert result.correct is False
    assert result.identification_hierarchy_correct is False


def test_exact_identification_accuracy_uses_selection_not_rank() -> None:
    base = _exact_case_result_with_multiple_candidates()
    acceptable_ids = set(base.case.acceptable_catalogue_product_ids)
    other_candidate = next(
        c for c in base.record.candidates if c.catalogue_product_id not in acceptable_ids
    )
    tampered_decision = dataclasses.replace(
        base.record.decision,
        selected_candidate_instance_id=other_candidate.candidate_instance_id,
    )
    tampered_record = dataclasses.replace(base.record, decision=tampered_decision)
    tampered_result = evaluate_case(base.case, tampered_record)

    metrics_correct = compute_product_metrics([base])
    metrics_tampered = compute_product_metrics([tampered_result])

    assert metrics_correct.exact_identification_accuracy.numerator == 1
    # Same case, same retrieval rank, only the selection differs - the
    # metric must flip to 0, proving it is not rank-derived.
    assert metrics_tampered.exact_identification_accuracy.numerator == 0
    assert metrics_tampered.exact_identification_accuracy.denominator == 1


def test_hierarchical_identification_accuracy_uses_selection_not_rank() -> None:
    base = _exact_case_result_with_multiple_candidates()
    acceptable_ids = set(base.case.acceptable_catalogue_product_ids)
    other_candidate = next(
        c for c in base.record.candidates if c.catalogue_product_id not in acceptable_ids
    )
    tampered_decision = dataclasses.replace(
        base.record.decision,
        selected_candidate_instance_id=other_candidate.candidate_instance_id,
    )
    tampered_record = dataclasses.replace(base.record, decision=tampered_decision)
    tampered_result = evaluate_case(base.case, tampered_record)

    metrics_tampered = compute_product_metrics([tampered_result])
    assert metrics_tampered.hierarchical_identification_accuracy.numerator == 0
    assert metrics_tampered.hierarchical_identification_accuracy.denominator == 1


def test_hierarchical_accuracy_ignores_unrelated_checks() -> None:
    """A case failing an unrelated check (e.g. min_evidence_count) but with
    a correct identification level/selection must still count as
    hierarchically correct - the metric is scoped to identity, not overall
    correctness."""
    base = _exact_case_result_with_multiple_candidates()
    # Force an unrelated check to fail by inflating the gold minimum
    # evidence count far beyond what any case produces.
    inflated_case = dataclasses.replace(base.case, min_evidence_count=10_000)
    result = evaluate_case(inflated_case, base.record)

    assert result.correct is False  # unrelated check now fails
    assert result.identification_hierarchy_correct is True  # identity itself is still right


def test_identification_hierarchy_correct_is_none_when_not_applicable() -> None:
    no_level_case = next(r for r in _RUN.results if not r.case.expected_identification_levels)
    assert no_level_case.identification_hierarchy_correct is None
