"""Unit tests: Candidate Evaluation and the hard-contradiction policy."""

from __future__ import annotations

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.claims import construct_claims, validate_identifier_claims
from digital_arbitrage.pue.enums import CandidateOutcome, ContradictionSeverity
from digital_arbitrage.pue.evaluation import evaluate_candidates
from digital_arbitrage.pue.evidence import extract_evidence
from digital_arbitrage.pue.hypotheses import generate_hypotheses
from digital_arbitrage.pue.orchestration import CaseReasoningState
from digital_arbitrage.pue.retrieval import retrieve_candidates

from .conftest import make_normalized


def _evaluate(title, context, repository, extra=None):
    obs = admit_observation(make_normalized(title, extra=extra), context)
    evidence = extract_evidence(obs, context)
    claims = construct_claims(obs, evidence, context)
    claims = validate_identifier_claims(claims, context, repository)
    hyps = generate_hypotheses(obs, claims, context)
    candidates = retrieve_candidates(hyps, repository, context, observation=obs, claims=claims)
    state = CaseReasoningState(
        observation=obs, evidence=evidence, claims=claims, hypotheses=hyps, candidates=candidates
    )
    evaluations = evaluate_candidates(state, repository, context)
    return state, evaluations


def test_exact_mpn_candidate_strongly_supported(deterministic_context, repository) -> None:
    _, evaluations = _evaluate(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context, repository
    )
    strong = [e for e in evaluations if e.evaluation_outcome == CandidateOutcome.STRONGLY_SUPPORTED]
    assert strong
    assert not strong[0].hard_rejected


def test_water_block_hard_rejects_complete_gpu_candidate(deterministic_context, repository) -> None:
    """Spec 15.6 worked example: a highly similar complete-GPU Candidate
    must be hard-rejected for a water-block hypothesis."""
    state, evaluations = _evaluate(
        "RTX 4090 Waterblock Full Cover GPU Cooling Block", deterministic_context, repository
    )
    by_product = {}
    for ev in evaluations:
        cand = next(
            c for c in state.candidates if c.candidate_instance_id == ev.candidate_instance_id
        )
        by_product[cand.catalogue_product_id] = ev

    complete_gpu_evals = [
        ev for pid, ev in by_product.items() if pid.startswith("gpu-") and "4090" in pid
    ]
    assert complete_gpu_evals, "expected at least one complete RTX 4090 Candidate to be retrieved"
    for ev in complete_gpu_evals:
        assert ev.hard_rejected
        assert ev.evaluation_outcome == CandidateOutcome.REJECTED
        assert any(f.severity == ContradictionSeverity.HARD for f in ev.contradictions)


def test_gpu_not_included_hard_rejects_complete_gpu(deterministic_context, repository) -> None:
    state, evaluations = _evaluate(
        "RTX 4090 GPU not included - water block only", deterministic_context, repository
    )
    for ev in evaluations:
        cand = next(
            c for c in state.candidates if c.candidate_instance_id == ev.candidate_instance_id
        )
        product = repository.get_by_id(cand.catalogue_product_id)
        if product is not None and product.product_form.value == "complete_product":
            assert ev.hard_rejected


def test_missing_information_is_neutral_not_contradiction(
    deterministic_context, repository
) -> None:
    """A listing that omits board partner must not be treated as
    contradicting a Candidate's board partner (spec 15.2)."""
    _, evaluations = _evaluate("NVIDIA RTX 4090", deterministic_context, repository)
    for ev in evaluations:
        brand_missing = [f for f in ev.missing_information if f.field == "brand"]
        if brand_missing:
            assert not ev.hard_rejected or any(
                f.severity.value == "hard" for f in ev.contradictions if f.field != "brand"
            )


def test_mobile_listing_hard_rejects_desktop_candidate(deterministic_context, repository) -> None:
    """A desktop GPU Candidate must be hard-rejected when the listing
    explicitly describes a laptop/mobile GPU (mobile-vs-desktop hard
    contradiction)."""
    state, evaluations = _evaluate("Laptop RTX 4090 GPU", deterministic_context, repository)
    desktop_evals = []
    for ev in evaluations:
        cand = next(
            c for c in state.candidates if c.candidate_instance_id == ev.candidate_instance_id
        )
        product = repository.get_by_id(cand.catalogue_product_id)
        if product is not None and product.attributes.get("form_factor") == "desktop":
            desktop_evals.append(ev)
    assert desktop_evals, "expected at least one desktop Candidate to be retrieved"
    for ev in desktop_evals:
        assert ev.hard_rejected
        assert any(
            f.field == "form_factor" and f.severity == ContradictionSeverity.HARD
            for f in ev.contradictions
        )

    # The mobile Candidate itself must not be rejected on this ground.
    mobile_evals = []
    for ev in evaluations:
        cand = next(
            c for c in state.candidates if c.candidate_instance_id == ev.candidate_instance_id
        )
        product = repository.get_by_id(cand.catalogue_product_id)
        if product is not None and product.attributes.get("form_factor") == "mobile":
            mobile_evals.append(ev)
    assert mobile_evals, "expected the mobile Candidate to be retrieved"
    for ev in mobile_evals:
        assert not any(f.field == "form_factor" for f in ev.contradictions)


def test_desktop_listing_does_not_reject_desktop_candidate(
    deterministic_context, repository
) -> None:
    """The mobile-vs-desktop rule must not fire for an ordinary desktop
    listing (no mobile Claim present)."""
    _, evaluations = _evaluate(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context, repository
    )
    for ev in evaluations:
        assert not any(f.field == "form_factor" for f in ev.contradictions)


def test_exact_mpn_candidate_evaluation_references_candidate_and_hypothesis(
    deterministic_context, repository
) -> None:
    state, evaluations = _evaluate(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context, repository
    )
    candidate_ids = {c.candidate_instance_id for c in state.candidates}
    hypothesis_ids = {h.hypothesis_id for h in state.hypotheses}
    for ev in evaluations:
        assert ev.candidate_instance_id in candidate_ids
        assert ev.hypothesis_id in hypothesis_ids
