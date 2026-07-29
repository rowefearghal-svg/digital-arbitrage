"""Unit tests: Claim construction, provenance, and conflict retention."""

from __future__ import annotations

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.claims import construct_claims
from digital_arbitrage.pue.enums import ClaimPredicate, ClaimStatus
from digital_arbitrage.pue.evidence import extract_evidence

from .conftest import make_normalized


def _claims(title, context, extra=None):
    obs = admit_observation(make_normalized(title, extra=extra), context)
    evidence = extract_evidence(obs, context)
    return evidence, construct_claims(obs, evidence, context)


def test_every_claim_references_evidence(deterministic_context) -> None:
    _, claims = _claims("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context)
    for claim in claims:
        assert (
            claim.supporting_evidence_ids
            or claim.contradicting_evidence_ids
            or claim.qualifying_evidence_ids
        ), f"Claim {claim.predicate} has no Evidence reference"


def test_water_block_family_marked_qualified_not_identity(deterministic_context) -> None:
    _, claims = _claims("RTX 4090 water block", deterministic_context)
    family_claims = [c for c in claims if c.predicate is ClaimPredicate.PRODUCT_FAMILY]
    assert family_claims
    assert all(c.status == ClaimStatus.QUALIFIED for c in family_claims)
    assert any(c.predicate is ClaimPredicate.COMPATIBLE_WITH for c in claims)


def test_complete_product_family_is_supported_not_qualified(deterministic_context) -> None:
    _, claims = _claims("ASUS TUF RTX 4090 OC", deterministic_context)
    family_claims = [c for c in claims if c.predicate is ClaimPredicate.PRODUCT_FAMILY]
    assert family_claims
    assert all(c.status == ClaimStatus.SUPPORTED for c in family_claims)


def test_box_only_creates_not_included_claim(deterministic_context) -> None:
    _, claims = _claims("RTX 4090 box only", deterministic_context)
    assert any(
        c.predicate is ClaimPredicate.NOT_INCLUDED and c.value == "graphics_card" for c in claims
    )


def test_title_structured_attribute_conflict_retained(deterministic_context) -> None:
    _, claims = _claims("RTX 4080 Gaming OC", deterministic_context, extra={"model": "RTX 4070"})
    contradicted = [c for c in claims if c.status == ClaimStatus.CONTRADICTED]
    assert contradicted, "expected a CONTRADICTED claim for the conflicting structured attribute"
    # Both the title's own family Claim AND the conflicting one must survive
    # side by side (not silently merged).
    supported_family = [
        c
        for c in claims
        if c.predicate is ClaimPredicate.PRODUCT_FAMILY and c.status == ClaimStatus.SUPPORTED
    ]
    assert supported_family


def test_chipset_manufacturer_distinct_from_board_partner_brand(deterministic_context) -> None:
    _, claims = _claims("NVIDIA RTX 4090", deterministic_context)
    assert any(c.predicate is ClaimPredicate.CHIPSET_MANUFACTURER for c in claims)
    assert not any(c.predicate is ClaimPredicate.BRAND for c in claims)

    _, claims_asus = _claims("ASUS RTX 4090", deterministic_context)
    assert any(c.predicate is ClaimPredicate.BRAND and c.value == "asus" for c in claims_asus)


def test_mpn_claim_is_proposed_until_validated(deterministic_context) -> None:
    _, claims = _claims("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", deterministic_context)
    mpn_claims = [c for c in claims if c.predicate is ClaimPredicate.MPN]
    assert mpn_claims
    assert all(c.status == ClaimStatus.PROPOSED for c in mpn_claims)
