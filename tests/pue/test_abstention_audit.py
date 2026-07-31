"""Abstention-reason audit (Sprint 2, Task 3).

Every :class:`~digital_arbitrage.pue.enums.AbstentionReason` member must be
accounted for in
:data:`digital_arbitrage.pue.decisions.ABSTENTION_REASON_REACHABILITY`, and
every reason marked "reachable" there must have a genuine, asserted test
below. Reasons marked "reserved" are deliberately not exercised - see the
inline NOTEs in ``decisions.py`` for why no artificial behaviour was added
merely to make them fire.
"""

from __future__ import annotations

from digital_arbitrage.pue.decisions import ABSTENTION_REASON_REACHABILITY
from digital_arbitrage.pue.enums import AbstentionReason, DecisionType
from digital_arbitrage.pue.orchestration import process_one

from .conftest import make_normalized


def test_every_abstention_reason_is_documented() -> None:
    """Regression: adding a new AbstentionReason member without updating
    the reachability registry must fail loudly, not silently."""
    for reason in AbstentionReason:
        assert reason in ABSTENTION_REASON_REACHABILITY, (
            f"{reason} is missing from ABSTENTION_REASON_REACHABILITY"
        )
    # No stale entries either.
    assert set(ABSTENTION_REASON_REACHABILITY) == set(AbstentionReason)


def test_insufficient_evidence_is_reachable(deterministic_context, repository) -> None:
    record = process_one(make_normalized("   "), deterministic_context, repository=repository)
    assert record.decision.decision_type == DecisionType.ABSTAINED
    assert record.decision.abstention_reason == AbstentionReason.INSUFFICIENT_EVIDENCE
    assert record.decision.review_recommended is True


def test_unresolved_contradiction_is_reachable(deterministic_context, repository) -> None:
    """A title family token contradicted by a structured attribute must
    abstain with UNRESOLVED_CONTRADICTION - not AMBIGUOUS, which is
    reserved for genuinely multiple plausible hypotheses (see
    test_ambiguous_is_preserved_for_genuine_multiple_hypotheses)."""
    listing = make_normalized("RTX 4080 Gaming OC", extra={"model": "RTX 4070"})
    record = process_one(listing, deterministic_context, repository=repository)

    decision = record.decision
    assert decision.decision_type == DecisionType.ABSTAINED
    assert decision.abstention_reason == AbstentionReason.UNRESOLVED_CONTRADICTION
    assert decision.identified_family is None
    assert decision.review_recommended is True
    assert "title_structured_attribute_conflict" in decision.contradiction_codes


def test_ambiguous_is_preserved_for_genuine_multiple_hypotheses(
    deterministic_context, repository
) -> None:
    """Regression: the UNRESOLVED_CONTRADICTION fix must not change the
    genuinely-ambiguous multi-hypothesis case (a complete product bundled
    with a component is a materially different interpretation from the
    component alone)."""
    listing = make_normalized("ASUS RTX 4090 with EK water block")
    record = process_one(listing, deterministic_context, repository=repository)

    assert len(record.hypotheses) > 1
    assert record.decision.decision_type == DecisionType.AMBIGUOUS
    assert record.decision.abstention_reason is None


def test_technical_failure_is_never_an_abstention(deterministic_context) -> None:
    """A malformed input must remain PROCESSING_FAILED, never an
    abstention reason, regardless of the abstention-reason audit."""
    record = process_one(object(), deterministic_context)
    assert record.decision.decision_type == DecisionType.PROCESSING_FAILED
    assert record.decision.abstention_reason is None


def test_reserved_reasons_have_a_non_trivial_documented_justification() -> None:
    reserved = {
        reason: note
        for reason, note in ABSTENTION_REASON_REACHABILITY.items()
        if note.startswith("reserved")
    }
    expected_reserved = {
        AbstentionReason.CANDIDATES_INDISTINGUISHABLE,
        AbstentionReason.NO_SUITABLE_CANDIDATE,
        AbstentionReason.SOURCE_QUALITY_TOO_LOW,
        AbstentionReason.PROCESSING_LIMIT_REACHED,
        AbstentionReason.UNKNOWN_PRODUCT_PATTERN,
    }
    assert set(reserved) == expected_reserved
    for note in reserved.values():
        assert len(note) > 40  # not a placeholder stub
