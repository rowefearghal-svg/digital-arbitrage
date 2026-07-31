"""Executable hard-contradiction matrix (Sprint 2, Task 6; rebuilt for the
Sprint 2 pre-merge correction item 4).

Enumerates all seven v0.1 hard-rejection rules (spec section 15.3) as one
parameterized matrix. Each row builds a **valid reasoning graph** rooted in
one real, admitted :class:`Observation`:

    Observation -> real Evidence -> Claim -> ProductHypothesis -> Candidate
    -> CandidateEvaluation -> Decision

Every Claim's ``supporting_evidence_ids`` references a real ``Evidence``
object that is actually present in the row's Evidence tuple and whose
``observation_id`` matches the same admitted Observation used for Decision
Formation - no fabricated Evidence IDs, no mismatched ``observation_id``
values. This file adds no new production logic; it only exercises the
already-implemented, already-tested inline rules in ``evaluation.py`` (spec
section 15.3 / risk 4 control).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.decisions import form_decision
from digital_arbitrage.pue.enums import (
    CandidateOutcome,
    ClaimPredicate,
    ClaimStatus,
    ContradictionSeverity,
    EvidenceType,
    HypothesisStatus,
    ProductForm,
    RetrievalMethod,
    SupportLevel,
)
from digital_arbitrage.pue.evaluation import evaluate_candidates
from digital_arbitrage.pue.models import (
    Candidate,
    CandidateEvaluation,
    Claim,
    Evidence,
    Observation,
    ProductHypothesis,
)
from digital_arbitrage.pue.policies import DecisionPolicy

from .conftest import make_normalized


@dataclass
class _MatrixState:
    """Minimal structural stand-in for the reasoning state that
    ``evaluate_candidates`` requires (hypotheses, candidates, claims only)."""

    hypotheses: tuple[ProductHypothesis, ...]
    candidates: tuple[Candidate, ...]
    claims: tuple[Claim, ...]


@dataclass
class _DecisionReasoningState:
    """Minimal structural stand-in for ``decisions.CaseReasoningState``."""

    observation: Observation
    claims: tuple[Claim, ...]
    hypotheses: tuple[ProductHypothesis, ...]
    candidates: tuple[Candidate, ...]
    candidate_evaluations: tuple[CandidateEvaluation, ...]


@dataclass
class MatrixRow:
    """One fully-built, valid reasoning graph for a single hard-rejection
    rule, plus the field the resulting HARD contradiction must land on."""

    observation: Observation
    evidence: tuple[Evidence, ...]
    claims: tuple[Claim, ...]
    hypothesis: ProductHypothesis
    candidate: Candidate
    expected_field: str


def _observation(context, title: str) -> Observation:
    return admit_observation(make_normalized(title), context)


def _evidence(
    context, observation: Observation, evidence_type: EvidenceType, raw_value: str
) -> Evidence:
    """A real Evidence object rooted in ``observation`` (same
    ``observation_id``) - never a fabricated ID with no backing object."""
    return Evidence(
        evidence_id=context.id_factory(),
        observation_id=observation.observation_id,
        evidence_type=evidence_type,
        raw_value=raw_value,
        normalized_value=raw_value.lower(),
        source_field="title",
        source_start=0,
        source_end=len(raw_value),
        extraction_method="test_hard_contradiction_matrix_fixture",
        extraction_confidence=1.0,
        polarity_hint=None,
        capability_version=context.capability_version,
    )


def _claim(
    context, observation: Observation, predicate: ClaimPredicate, value, evidence: Evidence
) -> Claim:
    """A Claim whose ``observation_id`` matches ``observation`` and whose
    ``supporting_evidence_ids`` references a real, co-located Evidence id."""
    return Claim(
        claim_id=context.id_factory(),
        observation_id=observation.observation_id,
        predicate=predicate,
        value=value,
        status=ClaimStatus.SUPPORTED,
        supporting_evidence_ids=(evidence.evidence_id,),
        contradicting_evidence_ids=(),
        qualifying_evidence_ids=(),
        support_level=SupportLevel.STRONG,
        created_by="test_hard_contradiction_matrix",
        capability_version=context.capability_version,
    )


def _hypothesis(
    context,
    observation: Observation,
    *,
    claim_ids: tuple[str, ...],
    product_form: ProductForm,
    product_type: str | None,
    family: str | None,
) -> ProductHypothesis:
    return ProductHypothesis(
        hypothesis_id=context.id_factory(),
        observation_id=observation.observation_id,
        claim_ids=claim_ids,
        product_form=product_form,
        product_type=product_type,
        brand=None,
        family=family,
        model=family,
        variant=None,
        compatibility_target=family if product_form == ProductForm.COMPATIBLE_ITEM else None,
        coherence=1.0,
        evidence_coverage=0.5,
        status=HypothesisStatus.ACTIVE,
        unresolved_fields=(),
    )


def _candidate(context, hypothesis_id: str, catalogue_product_id: str) -> Candidate:
    return Candidate(
        candidate_instance_id=context.id_factory(),
        catalogue_product_id=catalogue_product_id,
        hypothesis_id=hypothesis_id,
        retrieval_method=RetrievalMethod.STRUCTURED_FILTER,
        retrieval_rank=0,
        # Deliberately high similarity: proves retrieval score alone cannot
        # override a hard contradiction (spec risk 4 control).
        retrieval_score=99.0,
        matched_fields=("family",),
        knowledge_version=context.knowledge_version,
    )


def _row_explicit_mpn_disagreement(context) -> MatrixRow:
    obs = _observation(context, "ASUS TUF RTX 4090 WRONG-MPN-999")
    ev = _evidence(context, obs, EvidenceType.MPN_TOKEN, "WRONG-MPN-999")
    claim = _claim(context, obs, ClaimPredicate.MPN, "WRONG-MPN-999", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.COMPLETE_PRODUCT,
        product_type="graphics_card",
        family="rtx 4090",
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-asus-tuf-rtx4090-o24g")
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "mpn")


def _row_non_complete_form_vs_complete_gpu(context) -> MatrixRow:
    obs = _observation(context, "RTX 4090 GPU Anti-Sag Support Bracket")
    ev = _evidence(context, obs, EvidenceType.PRODUCT_TYPE_TERM, "bracket")
    claim = _claim(context, obs, ClaimPredicate.PRODUCT_FORM, "accessory", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.ACCESSORY,
        product_type="gpu_bracket",
        family=None,
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "product_form")


def _row_gpu_not_included(context) -> MatrixRow:
    obs = _observation(context, "RTX 4090 Waterblock - GPU not included")
    ev = _evidence(context, obs, EvidenceType.EXCLUSION_TERM, "GPU not included")
    claim = _claim(context, obs, ClaimPredicate.NOT_INCLUDED, "graphics_card", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.COMPONENT,
        product_type="gpu_water_block",
        family=None,
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "included")


def _row_packaging_only_vs_contained_gpu(context) -> MatrixRow:
    obs = _observation(context, "Empty RTX 4090 Founders Edition Box Only")
    ev = _evidence(context, obs, EvidenceType.PACKAGING_TERM, "box only")
    claim = _claim(context, obs, ClaimPredicate.PRODUCT_FORM, "packaging_only", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.PACKAGING_ONLY,
        product_type="retail_packaging",
        family=None,
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "product_form")


def _row_unexplained_family_conflict(context) -> MatrixRow:
    obs = _observation(context, "RTX 4090 Graphics Card")
    ev = _evidence(context, obs, EvidenceType.PRODUCT_FAMILY_TOKEN, "4090")
    claim = _claim(context, obs, ClaimPredicate.PRODUCT_FAMILY, "rtx 4090", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.COMPLETE_PRODUCT,
        product_type="graphics_card",
        family="rtx 4090",
    )
    # An RTX 4080 Super Candidate does not list "rtx 4090" as a
    # compatibility target - a genuine, unexplained family conflict.
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-asus-tuf-rtx4080super-oc")
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "family")


def _row_desktop_vs_mobile_conflict(context) -> MatrixRow:
    obs = _observation(context, "Laptop RTX 4090 GPU")
    ev = _evidence(context, obs, EvidenceType.PRODUCT_FORM_TERM, "laptop")
    claim = _claim(context, obs, ClaimPredicate.FORM_FACTOR, "mobile", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.COMPLETE_PRODUCT,
        product_type="graphics_card",
        family="rtx 4090",
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")  # desktop
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "form_factor")


def _row_compatibility_treated_as_identity(context) -> MatrixRow:
    obs = _observation(context, "Compatible with RTX 4090")
    ev = _evidence(context, obs, EvidenceType.COMPATIBILITY_TERM, "compatible with")
    claim = _claim(context, obs, ClaimPredicate.COMPATIBLE_WITH, "rtx 4090", ev)
    hyp = _hypothesis(
        context,
        obs,
        claim_ids=(claim.claim_id,),
        product_form=ProductForm.COMPATIBLE_ITEM,
        product_type=None,
        family="rtx 4090",
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return MatrixRow(obs, (ev,), (claim,), hyp, candidate, "product_form")


MATRIX_ROWS = [
    pytest.param(_row_explicit_mpn_disagreement, id="explicit_mpn_disagreement"),
    pytest.param(_row_non_complete_form_vs_complete_gpu, id="non_complete_form_vs_complete_gpu"),
    pytest.param(_row_gpu_not_included, id="gpu_explicitly_not_included"),
    pytest.param(_row_packaging_only_vs_contained_gpu, id="packaging_only_vs_contained_gpu"),
    pytest.param(_row_unexplained_family_conflict, id="unexplained_family_conflict"),
    pytest.param(_row_desktop_vs_mobile_conflict, id="desktop_vs_mobile_conflict"),
    pytest.param(
        _row_compatibility_treated_as_identity, id="compatibility_relationship_treated_as_identity"
    ),
]


@pytest.mark.parametrize("build_row", MATRIX_ROWS)
def test_hard_contradiction_matrix_row(build_row, deterministic_context, repository) -> None:
    row = build_row(deterministic_context)

    # Sanity check on the graph itself before evaluating it: every Claim's
    # supporting Evidence really exists and really belongs to the same
    # Observation used for Decision Formation (the exact defect this
    # rebuild corrects - Sprint 2 pre-merge correction item 4).
    evidence_by_id = {e.evidence_id: e for e in row.evidence}
    for claim in row.claims:
        assert claim.observation_id == row.observation.observation_id
        for eid in claim.supporting_evidence_ids:
            assert eid in evidence_by_id, f"Claim references nonexistent Evidence id {eid!r}"
            assert evidence_by_id[eid].observation_id == row.observation.observation_id
    assert row.hypothesis.observation_id == row.observation.observation_id

    eval_state = _MatrixState(
        hypotheses=(row.hypothesis,), candidates=(row.candidate,), claims=row.claims
    )
    evaluations = evaluate_candidates(eval_state, repository, deterministic_context)
    assert len(evaluations) == 1
    evaluation = evaluations[0]

    # 1. The Candidate is hard rejected.
    assert evaluation.hard_rejected is True
    assert evaluation.evaluation_outcome == CandidateOutcome.REJECTED

    # 2. The decisive contradiction is visible, at HARD severity -
    #    retrieval similarity (retrieval_score=99.0) never downgrades or
    #    removes it.
    hard_findings = [
        f for f in evaluation.contradictions if f.severity == ContradictionSeverity.HARD
    ]
    assert hard_findings, "expected at least one HARD contradiction"
    matching = [f for f in hard_findings if f.field == row.expected_field]
    assert matching, (
        f"expected a HARD contradiction on {row.expected_field!r}, "
        f"got fields {[f.field for f in hard_findings]!r}"
    )

    # 3. The finding references actual Evidence present in the case, and
    #    that Evidence traces to the same Observation (never a fabricated
    #    id used merely to satisfy a non-empty-tuple assertion).
    for finding in matching:
        assert finding.evidence_ids, "expected the decisive finding to cite Evidence"
        for eid in finding.evidence_ids:
            assert eid in evidence_by_id, f"finding cites nonexistent Evidence id {eid!r}"
            assert evidence_by_id[eid].observation_id == row.observation.observation_id

    # 4. The rejected Candidate cannot become the Decision.
    decision_state = _DecisionReasoningState(
        observation=row.observation,
        claims=row.claims,
        hypotheses=(row.hypothesis,),
        candidates=(row.candidate,),
        candidate_evaluations=(evaluation,),
    )
    decision = form_decision(
        decision_state, DecisionPolicy(), deterministic_context, repository=repository
    )
    assert decision.selected_candidate_instance_id != row.candidate.candidate_instance_id
