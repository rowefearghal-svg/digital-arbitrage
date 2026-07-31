"""Bundle Decision regression coverage (Sprint 2, Task 5).

Direct field-level assertions for the two bundle-adjacent scenarios named in
the Sprint 2 brief: a title that unambiguously establishes a bundle, and a
title that must remain genuinely ambiguous because it cannot establish
whether the GPU itself is included alongside the component.
"""

from __future__ import annotations

from digital_arbitrage.pue.enums import (
    ComparabilityStatus,
    DecisionType,
    IdentificationLevel,
    ProductForm,
)
from digital_arbitrage.pue.orchestration import process_one

from .conftest import make_normalized


# --------------------------------------------------------------------------- #
# 1. A clear, single bundle hypothesis.
# --------------------------------------------------------------------------- #
def test_clear_bundle_listing_is_a_single_bundle_hypothesis(
    deterministic_context, repository
) -> None:
    listing = make_normalized("RTX 4090 graphics card + power supply bundle")
    record = process_one(listing, deterministic_context, repository=repository)

    assert len(record.hypotheses) == 1
    assert record.hypotheses[0].product_form == ProductForm.BUNDLE
    assert record.hypotheses[0].family == "rtx 4090"


def test_clear_bundle_listing_decision_fields(deterministic_context, repository) -> None:
    listing = make_normalized("RTX 4090 graphics card + power supply bundle")
    record = process_one(listing, deterministic_context, repository=repository)
    decision = record.decision

    assert decision.product_form == ProductForm.BUNDLE
    assert decision.decision_type in (
        DecisionType.PARTIALLY_IDENTIFIED,
        DecisionType.CLASSIFIED,
    )
    assert decision.comparability_status == ComparabilityStatus.NOT_COMPARABLE_BUNDLE
    assert "bundle_contents" in decision.unresolved_fields
    # No direct single-product comparison: never an exact/complete-product
    # identification level for a bundle, and never a selected exact
    # catalogue Candidate standing in for "the GPU" alone.
    assert decision.identification_level != IdentificationLevel.EXACT_CATALOGUE_PRODUCT
    assert decision.decision_type != DecisionType.IDENTIFIED


def test_clear_bundle_listing_identifies_the_gpu_family_when_present(
    deterministic_context, repository
) -> None:
    listing = make_normalized("RTX 4090 graphics card + power supply bundle")
    record = process_one(listing, deterministic_context, repository=repository)
    decision = record.decision

    assert decision.decision_type == DecisionType.PARTIALLY_IDENTIFIED
    assert decision.identification_level == IdentificationLevel.MODEL
    assert decision.identified_family == "rtx 4090"


def test_bundle_without_a_recognizable_family_is_classified_not_identified(
    deterministic_context, repository
) -> None:
    """A bundle whose GPU family cannot be established must still be
    recognized as a bundle and never escalate past CLASSIFIED."""
    listing = make_normalized("Graphics card + power supply bundle")
    record = process_one(listing, deterministic_context, repository=repository)
    decision = record.decision

    assert decision.product_form == ProductForm.BUNDLE
    assert decision.decision_type in (DecisionType.CLASSIFIED, DecisionType.PARTIALLY_IDENTIFIED)
    assert decision.comparability_status == ComparabilityStatus.NOT_COMPARABLE_BUNDLE


# --------------------------------------------------------------------------- #
# 2. Genuine ambiguity: GPU-inclusion cannot be established from the title.
# --------------------------------------------------------------------------- #
def test_gpu_with_component_listing_remains_ambiguous(deterministic_context, repository) -> None:
    listing = make_normalized("ASUS RTX 4090 with EK water block")
    record = process_one(listing, deterministic_context, repository=repository)
    decision = record.decision

    assert decision.decision_type == DecisionType.AMBIGUOUS
    assert decision.abstention_reason is None
    assert decision.comparability_status == ComparabilityStatus.INSUFFICIENT_INFORMATION
    assert decision.review_recommended is True


def test_gpu_with_component_listing_preserves_both_alternative_interpretations(
    deterministic_context, repository
) -> None:
    """Both a component-only interpretation and a complete-product-plus-
    component (bundle) interpretation must survive as active hypotheses -
    neither is silently collapsed into the other."""
    listing = make_normalized("ASUS RTX 4090 with EK water block")
    record = process_one(listing, deterministic_context, repository=repository)

    assert len(record.hypotheses) > 1
    forms = {h.product_form for h in record.hypotheses}
    assert ProductForm.COMPONENT in forms
    assert ProductForm.BUNDLE in forms

    component_hyp = next(h for h in record.hypotheses if h.product_form == ProductForm.COMPONENT)
    bundle_hyp = next(h for h in record.hypotheses if h.product_form == ProductForm.BUNDLE)
    assert component_hyp.family is None  # the component alone, no GPU identity claimed
    assert bundle_hyp.family == "rtx 4090"  # the GPU-plus-component interpretation


def test_gpu_with_component_listing_does_not_force_the_bundle_branch(
    deterministic_context, repository
) -> None:
    """Regression: this title must not be silently routed into the
    single-hypothesis bundle Decision branch (NOT_COMPARABLE_BUNDLE) - the
    Evidence does not establish a bundle over a component-only reading, so
    the multi-hypothesis AMBIGUOUS path must remain the outcome."""
    listing = make_normalized("ASUS RTX 4090 with EK water block")
    record = process_one(listing, deterministic_context, repository=repository)
    assert record.decision.comparability_status != ComparabilityStatus.NOT_COMPARABLE_BUNDLE
    assert record.decision.product_form != ProductForm.BUNDLE
