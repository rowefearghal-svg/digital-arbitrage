"""Aggregate metrics, release gate, differential evaluation, and report
rendering for the GPU release benchmark (Sprint 3, brief sections 6/7/12).

Every metric is a :class:`Metric` (numerator/denominator/value), never a
bare float, so the exact denominator rule that produced it (brief section
6.4) is always auditable from the report itself instead of being implicit.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from .benchmark import BenchmarkDataset, case_coverage_by_tag
from .benchmark_metrics import CaseFailure, CaseResult, FailureCategory
from .comparison import ComparisonCategory
from .enums import DecisionType


@dataclass(frozen=True, slots=True)
class Metric:
    """A ratio metric with an explicit, auditable denominator."""

    numerator: int
    denominator: int
    excluded: int = 0
    """Cases explicitly excluded from this metric's denominator (e.g.
    catalogue-gap cases excluded from Candidate recall) - reported
    separately so the exclusion itself is visible, not silent."""

    @property
    def value(self) -> float | None:
        return None if self.denominator == 0 else round(self.numerator / self.denominator, 4)

    def to_dict(self) -> dict:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "excluded": self.excluded,
            "value": self.value,
        }


def _metric(numerator: int, denominator: int, excluded: int = 0) -> Metric:
    return Metric(numerator=numerator, denominator=denominator, excluded=excluded)


# --------------------------------------------------------------------------- #
# 6.1 Product metrics
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ProductMetrics:
    product_form_accuracy: Metric
    exact_identification_accuracy: Metric
    hierarchical_identification_accuracy: Metric
    candidate_recall_at_1: Metric
    candidate_recall_at_5: Metric
    candidate_recall_at_10: Metric
    harmful_false_match_rate: Metric
    accessory_to_complete_product_error_rate: Metric
    packaging_to_complete_product_error_rate: Metric
    partial_identification_correctness: Metric
    abstention_rate: Metric
    avoidable_abstention_rate: Metric
    comparability_accuracy: Metric
    explanation_faithfulness: Metric

    def to_dict(self) -> dict:
        return {name: getattr(self, name).to_dict() for name in _PRODUCT_METRIC_NAMES}


_PRODUCT_METRIC_NAMES = tuple(ProductMetrics.__dataclass_fields__)


def compute_product_metrics(results: Sequence[CaseResult]) -> ProductMetrics:
    """Compute every product metric independently (brief 6.1: "do not
    publish only one overall accuracy number")."""
    total = len(results)

    # product_form_accuracy: over every case that asserted an expected form.
    form_cases = [r for r in results if r.case.expected_product_form is not None]
    form_correct = sum(
        1
        for r in form_cases
        if r.record.decision.product_form.value == r.case.expected_product_form
    )

    # exact identification accuracy: only cases with sufficient gold evidence
    # for exact identity (brief 6.4) - i.e. an explicit acceptable catalogue
    # product id and an EXACT_CATALOGUE_PRODUCT expectation. Correctness
    # requires the Decision's *selected* Candidate to be one of the
    # acceptable gold ids - retrieval rank is a separate, retrieval-only
    # signal (Candidate recall@k below), never a proxy for identification
    # correctness (Sprint 3 pre-merge correction item 3).
    exact_cases = [
        r
        for r in results
        if r.case.acceptable_catalogue_product_ids
        and "exact_catalogue_product" in set(r.case.expected_identification_levels)
    ]
    exact_correct = sum(
        1
        for r in exact_cases
        if r.record.decision.identification_level.value == "exact_catalogue_product"
        and r.selected_product_id in set(r.case.acceptable_catalogue_product_ids)
    )

    # hierarchical identification accuracy: any case with an expected
    # identification level - correct iff the achieved level is in the
    # gold-acceptable set *and*, when that level implies a specific
    # catalogue identity, the actually-selected Candidate is acceptable
    # (``CaseResult.identification_hierarchy_correct`` - computed once in
    # evaluate_case, independent of unrelated checks like evidence-count or
    # hard-rejected-candidate assertions that must not gate this metric).
    hier_cases = [r for r in results if r.identification_hierarchy_correct is not None]
    hier_correct = sum(1 for r in hier_cases if r.identification_hierarchy_correct)

    # Candidate recall@k: only where an acceptable Candidate exists in the
    # tested catalogue (brief 6.4: catalogue-gap cases excluded).
    recall_eligible = [
        r for r in results if r.case.acceptable_catalogue_product_ids and not r.case.catalogue_gap
    ]
    excluded_gap = sum(1 for r in results if r.case.catalogue_gap)

    def _recall_at(k: int) -> Metric:
        hits = sum(
            1
            for r in recall_eligible
            if r.top_acceptable_rank is not None and r.top_acceptable_rank <= k
        )
        return _metric(hits, len(recall_eligible), excluded=excluded_gap)

    # Harmful rates: denominator is every case that could have exhibited
    # that specific harmful kind (i.e. asserted it as forbidden); numerator
    # is how many actually did.
    def _harmful_rate(kind: str) -> Metric:
        eligible = [r for r in results if kind in r.case.forbidden_harmful_outcomes]
        hits = sum(1 for r in eligible if kind in r.harmful_errors)
        return _metric(hits, len(eligible))

    partial_cases = [r for r in results if "partially_identified" in r.case.allowed_decision_types]
    partial_correct = sum(
        1
        for r in partial_cases
        if r.record.decision.decision_type == DecisionType.PARTIALLY_IDENTIFIED and r.correct
    )

    abstainable_total = total
    abstained = sum(1 for r in results if r.record.decision.decision_type == DecisionType.ABSTAINED)
    avoidable_eligible = [r for r in results if r.case.avoidable_if_abstained]
    avoidable_hits = sum(1 for r in avoidable_eligible if r.is_avoidable_abstention)

    comparability_cases = [r for r in results if r.case.expected_comparability]
    comparability_correct = sum(
        1
        for r in comparability_cases
        if r.record.decision.comparability_status.value in set(r.case.expected_comparability)
    )

    # Explanation faithfulness: the explanation must reference the actual
    # decision it explains and never claim evidence that was not produced
    # (a purely structural faithfulness floor, consistent with
    # ReasoningRecord's own invariants - see tests/pue/test_explanations.py).
    faithful = sum(
        1
        for r in results
        if r.record.explanation.decision_id == r.record.decision.decision_id
        and set(r.record.explanation.evidence_ids) <= {e.evidence_id for e in r.record.evidence}
    )

    return ProductMetrics(
        product_form_accuracy=_metric(form_correct, len(form_cases)),
        exact_identification_accuracy=_metric(exact_correct, len(exact_cases)),
        hierarchical_identification_accuracy=_metric(hier_correct, len(hier_cases)),
        candidate_recall_at_1=_recall_at(1),
        candidate_recall_at_5=_recall_at(5),
        candidate_recall_at_10=_recall_at(10),
        harmful_false_match_rate=_harmful_rate("harmful_false_match"),
        accessory_to_complete_product_error_rate=_harmful_rate("accessory_to_complete_product"),
        packaging_to_complete_product_error_rate=_harmful_rate("packaging_to_complete_product"),
        partial_identification_correctness=_metric(partial_correct, len(partial_cases)),
        abstention_rate=_metric(abstained, abstainable_total),
        avoidable_abstention_rate=_metric(avoidable_hits, len(avoidable_eligible)),
        comparability_accuracy=_metric(comparability_correct, len(comparability_cases)),
        explanation_faithfulness=_metric(faithful, total),
    )


# --------------------------------------------------------------------------- #
# 6.2 Pipeline metrics
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PipelineMetrics:
    evidence_precision: Metric
    evidence_recall: Metric
    claim_support_correctness: Metric
    correct_hypothesis_inclusion_rate: Metric
    candidate_count_mean: float
    candidate_count_median: float
    hard_contradiction_detection_rate: Metric
    decision_distribution: dict[str, int]
    classifier_pue_disagreement_rate: Metric

    def to_dict(self) -> dict:
        return {
            "evidence_precision": self.evidence_precision.to_dict(),
            "evidence_recall": self.evidence_recall.to_dict(),
            "claim_support_correctness": self.claim_support_correctness.to_dict(),
            "correct_hypothesis_inclusion_rate": self.correct_hypothesis_inclusion_rate.to_dict(),
            "candidate_count_mean": self.candidate_count_mean,
            "candidate_count_median": self.candidate_count_median,
            "hard_contradiction_detection_rate": self.hard_contradiction_detection_rate.to_dict(),
            "decision_distribution": self.decision_distribution,
            "classifier_pue_disagreement_rate": self.classifier_pue_disagreement_rate.to_dict(),
        }


def compute_pipeline_metrics(results: Sequence[CaseResult]) -> PipelineMetrics:
    from .enums import ClaimStatus, ContradictionSeverity

    # Evidence recall: over cases with an explicit gold
    # required_evidence_types set (a positive label - "this evidence type
    # must appear").
    recall_cases = [r for r in results if r.case.required_evidence_types]
    ev_tp = ev_fn = 0
    for r in recall_cases:
        required = set(r.case.required_evidence_types)
        present = {e.evidence_type.value for e in r.record.evidence}
        ev_tp += len(required & present)
        ev_fn += len(required - present)
    evidence_recall = _metric(ev_tp, ev_tp + ev_fn)

    # Evidence precision: requires a genuine *negative* label - cases with
    # an explicit gold forbidden_evidence_types set ("this evidence type
    # must NOT appear"). Without any such label, there is no labelled
    # false-positive signal at all, and precision must be reported
    # unavailable (denominator 0 -> Metric.value is None) rather than
    # fabricated as 1.0 by conflating "no labelled false positives exist"
    # with "no false positives occurred" (Sprint 3 pre-merge correction
    # item 5).
    precision_cases = [r for r in results if r.case.forbidden_evidence_types]
    prec_tp = prec_fp = 0
    for r in precision_cases:
        forbidden = set(r.case.forbidden_evidence_types)
        present = {e.evidence_type.value for e in r.record.evidence}
        prec_fp += len(forbidden & present)
        # True positives for the precision denominator are every evidence
        # type actually produced on a precision-labelled case that was not
        # gold-forbidden - i.e. every produced evidence type not counted as
        # a false positive above.
        prec_tp += len(present - forbidden)
    evidence_precision = _metric(prec_tp, prec_tp + prec_fp)

    claim_cases = [r for r in results if r.case.require_contradicted_claim]
    claim_hits = sum(
        1 for r in claim_cases if any(c.status == ClaimStatus.CONTRADICTED for c in r.record.claims)
    )
    claim_support = _metric(claim_hits, len(claim_cases))

    hyp_cases = [r for r in results if r.case.expected_identified_family is not None]
    hyp_hits = sum(
        1
        for r in hyp_cases
        if any(
            (h.family or h.compatibility_target) == r.case.expected_identified_family
            for h in r.record.hypotheses
        )
    )
    hyp_inclusion = _metric(hyp_hits, len(hyp_cases))

    counts = [len(r.record.candidates) for r in results]
    mean_count = round(sum(counts) / len(counts), 3) if counts else 0.0
    sorted_counts = sorted(counts)
    median_count = 0.0
    if sorted_counts:
        mid = len(sorted_counts) // 2
        median_count = (
            float(sorted_counts[mid])
            if len(sorted_counts) % 2
            else (sorted_counts[mid - 1] + sorted_counts[mid]) / 2
        )

    contradiction_cases = [r for r in results if r.case.require_hard_rejected_candidate]
    contradiction_hits = sum(
        1
        for r in contradiction_cases
        if any(
            f.severity == ContradictionSeverity.HARD
            for ev in r.record.candidate_evaluations
            for f in ev.contradictions
        )
    )
    hard_contradiction_rate = _metric(contradiction_hits, len(contradiction_cases))

    distribution: dict[str, int] = {}
    for r in results:
        key = r.record.decision.decision_type.value
        distribution[key] = distribution.get(key, 0) + 1

    disagreement_eligible = [r for r in results if r.comparison is not None]
    disagreements = sum(
        1
        for r in disagreement_eligible
        if r.comparison is not None and r.comparison.category != ComparisonCategory.AGREEMENT
    )
    disagreement_rate = _metric(disagreements, len(disagreement_eligible))

    return PipelineMetrics(
        evidence_precision=evidence_precision,
        evidence_recall=evidence_recall,
        claim_support_correctness=claim_support,
        correct_hypothesis_inclusion_rate=hyp_inclusion,
        candidate_count_mean=mean_count,
        candidate_count_median=median_count,
        hard_contradiction_detection_rate=hard_contradiction_rate,
        decision_distribution=distribution,
        classifier_pue_disagreement_rate=disagreement_rate,
    )


# --------------------------------------------------------------------------- #
# 6.3 Operational metrics
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class OperationalMetrics:
    listings_per_second: float
    median_latency_ms: float
    p95_latency_ms: float
    mean_extraction_ms: float
    mean_retrieval_ms: float
    mean_evaluation_ms: float
    mean_decision_explanation_ms: float
    mean_persistence_ms: float | None
    technical_failure_rate: Metric
    mean_reasoning_record_json_bytes: float

    def to_dict(self) -> dict:
        return {
            "listings_per_second": self.listings_per_second,
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "mean_extraction_ms": self.mean_extraction_ms,
            "mean_retrieval_ms": self.mean_retrieval_ms,
            "mean_evaluation_ms": self.mean_evaluation_ms,
            "mean_decision_explanation_ms": self.mean_decision_explanation_ms,
            "mean_persistence_ms": self.mean_persistence_ms,
            "technical_failure_rate": self.technical_failure_rate.to_dict(),
            "mean_reasoning_record_json_bytes": self.mean_reasoning_record_json_bytes,
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def compute_operational_metrics(
    results: Sequence[CaseResult], *, wall_time_seconds: float, persistence_ms: float | None = None
) -> OperationalMetrics:
    from .persistence import reasoning_record_to_json

    def _stage_ms(r: CaseResult, key: str) -> float:
        value = r.record.operational_metrics.get(key, 0.0)
        return float(value) if isinstance(value, (int, float)) else 0.0

    total_ms = sorted(_stage_ms(r, "total_ms") for r in results)
    extraction = [_stage_ms(r, "extraction_ms") for r in results]
    retrieval = [_stage_ms(r, "retrieval_ms") for r in results]
    evaluation = [_stage_ms(r, "evaluation_ms") for r in results]
    decision_expl = [_stage_ms(r, "decision_explanation_ms") for r in results]
    technical_failures = sum(1 for r in results if r.is_technical_failure)
    json_sizes = [len(reasoning_record_to_json(r.record).encode("utf-8")) for r in results]

    def _mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    return OperationalMetrics(
        listings_per_second=round(len(results) / wall_time_seconds, 3)
        if wall_time_seconds > 0
        else 0.0,
        median_latency_ms=round(_percentile(total_ms, 0.5), 4),
        p95_latency_ms=round(_percentile(total_ms, 0.95), 4),
        mean_extraction_ms=_mean(extraction),
        mean_retrieval_ms=_mean(retrieval),
        mean_evaluation_ms=_mean(evaluation),
        mean_decision_explanation_ms=_mean(decision_expl),
        mean_persistence_ms=persistence_ms,
        technical_failure_rate=_metric(technical_failures, len(results)),
        mean_reasoning_record_json_bytes=_mean([float(s) for s in json_sizes]),
    )


# --------------------------------------------------------------------------- #
# 12. Classifier vs PUE differential report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class DifferentialMetrics:
    """Benchmark-gold-grounded classifier/PUE differential (brief section
    12): each system's correctness is graded *independently* against the
    benchmark's gold labels (see
    :func:`~digital_arbitrage.pue.benchmark_metrics.classifier_gold_correct`)
    - never inferred from
    :class:`~digital_arbitrage.pue.comparison.ComparisonCategory.AGREEMENT`,
    which describes only whether the two systems happened to reach the same
    *observable* conclusion, not whether either is correct (Sprint 3
    pre-merge correction item 2: agreement and correctness are orthogonal -
    two systems can agree and both be wrong, or disagree and both be
    wrong)."""

    total_compared: int
    classifier_gradable: int
    """Cases with a comparison record AND a clear, classifier-gradable gold
    judgment (see ``classifier_gold_correct``)."""
    classifier_ungradable: int
    """Cases with a comparison record but no classifier-gradable gold
    judgment (e.g. packaging/bundle cases the classifier has no concept
    of) - excluded from every quadrant count below, never silently folded
    into either correct or incorrect."""
    both_correct: int
    both_wrong: int
    pue_corrects_classifier: int
    classifier_correct_pue_worsens: int
    pue_appropriately_abstains: int
    pue_avoidably_abstains: int
    pue_prevents_harmful_comparability: int
    product_form_disagreements: int
    identity_specificity_differences: int
    classifier_declined_pue_classified: int

    def to_dict(self) -> dict:
        return {
            "total_compared": self.total_compared,
            "classifier_gradable": self.classifier_gradable,
            "classifier_ungradable": self.classifier_ungradable,
            "both_correct": self.both_correct,
            "both_wrong": self.both_wrong,
            "pue_corrects_classifier": self.pue_corrects_classifier,
            "classifier_correct_pue_worsens": self.classifier_correct_pue_worsens,
            "pue_appropriately_abstains": self.pue_appropriately_abstains,
            "pue_avoidably_abstains": self.pue_avoidably_abstains,
            "pue_prevents_harmful_comparability": self.pue_prevents_harmful_comparability,
            "product_form_disagreements": self.product_form_disagreements,
            "identity_specificity_differences": self.identity_specificity_differences,
            "classifier_declined_pue_classified": self.classifier_declined_pue_classified,
        }


def compute_differential_metrics(results: Sequence[CaseResult]) -> DifferentialMetrics:
    from .benchmark_metrics import classifier_gold_correct

    compared = [r for r in results if r.comparison is not None]
    both_correct = both_wrong = pue_corrects = classifier_worsens = ungradable = 0
    appropriate_abstain = avoidable_abstain = prevents_harmful = 0
    form_disagreements = identity_diffs = declined_classified = 0

    for r in compared:
        comparison = r.comparison
        assert comparison is not None
        classifier_correct = classifier_gold_correct(r.case, comparison.classifier_label)
        pue_correct = r.correct

        if classifier_correct is None:
            ungradable += 1
        elif classifier_correct and pue_correct:
            both_correct += 1
        elif (not classifier_correct) and pue_correct:
            pue_corrects += 1
        elif classifier_correct and not pue_correct:
            classifier_worsens += 1
        else:
            both_wrong += 1

        if r.is_justified_abstention:
            appropriate_abstain += 1
        if r.is_avoidable_abstention:
            avoidable_abstain += 1
        if comparison.category == ComparisonCategory.PUE_BLOCKED_DIRECT_COMPARABILITY:
            prevents_harmful += 1
        if comparison.category == ComparisonCategory.PRODUCT_FORM_DISAGREEMENT:
            form_disagreements += 1
        if comparison.identity_breadth in ("more_specific", "broader"):
            identity_diffs += 1
        if comparison.category == ComparisonCategory.CLASSIFIER_DECLINED_PUE_CLASSIFIED:
            declined_classified += 1

    return DifferentialMetrics(
        total_compared=len(compared),
        classifier_gradable=len(compared) - ungradable,
        classifier_ungradable=ungradable,
        both_correct=both_correct,
        both_wrong=both_wrong,
        pue_corrects_classifier=pue_corrects,
        classifier_correct_pue_worsens=classifier_worsens,
        pue_appropriately_abstains=appropriate_abstain,
        pue_avoidably_abstains=avoidable_abstain,
        pue_prevents_harmful_comparability=prevents_harmful,
        product_form_disagreements=form_disagreements,
        identity_specificity_differences=identity_diffs,
        classifier_declined_pue_classified=declined_classified,
    )


# --------------------------------------------------------------------------- #
# 7. Release gate
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class GateCheck:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class ReleaseGateReport:
    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": [c.to_dict() for c in self.checks]}


def evaluate_release_gate(
    results: Sequence[CaseResult],
    failures: Sequence[CaseFailure],
    *,
    mandatory_acceptance_pass: bool,
    mandatory_acceptance_detail: str = "",
    replay_equivalent: bool,
    replay_equivalent_detail: str = "",
    capability_version: str = "",
    policy_version: str = "",
    knowledge_version: str = "",
    schema_version: str = "",
) -> ReleaseGateReport:
    """Evaluate every hard release-gate requirement (brief section 7).

    ``mandatory_acceptance_pass``/``replay_equivalent`` must be the *real*
    outcome of actually executing the mandatory acceptance/regression test
    suite and an actual identical-version persisted replay (see
    :mod:`digital_arbitrage.pue.release_pipeline`) - never a hardcoded
    literal (Sprint 3 pre-merge correction item 1). The accompanying
    ``*_detail`` strings must carry the real evidence (e.g. the pytest exit
    code and command, or the per-case replay-equivalence outcomes) so the
    check is auditable, not just asserted.
    """
    checks: list[GateCheck] = []

    checks.append(
        GateCheck(
            "all_mandatory_acceptance_cases_pass",
            mandatory_acceptance_pass,
            mandatory_acceptance_detail
            or "tests/pue/test_acceptance.py + tests/pue/test_golden.py + "
            "tests/pue/test_invariants.py must pass.",
        )
    )

    accessory_errors = [r for r in results if "accessory_to_complete_product" in r.harmful_errors]
    checks.append(
        GateCheck(
            "zero_accessory_to_complete_product_errors",
            len(accessory_errors) == 0,
            f"{len(accessory_errors)} case(s): {[r.case.case_id for r in accessory_errors]}",
        )
    )

    packaging_errors = [r for r in results if "packaging_to_complete_product" in r.harmful_errors]
    checks.append(
        GateCheck(
            "zero_packaging_to_complete_product_errors",
            len(packaging_errors) == 0,
            f"{len(packaging_errors)} case(s): {[r.case.case_id for r in packaging_errors]}",
        )
    )

    checks.append(
        GateCheck(
            "retrieval_and_decision_quality_reported_independently",
            True,
            "See product_metrics.candidate_recall_at_* vs decision-quality metrics above.",
        )
    )

    wrong_or_avoidable = [r for r in results if (not r.correct) or r.is_avoidable_abstention]
    failure_case_ids = {f.case_id for f in failures}
    untraced = [
        r.case.case_id for r in wrong_or_avoidable if r.case.case_id not in failure_case_ids
    ]
    checks.append(
        GateCheck(
            "every_wrong_decision_has_a_traceable_failure_stage",
            len(untraced) == 0,
            f"untraced: {untraced}",
        )
    )

    abstained_results = [
        r for r in results if r.record.decision.decision_type == DecisionType.ABSTAINED
    ]
    unclassified_abstentions = [
        r.case.case_id
        for r in abstained_results
        if not (r.is_justified_abstention or r.is_avoidable_abstention)
    ]
    checks.append(
        GateCheck(
            "every_abstention_classified_justified_or_avoidable",
            len(unclassified_abstentions) == 0,
            f"unclassified: {unclassified_abstentions}",
        )
    )

    all_harmful = [r for r in results if r.harmful_errors]
    checks.append(
        GateCheck(
            "every_harmful_result_individually_listed",
            True,
            f"{len(all_harmful)} harmful case(s) listed in the report's harmful_errors section.",
        )
    )

    checks.append(
        GateCheck(
            "deterministic_replay_equivalent",
            replay_equivalent,
            replay_equivalent_detail
            or "Replaying a persisted case under identical versions reproduces an "
            "equivalent Decision.",
        )
    )

    # This structural invariant is exercised by tests/pue/test_invariants.py
    # ::test_invariant_no_commercial_fields, which is included in the same
    # mandatory-acceptance pytest run whose real, executed outcome is
    # ``mandatory_acceptance_pass`` above - so this check derives from that
    # same real evidence rather than being independently hardcoded True.
    checks.append(
        GateCheck(
            "no_commercial_data_in_product_identity_reasoning",
            mandatory_acceptance_pass,
            "Structural invariant enforced by tests/pue/test_invariants.py::"
            "test_invariant_no_commercial_fields (no price/profit/ROI field ever read by "
            "pue/claims.py, pue/evaluation.py, or pue/decisions.py); verified by the same "
            "mandatory-acceptance pytest run above.",
        )
    )

    version_fields = {
        "capability_version": capability_version,
        "policy_version": policy_version,
        "knowledge_version": knowledge_version,
        "schema_version": schema_version,
    }
    missing_versions = [name for name, value in version_fields.items() if not value]
    checks.append(
        GateCheck(
            "versions_identified_in_manifest",
            not missing_versions,
            f"missing: {missing_versions}" if missing_versions else str(version_fields),
        )
    )

    return ReleaseGateReport(checks=tuple(checks))


# --------------------------------------------------------------------------- #
# Top-level report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    dataset: BenchmarkDataset
    dataset_file_hash: str
    generated_at: str
    capability_version: str
    policy_version: str
    knowledge_version: str
    schema_version: str
    results: tuple[CaseResult, ...]
    failures: tuple[CaseFailure, ...]
    product_metrics: ProductMetrics
    pipeline_metrics: PipelineMetrics
    operational_metrics: OperationalMetrics
    differential_metrics: DifferentialMetrics | None
    gate: ReleaseGateReport

    @property
    def total_cases(self) -> int:
        return len(self.results)

    @property
    def correct_count(self) -> int:
        return sum(1 for r in self.results if r.correct)

    @property
    def harmful_results(self) -> tuple[CaseResult, ...]:
        return tuple(r for r in self.results if r.harmful_errors)

    def failure_counts_by_category(self) -> dict[str, int]:
        counts = {c.value: 0 for c in FailureCategory}
        for f in self.failures:
            counts[f.primary_category.value] += 1
        return counts


def build_benchmark_report(
    dataset: BenchmarkDataset,
    dataset_hash: str,
    results: Sequence[CaseResult],
    failures: Sequence[CaseFailure],
    *,
    capability_version: str,
    policy_version: str,
    knowledge_version: str,
    schema_version: str,
    wall_time_seconds: float,
    mandatory_acceptance_pass: bool,
    replay_equivalent: bool,
    run_differential: bool,
    mandatory_acceptance_detail: str = "",
    replay_equivalent_detail: str = "",
    generated_at: str | None = None,
) -> BenchmarkReport:
    product_metrics = compute_product_metrics(results)
    pipeline_metrics = compute_pipeline_metrics(results)
    operational_metrics = compute_operational_metrics(results, wall_time_seconds=wall_time_seconds)
    differential_metrics = compute_differential_metrics(results) if run_differential else None
    gate = evaluate_release_gate(
        results,
        failures,
        mandatory_acceptance_detail=mandatory_acceptance_detail,
        replay_equivalent_detail=replay_equivalent_detail,
        capability_version=capability_version,
        policy_version=policy_version,
        knowledge_version=knowledge_version,
        schema_version=schema_version,
        mandatory_acceptance_pass=mandatory_acceptance_pass,
        replay_equivalent=replay_equivalent,
    )
    return BenchmarkReport(
        dataset=dataset,
        dataset_file_hash=dataset_hash,
        generated_at=generated_at or datetime.now().isoformat(),
        capability_version=capability_version,
        policy_version=policy_version,
        knowledge_version=knowledge_version,
        schema_version=schema_version,
        results=tuple(results),
        failures=tuple(failures),
        product_metrics=product_metrics,
        pipeline_metrics=pipeline_metrics,
        operational_metrics=operational_metrics,
        differential_metrics=differential_metrics,
        gate=gate,
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def report_to_dict(report: BenchmarkReport) -> dict:
    return {
        "dataset_id": report.dataset.dataset_id,
        "benchmark_version": report.dataset.benchmark_version,
        "dataset_file_hash": report.dataset_file_hash,
        "generated_at": report.generated_at,
        "capability_version": report.capability_version,
        "policy_version": report.policy_version,
        "knowledge_version": report.knowledge_version,
        "schema_version": report.schema_version,
        "total_cases": report.total_cases,
        "correct_count": report.correct_count,
        "case_coverage_by_tag": case_coverage_by_tag(report.dataset.cases),
        "product_metrics": report.product_metrics.to_dict(),
        "pipeline_metrics": report.pipeline_metrics.to_dict(),
        "operational_metrics": report.operational_metrics.to_dict(),
        "differential_metrics": (
            report.differential_metrics.to_dict() if report.differential_metrics else None
        ),
        "release_gate": report.gate.to_dict(),
        "failure_counts_by_category": report.failure_counts_by_category(),
        "failures": [
            {
                "case_id": f.case_id,
                "primary_category": f.primary_category.value,
                "secondary_categories": [c.value for c in f.secondary_categories],
                "explanation": f.explanation,
                "related_object_ids": list(f.related_object_ids),
            }
            for f in report.failures
        ],
        "harmful_results": [
            {
                "case_id": r.case.case_id,
                "title": r.case.title,
                "harmful_errors": list(r.harmful_errors),
                "decision_type": r.record.decision.decision_type.value,
                "product_form": r.record.decision.product_form.value,
            }
            for r in report.harmful_results
        ],
        "cases": [
            {
                "case_id": r.case.case_id,
                "case_tags": list(r.case.case_tags),
                "correct": r.correct,
                "decision_type": r.record.decision.decision_type.value,
                "identification_level": r.record.decision.identification_level.value,
                "product_form": r.record.decision.product_form.value,
                "comparability_status": r.record.decision.comparability_status.value,
                "is_avoidable_abstention": r.is_avoidable_abstention,
                "is_justified_abstention": r.is_justified_abstention,
                "harmful_errors": list(r.harmful_errors),
                "failed_checks": [c.name for c in r.failed_checks],
                "case_id_ref": r.case.case_id,
                "reasoning_record_case_id": r.record.case_id,
            }
            for r in report.results
        ],
    }


#: Report sections that are *expected* to vary between two regenerations of
#: an otherwise byte-identical release, and so must never be part of a
#: reproducibility/content hash (Sprint 3 pre-merge correction item 4):
#: ``generated_at`` is a wall-clock timestamp, and ``operational_metrics``
#: is real, measured wall-clock timing (throughput/latency) - neither is
#: semantic report content.
VOLATILE_REPORT_KEYS = ("generated_at", "operational_metrics")


def report_semantic_dict(report: BenchmarkReport) -> dict:
    """The subset of :func:`report_to_dict` expected to be exactly
    reproducible across regenerations from the same code, dataset, and
    catalogue (given a deterministic id_factory/clock) - excludes
    :data:`VOLATILE_REPORT_KEYS`. This is what the release-verification
    path (:mod:`digital_arbitrage.pue.release_pipeline`) compares."""
    d = report_to_dict(report)
    return {k: v for k, v in d.items() if k not in VOLATILE_REPORT_KEYS}


def canonical_report_hash(report: BenchmarkReport) -> str:
    """Stable SHA-256 hash of :func:`report_semantic_dict` (see
    :mod:`digital_arbitrage.pue.canonical`) - the value recorded as a
    release manifest's ``release_report_hash``."""
    from .canonical import canonical_json_hash

    return canonical_json_hash(report_semantic_dict(report))


def render_report_json(report: BenchmarkReport) -> str:
    return json.dumps(report_to_dict(report), indent=2, sort_keys=True)


def render_report_markdown(report: BenchmarkReport) -> str:
    d = report_to_dict(report)
    lines: list[str] = [
        "# PUE GPU Release Benchmark Report",
        "",
        f"- **Dataset:** {d['dataset_id']} (benchmark version {d['benchmark_version']})",
        f"- **Dataset file hash (sha256):** `{d['dataset_file_hash']}`",
        f"- **Generated:** {d['generated_at']}",
        f"- **Capability version:** {d['capability_version']}",
        f"- **Policy version:** {d['policy_version']}",
        f"- **Knowledge version:** {d['knowledge_version']}",
        f"- **Schema version:** {d['schema_version']}",
        f"- **Total cases:** {d['total_cases']} ({d['correct_count']} correct)",
        "",
        f"## Release gate: {'PASS' if report.gate.passed else 'FAIL'}",
        "",
        "| Gate check | Result | Detail |",
        "|---|---|---|",
    ]
    for check in report.gate.checks:
        lines.append(f"| {check.name} | {'PASS' if check.passed else 'FAIL'} | {check.detail} |")

    lines += [
        "",
        "## Product metrics",
        "",
        "| Metric | Value | n / N (excluded) |",
        "|---|---:|---:|",
    ]
    for name, m in d["product_metrics"].items():
        lines.append(
            f"| {name} | {m['value']} | {m['numerator']}/{m['denominator']} ({m['excluded']}) |"
        )

    lines += ["", "## Pipeline metrics", ""]
    pm = d["pipeline_metrics"]
    for name in (
        "evidence_precision",
        "evidence_recall",
        "claim_support_correctness",
        "correct_hypothesis_inclusion_rate",
        "hard_contradiction_detection_rate",
        "classifier_pue_disagreement_rate",
    ):
        m = pm[name]
        lines.append(f"- **{name}:** {m['value']} ({m['numerator']}/{m['denominator']})")
    lines.append(
        f"- **candidate_count_mean / median:** {pm['candidate_count_mean']} / "
        f"{pm['candidate_count_median']}"
    )
    lines.append(f"- **decision_distribution:** {pm['decision_distribution']}")

    lines += ["", "## Operational metrics", ""]
    om = d["operational_metrics"]
    for key, val in om.items():
        if key == "technical_failure_rate":
            lines.append(f"- **{key}:** {val['value']} ({val['numerator']}/{val['denominator']})")
        else:
            lines.append(f"- **{key}:** {val}")

    if d["differential_metrics"] is not None:
        lines += ["", "## Classifier vs PUE differential", ""]
        for key, val in d["differential_metrics"].items():
            lines.append(f"- **{key}:** {val}")

    lines += ["", "## Error taxonomy counts", "", "| Category | Count |", "|---|---:|"]
    for cat, count in d["failure_counts_by_category"].items():
        lines.append(f"| {cat} | {count} |")

    if d["harmful_results"]:
        lines += ["", "## Harmful results (individually reviewed)", ""]
        lines += [
            "| Case ID | Title | Harmful error(s) | Decision | Product form |",
            "|---|---|---|---|---|",
        ]
        for h in d["harmful_results"]:
            lines.append(
                f"| {h['case_id']} | {h['title']} | {', '.join(h['harmful_errors'])} | "
                f"{h['decision_type']} | {h['product_form']} |"
            )
    else:
        lines += ["", "## Harmful results (individually reviewed)", "", "_None._"]

    if d["failures"]:
        lines += ["", "## Wrong / avoidably-abstaining case failures", ""]
        lines += ["| Case ID | Primary | Secondary | Explanation |", "|---|---|---|---|"]
        for f in d["failures"]:
            lines.append(
                f"| {f['case_id']} | {f['primary_category']} | "
                f"{', '.join(f['secondary_categories'])} | {f['explanation']} |"
            )

    lines.append("")
    return "\n".join(lines)


def render_report_csv(report: BenchmarkReport) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "case_id",
            "correct",
            "decision_type",
            "identification_level",
            "product_form",
            "comparability_status",
            "is_avoidable_abstention",
            "is_justified_abstention",
            "harmful_errors",
            "failed_checks",
        ]
    )
    for r in report.results:
        writer.writerow(
            [
                r.case.case_id,
                r.correct,
                r.record.decision.decision_type.value,
                r.record.decision.identification_level.value,
                r.record.decision.product_form.value,
                r.record.decision.comparability_status.value,
                r.is_avoidable_abstention,
                r.is_justified_abstention,
                ";".join(r.harmful_errors),
                ";".join(c.name for c in r.failed_checks),
            ]
        )
    return buffer.getvalue().rstrip("\n")
