"""Property/invariant tests (spec section 23.2).

Each test name maps directly to one numbered invariant in the spec.
"""

from __future__ import annotations

from digital_arbitrage.pue.enums import ComparisonResult, DecisionType
from digital_arbitrage.pue.orchestration import process_many, process_one

from .conftest import make_normalized

_SAMPLE_TITLES = [
    "Samsung?",
    "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
    "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G",
    "RTX 4090 Waterblock Full Cover GPU Cooling Block",
    "Empty RTX 4090 Founders Edition Box Only",
    "RTX 4090 replacement fan set",
    "RTX 4090 GPU not included - water block only",
    "ASUS RTX 4090 with EK water block",
    "NVIDIA RTX 4090",
    "RTX 3060",
    "For parts RTX 4090 not working",
    "RTX 4090 retail box included",
    "Compatible with RTX 4090",
    "RTX 4090 + PSU bundle",
    "   ",
]


def _records(context, repository):
    return [process_one(make_normalized(t), context, repository=repository) for t in _SAMPLE_TITLES]


# 1. Raw title remains unchanged.
def test_invariant_raw_title_preserved(deterministic_context, repository) -> None:
    for title in _SAMPLE_TITLES:
        listing = make_normalized(title)
        record = process_one(listing, deterministic_context, repository=repository)
        assert record.observation.raw_title == listing.source.title


# 2. Every Claim references at least one Evidence object.
def test_invariant_claim_evidence_linkage(deterministic_context, repository) -> None:
    for record in _records(deterministic_context, repository):
        evidence_ids = {e.evidence_id for e in record.evidence}
        for claim in record.claims:
            referenced = (
                set(claim.supporting_evidence_ids)
                | set(claim.contradicting_evidence_ids)
                | set(claim.qualifying_evidence_ids)
            )
            assert referenced, f"Claim {claim.claim_id} has no Evidence reference"
            assert referenced.issubset(evidence_ids)


# 3. Every Candidate Evaluation references a Candidate and Product Hypothesis.
def test_invariant_candidate_evaluation_linkage(deterministic_context, repository) -> None:
    for record in _records(deterministic_context, repository):
        candidate_ids = {c.candidate_instance_id for c in record.candidates}
        hypothesis_ids = {h.hypothesis_id for h in record.hypotheses}
        for ev in record.candidate_evaluations:
            assert ev.candidate_instance_id in candidate_ids
            assert ev.hypothesis_id in hypothesis_ids


# 4. Retrieval score alone cannot produce a Decision (i.e. hard-rejected
#    Candidates, however high their score, are never selected).
def test_invariant_retrieval_score_cannot_decide_identity(
    deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("RTX 4090 Waterblock Full Cover GPU Cooling Block"),
        deterministic_context,
        repository=repository,
    )
    rejected_ids = {
        ev.candidate_instance_id for ev in record.candidate_evaluations if ev.hard_rejected
    }
    assert record.decision.selected_candidate_instance_id not in rejected_ids


# 5. A hard product-form contradiction rejects a complete-product Candidate.
def test_invariant_hard_form_contradiction_rejects_complete_product(
    deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("RTX 4090 Waterblock Full Cover GPU Cooling Block"),
        deterministic_context,
        repository=repository,
    )
    complete_product_evals = []
    for ev in record.candidate_evaluations:
        cand = next(
            c for c in record.candidates if c.candidate_instance_id == ev.candidate_instance_id
        )
        product = repository.get_by_id(cand.catalogue_product_id)
        if product is not None and product.product_form.value == "complete_product":
            complete_product_evals.append(ev)
    assert complete_product_evals
    assert all(ev.hard_rejected for ev in complete_product_evals)


# 6. A Decision cannot be more specific than its supporting Claims.
def test_invariant_decision_bounded_by_claims(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("Graphics card excellent condition"),
        deterministic_context,
        repository=repository,
    )
    # No family Claim exists, so the Decision must not claim exact identity.
    assert record.decision.decision_type != DecisionType.IDENTIFIED
    assert record.decision.identified_family is None


# 7. An Explanation cannot name a product absent from the Decision.
def test_invariant_explanation_names_only_decided_product(
    deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G"),
        deterministic_context,
        repository=repository,
    )
    if record.decision.identified_family:
        assert (
            record.decision.identified_family in record.explanation.summary.lower()
            or (record.decision.identified_brand or "") in record.explanation.summary.lower()
        )


