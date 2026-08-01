"""Per-case grading, stage-based error taxonomy, and aggregate benchmark
metrics for the GPU release benchmark (Sprint 3).

Three layers, in order:

1. :func:`evaluate_case` - grades one already-computed :class:`ReasoningRecord`
   against one :class:`BenchmarkCase`'s gold labels. Never re-runs the PUE.
2. :func:`classify_failure` - for a wrong or avoidably-abstaining case,
   assigns a primary (and optional secondary) stage-based failure category
   (brief section 8).
3. :func:`compute_metrics` - aggregates a sequence of :class:`CaseResult`
   into the product/pipeline/operational metric groups (brief section 6),
   with explicit denominators (brief section 6.4) rather than one overall
   accuracy number.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..classification.models import Classification
from .benchmark import BenchmarkCase
from .catalogue import CandidateRepository
from .comparison import ClassifierPueComparison
from .enums import ContradictionSeverity, DecisionType, IdentificationLevel, ProductForm
from .models import ReasoningRecord


# --------------------------------------------------------------------------- #
# 8. Stage-based error taxonomy
# --------------------------------------------------------------------------- #
class FailureCategory(StrEnum):
    """Primary/secondary failure stage for a wrong or avoidably-abstaining
    benchmark case (brief section 8). Every member corresponds to exactly
    one PUE reasoning stage or the runtime boundary around all of them."""

    OBSERVATION_FAILURE = "observation_failure"
    EVIDENCE_FAILURE = "evidence_failure"
    CLAIM_FAILURE = "claim_failure"
    HYPOTHESIS_FAILURE = "hypothesis_failure"
    RETRIEVAL_FAILURE = "retrieval_failure"
    KNOWLEDGE_FAILURE = "knowledge_failure"
    EVALUATION_FAILURE = "evaluation_failure"
    DECISION_POLICY_FAILURE = "decision_policy_failure"
    EXPLANATION_FAILURE = "explanation_failure"
    RUNTIME_FAILURE = "runtime_failure"


@dataclass(frozen=True, slots=True)
class CaseFailure:
    """One case's failure classification (brief section 8)."""

    case_id: str
    primary_category: FailureCategory
    secondary_categories: tuple[FailureCategory, ...]
    explanation: str
    related_object_ids: tuple[str, ...] = ()


#: Identification-level specificity ranking (spec taxonomy order), most
#: specific first. Used only to evaluate
#: ``maximum_justified_identification_level`` (a Decision must never be
#: *more* specific than the gold-permitted ceiling).
_IDENTIFICATION_LEVEL_RANK: dict[str, int] = {
    IdentificationLevel.EXACT_CATALOGUE_PRODUCT.value: 0,
    IdentificationLevel.VARIANT.value: 1,
    IdentificationLevel.MODEL.value: 2,
    IdentificationLevel.FAMILY.value: 3,
    IdentificationLevel.BRAND_AND_PRODUCT_TYPE.value: 4,
    IdentificationLevel.PRODUCT_TYPE.value: 5,
    IdentificationLevel.UNKNOWN.value: 6,
}

_ACCESSORY_LIKE_FORMS = frozenset(
    {
        ProductForm.ACCESSORY.value,
        ProductForm.COMPONENT.value,
        ProductForm.REPLACEMENT_PART.value,
        ProductForm.COMPATIBLE_ITEM.value,
    }
)

#: Identification levels that imply a specific catalogue-product identity
#: was chosen, not merely a family/model claim - only at these levels does
#: "which Candidate was selected" have to agree with the gold-acceptable
#: catalogue product ids (Sprint 3 pre-merge correction item 3).
_SELECTION_REQUIRING_LEVELS = frozenset(
    {IdentificationLevel.EXACT_CATALOGUE_PRODUCT.value, IdentificationLevel.VARIANT.value}
)


