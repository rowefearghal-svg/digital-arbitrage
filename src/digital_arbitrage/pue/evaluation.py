"""Candidate Evaluation (spec section 15).

Evaluates how well each retrieved Candidate explains the listing, records
agreements/contradictions/missing information separately, and applies the
hard-rejection matrix. Retrieval similarity can never override a hard
product-form contradiction (spec 15.6 worked example; risk 4 control).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .catalogue import CandidateRepository
from .enums import (
    CandidateOutcome,
    ClaimPredicate,
    ClaimStatus,
    ComparisonResult,
    ContradictionSeverity,
    ProductForm,
)
from .models import (
    Candidate,
    CandidateEvaluation,
    Claim,
    ComparisonFinding,
    ProcessingContext,
    ProductHypothesis,
)

#: Product forms that are never the same sold item as a complete GPU.
_NON_COMPLETE_FORMS = {
    ProductForm.ACCESSORY,
    ProductForm.COMPONENT,
    ProductForm.REPLACEMENT_PART,
    ProductForm.PACKAGING_ONLY,
    ProductForm.SERVICE,
    ProductForm.COMPATIBLE_ITEM,
}


class _HasHypothesesAndCandidates(Protocol):
    hypotheses: Sequence[ProductHypothesis]
    candidates: Sequence[Candidate]
    claims: Sequence[Claim]


def _hypothesis_for(
    hyp_id: str, hypotheses: Sequence[ProductHypothesis]
) -> ProductHypothesis | None:
    for h in hypotheses:
        if h.hypothesis_id == hyp_id:
            return h
    return None


def _mpn_claims(claims: Sequence[Claim]) -> list[Claim]:
    # A PROPOSED identifier Claim has not yet been validated against the
    # catalogue (see claims.validate_identifier_claims) and must never be
    # treated as agreement here; only a validated, SUPPORTED MPN Claim may
    # materially affect a Decision (spec 10.4-style rule; regression test:
    # test_invariants.py::test_exact_decision_never_depends_on_proposed_claim).
    return [
        c for c in claims if c.predicate is ClaimPredicate.MPN and c.status is ClaimStatus.SUPPORTED
    ]


def _mobile_form_factor_claim(claims: Sequence[Claim]) -> Claim | None:
    for c in claims:
        if c.predicate is ClaimPredicate.FORM_FACTOR and c.value == "mobile":
            return c
    return None


def _capacity_claim(claims: Sequence[Claim]) -> Claim | None:
    matches = [c for c in claims if c.predicate is ClaimPredicate.CAPACITY]
    return matches[0] if matches else None


def _evidence_ids_for_claims(claim_ids: Sequence[str], claims: Sequence[Claim]) -> tuple[str, ...]:
    """Resolve Claim ids to their supporting Evidence ids (never claim ids
    themselves - ``ComparisonFinding.evidence_ids`` must reference Evidence)."""
    by_id = {c.claim_id: c for c in claims}
    ids: list[str] = []
    for claim_id in claim_ids:
        claim = by_id.get(claim_id)
        if claim is not None:
            ids.extend(claim.supporting_evidence_ids)
    return tuple(dict.fromkeys(ids))


def evaluate_candidates(
    state: _HasHypothesesAndCandidates,
    repository: CandidateRepository,
    context: ProcessingContext,
) -> tuple[CandidateEvaluation, ...]:
    """Evaluate every retrieved Candidate against its originating hypothesis."""
    evaluations: list[CandidateEvaluation] = []
    mpn_claims = _mpn_claims(state.claims)
    capacity_claim = _capacity_claim(state.claims)
    mobile_claim = _mobile_form_factor_claim(state.claims)

    for candidate in state.candidates[: context.max_candidate_evaluations]:
        hypothesis = _hypothesis_for(candidate.hypothesis_id, state.hypotheses)
        product = repository.get_by_id(candidate.catalogue_product_id)

        agreements: list[ComparisonFinding] = []
        contradictions: list[ComparisonFinding] = []
        missing: list[ComparisonFinding] = []
        hard_rejected = False

        if hypothesis is None or product is None:
            evaluations.append(
                CandidateEvaluation(
                    candidate_evaluation_id=context.id_factory(),
                    candidate_instance_id=candidate.candidate_instance_id,
                    hypothesis_id=candidate.hypothesis_id,
                    agreements=(),
                    contradictions=(),
                    missing_information=(),
                    identity_fit=0.0,
                    product_form_fit=0.0,
                    attribute_fit=0.0,
                    evidence_coverage=0.0,
                    hard_rejected=True,
                    evaluation_outcome=CandidateOutcome.UNEVALUABLE,
                    policy_version=context.policy_version,
                )
            )
            continue

        # -- rule 1: explicit MPN disagreement -------------------------- #
        candidate_mpns = {v.strip().lower() for v in product.identifiers.get("mpn", ())}
        for claim in mpn_claims:
            claim_value = str(claim.value).strip().lower()
            if candidate_mpns and claim_value not in candidate_mpns:
                contradictions.append(
                    ComparisonFinding(
                        field="mpn",
                        observed_value=claim.value,
                        candidate_value=tuple(product.identifiers.get("mpn", ())),
                        result=ComparisonResult.CONTRADICT,
                        severity=ContradictionSeverity.HARD,
                        evidence_ids=claim.supporting_evidence_ids,
                        explanation="Listing MPN does not match this Candidate's MPN.",
                    )
                )
                hard_rejected = True
            elif claim_value in candidate_mpns:
                agreements.append(
                    ComparisonFinding(
                        field="mpn",
                        observed_value=claim.value,
                        candidate_value=tuple(product.identifiers.get("mpn", ())),
                        result=ComparisonResult.AGREE,
                        severity=None,
                        evidence_ids=claim.supporting_evidence_ids,
                        explanation="Listing MPN matches this Candidate's validated MPN.",
                    )
                )

        # -- rule 2/4: non-complete listing form vs. complete Candidate -- #
        if hypothesis.product_form in _NON_COMPLETE_FORMS and product.product_form in (
            ProductForm.COMPLETE_PRODUCT,
            ProductForm.INCOMPLETE_PRODUCT,
        ):
            contradictions.append(
                ComparisonFinding(
                    field="product_form",
                    observed_value=hypothesis.product_form.value,
                    candidate_value=product.product_form.value,
                    result=ComparisonResult.CONTRADICT,
                    severity=ContradictionSeverity.HARD,
                    evidence_ids=_evidence_ids_for_claims(hypothesis.claim_ids, state.claims),
                    explanation=(
                        "Listing is supported as "
                        f"{hypothesis.product_form.value}, not a complete graphics card."
                    ),
                )
            )
            hard_rejected = True
        elif hypothesis.product_form == product.product_form:
            agreements.append(
                ComparisonFinding(
                    field="product_form",
                    observed_value=hypothesis.product_form.value,
                    candidate_value=product.product_form.value,
                    result=ComparisonResult.AGREE,
                    severity=None,
                    evidence_ids=(),
                    explanation="Listing and Candidate product form agree.",
                )
            )
        else:
            missing.append(
                ComparisonFinding(
                    field="product_form",
                    observed_value=hypothesis.product_form.value,
                    candidate_value=product.product_form.value,
                    result=ComparisonResult.MISSING,
                    severity=None,
                    evidence_ids=(),
                    explanation="Product form relationship not directly comparable.",
                )
            )

        # -- rule 3: explicit GPU-not-included exclusion ------------------ #
        not_included_claims = [
            c
            for c in state.claims
            if c.predicate is ClaimPredicate.NOT_INCLUDED and c.value == "graphics_card"
        ]
        if not_included_claims and product.product_form == ProductForm.COMPLETE_PRODUCT:
            contradictions.append(
                ComparisonFinding(
                    field="included",
                    observed_value="graphics_card_not_included",
                    candidate_value="complete_product",
                    result=ComparisonResult.CONTRADICT,
                    severity=ContradictionSeverity.HARD,
                    evidence_ids=not_included_claims[0].supporting_evidence_ids,
                    explanation="Listing explicitly states the GPU/card is not included.",
                )
            )
            hard_rejected = True

        # -- rule 5: explicit family conflict ------------------------------ #
        if hypothesis.family is not None and hypothesis.family != product.family:
            if hypothesis.family not in product.compatibility_targets:
                contradictions.append(
                    ComparisonFinding(
                        field="family",
                        observed_value=hypothesis.family,
                        candidate_value=product.family,
                        result=ComparisonResult.CONTRADICT,
                        severity=ContradictionSeverity.HARD,
                        evidence_ids=_evidence_ids_for_claims(hypothesis.claim_ids, state.claims),
                        explanation="Listing family conflicts with Candidate family.",
                    )
                )
                hard_rejected = True
        elif hypothesis.family is not None and hypothesis.family == product.family:
            agreements.append(
                ComparisonFinding(
                    field="family",
                    observed_value=hypothesis.family,
                    candidate_value=product.family,
                    result=ComparisonResult.AGREE,
                    severity=None,
                    evidence_ids=_evidence_ids_for_claims(hypothesis.claim_ids, state.claims),
                    explanation="Listing and Candidate family agree.",
                )
            )
        elif hypothesis.family is None:
            missing.append(
                ComparisonFinding(
                    field="family",
                    observed_value=None,
                    candidate_value=product.family,
                    result=ComparisonResult.MISSING,
                    severity=None,
                    evidence_ids=(),
                    explanation="Listing does not state a family; not penalized.",
                )
            )

        # -- rule 6: mobile listing vs. desktop Candidate (hard) ------------ #
        if mobile_claim is not None and product.attributes.get("form_factor") == "desktop":
            contradictions.append(
                ComparisonFinding(
                    field="form_factor",
                    observed_value="mobile",
                    candidate_value="desktop",
                    result=ComparisonResult.CONTRADICT,
                    severity=ContradictionSeverity.HARD,
                    evidence_ids=mobile_claim.supporting_evidence_ids,
                    explanation=(
                        "Listing explicitly describes a laptop/mobile GPU; this "
                        "Candidate is a desktop product and cannot be the same item."
                    ),
                )
            )
            hard_rejected = True

        # -- rule 7: compatibility relationship treated as identity -------- #
        if hypothesis.product_form == ProductForm.COMPATIBLE_ITEM and product.product_form != (
            ProductForm.COMPATIBLE_ITEM
        ):
            contradictions.append(
                ComparisonFinding(
                    field="product_form",
                    observed_value="compatible_item",
                    candidate_value=product.product_form.value,
                    result=ComparisonResult.CONTRADICT,
                    severity=ContradictionSeverity.HARD,
                    evidence_ids=(),
                    explanation=(
                        "Listing describes compatibility only, not this Candidate's identity."
                    ),
                )
            )
            hard_rejected = True

        # -- brand / board-partner agreement (soft) ------------------------ #
        if hypothesis.brand is not None:
            if hypothesis.brand == product.brand:
                agreements.append(
                    ComparisonFinding(
                        field="brand",
                        observed_value=hypothesis.brand,
                        candidate_value=product.brand,
                        result=ComparisonResult.AGREE,
                        severity=None,
                        evidence_ids=(),
                        explanation="Board-partner brand agrees.",
                    )
                )
            else:
                contradictions.append(
                    ComparisonFinding(
                        field="brand",
                        observed_value=hypothesis.brand,
                        candidate_value=product.brand,
                        result=ComparisonResult.CONTRADICT,
                        severity=ContradictionSeverity.SOFT,
                        evidence_ids=(),
                        explanation="Board-partner brand differs (soft signal only).",
                    )
                )
        else:
            missing.append(
                ComparisonFinding(
                    field="brand",
                    observed_value=None,
                    candidate_value=product.brand,
                    result=ComparisonResult.MISSING,
                    severity=None,
                    evidence_ids=(),
                    explanation="Listing does not state a board partner; not penalized.",
                )
            )

        # -- critical attribute: capacity ---------------------------------- #
        candidate_capacity = product.attributes.get("capacity_gb")
        attribute_fit = 0.5
        if capacity_claim is not None and candidate_capacity is not None:
            if int(capacity_claim.value) == int(candidate_capacity):  # type: ignore[call-overload]
                attribute_fit = 1.0
                agreements.append(
                    ComparisonFinding(
                        field="capacity_gb",
                        observed_value=capacity_claim.value,
                        candidate_value=candidate_capacity,
                        result=ComparisonResult.AGREE,
                        severity=None,
                        evidence_ids=capacity_claim.supporting_evidence_ids,
                        explanation="Capacity agrees.",
                    )
                )
            else:
                attribute_fit = 0.0
                contradictions.append(
                    ComparisonFinding(
                        field="capacity_gb",
                        observed_value=capacity_claim.value,
                        candidate_value=candidate_capacity,
                        result=ComparisonResult.CONTRADICT,
                        severity=ContradictionSeverity.SOFT,
                        evidence_ids=capacity_claim.supporting_evidence_ids,
                        explanation="Capacity differs between listing and Candidate.",
                    )
                )
        else:
            missing.append(
                ComparisonFinding(
                    field="capacity_gb",
                    observed_value=capacity_claim.value if capacity_claim else None,
                    candidate_value=candidate_capacity,
                    result=ComparisonResult.MISSING,
                    severity=None,
                    evidence_ids=(),
                    explanation="Capacity not stated on one side; not penalized.",
                )
            )

        # -- fit scores ------------------------------------------------------ #
        exact_mpn_agree = any(
            f.field == "mpn" and f.result == ComparisonResult.AGREE for f in agreements
        )
        if exact_mpn_agree:
            identity_fit = 1.0
        elif hypothesis.family is not None and hypothesis.family == product.family:
            identity_fit = 0.7
        elif hypothesis.compatibility_target is not None and (
            hypothesis.compatibility_target == product.family
            or hypothesis.compatibility_target in product.compatibility_targets
        ):
            identity_fit = 0.5
        else:
            identity_fit = 0.0

        product_form_fit = 1.0 if hypothesis.product_form == product.product_form else 0.0
        evidence_coverage = hypothesis.evidence_coverage

        if hard_rejected:
            outcome = CandidateOutcome.REJECTED
        elif exact_mpn_agree and not any(
            f.severity == ContradictionSeverity.HARD for f in contradictions
        ):
            outcome = CandidateOutcome.STRONGLY_SUPPORTED
        elif identity_fit >= 0.7 and product_form_fit >= 1.0:
            outcome = CandidateOutcome.SUPPORTED
        elif identity_fit >= 0.5 and product_form_fit >= 1.0:
            outcome = CandidateOutcome.PROVISIONALLY_SUPPORTED
        elif product_form_fit >= 1.0:
            outcome = CandidateOutcome.WEAKLY_SUPPORTED
        elif contradictions:
            outcome = CandidateOutcome.CONTRADICTED
        else:
            outcome = CandidateOutcome.UNEVALUABLE

        evaluations.append(
            CandidateEvaluation(
                candidate_evaluation_id=context.id_factory(),
                candidate_instance_id=candidate.candidate_instance_id,
                hypothesis_id=candidate.hypothesis_id,
                agreements=tuple(agreements),
                contradictions=tuple(contradictions),
                missing_information=tuple(missing),
                identity_fit=identity_fit,
                product_form_fit=product_form_fit,
                attribute_fit=attribute_fit,
                evidence_coverage=evidence_coverage,
                hard_rejected=hard_rejected,
                evaluation_outcome=outcome,
                policy_version=context.policy_version,
            )
        )

    return tuple(evaluations)
