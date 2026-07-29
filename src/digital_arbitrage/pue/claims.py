"""Claim Construction and Validation (spec section 10).

Claims are created from Evidence using explicit mappings. Conflicting claims
(e.g. a title family token disagreeing with a structured attribute) are
retained side by side rather than silently merged (spec 10.2).
"""

from __future__ import annotations

from .enums import (
    ClaimPredicate,
    ClaimStatus,
    EvidenceType,
    SupportLevel,
)
from .models import Claim, Evidence, Observation, ProcessingContext
from .validation import PueValidationError

#: Evidence PRODUCT_FORM_TERM/PRODUCT_TYPE_TERM normalized values that
#: indicate the item itself is not a complete graphics card (spec 10.1/10.3).
_NON_COMPLETE_FORM_TYPES: dict[str, str] = {
    "gpu_water_block": "component",
    "gpu_fan": "replacement_part",
    "gpu_cooler": "replacement_part",
    "gpu_backplate": "replacement_part",
    "gpu_bracket": "accessory",
    "power_adapter": "accessory",
    "riser_cable": "accessory",
    "housing": "accessory",
}

#: Maximum character gap between a compatibility phrase and the family
#: mention it qualifies, e.g. "compatible with " + "RTX 4090".
_COMPATIBILITY_ADJACENCY_CHARS = 6

#: Chipset-level brand tokens ("NVIDIA"/"AMD"/"Intel") describe the chip
#: inside many different board-partner cards; they must not be read as a
#: specific board-partner identity (spec case: generic "NVIDIA RTX 4090"
#: stays board-partner-unresolved -> PARTIALLY_IDENTIFIED).
_CHIPSET_BRANDS = {"nvidia", "amd", "intel"}

#: Brand tokens that are recognized but clearly outside the GPU domain
#: (used only for traceability; never treated as GPU-domain evidence).
_NON_GPU_BRANDS = {"apple", "samsung"}


def _adjacent(a: Evidence, b: Evidence) -> bool:
    if a.source_start is None or a.source_end is None:
        return False
    if b.source_start is None or b.source_end is None:
        return False
    gap = b.source_start - a.source_end
    return 0 <= gap <= _COMPATIBILITY_ADJACENCY_CHARS