# --------------------------------------------------------------------------- #
# Classifier gold-grounded correctness (Sprint 3 pre-merge correction item 2)
# --------------------------------------------------------------------------- #
def classifier_gold_correct(case: BenchmarkCase, classifier_label: str) -> bool | None:
    """Grade the existing title classifier's verdict *independently*
    against this benchmark case's gold labels - never against
    :data:`~digital_arbitrage.pue.comparison.ComparisonCategory.AGREEMENT`,
    which describes only whether the classifier and the PUE happened to
    reach the same observable conclusion, not whether either is correct.

    Returns ``None`` when this case's gold labels give no clear,
    classifier-gradable judgment at all (the classifier has no concept of
    packaging/bundle/incomplete-product distinctions, and many cases assert
    nothing about product form) - such cases are excluded from the
    classifier-correctness denominator, never silently counted either way.

    Two classifier-gradable judgments only (brief: "particularly product
    form and declined/non-declined semantics"):

    1. Declined/non-declined: a case gold-labelled as *not* a genuine,
       in-scope GPU product (misleading-similarity merchandise or an
       unsupported-domain listing) is correctly classified only if the
       classifier declines to treat it as a product match (``REJECTED`` or
       ``UNKNOWN`` - never ``COMPLETE_PRODUCT``/``ACCESSORY``/``PART``).
    2. Product form: for a case with a gold ``expected_product_form``, the
       classifier is correct iff its coarse bucket (complete vs.
       accessory/part) matches.
    """
    label = Classification(classifier_label)
    if label in (Classification.COMPLETE_PRODUCT,):
        bucket = "complete"
    elif label in (Classification.ACCESSORY, Classification.PART):
        bucket = "non_complete"
    elif label is Classification.REJECTED:
        bucket = "rejected"
    else:
        bucket = "unknown"

    if "misleading_similarity" in case.case_tags or case.unsupported_domain:
        return bucket in ("rejected", "unknown")

    if case.expected_product_form == ProductForm.COMPLETE_PRODUCT.value:
        return bucket == "complete"

    if case.expected_product_form in _ACCESSORY_LIKE_FORMS:
        return bucket == "non_complete"

    return None


# --------------------------------------------------------------------------- #
# Per-case grading
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CheckOutcome:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CaseResult:
    """The graded outcome of running one :class:`BenchmarkCase` through the
    real PUE orchestration path (and, optionally, the existing classifier).
    """

    case: BenchmarkCase
    record: ReasoningRecord
    comparison: ClassifierPueComparison | None
    checks: tuple[CheckOutcome, ...]
    correct: bool
    harmful_errors: tuple[str, ...]
    """Non-empty when this case triggered one of :data:`HARMFUL_OUTCOME_KINDS`."""
    is_avoidable_abstention: bool
    is_justified_abstention: bool
    is_technical_failure: bool
    top_acceptable_rank: int | None
    """1-based retrieval rank of the best-ranked acceptable Candidate among
    ``record.candidates``, or ``None`` if no acceptable Candidate was
    retrieved at all (see :func:`_acceptable_candidate_rank`). This is a
    pure *retrieval* signal - it belongs only in Candidate recall@k, never
    in an identification-*correctness* metric (Sprint 3 pre-merge
    correction item 3): the Decision may select a different Candidate than
    the one retrieval ranked highest."""
    selected_product_id: str | None
    """The catalogue_product_id of the Candidate actually *selected* by
    Decision Formation (``decision.selected_candidate_instance_id``), or
    ``None`` if no Candidate was selected (e.g. PARTIALLY_IDENTIFIED never
    selects one - see ``pue/decisions.py``). Identification-*correctness*
    metrics (exact/hierarchical) must be computed against this field, never
    against ``top_acceptable_rank``."""
    identification_hierarchy_correct: bool | None
    """Whether the achieved identification level is within
    ``case.expected_identification_levels`` *and*, when that level implies
    a specific catalogue identity (EXACT_CATALOGUE_PRODUCT or VARIANT) and
    the case defines ``acceptable_catalogue_product_ids``, the actually
    selected Candidate is one of them. ``None`` when the case asserts no
    ``expected_identification_levels`` at all (not applicable - excluded
    from the metric's denominator, never counted as either correct or
    incorrect)."""

    @property
    def failed_checks(self) -> tuple[CheckOutcome, ...]:
        return tuple(c for c in self.checks if not c.passed)


