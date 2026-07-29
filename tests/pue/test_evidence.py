"""Unit tests: Evidence extraction, spans, and provenance."""

from __future__ import annotations

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.enums import EvidenceType
from digital_arbitrage.pue.evidence import extract_evidence

from .conftest import make_normalized


def _extract(title, context):
    obs = admit_observation(make_normalized(title), context)
    return obs, extract_evidence(obs, context)


def test_empty_title_yields_no_evidence(deterministic_context) -> None:
    obs, evidence = _extract("   ", deterministic_context)
    assert evidence == ()


def test_brand_and_family_extracted(deterministic_context) -> None:
    obs, evidence = _extract("ASUS TUF RTX 4090 OC", deterministic_context)
    types = {e.evidence_type for e in evidence}
    assert EvidenceType.BRAND_TOKEN in types
    assert EvidenceType.PRODUCT_FAMILY_TOKEN in types
    family = next(e for e in evidence if e.evidence_type == EvidenceType.PRODUCT_FAMILY_TOKEN)
    assert family.normalized_value == "rtx 4090"


def test_evidence_spans_are_within_title_bounds(deterministic_context) -> None:
    obs, evidence = _extract("RTX 4090 water block", deterministic_context)
    for e in evidence:
        if e.source_start is not None:
            assert 0 <= e.source_start < e.source_end <= len(obs.normalized_title)
            assert (
                obs.normalized_title[e.source_start : e.source_end].lower() == e.raw_value.lower()
            )


def test_capacity_extraction(deterministic_context) -> None:
    obs, evidence = _extract("RTX 4090 24GB", deterministic_context)
    capacity = next(e for e in evidence if e.evidence_type == EvidenceType.CAPACITY_VALUE)
    assert capacity.normalized_value == 24


def test_mpn_token_extracted_from_raw_title(deterministic_context) -> None:
    obs, evidence = _extract("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context)
    mpns = [e for e in evidence if e.evidence_type == EvidenceType.MPN_TOKEN]
    assert any(e.normalized_value == "TUF-RTX4090-O24G" for e in mpns)


def test_exclusion_term_not_swallowed_by_compatibility_phrase(deterministic_context) -> None:
    """'for parts' must be recognized whole, not partially consumed by a
    generic 'for' compatibility match (regression for a real bug found
    during Sprint 1 implementation)."""
    obs, evidence = _extract("RTX 4090 for parts not working", deterministic_context)
    exclusions = {
        e.normalized_value for e in evidence if e.evidence_type == EvidenceType.EXCLUSION_TERM
    }
    assert "for_parts" in exclusions


def test_box_only_vs_box_included_are_distinguished(deterministic_context) -> None:
    _, box_only_evidence = _extract("RTX 4090 box only", deterministic_context)
    _, box_included_evidence = _extract("RTX 4090 box included", deterministic_context)
    only_values = {
        e.normalized_value
        for e in box_only_evidence
        if e.evidence_type == EvidenceType.PACKAGING_TERM
    }
    included_values = {
        e.normalized_value
        for e in box_included_evidence
        if e.evidence_type == EvidenceType.PACKAGING_TERM
    }
    assert "packaging_only" in only_values
    assert "packaging_only" not in included_values
    assert "box_included" in included_values


def test_structured_attributes_become_evidence(deterministic_context) -> None:
    obs = admit_observation(
        make_normalized("RTX 4080 Gaming OC", extra={"model": "RTX 4070"}), deterministic_context
    )
    evidence = extract_evidence(obs, deterministic_context)
    structured = [e for e in evidence if e.evidence_type == EvidenceType.STRUCTURED_ATTRIBUTE]
    assert any(e.normalized_value == "RTX 4070" for e in structured)


def test_extraction_is_bounded_no_arbitrary_tokens(deterministic_context) -> None:
    """A word with no defined term/evidence type produces no Evidence for
    it specifically (spec 9.5 recall/bounding policy)."""
    obs, evidence = _extract("the quick brown fox RTX 4090", deterministic_context)
    raw_values = {e.raw_value.lower() for e in evidence}
    assert "quick" not in raw_values
    assert "brown" not in raw_values
    assert "fox" not in raw_values