def construct_claims(
    observation: Observation, evidence: tuple[Evidence, ...], context: ProcessingContext
) -> tuple[Claim, ...]:
    """Build the Claim set for one Observation from its extracted Evidence."""
    claims: list[Claim] = []
    created_by = "claim_construction_v0.1"

    def new_claim(
        predicate: ClaimPredicate,
        value: str | int | float | bool | None,
        *,
        status: ClaimStatus,
        support_level: SupportLevel,
        supporting: tuple[str, ...] = (),
        contradicting: tuple[str, ...] = (),
        qualifying: tuple[str, ...] = (),
    ) -> Claim:
        if value is None:
            raise PueValidationError(f"Claim value for {predicate} must not be None")
        return Claim(
            claim_id=context.id_factory(),
            observation_id=observation.observation_id,
            predicate=predicate,
            value=value,
            status=status,
            supporting_evidence_ids=supporting,
            contradicting_evidence_ids=contradicting,
            qualifying_evidence_ids=qualifying,
            support_level=support_level,
            created_by=created_by,
            capability_version=context.capability_version,
        )

    family_evidence = [e for e in evidence if e.evidence_type == EvidenceType.PRODUCT_FAMILY_TOKEN]
    compatibility_evidence = [
        e for e in evidence if e.evidence_type == EvidenceType.COMPATIBILITY_TERM
    ]

    # A family mention is a "compatibility target" (not identity) if an
    # explicit compatibility phrase sits immediately before it, or if any
    # non-complete product-form evidence is present in the same Observation
    # (e.g. "water block" + "RTX 4090" -> the family describes what the
    # water block fits, not the sold item's own identity).
    non_complete_form_present = any(
        e.evidence_type == EvidenceType.PRODUCT_FORM_TERM
        and str(e.normalized_value) in _NON_COMPLETE_FORM_TYPES
        for e in evidence
    )
    packaging_only_present = any(
        e.evidence_type == EvidenceType.PACKAGING_TERM and e.normalized_value == "packaging_only"
        for e in evidence
    )

    explicit_compat_targets: set[str] = set()
    for fam in family_evidence:
        if any(_adjacent(comp, fam) for comp in compatibility_evidence):
            explicit_compat_targets.add(str(fam.normalized_value))

    for fam in family_evidence:
        is_compat_target = (
            str(fam.normalized_value) in explicit_compat_targets
            or non_complete_form_present
            or packaging_only_present
        )
        status = ClaimStatus.QUALIFIED if is_compat_target else ClaimStatus.SUPPORTED
        claims.append(
            new_claim(
                ClaimPredicate.PRODUCT_FAMILY,
                fam.normalized_value,
                status=status,
                support_level=SupportLevel.STRONG,
                supporting=(fam.evidence_id,),
                qualifying=tuple(
                    c.evidence_id for c in compatibility_evidence if _adjacent(c, fam)
                ),
            )
        )
        if is_compat_target:
            claims.append(
                new_claim(
                    ClaimPredicate.COMPATIBLE_WITH,
                    fam.normalized_value,
                    status=ClaimStatus.SUPPORTED,
                    support_level=SupportLevel.MODERATE,
                    supporting=(fam.evidence_id,)
                    + tuple(c.evidence_id for c in compatibility_evidence if _adjacent(c, fam)),
                )
            )

    for e in evidence:
        if e.evidence_type == EvidenceType.MODEL_TOKEN:
            claims.append(
                new_claim(
                    ClaimPredicate.MODEL,
                    e.normalized_value,
                    status=ClaimStatus.SUPPORTED,
                    support_level=SupportLevel.STRONG,
                    supporting=(e.evidence_id,),
                )
            )
        elif e.evidence_type == EvidenceType.BRAND_TOKEN:
            value = str(e.normalized_value)
            predicate = (
                ClaimPredicate.CHIPSET_MANUFACTURER
                if value in _CHIPSET_BRANDS
                else ClaimPredicate.BRAND
            )
            claims.append(
                new_claim(
                    predicate,
                    e.normalized_value,
                    status=ClaimStatus.SUPPORTED,
                    support_level=SupportLevel.STRONG,
                    supporting=(e.evidence_id,),
                )
            )
        elif e.evidence_type == EvidenceType.MPN_TOKEN:
            claims.append(
                new_claim(
                    ClaimPredicate.MPN,
                    e.normalized_value,
                    status=ClaimStatus.PROPOSED,
                    support_level=SupportLevel.MODERATE,
                    supporting=(e.evidence_id,),
                )
            )
        elif e.evidence_type == EvidenceType.GTIN_TOKEN:
            claims.append(
                new_claim(
                    ClaimPredicate.GTIN,
                    e.normalized_value,
                    status=ClaimStatus.PROPOSED,
                    support_level=SupportLevel.WEAK,
                    supporting=(e.evidence_id,),
                )
            )
        elif e.evidence_type == EvidenceType.CAPACITY_VALUE:
            claims.append(
                new_claim(
                    ClaimPredicate.CAPACITY,
                    e.normalized_value,
                    status=ClaimStatus.SUPPORTED,
                    support_level=SupportLevel.STRONG,
                    supporting=(e.evidence_id,),
                )
            )
        elif e.evidence_type == EvidenceType.PRODUCT_FORM_TERM:
            value = str(e.normalized_value)
            if value in _NON_COMPLETE_FORM_TYPES:
                claims.append(
                    new_claim(
                        ClaimPredicate.PRODUCT_FORM,
                        _NON_COMPLETE_FORM_TYPES[value],
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.DETERMINISTIC,
                        supporting=(e.evidence_id,),
                    )
                )
                claims.append(
                    new_claim(
                        ClaimPredicate.PRODUCT_TYPE,
                        value,
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.DETERMINISTIC,
                        supporting=(e.evidence_id,),
                    )
                )
        elif e.evidence_type == EvidenceType.PRODUCT_TYPE_TERM:
            if e.normalized_value == "graphics_card":
                claims.append(
                    new_claim(
                        ClaimPredicate.PRODUCT_TYPE,
                        "graphics_card",
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.MODERATE,
                        supporting=(e.evidence_id,),
                    )
                )
        elif e.evidence_type == EvidenceType.PACKAGING_TERM:
            if e.normalized_value == "packaging_only":
                claims.append(
                    new_claim(
                        ClaimPredicate.PRODUCT_FORM,
                        "packaging_only",
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.DETERMINISTIC,
                        supporting=(e.evidence_id,),
                    )
                )
                claims.append(
                    new_claim(
                        ClaimPredicate.NOT_INCLUDED,
                        "graphics_card",
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.STRONG,
                        supporting=(e.evidence_id,),
                    )
                )
            elif e.normalized_value == "box_included":
                claims.append(
                    new_claim(
                        ClaimPredicate.INCLUDED,
                        "retail_box",
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.MODERATE,
                        supporting=(e.evidence_id,),
                    )
                )
        elif e.evidence_type == EvidenceType.EXCLUSION_TERM:
            if e.normalized_value == "gpu_not_included":
                claims.append(
                    new_claim(
                        ClaimPredicate.NOT_INCLUDED,
                        "graphics_card",
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.DETERMINISTIC,
                        supporting=(e.evidence_id,),
                    )
                )
            elif e.normalized_value == "for_parts":
                claims.append(
                    new_claim(
                        ClaimPredicate.CONDITION,
                        "for_parts",
                        status=ClaimStatus.SUPPORTED,
                        support_level=SupportLevel.STRONG,
                        supporting=(e.evidence_id,),
                    )
                )
        elif e.evidence_type == EvidenceType.CONDITION_TERM:
            claims.append(
                new_claim(
                    ClaimPredicate.CONDITION,
                    e.normalized_value,
                    status=ClaimStatus.SUPPORTED,
                    support_level=SupportLevel.MODERATE,
                    supporting=(e.evidence_id,),
                )
            )
        elif e.evidence_type == EvidenceType.BUNDLE_TERM:
            claims.append(
                new_claim(
                    ClaimPredicate.BUNDLE_CONTENT,
                    e.normalized_value,
                    status=ClaimStatus.SUPPORTED,
                    support_level=SupportLevel.MODERATE,
                    supporting=(e.evidence_id,),
                )
            )

    # -- title vs. structured-attribute conflicts (retained, not merged) --- #
    structured = [e for e in evidence if e.evidence_type == EvidenceType.STRUCTURED_ATTRIBUTE]
    family_values = {str(f.normalized_value) for f in family_evidence}
    for attr in structured:
        attr_value = str(attr.normalized_value).strip().lower()
        if not attr_value or not family_values:
            continue
        # Only flag a conflict when the structured attribute itself looks
        # like a family/model designation that disagrees with the title.
        if attr.source_field.endswith("model") or attr.source_field.endswith("family"):
            if attr_value not in family_values:
                claims.append(
                    new_claim(
                        ClaimPredicate.PRODUCT_FAMILY,
                        attr.normalized_value,
                        status=ClaimStatus.CONTRADICTED,
                        support_level=SupportLevel.MODERATE,
                        supporting=(attr.evidence_id,),
                        contradicting=tuple(f.evidence_id for f in family_evidence),
                    )
                )

    return tuple(claims)