# 8. An abstention is not recorded as technical failure.
def test_invariant_abstention_not_technical_failure(deterministic_context, repository) -> None:
    record = process_one(make_normalized("   "), deterministic_context, repository=repository)
    assert record.decision.decision_type == DecisionType.ABSTAINED
    assert record.decision.decision_type != DecisionType.PROCESSING_FAILED
    assert "failure_category" not in record.operational_metrics


# 9. ESCALATED cannot appear as a Decision type.
def test_invariant_no_escalated_decision(deterministic_context, repository) -> None:
    assert "ESCALATED" not in DecisionType.__members__
    for record in _records(deterministic_context, repository):
        assert record.decision.decision_type.value != "escalated"


# 10. A superseding run does not overwrite the earlier record.
def test_invariant_no_overwrite_on_rerun(tmp_path, deterministic_context, repository) -> None:
    from digital_arbitrage.pue.persistence import PueCaseStore
    from digital_arbitrage.pue.validation import PueValidationError

    record = process_one(
        make_normalized("RTX 3060 12GB"), deterministic_context, repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        try:
            store.save_case(record)
            raised = False
        except PueValidationError:
            raised = True
        assert raised
        assert store.get_case(record.case_id) == record


# 11. Profit and ROI do not enter Claim or Candidate Evaluation inputs.
def test_invariant_no_commercial_fields(deterministic_context, repository) -> None:
    for record in _records(deterministic_context, repository):
        for claim in record.claims:
            assert claim.predicate.value not in ("price", "profit", "roi")
        for ev in record.candidate_evaluations:
            for finding in (*ev.agreements, *ev.contradictions, *ev.missing_information):
                assert finding.field not in ("price", "profit", "roi", "asking_price")


# 12. The Product Understanding Result references the underlying Decision.
def test_invariant_result_references_decision(deterministic_context, repository) -> None:
    from digital_arbitrage.pue.orchestration import publish_result

    record = process_one(
        make_normalized("RTX 4080 Super Gaming OC"), deterministic_context, repository=repository
    )
    result = publish_result(record)
    assert result.decision_id == record.decision.decision_id
    assert result.observation_id == record.observation.observation_id
    assert result.case_id == record.case_id


# Additional required invariants from the brief.
def test_invariant_no_forced_nearest_match(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("RTX 5099 Ultra graphics card"),
        deterministic_context,
        repository=repository,
    )
    assert record.decision.decision_type != DecisionType.IDENTIFIED


def test_invariant_exact_identifier_cannot_override_form_exclusion(
    deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G Box Only"),
        deterministic_context,
        repository=repository,
    )
    assert record.decision.product_form.value != "complete_product"
    assert record.decision.decision_type != DecisionType.IDENTIFIED


def test_invariant_missing_differs_from_contradiction(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("NVIDIA RTX 4090"), deterministic_context, repository=repository
    )
    for ev in record.candidate_evaluations:
        for finding in ev.missing_information:
            assert finding.result == ComparisonResult.MISSING
        for finding in ev.contradictions:
            assert finding.result == ComparisonResult.CONTRADICT


# 13. An exact Decision (IDENTIFIED / EXACT_CATALOGUE_PRODUCT) can never
#     depend on a PROPOSED identifier Claim - it must first be validated
#     (SUPPORTED) against the catalogue (pre-merge correction: claims.py's
#     construct_claims always creates MPN/GTIN Claims as PROPOSED; only
#     claims.validate_identifier_claims may promote one to SUPPORTED).
def test_invariant_exact_decision_never_depends_on_proposed_claim(
    deterministic_context, repository
) -> None:
    from digital_arbitrage.pue.admission import admit_observation
    from digital_arbitrage.pue.claims import construct_claims
    from digital_arbitrage.pue.decisions import form_decision
    from digital_arbitrage.pue.enums import ClaimPredicate, ClaimStatus, DecisionType
    from digital_arbitrage.pue.evaluation import evaluate_candidates
    from digital_arbitrage.pue.evidence import extract_evidence
    from digital_arbitrage.pue.hypotheses import generate_hypotheses
    from digital_arbitrage.pue.orchestration import DEFAULT_POLICY, CaseReasoningState
    from digital_arbitrage.pue.retrieval import retrieve_candidates

    title = "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G"
    obs = admit_observation(make_normalized(title), deterministic_context)
    evidence = extract_evidence(obs, deterministic_context)
    claims = construct_claims(obs, evidence, deterministic_context)

    # Deliberately skip validate_identifier_claims: every MPN Claim must
    # still be PROPOSED at this point.
    mpn_claims = [c for c in claims if c.predicate is ClaimPredicate.MPN]
    assert mpn_claims, "expected at least one MPN Claim for this exact-MPN title"
    assert all(c.status == ClaimStatus.PROPOSED for c in mpn_claims)

    hyps = generate_hypotheses(obs, claims, deterministic_context)
    candidates = retrieve_candidates(
        hyps, repository, deterministic_context, observation=obs, claims=claims
    )
    state = CaseReasoningState(
        observation=obs, evidence=evidence, claims=claims, hypotheses=hyps, candidates=candidates
    )
    evaluations = evaluate_candidates(state, repository, deterministic_context)
    state.candidate_evaluations = evaluations

    # No CandidateEvaluation may record an MPN agreement while the backing
    # Claim is still PROPOSED.
    for ev in evaluations:
        assert not any(f.field == "mpn" for f in ev.agreements)

    decision = form_decision(state, DEFAULT_POLICY, deterministic_context, repository=repository)
    assert decision.decision_type != DecisionType.IDENTIFIED
    assert decision.identification_level.value != "exact_catalogue_product"

    # With validation, the same title *does* reach exact identification -
    # confirming the negative result above is due to the missing
    # validation step, not an unrelated difference.
    validated_record = process_one(
        make_normalized(title), deterministic_context, repository=repository
    )
    assert validated_record.decision.decision_type == DecisionType.IDENTIFIED


# 14. Unavailable/invalid catalogue data becomes PROCESSING_FAILED with
#     ProcessingFailureCategory.CATALOGUE_UNAVAILABLE, never an uncaught
#     exception and never product uncertainty (default repository creation
#     is protected inside orchestration.process_one/process_many).
def test_invariant_catalogue_unavailable_becomes_processing_failed(
    deterministic_context, monkeypatch
) -> None:
    from digital_arbitrage.pue.enums import DecisionType, ProcessingFailureCategory
    from digital_arbitrage.pue.validation import PueValidationError

    def _raise_unavailable() -> None:
        raise PueValidationError("simulated catalogue load failure")

    monkeypatch.setattr(
        "digital_arbitrage.pue.orchestration.JsonCandidateRepository", _raise_unavailable
    )

    record = process_one(make_normalized("RTX 4090"), deterministic_context)
    assert record.decision.decision_type == DecisionType.PROCESSING_FAILED
    assert record.decision.abstention_reason is None
    assert (
        record.operational_metrics["failure_category"]
        == ProcessingFailureCategory.CATALOGUE_UNAVAILABLE.value
    )

    # process_many produces the same per-listing outcome for every listing
    # in the batch, not an uncaught exception for the whole batch.
    batch = process_many(
        [make_normalized("RTX 4090"), make_normalized("RTX 3060")], deterministic_context
    )
    assert len(batch) == 2
    for rec in batch:
        assert rec.decision.decision_type == DecisionType.PROCESSING_FAILED
        assert (
            rec.operational_metrics["failure_category"]
            == ProcessingFailureCategory.CATALOGUE_UNAVAILABLE.value
        )


def test_invariant_batch_and_single_case_semantics_agree(deterministic_context, repository) -> None:
    from digital_arbitrage.pue.persistence import reasoning_record_to_dict

    single = [
        process_one(make_normalized(t), deterministic_context, repository=repository)
        for t in _SAMPLE_TITLES
    ]
    batch = process_many(
        [make_normalized(t) for t in _SAMPLE_TITLES], deterministic_context, repository=repository
    )
    assert len(single) == len(batch)
    for s, b in zip(single, batch, strict=True):
        s_dict = reasoning_record_to_dict(s)
        b_dict = reasoning_record_to_dict(b)
        # Ignore volatile identifiers/timestamps; decision content must match.
        assert s_dict["decision"]["decision_type"] == b_dict["decision"]["decision_type"]
        assert s_dict["decision"]["product_form"] == b_dict["decision"]["product_form"]
        assert (
            s_dict["decision"]["identification_level"] == b_dict["decision"]["identification_level"]
        )