def _check(name: str, passed: bool, detail: str = "") -> CheckOutcome:
    return CheckOutcome(name=name, passed=passed, detail=detail)


def _acceptable_candidate_rank(case: BenchmarkCase, record: ReasoningRecord) -> int | None:
    if not case.acceptable_catalogue_product_ids:
        return None
    acceptable = set(case.acceptable_catalogue_product_ids)
    ranked = sorted(record.candidates, key=lambda c: c.retrieval_rank or 10**9)
    for position, candidate in enumerate(ranked, start=1):
        if candidate.catalogue_product_id in acceptable:
            return position
    return None


def evaluate_case(
    case: BenchmarkCase, record: ReasoningRecord, comparison: ClassifierPueComparison | None = None
) -> CaseResult:
    """Grade one already-computed :class:`ReasoningRecord` against ``case``'s
    gold labels. Pure function: never re-runs the PUE, never mutates
    ``record`` (brief section 5 "retain case-level expected and actual
    results")."""
    decision = record.decision
    checks: list[CheckOutcome] = []

    is_technical_failure = decision.decision_type == DecisionType.PROCESSING_FAILED
    checks.append(
        _check(
            "technical_failure_not_counted_as_abstention",
            not (is_technical_failure and decision.decision_type == DecisionType.ABSTAINED),
        )
    )

    allowed = set(case.allowed_decision_types)
    checks.append(
        _check(
            "decision_type_allowed",
            decision.decision_type.value in allowed,
            f"got {decision.decision_type.value}, allowed {sorted(allowed)}",
        )
    )
    forbidden_decisions = set(case.forbidden_decision_types)
    checks.append(
        _check(
            "decision_type_not_forbidden",
            decision.decision_type.value not in forbidden_decisions,
            f"got {decision.decision_type.value}",
        )
    )

    if case.expected_product_form is not None:
        checks.append(
            _check(
                "expected_product_form",
                decision.product_form.value == case.expected_product_form,
                f"got {decision.product_form.value}, expected {case.expected_product_form}",
            )
        )
    if case.forbidden_product_forms:
        checks.append(
            _check(
                "product_form_not_forbidden",
                decision.product_form.value not in set(case.forbidden_product_forms),
                f"got {decision.product_form.value}",
            )
        )
    if case.expected_product_type is not None:
        checks.append(
            _check(
                "expected_product_type",
                decision.product_type == case.expected_product_type,
                f"got {decision.product_type!r}",
            )
        )
    if case.expected_identification_levels:
        checks.append(
            _check(
                "expected_identification_level",
                decision.identification_level.value in set(case.expected_identification_levels),
                f"got {decision.identification_level.value}",
            )
        )
    if case.maximum_justified_identification_level is not None:
        ceiling_rank = _IDENTIFICATION_LEVEL_RANK.get(
            case.maximum_justified_identification_level, 0
        )
        actual_rank = _IDENTIFICATION_LEVEL_RANK.get(decision.identification_level.value, 6)
        checks.append(
            _check(
                "identification_level_not_overclaimed",
                actual_rank >= ceiling_rank,
                f"got {decision.identification_level.value} "
                f"(max justified: {case.maximum_justified_identification_level})",
            )
        )
    if case.expected_comparability:
        checks.append(
            _check(
                "expected_comparability",
                decision.comparability_status.value in set(case.expected_comparability),
                f"got {decision.comparability_status.value}",
            )
        )
    for field_name, expected, actual in (
        ("expected_identified_brand", case.expected_identified_brand, decision.identified_brand),
        ("expected_identified_family", case.expected_identified_family, decision.identified_family),
        ("expected_identified_model", case.expected_identified_model, decision.identified_model),
        (
            "expected_identified_variant",
            case.expected_identified_variant,
            decision.identified_variant,
        ),
    ):
        if expected is not None:
            checks.append(_check(field_name, actual == expected, f"got {actual!r}"))

    # --- abstention semantics ------------------------------------------- #
    is_abstained = decision.decision_type == DecisionType.ABSTAINED
    is_avoidable_abstention = is_abstained and case.avoidable_if_abstained
    is_justified_abstention = is_abstained and not case.avoidable_if_abstained
    if is_abstained and case.acceptable_abstention_reasons:
        checks.append(
            _check(
                "abstention_reason_acceptable",
                decision.abstention_reason is not None
                and decision.abstention_reason.value in set(case.acceptable_abstention_reasons),
                f"got {decision.abstention_reason}",
            )
        )
    checks.append(_check("avoidable_abstention_did_not_occur", not is_avoidable_abstention))

    # --- Candidate-level gold labels -------------------------------------- #
    selected_product_id: str | None = None
    if decision.selected_candidate_instance_id is not None:
        selected = next(
            (
                c
                for c in record.candidates
                if c.candidate_instance_id == decision.selected_candidate_instance_id
            ),
            None,
        )
        selected_product_id = selected.catalogue_product_id if selected else None

    if case.acceptable_catalogue_product_ids and selected_product_id is not None:
        checks.append(
            _check(
                "selected_candidate_acceptable",
                selected_product_id in set(case.acceptable_catalogue_product_ids),
                f"selected {selected_product_id}",
            )
        )
    if case.forbidden_catalogue_product_ids:
        checks.append(
            _check(
                "selected_candidate_not_forbidden",
                selected_product_id not in set(case.forbidden_catalogue_product_ids),
                f"selected {selected_product_id}",
            )
        )
        retrieved_forbidden = {c.catalogue_product_id for c in record.candidates} & set(
            case.forbidden_catalogue_product_ids
        )
        # A forbidden Candidate may be *retrieved* (evaluation must reject
        # it) but must never be *selected* - already checked above.
        del retrieved_forbidden

    # --- reasoning-trace assertions ---------------------------------------- #
    if case.required_evidence_types:
        present = {e.evidence_type.value for e in record.evidence}
        missing = [t for t in case.required_evidence_types if t not in present]
        checks.append(_check("required_evidence_present", not missing, f"missing {missing}"))
    checks.append(
        _check(
            "min_evidence_count",
            len(record.evidence) >= case.min_evidence_count,
            f"got {len(record.evidence)}, need >= {case.min_evidence_count}",
        )
    )
    if case.require_hard_rejected_candidate:
        checks.append(
            _check(
                "hard_rejected_candidate_present",
                any(ev.hard_rejected for ev in record.candidate_evaluations),
            )
        )
    if case.require_contradicted_claim:
        from .enums import ClaimStatus

        checks.append(
            _check(
                "contradicted_claim_present",
                any(c.status == ClaimStatus.CONTRADICTED for c in record.claims),
            )
        )
    if case.require_multiple_hypotheses:
        checks.append(_check("multiple_hypotheses_present", len(record.hypotheses) > 1))
    if case.expected_contradiction_fields:
        contradicted_fields = {
            f.field
            for ev in record.candidate_evaluations
            for f in ev.contradictions
            if f.severity == ContradictionSeverity.HARD
        }
        missing_fields = [
            f for f in case.expected_contradiction_fields if f not in contradicted_fields
        ]
        checks.append(
            _check("expected_contradiction_fields", not missing_fields, f"missing {missing_fields}")
        )

    correct = all(c.passed for c in checks)

    # --- harmful outcomes (brief sections 6.1 / 7 / 8) --------------------- #
    harmful_errors: list[str] = []
    if (
        "accessory_to_complete_product" in case.forbidden_harmful_outcomes
        and case.expected_product_form in _ACCESSORY_LIKE_FORMS
        and decision.product_form == ProductForm.COMPLETE_PRODUCT
    ):
        harmful_errors.append("accessory_to_complete_product")
    if (
        "packaging_to_complete_product" in case.forbidden_harmful_outcomes
        and case.expected_product_form == ProductForm.PACKAGING_ONLY.value
        and decision.product_form == ProductForm.COMPLETE_PRODUCT
    ):
        harmful_errors.append("packaging_to_complete_product")
    if (
        "harmful_false_match" in case.forbidden_harmful_outcomes
        and case.forbidden_catalogue_product_ids
        and selected_product_id in set(case.forbidden_catalogue_product_ids)
    ):
        harmful_errors.append("harmful_false_match")

    identification_hierarchy_correct: bool | None = None
    if case.expected_identification_levels:
        level_ok = decision.identification_level.value in set(case.expected_identification_levels)
        selection_ok = True
        if (
            level_ok
            and decision.identification_level.value in _SELECTION_REQUIRING_LEVELS
            and case.acceptable_catalogue_product_ids
        ):
            selection_ok = selected_product_id in set(case.acceptable_catalogue_product_ids)
        identification_hierarchy_correct = level_ok and selection_ok

    return CaseResult(
        case=case,
        record=record,
        comparison=comparison,
        checks=tuple(checks),
        correct=correct and not harmful_errors,
        harmful_errors=tuple(harmful_errors),
        is_avoidable_abstention=is_avoidable_abstention,
        is_justified_abstention=is_justified_abstention,
        is_technical_failure=is_technical_failure,
        top_acceptable_rank=_acceptable_candidate_rank(case, record),
        selected_product_id=selected_product_id,
        identification_hierarchy_correct=identification_hierarchy_correct,
    )


