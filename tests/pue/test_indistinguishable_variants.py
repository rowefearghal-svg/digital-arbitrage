"""Indistinguishable-variant regression coverage (Sprint 2, Task 4).

A generic "RTX 3060" listing has five catalogue variants (two capacities x
several board partners; see ``data/pue/catalogues/gpu_seed_v0.1.json``) and
no title evidence to prefer one over another. The PUE must publish the
broadest justified partial identity rather than guessing, or forcing an
abstention when a genuinely useful broader Decision is available.
"""

from __future__ import annotations

from digital_arbitrage.pue.decisions import ABSTENTION_REASON_REACHABILITY
from digital_arbitrage.pue.enums import (
    AbstentionReason,
    ComparabilityStatus,
    DecisionType,
    IdentificationLevel,
    UncertaintyBand,
)
from digital_arbitrage.pue.orchestration import process_one

from .conftest import make_normalized


def test_generic_rtx3060_does_not_select_an_exact_candidate(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    decision = record.decision

    assert decision.decision_type != DecisionType.IDENTIFIED
    assert decision.selected_candidate_instance_id is None
    assert decision.identification_level != IdentificationLevel.EXACT_CATALOGUE_PRODUCT


def test_generic_rtx3060_is_partial_at_the_justified_level(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    decision = record.decision

    assert decision.decision_type == DecisionType.PARTIALLY_IDENTIFIED
    assert decision.identification_level == IdentificationLevel.MODEL
    assert decision.identified_family == "rtx 3060"
    assert decision.identified_brand is None  # board partner genuinely unresolved


def test_generic_rtx3060_preserves_alternative_candidates(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    decision = record.decision

    # All five catalogue RTX 3060 variants remain visible as alternatives;
    # none is silently discarded.
    assert len(decision.alternative_candidate_ids) >= 5
    alt_products = {
        c.catalogue_product_id
        for c in record.candidates
        if c.candidate_instance_id in decision.alternative_candidate_ids
    }
    assert len(alt_products) >= 5


def test_generic_rtx3060_distinguishability_reflects_unresolved_alternatives(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    assert record.decision.uncertainty.distinguishability == UncertaintyBand.LOW


def test_generic_rtx3060_unresolved_variant_fields_present(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    decision = record.decision
    assert "variant" in decision.unresolved_fields
    assert "brand" in decision.unresolved_fields


def test_generic_rtx3060_explanation_does_not_invent_the_variant(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    summary = record.explanation.summary.lower()

    # No specific board-partner brand or capacity value may be named - the
    # explanation must faithfully reflect that these remain unresolved.
    for unsupported_detail in ("asus", "msi", "gigabyte", "8gb", "12gb"):
        assert unsupported_detail not in summary
    assert "board-partner variant could not be established" in summary


def test_generic_rtx3060_does_not_overstate_comparability(
    deterministic_context, repository
) -> None:
    record = process_one(make_normalized("RTX 3060"), deterministic_context, repository=repository)
    assert record.decision.comparability_status != ComparabilityStatus.DIRECTLY_COMPARABLE
    assert record.decision.comparability_status == ComparabilityStatus.COMPARABLE_AT_BROADER_LEVEL


def test_candidates_indistinguishable_reason_is_documented_as_reserved() -> None:
    """CANDIDATES_INDISTINGUISHABLE is not forced for this case (or any
    other reachable case today) - see the audit note in decisions.py. This
    regression protects against a future change silently making it
    reachable through a Decision-logic distortion rather than a deliberate,
    reviewed capability change."""
    note = ABSTENTION_REASON_REACHABILITY[AbstentionReason.CANDIDATES_INDISTINGUISHABLE]
    assert note.startswith("reserved")


def test_rtx3060_with_explicit_capacity_still_does_not_force_a_board_partner(
    deterministic_context, repository
) -> None:
    """Even when capacity narrows the candidate pool (12GB has 3 variants,
    still multiple board partners), the board partner must remain
    unresolved rather than an arbitrary pick."""
    record = process_one(
        make_normalized("RTX 3060 12GB"), deterministic_context, repository=repository
    )
    decision = record.decision
    assert decision.decision_type != DecisionType.IDENTIFIED
    assert decision.identified_brand is None
