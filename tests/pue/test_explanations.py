"""Unit tests: Explanation faithfulness."""

from __future__ import annotations

from digital_arbitrage.pue.orchestration import process_one

from .conftest import make_normalized


def test_explanation_evidence_ids_exist(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G"),
        deterministic_context,
        repository=repository,
    )
    known_ids = {e.evidence_id for e in record.evidence}
    for eid in record.explanation.evidence_ids:
        assert eid in known_ids


def test_explanation_references_correct_decision(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("RTX 4090 water block"), deterministic_context, repository=repository
    )
    assert record.explanation.decision_id == record.decision.decision_id


def test_abstained_explanation_states_reason(deterministic_context, repository) -> None:
    record = process_one(make_normalized("   "), deterministic_context, repository=repository)
    assert "abstained" in record.explanation.summary.lower()


def test_explanation_summary_never_empty(deterministic_context, repository) -> None:
    for title in ["Samsung?", "RTX 4090", "RTX 4090 box only", "For parts RTX 4090 not working"]:
        record = process_one(make_normalized(title), deterministic_context, repository=repository)
        assert record.explanation.summary.strip() != ""
