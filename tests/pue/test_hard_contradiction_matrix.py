"""Executable hard-contradiction matrix (Sprint 2, Task 6).

Enumerates all seven v0.1 hard-rejection rules (spec section 15.3) as one
parameterized matrix. Each row directly constructs the minimal Claim(s) and
ProductHypothesis needed to trigger exactly one rule against a real
catalogue Candidate (via the seed ``JsonCandidateRepository``), then calls
:func:`evaluate_candidates` and :func:`form_decision` directly - this keeps
the matrix deterministic and independent of Evidence-extraction/retrieval
side effects, per the working, already-tested inline rules in
``evaluation.py`` (this file adds no new production logic; see spec
section 15.3 / risk 4 control).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.decisions import form_decision
from digital_arbitrage.pue.enums import (
    CandidateOutcome,
    ClaimPredicate,
    ClaimStatus,
    ContradictionSeverity,
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
    claims: tuple[Claim, ...] = field(default_factory=tuple)


@dataclass
class _DecisionReasoningState:
    """Minimal structural stand-in for ``decisions.CaseReasoningState``."""

    observation: Observation
    claims: tuple[Claim, ...]
    hypotheses: tuple[ProductHypothesis, ...]
    candidates: tuple[Candidate, ...]
    candidate_evaluations: tuple[CandidateEvaluation, ...]


def _claim(context, predicate: ClaimPredicate, value, *, evidence_id: str = "ev-1") -> Claim:
    return Claim(
        claim_id=context.id_factory(),
        observation_id="obs-matrix",
        predicate=predicate,
        value=value,
        status=ClaimStatus.SUPPORTED,
        supporting_evidence_ids=(evidence_id,),
        contradicting_evidence_ids=(),
        qualifying_evidence_ids=(),
        support_level=SupportLevel.STRONG,
        created_by="test_hard_contradiction_matrix",
        capability_version=context.capability_version,
    )


def _hypothesis(
    context,
    *,
    claim_ids: tuple[str, ...],
    product_form: ProductForm,
    product_type: str | None,
    family: str | None,
) -> ProductHypothesis:
    return ProductHypothesis(
        hypothesis_id=context.id_factory(),
        observation_id="obs-matrix",
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


def _row_explicit_mpn_disagreement(context):
    mpn_claim = _claim(context, ClaimPredicate.MPN, "WRONG-MPN-999")
    hyp = _hypothesis(
        context,
        claim_ids=(mpn_claim.claim_id,),
        product_form=ProductForm.COMPLETE_PRODUCT,
        product_type="graphics_card",
        family="rtx 4090",
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-asus-tuf-rtx4090-o24g")
    return hyp, candidate, (mpn_claim,), "mpn"


def _row_non_complete_form_vs_complete_gpu(context):
    hyp = _hypothesis(
        context,
        claim_ids=(),
        product_form=ProductForm.ACCESSORY,
        product_type="gpu_bracket",
        family=None,
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return hyp, candidate, (), "product_form"


def _row_gpu_not_included(context):
    not_included_claim = _claim(context, ClaimPredicate.NOT_INCLUDED, "graphics_card")
    hyp = _hypothesis(
        context,
        claim_ids=(not_included_claim.claim_id,),
        product_form=ProductForm.COMPONENT,
        product_type="gpu_water_block",
        family=None,
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return hyp, candidate, (not_included_claim,), "included"


def _row_packaging_only_vs_contained_gpu(context):
    hyp = _hypothesis(
        context,
        claim_ids=(),
        product_form=ProductForm.PACKAGING_ONLY,
        product_type="retail_packaging",
        family=None,
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return hyp, candidate, (), "product_form"


def _row_unexplained_family_conflict(context):
    hyp = _hypothesis(
        context,
        claim_ids=(),
        product_form=ProductForm.COMPLETE_PRODUCT,
        product_type="graphics_card",
        family="rtx 4090",
    )
    # An RTX 4080 Super Candidate does not list "rtx 4090" as a
    # compatibility target - a genuine, unexplained family conflict.
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-asus-tuf-rtx4080super-oc")
    return hyp, candidate, (), "family"


def _row_desktop_vs_mobile_conflict(context):
    mobile_claim = _claim(context, ClaimPredicate.FORM_FACTOR, "mobile")
    hyp = _hypothesis(
        context,
        claim_ids=(mobile_claim.claim_id,),
        product_form=ProductForm.COMPLETE_PRODUCT,
        product_type="graphics_card",
        family="rtx 4090",
    )
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")  # desktop
    return hyp, candidate, (mobile_claim,), "form_factor"


def _row_compatibility_treated_as_identity(context):
    compat_claim = _claim(context, ClaimPredicate.COMPATIBLE_WITH, "rtx 4090")
    hyp = _hypothesis(
        context,
        claim_ids=(compat_claim.claim_id,),
        product_form=ProductForm.COMPATIBLE_ITEM,
        product_type=None,
        family="rtx 4090",
    )
    # claim_ids already includes compat_claim.claim_id above, so rule 7's
    # evidence_ids (derived via hypothesis.claim_ids) are populated.
    candidate = _candidate(context, hyp.hypothesis_id, "gpu-nvidia-rtx4090-fe")
    return hyp, candidate, (compat_claim,), "product_form"


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


@pytest.mark.parametrize("row_builder", MATRIX_ROWS)
def test_hard_contradiction_matrix_row(row_builder, deterministic_context, repository) -> None:
    hypothesis, candidate, extra_claims, expected_field = row_builder(deterministic_context)
    state = _MatrixState(
        hypotheses=(hypothesis,), candidates=(candidate,), claims=tuple(extra_claims)
    )

    evaluations = evaluate_candidates(state, repository, deterministic_context)
    assert len(evaluations) == 1
    evaluation = evaluations[0]

    # 1. The Candidate is hard rejected.
    assert evaluation.hard_rejected is True
    assert evaluation.evaluation_outcome == CandidateOutcome.REJECTED

    # 2. The contradiction remains visible on the expected field, at HARD
    #    severity - retrieval similarity (retrieval_score=99.0) never
    #    downgrades or removes it.
    hard_findings = [
        f for f in evaluation.contradictions if f.severity == ContradictionSeverity.HARD
    ]
    assert hard_findings, "expected at least one HARD contradiction"
    assert any(f.field == expected_field for f in hard_findings), (
        f"expected a HARD contradiction on {expected_field!r}, "
        f"got fields {[f.field for f in hard_findings]!r}"
    )

    # 3. Relevant Evidence IDs are retained on at least one HARD finding
    #    when the row has supporting Claims/Evidence to cite.
    if extra_claims:
        assert any(f.evidence_ids for f in hard_findings)

    # 4. The final Decision does not identify the rejected Candidate.
    # ``form_decision`` needs a real Observation (case_id/normalized title),
    # which _MatrixState does not model; build a minimal real one here.
    observation = admit_observation(make_normalized("matrix row listing"), deterministic_context)
    full_state = _DecisionReasoningState(
        observation=observation,
        claims=tuple(extra_claims),
        hypotheses=(hypothesis,),
        candidates=(candidate,),
        candidate_evaluations=(evaluation,),
    )
    decision = form_decision(
        full_state, DecisionPolicy(), deterministic_context, repository=repository
    )
    assert decision.selected_candidate_instance_id != candidate.candidate_instance_id
