"""Unit tests: exact and fuzzy Candidate Retrieval."""

from __future__ import annotations

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.claims import construct_claims
from digital_arbitrage.pue.enums import RetrievalMethod
from digital_arbitrage.pue.evidence import extract_evidence
from digital_arbitrage.pue.hypotheses import generate_hypotheses
from digital_arbitrage.pue.retrieval import retrieve_candidates

from .conftest import make_normalized


def _retrieve(title, context, repository):
    obs = admit_observation(make_normalized(title), context)
    evidence = extract_evidence(obs, context)
    claims = construct_claims(obs, evidence, context)
    hyps = generate_hypotheses(obs, claims, context)
    return (
        obs,
        claims,
        hyps,
        retrieve_candidates(hyps, repository, context, observation=obs, claims=claims),
    )


def test_no_hypotheses_yields_no_candidates(deterministic_context, repository) -> None:
    _, _, hyps, candidates = _retrieve("Samsung?", deterministic_context, repository)
    assert hyps == ()
    assert candidates == ()


def test_exact_mpn_match_is_found(deterministic_context, repository) -> None:
    _, _, _, candidates = _retrieve(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context, repository
    )
    exact = [c for c in candidates if c.retrieval_method == RetrievalMethod.EXACT_MPN]
    assert exact
    assert exact[0].catalogue_product_id == "gpu-asus-tuf-rtx4090-o24g"
    assert exact[0].retrieval_score == 100.0


def test_fuzzy_retrieval_finds_family_matches(deterministic_context, repository) -> None:
    _, _, _, candidates = _retrieve("NVIDIA RTX 4090", deterministic_context, repository)
    assert candidates
    product_ids = {c.catalogue_product_id for c in candidates}
    assert any("rtx4090" in pid for pid in product_ids)


def test_candidate_pool_respects_evaluation_limit(deterministic_context, repository) -> None:
    _, _, _, candidates = _retrieve("RTX 4090", deterministic_context, repository)
    fuzzy = [c for c in candidates if c.retrieval_method != RetrievalMethod.EXACT_MPN]
    assert len(fuzzy) <= deterministic_context.max_candidate_evaluations


def test_water_block_retrieval_still_surfaces_complete_product(
    deterministic_context, repository
) -> None:
    """Retrieval must not pre-filter out a highly similar complete-product
    Candidate for a component hypothesis; Evaluation is responsible for the
    hard rejection (retrieval/evaluation separation invariant)."""
    _, _, hyps, candidates = _retrieve(
        "RTX 4090 Waterblock Full Cover GPU Cooling Block", deterministic_context, repository
    )
    product_ids = {c.catalogue_product_id for c in candidates}
    assert "gpu-nvidia-rtx4090-fe" in product_ids or any(
        pid.startswith("gpu-") and "4090" in pid for pid in product_ids
    )


def test_retrieval_score_is_bounded(deterministic_context, repository) -> None:
    _, _, _, candidates = _retrieve("RTX 3060", deterministic_context, repository)
    for c in candidates:
        assert 0.0 <= c.retrieval_score <= 100.0
