"""Explanation Generation (spec section 17).

Deterministic, template-based explanations derived only from the actual
reasoning record. Faithfulness is validated before publication (spec 17.2):
every cited Evidence ID must exist, no rejected Candidate may be described
as selected, and product form must match the Decision.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .enums import ContradictionSeverity, DecisionType, ExplanationProfile
from .models import (
    Candidate,
    CandidateEvaluation,
    Claim,
    Decision,
    Evidence,
    Explanation,
    ProcessingContext,
    ProductHypothesis,
)
from .validation import PueValidationError


class _State(Protocol):
    evidence: Sequence[Evidence]
    claims: Sequence[Claim]
    hypotheses: Sequence[ProductHypothesis]
    candidates: Sequence[Candidate]
    candidate_evaluations: Sequence[CandidateEvaluation]


def _hypothesis_for(
    hyp_id: str | None, hypotheses: Sequence[ProductHypothesis]
) -> ProductHypothesis | None:
    if hyp_id is None:
        return None
    for h in hypotheses:
        if h.hypothesis_id == hyp_id:
            return h
    return None


def _label(decision: Decision) -> str:
    parts = [p for p in (decision.identified_brand, decision.identified_family) if p]
    if parts:
        return " ".join(str(p) for p in parts)
    if decision.product_type:
        return str(decision.product_type).replace("_", " ")
    return "the listed item"


def generate_explanation(
    state: _State, decision: Decision, context: ProcessingContext
) -> Explanation:
    """Generate a faithful, evidence-grounded Explanation for ``decision``."""
    hypothesis = _hypothesis_for(decision.selected_hypothesis_id, state.hypotheses)
    supporting: list[str] = []
    contradictory: list[str] = []
    unresolved: list[str] = []
    rejected: list[str] = []
    evidence_ids: list[str] = []

    if hypothesis is not None:
        claims_by_id = {c.claim_id: c for c in state.claims}
        for claim_id in hypothesis.claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is not None:
                evidence_ids.extend(claim.supporting_evidence_ids)

    for ev in state.candidate_evaluations:
        for finding in ev.agreements:
            supporting.append(f"{finding.field}: {finding.explanation}")
            evidence_ids.extend(finding.evidence_ids)
        for finding in ev.contradictions:
            contradictory.append(
                f"{finding.field} ({finding.severity.value if finding.severity else 'soft'}): "
                f"{finding.explanation}"
            )
            evidence_ids.extend(finding.evidence_ids)
        if ev.hard_rejected:
            rejected.append(
                f"Candidate {ev.candidate_instance_id} rejected: "
                + "; ".join(
                    f.explanation
                    for f in ev.contradictions
                    if f.severity == ContradictionSeverity.HARD
                )
            )

    for field in decision.unresolved_fields:
        unresolved.append(f"{field} could not be established from the available evidence.")

    if decision.decision_type == DecisionType.IDENTIFIED:
        summary = (
            f"Identified as {_label(decision)}"
            + (f" {decision.identified_variant}" if decision.identified_variant else "")
            + ". No material contradiction was found."
        )
    elif decision.decision_type == DecisionType.PARTIALLY_IDENTIFIED:
        summary = (
            f"Identified as an {_label(decision)} graphics card. "
            "The exact board-partner variant could not be established."
        )
    elif decision.decision_type == DecisionType.CLASSIFIED:
        type_label = (decision.product_type or "item").replace("_", " ")
        summary = (
            f"Classified as a {type_label}, not a complete graphics card."
            if (decision.product_form.value not in ("complete_product", "incomplete_product"))
            else f"Classified as a {type_label}. Exact catalogue identity is unresolved."
        )
    elif decision.decision_type == DecisionType.AMBIGUOUS:
        summary = (
            "The listing could plausibly describe more than one materially different product; "
            "available evidence cannot distinguish them."
        )
    elif decision.decision_type == DecisionType.ABSTAINED:
        reason = decision.abstention_reason.value if decision.abstention_reason else "unknown"
        summary = f"Abstained from a product decision: {reason.replace('_', ' ')}."
    elif decision.decision_type == DecisionType.OUTSIDE_SUPPORTED_DOMAIN:
        summary = (
            "This listing does not appear to be within the supported graphics-hardware domain."
        )
    else:
        summary = "Processing could not complete for this listing."

    explanation = Explanation(
        explanation_id=context.id_factory(),
        decision_id=decision.decision_id,
        summary=summary,
        supporting_points=tuple(supporting),
        contradictory_points=tuple(contradictory),
        unresolved_points=tuple(unresolved),
        rejected_alternatives=tuple(rejected),
        evidence_ids=tuple(dict.fromkeys(evidence_ids)),
        profile=ExplanationProfile.OPERATOR,
    )
    _validate_faithfulness(state, decision, explanation)
    return explanation


def _validate_faithfulness(state: _State, decision: Decision, explanation: Explanation) -> None:
    """Faithfulness checks (spec 17.2)."""
    known_evidence_ids: set[str] = set()
    for claim in state.claims:
        known_evidence_ids.update(claim.supporting_evidence_ids)
        known_evidence_ids.update(claim.contradicting_evidence_ids)
        known_evidence_ids.update(claim.qualifying_evidence_ids)
    for ev in state.evidence:
        known_evidence_ids.add(ev.evidence_id)

    for eid in explanation.evidence_ids:
        if eid not in known_evidence_ids:
            raise PueValidationError(f"Explanation cites unknown evidence id: {eid}")

    if decision.decision_type == DecisionType.ABSTAINED and decision.abstention_reason is None:
        raise PueValidationError("ABSTAINED Decision must carry an abstention_reason")

    for ce in state.candidate_evaluations:
        if ce.hard_rejected and ce.candidate_instance_id == decision.selected_candidate_instance_id:
            raise PueValidationError("A hard-rejected Candidate cannot be the selected Candidate")
