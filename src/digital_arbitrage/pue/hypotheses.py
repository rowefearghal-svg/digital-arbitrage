"""Bounded Product Hypothesis Generation (spec section 11).

At most three active hypotheses are produced per case. Equivalent
hypotheses are merged; impossible combinations are rejected. Broad
hypotheses remain valid where specificity is unsupported (spec 8.4).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from .claims import _NON_GPU_BRANDS
from .enums import ClaimPredicate, ClaimStatus, HypothesisStatus, ProductForm
from .models import Claim, Observation, ProcessingContext, ProductHypothesis

#: PRODUCT_TYPE claim values that represent a non-complete-product form,
#: mapped to their governing ProductForm.
_TYPE_TO_FORM: dict[str, ProductForm] = {
    "gpu_water_block": ProductForm.COMPONENT,
    "gpu_fan": ProductForm.REPLACEMENT_PART,
    "gpu_cooler": ProductForm.REPLACEMENT_PART,
    "gpu_backplate": ProductForm.REPLACEMENT_PART,
    "gpu_bracket": ProductForm.ACCESSORY,
    "power_adapter": ProductForm.ACCESSORY,
    "riser_cable": ProductForm.ACCESSORY,
    "housing": ProductForm.ACCESSORY,
}

_WITH_RE = re.compile(r"\bwith\b")


def _claims_by_predicate(claims: Sequence[Claim], predicate: ClaimPredicate) -> list[Claim]:
    return [c for c in claims if c.predicate is predicate]


def _identity_family(claims: Sequence[Claim]) -> Claim | None:
    for c in _claims_by_predicate(claims, ClaimPredicate.PRODUCT_FAMILY):
        if c.status == ClaimStatus.SUPPORTED:
            return c
    return None


def _qualified_family(claims: Sequence[Claim]) -> Claim | None:
    for c in _claims_by_predicate(claims, ClaimPredicate.PRODUCT_FAMILY):
        if c.status == ClaimStatus.QUALIFIED:
            return c
    return None


def _board_partner_brand(claims: Sequence[Claim]) -> Claim | None:
    for c in _claims_by_predicate(claims, ClaimPredicate.BRAND):
        if str(c.value) not in _NON_GPU_BRANDS:
            return c
    return None


def _has_graphics_card_type(claims: Sequence[Claim]) -> bool:
    return any(
        c.predicate is ClaimPredicate.PRODUCT_TYPE and c.value == "graphics_card" for c in claims
    )


def _non_complete_type_claims(claims: Sequence[Claim]) -> list[Claim]:
    return [
        c
        for c in claims
        if c.predicate is ClaimPredicate.PRODUCT_TYPE and str(c.value) in _TYPE_TO_FORM
    ]


def _has_packaging_only(claims: Sequence[Claim]) -> bool:
    return any(
        c.predicate is ClaimPredicate.PRODUCT_FORM and c.value == "packaging_only" for c in claims
    )


def _has_gpu_not_included(claims: Sequence[Claim]) -> bool:
    return any(
        c.predicate is ClaimPredicate.NOT_INCLUDED and c.value == "graphics_card" for c in claims
    )


def _has_compatible_with(claims: Sequence[Claim]) -> Claim | None:
    matches = _claims_by_predicate(claims, ClaimPredicate.COMPATIBLE_WITH)
    return matches[0] if matches else None


def _has_for_parts(claims: Sequence[Claim]) -> bool:
    return any(c.predicate is ClaimPredicate.CONDITION and c.value == "for_parts" for c in claims)


def _evidence_coverage(supported_fields: Sequence[bool]) -> float:
    if not supported_fields:
        return 0.0
    return round(sum(1 for f in supported_fields if f) / len(supported_fields), 4)


def has_any_gpu_domain_signal(claims: Sequence[Claim]) -> bool:
    """True if any Claim indicates the listing is within the GPU domain."""
    if _identity_family(claims) or _qualified_family(claims):
        return True
    if _has_graphics_card_type(claims):
        return True
    if _non_complete_type_claims(claims):
        return True
    if _has_packaging_only(claims):
        return True
    if _claims_by_predicate(claims, ClaimPredicate.CHIPSET_MANUFACTURER):
        return True
    if _board_partner_brand(claims) is not None:
        return True
    if _has_compatible_with(claims) is not None:
        return True
    return False


def generate_hypotheses(
    observation: Observation, claims: tuple[Claim, ...], context: ProcessingContext
) -> tuple[ProductHypothesis, ...]:
    """Generate up to ``context.max_active_hypotheses`` ProductHypothesis objects."""
    hypotheses: list[ProductHypothesis] = []

    def new_hypothesis(
        *,
        claim_ids: tuple[str, ...],
        product_form: ProductForm,
        product_type: str | None,
        brand: str | None,
        family: str | None,
        model: str | None,
        compatibility_target: str | None,
        coherence: float,
        evidence_coverage: float,
        unresolved_fields: tuple[str, ...],
        status: HypothesisStatus = HypothesisStatus.ACTIVE,
    ) -> ProductHypothesis:
        return ProductHypothesis(
            hypothesis_id=context.id_factory(),
            observation_id=observation.observation_id,
            claim_ids=claim_ids,
            product_form=product_form,
            product_type=product_type,
            brand=brand,
            family=family,
            model=model,
            variant=None,
            compatibility_target=compatibility_target,
            coherence=coherence,
            evidence_coverage=evidence_coverage,
            status=status,
            unresolved_fields=unresolved_fields,
        )

    identity_family = _identity_family(claims)
    qualified_family = _qualified_family(claims)
    family_claim = identity_family or qualified_family
    board_brand = _board_partner_brand(claims)
    non_complete_types = _non_complete_type_claims(claims)
    packaging_only = _has_packaging_only(claims)
    gpu_not_included = _has_gpu_not_included(claims)
    compatible_with = _has_compatible_with(claims)
    for_parts = _has_for_parts(claims)
    graphics_card_type = _has_graphics_card_type(claims)
    mpn_claims = _claims_by_predicate(claims, ClaimPredicate.MPN)
    title_has_with = bool(_WITH_RE.search(observation.normalized_title.lower()))

    # -- 1. Packaging-only takes precedence: an explicit "box only"/"empty
    #    box" phrase controls product form regardless of family mentions
    #    (spec 10.3). --------------------------------------------------- #
    if packaging_only:
        packaging_claim_ids = tuple(
            c.claim_id
            for c in _claims_by_predicate(claims, ClaimPredicate.PRODUCT_FORM)
            if c.value == "packaging_only"
        )
        hypotheses.append(
            new_hypothesis(
                claim_ids=packaging_claim_ids + ((family_claim.claim_id,) if family_claim else ()),
                product_form=ProductForm.PACKAGING_ONLY,
                product_type="retail_packaging",
                brand=str(board_brand.value) if board_brand else None,
                family=None,
                model=None,
                compatibility_target=str(family_claim.value) if family_claim else None,
                coherence=1.0,
                evidence_coverage=_evidence_coverage([True, family_claim is not None]),
                unresolved_fields=(),
            )
        )

    # -- 2. Explicit accessory/component/replacement-part form terms. ---
    #    Multiple matched phrases can propose the SAME product type (e.g.
    #    "waterblock" and "full cover" both -> gpu_water_block); those are
    #    equivalent hypotheses and must be merged into one (spec 8.4/11.1),
    #    not one hypothesis per matched phrase. --------------------------- #
    distinct_type_values = list(dict.fromkeys(str(c.value) for c in non_complete_types))
    for type_value in distinct_type_values:
        type_claims_for_value = [c for c in non_complete_types if str(c.value) == type_value]
        form = _TYPE_TO_FORM[type_value]
        form_claims = [
            c
            for c in _claims_by_predicate(claims, ClaimPredicate.PRODUCT_FORM)
            if c.value == form.value
        ]
        claim_ids = tuple(c.claim_id for c in form_claims) + tuple(
            c.claim_id for c in type_claims_for_value
        )
        if family_claim is not None:
            claim_ids += (family_claim.claim_id,)
        type_claim = type_claims_for_value[0]
        hypotheses.append(
            new_hypothesis(
                claim_ids=claim_ids,
                product_form=form,
                product_type=str(type_claim.value),
                brand=str(board_brand.value) if board_brand else None,
                family=None,
                model=None,
                compatibility_target=str(family_claim.value) if family_claim else None,
                coherence=1.0,
                evidence_coverage=_evidence_coverage([True, family_claim is not None]),
                unresolved_fields=(),
            )
        )
        # A title that also says "<brand> <family> with <accessory>" may be
        # describing a modified complete product/bundle, not the accessory
        # alone (acceptance case: "ASUS RTX 4090 with EK water block"). Add
        # a second, bounded hypothesis rather than collapsing to the
        # accessory-only interpretation without evidence.
        if (
            title_has_with
            and family_claim is not None
            and len(hypotheses) < context.max_active_hypotheses
        ):
            hypotheses.append(
                new_hypothesis(
                    claim_ids=(family_claim.claim_id, type_claim.claim_id),
                    product_form=ProductForm.BUNDLE,
                    product_type="graphics_card_with_component",
                    brand=str(board_brand.value) if board_brand else None,
                    family=str(family_claim.value),
                    model=str(family_claim.value),
                    compatibility_target=None,
                    coherence=0.7,
                    evidence_coverage=_evidence_coverage([True, board_brand is not None]),
                    unresolved_fields=("variant",),
                )
            )

    # -- 3. Explicit compatibility phrase with no sold-item noun at all. - #
    if (
        compatible_with is not None
        and not non_complete_types
        and not graphics_card_type
        and not packaging_only
    ):
        hypotheses.append(
            new_hypothesis(
                claim_ids=(compatible_with.claim_id,),
                product_form=ProductForm.COMPATIBLE_ITEM,
                product_type=None,
                brand=str(board_brand.value) if board_brand else None,
                family=None,
                model=None,
                compatibility_target=str(compatible_with.value),
                coherence=0.4,
                evidence_coverage=_evidence_coverage([False]),
                unresolved_fields=("product_type",),
            )
        )

    # -- 4. Complete-product / classified graphics-card hypothesis. ----- #
    has_bundle_term = bool(_claims_by_predicate(claims, ClaimPredicate.BUNDLE_CONTENT))
    if not hypotheses and (identity_family is not None or graphics_card_type):
        if has_bundle_term:
            form = ProductForm.BUNDLE
        elif for_parts:
            form = ProductForm.INCOMPLETE_PRODUCT
        else:
            form = ProductForm.COMPLETE_PRODUCT
        product_type = "graphics_card_bundle" if has_bundle_term else "graphics_card"
        family_value = str(identity_family.value) if identity_family is not None else None
        unresolved: list[str] = []
        if family_value is None:
            unresolved.append("family")
        if board_brand is None:
            unresolved.append("brand")
        if not mpn_claims:
            unresolved.append("variant")
        claim_ids = tuple(
            c.claim_id
            for c in claims
            if c.predicate
            in (
                ClaimPredicate.PRODUCT_FAMILY,
                ClaimPredicate.MODEL,
                ClaimPredicate.BRAND,
                ClaimPredicate.CHIPSET_MANUFACTURER,
                ClaimPredicate.PRODUCT_TYPE,
                ClaimPredicate.CAPACITY,
                ClaimPredicate.MPN,
                ClaimPredicate.CONDITION,
                ClaimPredicate.BUNDLE_CONTENT,
            )
            and c.status == ClaimStatus.SUPPORTED
        )
        hypotheses.append(
            new_hypothesis(
                claim_ids=claim_ids,
                product_form=form,
                product_type=product_type,
                brand=str(board_brand.value) if board_brand else None,
                family=family_value,
                model=family_value,
                compatibility_target=None,
                coherence=1.0 if not gpu_not_included else 0.4,
                evidence_coverage=_evidence_coverage(
                    [family_value is not None, board_brand is not None, bool(mpn_claims)]
                ),
                unresolved_fields=tuple(unresolved),
            )
        )

    return tuple(hypotheses[: context.max_active_hypotheses])
