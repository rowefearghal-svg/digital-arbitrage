"""Mandatory Sprint 1 acceptance cases (spec section 21).

Drives ``tests/fixtures/pue/sprint1_acceptance_v0.1.json`` through the full
PUE pipeline and asserts not only the final Decision but key intermediate
reasoning (evidence presence, hard contradictions, contradicted claims,
forbidden product forms/catalogue selections).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.catalogue import JsonCandidateRepository
from digital_arbitrage.pue.enums import ClaimStatus, ContradictionSeverity

from .conftest import DeterministicIdFactory, FixedClock, make_normalized

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "pue"
    / "sprint1_acceptance_v0.1.json"
)


def _load_cases() -> list[dict]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return payload["cases"]


CASES = _load_cases()
assert len(CASES) == 25, f"expected 25 mandatory acceptance cases, found {len(CASES)}"


@pytest.fixture(scope="module")
def repo():
    return JsonCandidateRepository()


@pytest.fixture(scope="module")
def context():
    return orchestration.build_default_context(
        id_factory=DeterministicIdFactory(), clock=FixedClock()
    )


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_acceptance_case(case: dict, repo, context) -> None:
    if case.get("malformed"):
        record = orchestration.process_one(object(), context, repository=repo)
    else:
        listing = make_normalized(case["title"], extra=case.get("structured_attributes"))
        record = orchestration.process_one(listing, context, repository=repo)

    decision = record.decision

    allowed = set(case["allowed_decision_types"])
    assert decision.decision_type.value in allowed, (
        f"{case['case_id']}: decision {decision.decision_type.value} not in {allowed}"
    )

    forbidden = set(case.get("forbidden_decision_types", ()))
    assert decision.decision_type.value not in forbidden, (
        f"{case['case_id']}: forbidden decision {decision.decision_type.value}"
    )

    if "forbidden_product_forms" in case:
        assert decision.product_form.value not in set(case["forbidden_product_forms"]), (
            f"{case['case_id']}: forbidden product_form {decision.product_form.value}"
        )

    if "expected_product_form" in case:
        assert decision.product_form.value == case["expected_product_form"]

    if "expected_identification_levels" in case:
        assert decision.identification_level.value in set(case["expected_identification_levels"])

    if "expected_comparability" in case:
        assert decision.comparability_status.value in set(case["expected_comparability"])

    if "expected_abstention_reason" in case:
        assert decision.abstention_reason is not None
        assert decision.abstention_reason.value == case["expected_abstention_reason"]

    if case.get("expected_catalogue_product_id"):
        selected = decision.selected_candidate_instance_id
        assert selected is not None, f"{case['case_id']}: expected a selected Candidate"
        selected_candidate = next(
            c for c in record.candidates if c.candidate_instance_id == selected
        )
        assert selected_candidate.catalogue_product_id == case["expected_catalogue_product_id"]

    if case.get("forbidden_selected_catalogue_product_ids"):
        selected = decision.selected_candidate_instance_id
        if selected is not None:
            selected_candidate = next(
                c for c in record.candidates if c.candidate_instance_id == selected
            )
            assert selected_candidate.catalogue_product_id not in set(
                case["forbidden_selected_catalogue_product_ids"]
            )

    if "required_evidence_types" in case:
        present = {e.evidence_type.value for e in record.evidence}
        for required in case["required_evidence_types"]:
            assert required in present, f"{case['case_id']}: missing evidence type {required}"

    if case.get("require_hard_rejected_candidate"):
        assert any(ev.hard_rejected for ev in record.candidate_evaluations), (
            f"{case['case_id']}: expected at least one hard-rejected Candidate"
        )
        assert any(
            f.severity == ContradictionSeverity.HARD
            for ev in record.candidate_evaluations
            for f in ev.contradictions
        )

    if case.get("require_contradicted_claim"):
        assert any(c.status == ClaimStatus.CONTRADICTED for c in record.claims)

    assert len(record.evidence) >= case.get("min_evidence_count", 0)

    # Faithfulness / traceability floor for every case.
    assert record.decision.observation_id == record.observation.observation_id
    assert record.explanation.decision_id == record.decision.decision_id
