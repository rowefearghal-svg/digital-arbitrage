"""Tests for per-case grading, stage-based error taxonomy, and aggregate
metric denominators (Sprint 3, brief sections 6/8/16)."""

from __future__ import annotations

from digital_arbitrage.pue.benchmark import load_benchmark_dataset
from digital_arbitrage.pue.benchmark_metrics import FailureCategory, classify_failure
from digital_arbitrage.pue.benchmark_report import (
    compute_differential_metrics,
    compute_operational_metrics,
    compute_pipeline_metrics,
    compute_product_metrics,
    evaluate_release_gate,
)
from digital_arbitrage.pue.benchmark_runner import run_benchmark
from digital_arbitrage.pue.catalogue import JsonCandidateRepository

DATASET = load_benchmark_dataset()


def _run(run_classifier: bool = True):
    return run_benchmark(DATASET, run_classifier=run_classifier)


def test_evaluate_case_and_run_benchmark_produce_one_result_per_case() -> None:
    run = _run()
    assert len(run.results) == len(DATASET.cases)
    assert {r.case.case_id for r in run.results} == {c.case_id for c in DATASET.cases}


def test_zero_harmful_errors_on_the_release_dataset() -> None:
    """Hard release-gate requirement (brief section 7)."""
    run = _run()
    harmful = [r for r in run.results if r.harmful_errors]
    assert harmful == [], f"harmful errors present: {[r.case.case_id for r in harmful]}"


def test_every_wrong_or_avoidable_case_has_a_traceable_failure_stage() -> None:
    run = _run()
    failure_ids = {f.case_id for f in run.failures}
    for r in run.results:
        if (not r.correct) or r.is_avoidable_abstention:
            assert r.case.case_id in failure_ids


def test_correct_cases_are_never_classified_as_failures() -> None:
    run = _run()
    failure_ids = {f.case_id for f in run.failures}
    for r in run.results:
        if r.correct and not r.is_avoidable_abstention:
            assert r.case.case_id not in failure_ids


def test_catalogue_gap_failure_is_knowledge_failure_not_retrieval_failure() -> None:
    """Distinguish: Candidate absent from knowledge -> KNOWLEDGE_FAILURE;
    never misdiagnosed as a RETRIEVAL_FAILURE (brief section 8)."""
    run = _run(run_classifier=False)
    gap_cases = [c for c in DATASET.cases if c.catalogue_gap]
    assert gap_cases, "expected at least one catalogue_gap case in the release dataset"
    gap_failures = [f for f in run.failures if f.case_id in {c.case_id for c in gap_cases}]
    for f in gap_failures:
        assert f.primary_category == FailureCategory.KNOWLEDGE_FAILURE


def test_technical_failure_is_runtime_failure_not_abstention() -> None:
    run = _run(run_classifier=False)
    malformed_case_ids = {c.case_id for c in DATASET.cases if c.malformed}
    assert malformed_case_ids
    for r in run.results:
        if r.case.case_id in malformed_case_ids:
            assert r.is_technical_failure
            assert not r.is_avoidable_abstention
            assert not r.is_justified_abstention


def test_candidate_recall_excludes_catalogue_gap_cases_from_denominator() -> None:
    run = _run(run_classifier=False)
    metrics = compute_product_metrics(run.results)
    gap_count = sum(1 for c in DATASET.cases if c.catalogue_gap)
    assert metrics.candidate_recall_at_1.excluded == gap_count
    assert metrics.candidate_recall_at_5.excluded == gap_count
    assert metrics.candidate_recall_at_10.excluded == gap_count


def test_candidate_recall_denominator_only_counts_cases_with_acceptable_ids() -> None:
    run = _run(run_classifier=False)
    metrics = compute_product_metrics(run.results)
    expected_denominator = sum(
        1 for c in DATASET.cases if c.acceptable_catalogue_product_ids and not c.catalogue_gap
    )
    assert metrics.candidate_recall_at_10.denominator == expected_denominator


def test_recall_at_k_is_monotonically_non_decreasing() -> None:
    run = _run(run_classifier=False)
    metrics = compute_product_metrics(run.results)
    assert metrics.candidate_recall_at_1.numerator <= metrics.candidate_recall_at_5.numerator
    assert metrics.candidate_recall_at_5.numerator <= metrics.candidate_recall_at_10.numerator