# --------------------------------------------------------------------------- #
# Stage-based failure classification (brief section 8)
# --------------------------------------------------------------------------- #
def classify_failure(
    result: CaseResult, repository: CandidateRepository, *, knowledge_version: str
) -> CaseFailure | None:
    """Assign a primary failure stage to a wrong or avoidably-abstaining
    case. Returns ``None`` for a correct, non-avoidably-abstaining case.

    Distinguishes (brief section 8's closing requirement):

    * Candidate absent from the tested knowledge version -> KNOWLEDGE_FAILURE.
    * Candidate present in knowledge but never retrieved -> RETRIEVAL_FAILURE.
    * Candidate retrieved but the wrong one was ultimately selected/evaluated
      -> EVALUATION_FAILURE.
    """
    case, record = result.case, result.record
    if result.correct and not result.is_avoidable_abstention:
        return None

    secondary: list[FailureCategory] = []

    if record.decision.decision_type == DecisionType.PROCESSING_FAILED:
        return CaseFailure(
            case_id=case.case_id,
            primary_category=FailureCategory.RUNTIME_FAILURE,
            secondary_categories=(),
            explanation="Decision is PROCESSING_FAILED (technical failure, not a product "
            "reasoning error).",
            related_object_ids=(record.decision.decision_id,),
        )

    if case.malformed or (case.title is None and not record.evidence):
        return CaseFailure(
            case_id=case.case_id,
            primary_category=FailureCategory.OBSERVATION_FAILURE,
            secondary_categories=(),
            explanation="Malformed/unusable input never reached extraction.",
            related_object_ids=(record.observation.observation_id,),
        )

    if case.required_evidence_types:
        present = {e.evidence_type.value for e in record.evidence}
        missing = [t for t in case.required_evidence_types if t not in present]
        if missing:
            return CaseFailure(
                case_id=case.case_id,
                primary_category=FailureCategory.EVIDENCE_FAILURE,
                secondary_categories=tuple(secondary),
                explanation=f"Required evidence type(s) never extracted: {missing}.",
                related_object_ids=tuple(e.evidence_id for e in record.evidence),
            )

    if case.require_contradicted_claim or case.expected_contradiction_fields:
        from .enums import ClaimStatus

        has_contradicted = any(c.status == ClaimStatus.CONTRADICTED for c in record.claims)
        if case.require_contradicted_claim and not has_contradicted:
            return CaseFailure(
                case_id=case.case_id,
                primary_category=FailureCategory.CLAIM_FAILURE,
                secondary_categories=tuple(secondary),
                explanation="Expected a contradicted Claim; none was produced.",
                related_object_ids=tuple(c.claim_id for c in record.claims),
            )

    if case.require_multiple_hypotheses and len(record.hypotheses) <= 1:
        return CaseFailure(
            case_id=case.case_id,
            primary_category=FailureCategory.HYPOTHESIS_FAILURE,
            secondary_categories=tuple(secondary),
            explanation="Expected multiple competing hypotheses; only "
            f"{len(record.hypotheses)} produced.",
            related_object_ids=tuple(h.hypothesis_id for h in record.hypotheses),
        )

    if case.catalogue_gap:
        return CaseFailure(
            case_id=case.case_id,
            primary_category=FailureCategory.KNOWLEDGE_FAILURE,
            secondary_categories=tuple(secondary),
            explanation="Gold-labelled catalogue gap (no acceptable Candidate exists in the "
            f"tested knowledge version {knowledge_version!r}); the wrong/avoidable outcome "
            "traces to missing knowledge coverage, not a retrieval or evaluation defect.",
        )

    # --- Candidate-centric distinction: knowledge vs retrieval vs evaluation
    if case.acceptable_catalogue_product_ids and not case.catalogue_gap:
        acceptable = set(case.acceptable_catalogue_product_ids)
        in_knowledge = {
            p.catalogue_product_id
            for p in repository.all_products(knowledge_version)
            if p.catalogue_product_id in acceptable
        }
        if not in_knowledge:
            return CaseFailure(
                case_id=case.case_id,
                primary_category=FailureCategory.KNOWLEDGE_FAILURE,
                secondary_categories=tuple(secondary),
                explanation="No acceptable catalogue product exists in the tested "
                f"knowledge version {knowledge_version!r} - the gold label references a "
                "product the catalogue does not (yet) contain, but the case was not "
                "flagged catalogue_gap.",
            )
        retrieved_ids = {c.catalogue_product_id for c in record.candidates}
        if not (in_knowledge & retrieved_ids):
            return CaseFailure(
                case_id=case.case_id,
                primary_category=FailureCategory.RETRIEVAL_FAILURE,
                secondary_categories=tuple(secondary),
                explanation="An acceptable Candidate exists in the knowledge base but was "
                "never retrieved for this case.",
                related_object_ids=tuple(c.candidate_instance_id for c in record.candidates),
            )
        # Retrieved, but the wrong Candidate was ultimately selected/rejected.
        return CaseFailure(
            case_id=case.case_id,
            primary_category=FailureCategory.EVALUATION_FAILURE,
            secondary_categories=tuple(secondary),
            explanation="An acceptable Candidate was retrieved but Candidate Evaluation "
            "did not select it (wrong evaluation/ranking outcome).",
            related_object_ids=tuple(
                ev.candidate_evaluation_id for ev in record.candidate_evaluations
            ),
        )

    if result.harmful_errors or result.is_avoidable_abstention:
        return CaseFailure(
            case_id=case.case_id,
            primary_category=FailureCategory.DECISION_POLICY_FAILURE,
            secondary_categories=tuple(secondary),
            explanation=(
                f"Harmful outcome(s) {list(result.harmful_errors)}."
                if result.harmful_errors
                else "Avoidable abstention: gold annotation holds the available evidence "
                "supported a non-abstaining outcome."
            ),
            related_object_ids=(record.decision.decision_id,),
        )

    # Default: the Decision itself is wrong for a reason not narrowed above
    # (e.g. a disallowed decision_type/product_form/identity with an
    # otherwise-complete reasoning trace) - the policy applied the wrong
    # rule to a correct evaluation, not the evaluation itself.
    return CaseFailure(
        case_id=case.case_id,
        primary_category=FailureCategory.DECISION_POLICY_FAILURE,
        secondary_categories=tuple(secondary),
        explanation="Decision Formation reached a gold-disallowed outcome despite an "
        "otherwise-unremarkable reasoning trace.",
        related_object_ids=(record.decision.decision_id,),
    )
