"""Unit tests: bounded Hypothesis Generation, branching and merging."""

from __future__ import annotations

from digital_arbitrage.pue.admission import admit_observation
from digital_arbitrage.pue.claims import construct_claims
from digital_arbitrage.pue.enums import ProductForm
from digital_arbitrage.pue.evidence import extract_evidence
from digital_arbitrage.pue.hypotheses import generate_hypotheses

from .conftest import make_normalized


def _hyps(title, context):
    obs = admit_observation(make_normalized(title), context)
    evidence = extract_evidence(obs, context)
    claims = construct_claims(obs, evidence, context)
    return generate_hypotheses(obs, claims, context)


def test_no_hypotheses_for_non_gpu_domain(deterministic_context) -> None:
    assert _hyps("Samsung?", deterministic_context) == ()


def test_bounded_to_max_three(deterministic_context) -> None:
    hyps = _hyps("ASUS RTX 4090 with EK water block", deterministic_context)
    assert len(hyps) <= deterministic_context.max_active_hypotheses


def test_equivalent_hypotheses_are_merged(deterministic_context) -> None:
    """'waterblock' and 'full cover' both propose gpu_water_block; they must
    merge into a single hypothesis, not one per matched phrase (regression)."""
    hyps = _hyps("RTX 4090 Waterblock Full Cover GPU Cooling Block", deterministic_context)
    assert len(hyps) == 1
    assert hyps[0].product_form == ProductForm.COMPONENT


def test_water_block_hypothesis_has_no_identity_family(deterministic_context) -> None:
    hyps = _hyps("RTX 4090 water block", deterministic_context)
    assert len(hyps) == 1
    assert hyps[0].family is None
    assert hyps[0].compatibility_target == "rtx 4090"


def test_complete_product_hypothesis_carries_family(deterministic_context) -> None:
    hyps = _hyps("ASUS TUF RTX 4090 OC", deterministic_context)
    assert len(hyps) == 1
    assert hyps[0].product_form == ProductForm.COMPLETE_PRODUCT
    assert hyps[0].family == "rtx 4090"


def test_bundle_branches_into_two_hypotheses(deterministic_context) -> None:
    hyps = _hyps("ASUS RTX 4090 with EK water block", deterministic_context)
    forms = {h.product_form for h in hyps}
    assert ProductForm.COMPONENT in forms
    assert ProductForm.BUNDLE in forms


def test_compatible_item_hypothesis_when_no_sold_item_noun(deterministic_context) -> None:
    hyps = _hyps("Compatible with RTX 4090", deterministic_context)
    assert len(hyps) == 1
    assert hyps[0].product_form == ProductForm.COMPATIBLE_ITEM
    assert hyps[0].coherence < 0.5


def test_for_parts_produces_incomplete_product_form(deterministic_context) -> None:
    hyps = _hyps("For parts RTX 4090 not working", deterministic_context)
    assert len(hyps) == 1
    assert hyps[0].product_form == ProductForm.INCOMPLETE_PRODUCT


def test_explicit_bundle_term_produces_bundle_form(deterministic_context) -> None:
    hyps = _hyps("RTX 4090 + PSU bundle", deterministic_context)
    assert len(hyps) == 1
    assert hyps[0].product_form == ProductForm.BUNDLE