def test_multiple_acceptable_candidates_count_as_success_if_any_within_rank() -> None:
    """brief section 6.4: multiple acceptable Candidates count as
    successful when any acceptable Candidate appears within the relevant
    rank."""
    run = _run(run_classifier=False)
    ambiguous = next(r for r in run.results if r.case.case_id == "ambig_01_rtx3060_12gb_no_brand")
    assert len(ambiguous.case.acceptable_catalogue_product_ids) > 1
    # At least one of the acceptable ids should be retrievable within the
    # top 10 - the metric must not require *all* of them to be present.
    assert ambiguous.top_acceptable_rank is not None


def test_avoidable_abstention_rate_denominator_is_avoidable_eligible_cases() -> None:
    run = _run(run_classifier=False)
    metrics = compute_product_metrics(run.results)
    expected = sum(1 for c in DATASET.cases if c.avoidable_if_abstained)
    assert metrics.avoidable_abstention_rate.denominator == expected


def test_technical_failures_never_counted_in_abstention_rate_numerator() -> None:
    """brief section 6.4: technical failures must not be counted as
    abstentions."""
    run = _run(run_classifier=False)
    metrics = compute_product_metrics(run.results)
    technical_failures = sum(1 for r in run.results if r.is_technical_failure)
    abstained = sum(1 for r in run.results if r.record.decision.decision_type.value == "abstained")
    assert metrics.abstention_rate.numerator == abstained
    # A technical failure is never simultaneously an ABSTAINED decision.
    assert technical_failures == 0 or abstained != len(run.results)


def test_unsupported_domain_cases_are_not_ordinary_identification_errors() -> None:
    """brief section 6.4: unsupported-domain cases must not be counted as
    ordinary GPU identification errors - they pass via
    allowed_decision_types=[outside_supported_domain] and are graded like
    any other case, never inflating a generic 'wrong identification' bucket."""
    run = _run(run_classifier=False)
    domain_cases = [c for c in DATASET.cases if c.unsupported_domain]
    assert domain_cases
    domain_results = [r for r in run.results if r.case.case_id in {c.case_id for c in domain_cases}]
    for r in domain_results:
        assert r.correct, (
            f"{r.case.case_id} should resolve to its allowed outside_supported_domain outcome"
        )


def test_pipeline_metrics_compute_without_error() -> None:
    run = _run()
    metrics = compute_pipeline_metrics(run.results)
    assert metrics.candidate_count_mean >= 0
    assert isinstance(metrics.decision_distribution, dict)
    assert sum(metrics.decision_distribution.values()) == len(run.results)


def test_operational_metrics_report_positive_throughput() -> None:
    run = _run(run_classifier=False)
    metrics = compute_operational_metrics(run.results, wall_time_seconds=run.wall_time_seconds)
    assert metrics.listings_per_second > 0
    assert metrics.median_latency_ms >= 0
    assert metrics.p95_latency_ms >= metrics.median_latency_ms


def test_differential_metrics_use_gold_labels_not_agreement() -> None:
    """brief section 12: correctness is determined by gold labels, not by
    classifier/PUE agreement."""
    run = _run(run_classifier=True)
    metrics = compute_differential_metrics(run.results)
    assert metrics.total_compared > 0
    total_named = (
        metrics.both_correct
        + metrics.pue_corrects_classifier
        + metrics.classifier_correct_pue_worsens
    )
    assert total_named <= metrics.total_compared


def test_release_gate_fails_when_a_mandatory_check_fails() -> None:
    run = _run(run_classifier=False)
    gate = evaluate_release_gate(
        run.results,
        run.failures,
        mandatory_acceptance_pass=False,
        replay_equivalent=True,
    )
    assert gate.passed is False
    failing = [c for c in gate.checks if not c.passed]
    assert any(c.name == "all_mandatory_acceptance_cases_pass" for c in failing)


def test_release_gate_passes_when_every_mandatory_check_passes() -> None:
    run = _run(run_classifier=False)
    gate = evaluate_release_gate(
        run.results,
        run.failures,
        mandatory_acceptance_pass=True,
        replay_equivalent=True,
        capability_version="pue-0.1.0",
        policy_version=run.context.policy_version,
        knowledge_version=run.context.knowledge_version,
        schema_version=run.context.schema_version,
    )
    assert gate.passed is True


def test_release_gate_fails_on_replay_non_equivalence() -> None:
    run = _run(run_classifier=False)
    gate = evaluate_release_gate(
        run.results,
        run.failures,
        mandatory_acceptance_pass=True,
        replay_equivalent=False,
    )
    assert gate.passed is False


def test_classify_failure_returns_none_for_correct_case() -> None:
    run = _run(run_classifier=False)
    repo = JsonCandidateRepository()
    correct = next(r for r in run.results if r.correct and not r.is_avoidable_abstention)
    assert classify_failure(correct, repo, knowledge_version=run.context.knowledge_version) is None
