"""Unit tests: Decision Formation (exact, partial, abstention)."""

from __future__ import annotations

from digital_arbitrage.pue.enums import AbstentionReason, DecisionType
from digital_arbitrage.pue.orchestration import process_one

from .conftest import make_normalized


def test_exact_identification(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G"),
        deterministic_context,
        repository=repository,
    )
    assert record.decision.decision_type == DecisionType.IDENTIFIED
    assert record.decision.identified_brand == "asus"
    assert record.decision.identified_family == "rtx 4090"


def test_partial_identification_when_variant_unresolved(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("NVIDIA RTX 4090"), deterministic_context, repository=repository
    )
    assert record.decision.decision_type == DecisionType.PARTIALLY_IDENTIFIED
    assert record.decision.identified_family == "rtx 4090"
    assert (
        "variant" in record.decision.unresolved_fields
        or "brand" in record.decision.unresolved_fields
    )


def test_abstains_on_empty_title(deterministic_context, repository) -> None:
    record = process_one(make_normalized("   "), deterministic_context, repository=repository)
    assert record.decision.decision_type == DecisionType.ABSTAINED
    assert record.decision.abstention_reason == AbstentionReason.INSUFFICIENT_EVIDENCE


def test_outside_domain_for_non_gpu_listing(deterministic_context, repository) -> None:
    record = process_one(make_normalized("Samsung?"), deterministic_context, repository=repository)
    assert record.decision.decision_type == DecisionType.OUTSIDE_SUPPORTED_DOMAIN


def test_no_escalated_decision_type_exists() -> None:
    assert not hasattr(DecisionType, "ESCALATED")
    assert "ESCALATED" not in DecisionType.__members__


def test_decision_never_names_a_hard_rejected_candidate_as_selected(
    deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G Box Only"),
        deterministic_context,
        repository=repository,
    )
    decision = record.decision
    if decision.selected_candidate_instance_id is not None:
        selected_eval = next(
            ev
            for ev in record.candidate_evaluations
            if ev.candidate_instance_id == decision.selected_candidate_instance_id
        )
        assert not selected_eval.hard_rejected
