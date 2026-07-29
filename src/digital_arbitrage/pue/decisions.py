"""Decision Formation (spec section 16).

Turns the accumulated reasoning state (Observation, Claims, Hypotheses,
Candidates, Candidate Evaluations) into exactly one :class:`Decision`.
``ESCALATED`` never appears here; it is not a Decision type.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .catalogue import CandidateRepository
from .enums import (
    AbstentionReason,
    CalibrationStatus,
    ClaimPredicate,
    ClaimStatus,
    ComparabilityStatus,
    ComparisonResult,
    ContradictionSeverity,
    DecisionType,
    IdentificationLevel,
    ProductForm,
    UncertaintyBand,
)
from .models import (
    Candidate,
    CandidateEvaluation,
    Claim,
    Decision,
    DecisionUncertainty,
    Observation,
    ProcessingContext,
    ProductHypothesis,
)
from .policies import DecisionPolicy


class CaseReasoningState(Protocol):
    """Structural protocol for the accumulated per-case reasoning state."""

    observation: Observation
    claims: Sequence[Claim]
    hypotheses: Sequence[ProductHypothesis]
    candidates: Sequence[Candidate]
    candidate_evaluations: Sequence[CandidateEvaluation]


_NON_COMPLETE_CLASSIFIED_FORMS = (
    ProductForm.COMPONENT,
    ProductForm.REPLACEMENT_PART,
    ProductForm.ACCESSORY,
)


def _candidate_by_id(
    candidates: Sequence[Candidate], candidate_instance_id: str
) -> Candidate | None:
    for c in candidates:
        if c.candidate_instance_id == candidate_instance_id:
            return c
    return None


def _surviving(
    hypothesis: ProductHypothesis,
    candidates: Sequence[Candidate],
    evaluations: Sequence[CandidateEvaluation],
) -> list[tuple[Candidate, CandidateEvaluation]]:
    result = []
    for ev in evaluations:
        if ev.hypothesis_id != hypothesis.hypothesis_id or ev.hard_rejected:
            continue
        cand = _candidate_by_id(candidates, ev.candidate_instance_id)
        if cand is not None:
            result.append((cand, ev))
    result.sort(key=lambda pair: pair[0].retrieval_score, reverse=True)
    return result


def _contradiction_codes(evaluations: Sequence[CandidateEvaluation]) -> tuple[str, ...]:
    codes: list[str] = []
    for ev in evaluations:
        for finding in ev.contradictions:
            if finding.severity == ContradictionSeverity.HARD:
                code = f"hard_contradiction:{finding.field}"
                if code not in codes:
                    codes.append(code)
    return tuple(codes)


def _band(value: float, *, high: float, moderate: float) -> UncertaintyBand:
    if value >= high:
        return UncertaintyBand.HIGH
    if value >= moderate:
        return UncertaintyBand.MODERATE
    return UncertaintyBand.LOW


def _compute_uncertainty(
    observation: Observation,
    hypothesis: ProductHypothesis | None,
    surviving: Sequence[tuple[Candidate, CandidateEvaluation]],
    has_hard_contradiction: bool,
    has_soft_contradiction: bool,
    indistinguishable: bool,
) -> DecisionUncertainty:
    token_count = len(observation.normalized_title.split())
    observation_quality = _band(min(token_count / 6.0, 1.0), high=0.66, moderate=0.33)
    coverage = hypothesis.evidence_coverage if hypothesis is not None else 0.0
    claim_support = _band(coverage, high=0.66, moderate=0.33)
    evidence_coverage_band = _band(coverage, high=0.66, moderate=0.33)
    if surviving:
        candidate_fit = _band(surviving[0][1].identity_fit, high=0.9, moderate=0.5)
    else:
        candidate_fit = UncertaintyBand.UNKNOWN
    if has_hard_contradiction:
        contradiction_level = UncertaintyBand.HIGH
    elif has_soft_contradiction:
        contradiction_level = UncertaintyBand.MODERATE
    else:
        contradiction_level = UncertaintyBand.LOW
    if indistinguishable:
        distinguishability = UncertaintyBand.LOW
    elif surviving:
        distinguishability = UncertaintyBand.HIGH
    else:
        distinguishability = UncertaintyBand.UNKNOWN
    return DecisionUncertainty(
        observation_quality=observation_quality,
        claim_support=claim_support,
        candidate_fit=candidate_fit,
        evidence_coverage=evidence_coverage_band,
        contradiction_level=contradiction_level,
        distinguishability=distinguishability,
        calibration_status=CalibrationStatus.UNCALIBRATED,
    )


def _base_decision_kwargs(state: CaseReasoningState, context: ProcessingContext) -> dict:
    return dict(
        decision_id=context.id_factory(),
        case_id=state.observation.case_id,
        observation_id=state.observation.observation_id,
        policy_version=context.policy_version,
        knowledge_version=context.knowledge_version,
        capability_version=context.capability_version,
    )


def _abstained(
    state: CaseReasoningState,
    context: ProcessingContext,
    reason: AbstentionReason,
    uncertainty: DecisionUncertainty,
) -> Decision:
    return Decision(
        **_base_decision_kwargs(state, context),
        decision_type=DecisionType.ABSTAINED,
        identification_level=IdentificationLevel.UNKNOWN,
        selected_hypothesis_id=None,
        selected_candidate_instance_id=None,
        product_form=ProductForm.UNKNOWN,
        product_type=None,
        identified_brand=None,
        identified_family=None,
        identified_model=None,
        identified_variant=None,
        alternative_candidate_ids=(),
        unresolved_fields=(),
        contradiction_codes=(),
        abstention_reason=reason,
        review_recommended=True,
        comparability_status=ComparabilityStatus.INSUFFICIENT_INFORMATION,
        uncertainty=uncertainty,
    )


def _outside_domain(
    state: CaseReasoningState, context: ProcessingContext, uncertainty: DecisionUncertainty
) -> Decision:
    return Decision(
        **_base_decision_kwargs(state, context),
        decision_type=DecisionType.OUTSIDE_SUPPORTED_DOMAIN,
        identification_level=IdentificationLevel.UNKNOWN,
        selected_hypothesis_id=None,
        selected_candidate_instance_id=None,
        product_form=ProductForm.UNKNOWN,
        product_type=None,
        identified_brand=None,
        identified_family=None,
        identified_model=None,
        identified_variant=None,
        alternative_candidate_ids=(),
        unresolved_fields=(),
        contradiction_codes=(),
        abstention_reason=None,
        review_recommended=False,
        comparability_status=ComparabilityStatus.NOT_ASSESSED,
        uncertainty=uncertainty,
    )


def form_decision(
    state: CaseReasoningState,
    policy: DecisionPolicy,
    context: ProcessingContext,
    *,
    repository: CandidateRepository,
) -> Decision:
    """Form the final Decision for one case (spec section 16).

    Note on the component contract: the spec's abstract signature is
    ``form_decision(state, policy) -> Decision``. Resolving the winning
    Candidate's catalogue identity (brand/family/model/variant) requires the
    :class:`CandidateRepository`, and generating a deterministic
    ``decision_id`` requires the injectable ``ProcessingContext.id_factory``,
    so both are added as required parameters here. This is a documented,
    minimal deviation; no direct SQL or file parsing occurs in this module.
    """
    observation = state.observation
    hypotheses = list(state.hypotheses)

    if not hypotheses:
        uncertainty = _compute_uncertainty(observation, None, [], False, False, False)
        if not observation.normalized_title.strip():
            return _abstained(state, context, AbstentionReason.INSUFFICIENT_EVIDENCE, uncertainty)
        return _outside_domain(state, context, uncertainty)

    # Title/structured-attribute family conflicts take priority: a Decision
    # cannot be more specific than its (conflicting) supporting Claims.
    contradicted_family_claims = [
        c
        for c in state.claims
        if c.predicate is ClaimPredicate.PRODUCT_FAMILY and c.status == ClaimStatus.CONTRADICTED
    ]

    # More than one active hypothesis means materially different
    # interpretations remain plausible (spec 16.5): e.g. "water block alone"
    # vs. "complete card + water block bundle".
    if len(hypotheses) > 1:
        uncertainty = _compute_uncertainty(observation, hypotheses[0], [], False, False, True)
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.AMBIGUOUS,
            identification_level=IdentificationLevel.UNKNOWN,
            selected_hypothesis_id=None,
            selected_candidate_instance_id=None,
            product_form=ProductForm.UNKNOWN,
            product_type=None,
            identified_brand=None,
            identified_family=hypotheses[0].family or hypotheses[0].compatibility_target,
            identified_model=None,
            identified_variant=None,
            alternative_candidate_ids=tuple(
                c.candidate_instance_id
                for c in state.candidates
                if c.hypothesis_id in {h.hypothesis_id for h in hypotheses}
            ),
            unresolved_fields=("product_form",),
            contradiction_codes=(),
            abstention_reason=None,
            review_recommended=True,
            comparability_status=ComparabilityStatus.INSUFFICIENT_INFORMATION,
            uncertainty=uncertainty,
        )

    hypothesis = hypotheses[0]

    # -- packaging only ---------------------------------------------------- #
    if hypothesis.product_form == ProductForm.PACKAGING_ONLY:
        surviving = _surviving(hypothesis, state.candidates, state.candidate_evaluations)
        uncertainty = _compute_uncertainty(observation, hypothesis, surviving, True, False, False)
        codes = _contradiction_codes(
            [
                ev
                for ev in state.candidate_evaluations
                if ev.hypothesis_id == hypothesis.hypothesis_id
            ]
        )
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.CLASSIFIED,
            identification_level=IdentificationLevel.PRODUCT_TYPE,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=None,
            product_form=ProductForm.PACKAGING_ONLY,
            product_type=hypothesis.product_type,
            identified_brand=hypothesis.brand,
            identified_family=None,
            identified_model=None,
            identified_variant=None,
            alternative_candidate_ids=(),
            unresolved_fields=("catalogue_identity",),
            contradiction_codes=codes,
            abstention_reason=None,
            review_recommended=False,
            comparability_status=ComparabilityStatus.NOT_COMPARABLE_PRODUCT_FORM,
            uncertainty=uncertainty,
        )

    # -- accessory / component / replacement part -------------------------- #
    if hypothesis.product_form in _NON_COMPLETE_CLASSIFIED_FORMS:
        surviving = _surviving(hypothesis, state.candidates, state.candidate_evaluations)
        codes = _contradiction_codes(
            [
                ev
                for ev in state.candidate_evaluations
                if ev.hypothesis_id == hypothesis.hypothesis_id
            ]
        )
        uncertainty = _compute_uncertainty(
            observation, hypothesis, surviving, bool(codes), False, False
        )
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.CLASSIFIED,
            identification_level=IdentificationLevel.PRODUCT_TYPE,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=(
                surviving[0][0].candidate_instance_id if surviving else None
            ),
            product_form=hypothesis.product_form,
            product_type=hypothesis.product_type,
            identified_brand=hypothesis.brand,
            identified_family=None,
            identified_model=None,
            identified_variant=None,
            alternative_candidate_ids=tuple(c.candidate_instance_id for c, _ in surviving[1:]),
            unresolved_fields=("exact_variant",),
            contradiction_codes=codes,
            abstention_reason=None,
            review_recommended=False,
            comparability_status=ComparabilityStatus.NOT_COMPARABLE_PRODUCT_FORM,
            uncertainty=uncertainty,
        )

    # -- compatible item, no sold-item noun -------------------------------- #
    if hypothesis.product_form == ProductForm.COMPATIBLE_ITEM:
        uncertainty = _compute_uncertainty(observation, hypothesis, [], False, False, False)
        return _abstained(state, context, AbstentionReason.INSUFFICIENT_EVIDENCE, uncertainty)

    # -- bundle: never directly comparable to a single product ------------- #
    if hypothesis.product_form == ProductForm.BUNDLE:
        surviving = _surviving(hypothesis, state.candidates, state.candidate_evaluations)
        codes = _contradiction_codes(
            [
                ev
                for ev in state.candidate_evaluations
                if ev.hypothesis_id == hypothesis.hypothesis_id
            ]
        )
        uncertainty = _compute_uncertainty(
            observation, hypothesis, surviving, bool(codes), False, False
        )
        level = IdentificationLevel.MODEL if hypothesis.family else IdentificationLevel.PRODUCT_TYPE
        decision_type = (
            DecisionType.PARTIALLY_IDENTIFIED if hypothesis.family else DecisionType.CLASSIFIED
        )
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=decision_type,
            identification_level=level,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=None,
            product_form=ProductForm.BUNDLE,
            product_type=hypothesis.product_type,
            identified_brand=hypothesis.brand,
            identified_family=hypothesis.family,
            identified_model=hypothesis.model,
            identified_variant=None,
            alternative_candidate_ids=tuple(c.candidate_instance_id for c, _ in surviving),
            unresolved_fields=("bundle_contents", "exact_catalogue_product"),
            contradiction_codes=codes,
            abstention_reason=None,
            review_recommended=False,
            comparability_status=ComparabilityStatus.NOT_COMPARABLE_BUNDLE,
            uncertainty=uncertainty,
        )

    # -- complete / incomplete product: the main identification ladder ----- #
    surviving = _surviving(hypothesis, state.candidates, state.candidate_evaluations)
    all_hyp_evals = [
        ev for ev in state.candidate_evaluations if ev.hypothesis_id == hypothesis.hypothesis_id
    ]
    has_hard = any(
        finding.severity == ContradictionSeverity.HARD
        for ev in all_hyp_evals
        for finding in ev.contradictions
    )
    has_soft = any(
        finding.severity == ContradictionSeverity.SOFT
        for ev in all_hyp_evals
        for finding in ev.contradictions
    )
    codes = _contradiction_codes(all_hyp_evals)

    if contradicted_family_claims:
        uncertainty = _compute_uncertainty(observation, hypothesis, surviving, True, has_soft, True)
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.AMBIGUOUS,
            identification_level=IdentificationLevel.UNKNOWN,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=None,
            product_form=hypothesis.product_form,
            product_type=hypothesis.product_type,
            identified_brand=hypothesis.brand,
            identified_family=None,
            identified_model=None,
            identified_variant=None,
            alternative_candidate_ids=tuple(c.candidate_instance_id for c, _ in surviving),
            unresolved_fields=("product_family",),
            contradiction_codes=("title_structured_attribute_conflict",) + codes,
            abstention_reason=None,
            review_recommended=True,
            comparability_status=ComparabilityStatus.INSUFFICIENT_INFORMATION,
            uncertainty=uncertainty,
        )

    if not surviving:
        # Zero surviving Candidates is valid; never force the nearest match.
        uncertainty = _compute_uncertainty(observation, hypothesis, [], has_hard, has_soft, False)
        if hypothesis.family is not None or hypothesis.product_type == "graphics_card":
            level = (
                IdentificationLevel.FAMILY
                if hypothesis.family
                else IdentificationLevel.PRODUCT_TYPE
            )
            return Decision(
                **_base_decision_kwargs(state, context),
                decision_type=DecisionType.CLASSIFIED,
                identification_level=level,
                selected_hypothesis_id=hypothesis.hypothesis_id,
                selected_candidate_instance_id=None,
                product_form=hypothesis.product_form,
                product_type=hypothesis.product_type,
                identified_brand=hypothesis.brand,
                identified_family=hypothesis.family,
                identified_model=hypothesis.model,
                identified_variant=None,
                alternative_candidate_ids=(),
                unresolved_fields=("exact_catalogue_product",),
                contradiction_codes=codes,
                abstention_reason=None,
                review_recommended=False,
                comparability_status=(
                    ComparabilityStatus.COMPARABLE_AT_BROADER_LEVEL
                    if hypothesis.family
                    else ComparabilityStatus.INSUFFICIENT_INFORMATION
                ),
                uncertainty=uncertainty,
            )
        return _abstained(state, context, AbstentionReason.NO_SUITABLE_CANDIDATE, uncertainty)

    top_candidate, top_eval = surviving[0]
    distinct_products = {c.catalogue_product_id for c, _ in surviving}
    second_best_score = surviving[1][0].retrieval_score if len(surviving) > 1 else 0.0
    material_lead = (top_candidate.retrieval_score - second_best_score) >= policy.material_lead_gap
    exact_mpn_agree = any(
        f.field == "mpn" and f.result == ComparisonResult.AGREE for f in top_eval.agreements
    )
    brand_agree = any(
        f.field == "brand" and f.result == ComparisonResult.AGREE for f in top_eval.agreements
    )
    indistinguishable = len(distinct_products) > 1 and not material_lead and not exact_mpn_agree

    uncertainty = _compute_uncertainty(
        observation, hypothesis, surviving, has_hard, has_soft, indistinguishable
    )
    product = repository.get_by_id(top_candidate.catalogue_product_id)

    alternatives = tuple(c.candidate_instance_id for c, _ in surviving[1:])

    # -- exact identification ------------------------------------------- #
    is_exact = (
        product is not None
        and not indistinguishable
        and top_eval.evidence_coverage >= policy.exact_evidence_coverage_threshold
        and top_eval.identity_fit >= policy.exact_identity_fit_threshold
        and (exact_mpn_agree or (brand_agree and material_lead))
    )
    if is_exact and product is not None:
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.IDENTIFIED,
            identification_level=IdentificationLevel.EXACT_CATALOGUE_PRODUCT,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=top_candidate.candidate_instance_id,
            product_form=product.product_form,
            product_type=product.product_type,
            identified_brand=product.brand,
            identified_family=product.family,
            identified_model=product.model,
            identified_variant=product.variant,
            alternative_candidate_ids=alternatives,
            unresolved_fields=(),
            contradiction_codes=codes,
            abstention_reason=None,
            review_recommended=False,
            comparability_status=(
                ComparabilityStatus.DIRECTLY_COMPARABLE
                if hypothesis.product_form == ProductForm.COMPLETE_PRODUCT
                else ComparabilityStatus.NOT_COMPARABLE_CONDITION
            ),
            uncertainty=uncertainty,
        )

    # -- partial identification (family/model known, variant unresolved) - #
    if (
        hypothesis.family is not None
        and top_eval.evidence_coverage >= policy.minimum_usable_evidence_coverage
    ):
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.PARTIALLY_IDENTIFIED,
            identification_level=IdentificationLevel.MODEL,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=None,
            product_form=hypothesis.product_form,
            product_type=hypothesis.product_type,
            identified_brand=hypothesis.brand,
            identified_family=hypothesis.family,
            identified_model=hypothesis.model,
            identified_variant=None,
            alternative_candidate_ids=tuple(c.candidate_instance_id for c, _ in surviving),
            unresolved_fields=("brand", "variant"),
            contradiction_codes=codes,
            abstention_reason=None,
            review_recommended=False,
            comparability_status=(
                ComparabilityStatus.NOT_COMPARABLE_CONDITION
                if hypothesis.product_form == ProductForm.INCOMPLETE_PRODUCT
                else ComparabilityStatus.COMPARABLE_AT_BROADER_LEVEL
            ),
            uncertainty=uncertainty,
        )

    # -- classified (product type/form known, catalogue identity absent) - #
    if hypothesis.product_type == "graphics_card":
        return Decision(
            **_base_decision_kwargs(state, context),
            decision_type=DecisionType.CLASSIFIED,
            identification_level=IdentificationLevel.PRODUCT_TYPE,
            selected_hypothesis_id=hypothesis.hypothesis_id,
            selected_candidate_instance_id=None,
            product_form=hypothesis.product_form,
            product_type=hypothesis.product_type,
            identified_brand=hypothesis.brand,
            identified_family=hypothesis.family,
            identified_model=hypothesis.model,
            identified_variant=None,
            alternative_candidate_ids=tuple(c.candidate_instance_id for c, _ in surviving),
            unresolved_fields=("exact_catalogue_product",),
            contradiction_codes=codes,
            abstention_reason=None,
            review_recommended=False,
            comparability_status=ComparabilityStatus.INSUFFICIENT_INFORMATION,
            uncertainty=uncertainty,
        )

    return _abstained(state, context, AbstentionReason.CANDIDATES_INDISTINGUISHABLE, uncertainty)
