"""Unit tests for the product_matching package."""

from __future__ import annotations

import pytest

from digital_arbitrage.normalization import Normalizer
from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_matching import (
    DEFAULT_BRANDS,
    MatchConfig,
    MatchDecision,
    MatchResult,
    ProductMatcher,
    extract_brands,
    is_model_token,
    jaccard,
    model_tokens,
    overlap_coefficient,
    token_set,
)
from digital_arbitrage.product_scanner import Listing


def make_nl(tokens: tuple[str, ...], title: str | None = None) -> NormalizedListing:
    display = title if title is not None else (" ".join(tokens) or "untitled")
    listing = Listing(listing_id="x", title=display, provider="p", url="https://x/1")
    return NormalizedListing(source=listing, title=display, title_tokens=tuple(tokens))


# --------------------------------------------------------------------------- #
# scoring helpers
# --------------------------------------------------------------------------- #
def test_token_set_drops_empty() -> None:
    assert token_set(["a", "", "b"]) == frozenset({"a", "b"})


def test_jaccard() -> None:
    assert jaccard(frozenset("ab"), frozenset("bc")) == pytest.approx(1 / 3)
    assert jaccard(frozenset(), frozenset()) == 0.0
    assert jaccard(frozenset("a"), frozenset("a")) == 1.0


def test_overlap_coefficient() -> None:
    assert overlap_coefficient(frozenset("ab"), frozenset("abc")) == 1.0
    assert overlap_coefficient(frozenset(), frozenset("a")) == 0.0


@pytest.mark.parametrize(
    ("token", "expected"),
    [("4090", True), ("s24", True), ("512gb", True), ("1", False), ("16", False), ("rtx", False)],
)
def test_is_model_token(token: str, expected: bool) -> None:
    assert is_model_token(token) is expected


def test_model_tokens_filters() -> None:
    assert model_tokens(["rtx", "4090", "1", "s24"]) == frozenset({"4090", "s24"})


# --------------------------------------------------------------------------- #
# brands
# --------------------------------------------------------------------------- #
def test_extract_brands_default() -> None:
    assert extract_brands(["nvidia", "rtx", "4090"]) == frozenset({"nvidia"})


def test_extract_brands_custom_set() -> None:
    assert extract_brands(["acme", "widget"], frozenset({"acme"})) == frozenset({"acme"})


def test_default_brands_is_lowercase() -> None:
    assert all(b == b.lower() for b in DEFAULT_BRANDS)


# --------------------------------------------------------------------------- #
# MatchConfig / MatchResult
# --------------------------------------------------------------------------- #
def test_match_config_rejects_bad_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        MatchConfig(same_threshold=0.4, possible_threshold=0.5)


def test_match_config_rejects_bad_overlap_weight() -> None:
    with pytest.raises(ValueError, match="overlap_weight"):
        MatchConfig(overlap_weight=1.5)


def test_match_result_validates_score() -> None:
    with pytest.raises(ValueError, match="score must be in"):
        MatchResult(score=1.5, decision=MatchDecision.SAME_PRODUCT)


def test_match_result_is_match() -> None:
    assert MatchResult(score=0.9, decision=MatchDecision.SAME_PRODUCT).is_match
    assert not MatchResult(score=0.5, decision=MatchDecision.POSSIBLE_MATCH).is_match


# --------------------------------------------------------------------------- #
# ProductMatcher
# --------------------------------------------------------------------------- #
def test_identical_listings_are_same_product() -> None:
    a = make_nl(("nvidia", "rtx", "4090"))
    result = ProductMatcher().match(a, a)
    assert result.decision is MatchDecision.SAME_PRODUCT
    assert result.score == 1.0
    assert result.matched_tokens == ("4090", "nvidia", "rtx")
    assert result.unmatched_tokens == ()


def test_superset_same_model_is_same_product() -> None:
    a = make_nl(("rtx", "4090"))
    b = make_nl(("rtx", "4090", "graphics", "card", "gaming"))
    result = ProductMatcher().match(a, b)
    assert result.decision is MatchDecision.SAME_PRODUCT
    assert "4090" in result.matched_tokens


def test_conflicting_model_is_different_product() -> None:
    a = make_nl(("rtx", "4090"))
    b = make_nl(("rtx", "4080"))
    result = ProductMatcher().match(a, b)
    assert result.decision is MatchDecision.DIFFERENT_PRODUCT
    assert result.score <= MatchConfig().model_conflict_cap
    assert any("conflicting model" in r for r in result.reasons)


def test_conflicting_brand_pulls_down_to_different() -> None:
    a = make_nl(("nvidia", "gpu", "4090"))
    b = make_nl(("amd", "gpu", "4090"))
    result = ProductMatcher().match(a, b)
    assert result.decision is MatchDecision.DIFFERENT_PRODUCT
    assert any("conflicting brands" in r for r in result.reasons)


def test_shared_brand_no_model_is_possible_match() -> None:
    a = make_nl(("apple", "macbook", "pro"))
    b = make_nl(("apple", "macbook", "air"))
    result = ProductMatcher().match(a, b)
    assert result.decision is MatchDecision.POSSIBLE_MATCH
    assert any("shared brand" in r for r in result.reasons)


def test_no_tokens_is_different_product() -> None:
    a = make_nl(())
    b = make_nl(("rtx", "4090"))
    result = ProductMatcher().match(a, b)
    assert result.decision is MatchDecision.DIFFERENT_PRODUCT
    assert result.score == 0.0
    assert any("no comparable tokens" in r for r in result.reasons)


def test_matched_and_unmatched_tokens() -> None:
    a = make_nl(("rtx", "4090", "founders"))
    b = make_nl(("rtx", "4090", "edition"))
    result = ProductMatcher().match(a, b)
    assert result.matched_tokens == ("4090", "rtx")
    assert result.unmatched_tokens == ("edition", "founders")


def test_match_is_symmetric() -> None:
    a = make_nl(("apple", "iphone", "13", "pro"))
    b = make_nl(("apple", "iphone", "13"))
    assert ProductMatcher().match(a, b).score == ProductMatcher().match(b, a).score


def test_reasons_always_populated() -> None:
    result = ProductMatcher().match(make_nl(("a", "b")), make_nl(("a", "c")))
    assert result.reasons
    assert any(r.startswith("token similarity") for r in result.reasons)
    assert any(r.startswith("decision") for r in result.reasons)


def test_thresholds_are_configurable() -> None:
    a = make_nl(("apple", "macbook", "pro"))
    b = make_nl(("apple", "macbook", "air"))
    strict = ProductMatcher(MatchConfig(same_threshold=0.95, possible_threshold=0.9))
    assert strict.match(a, b).decision is MatchDecision.DIFFERENT_PRODUCT
    lenient = ProductMatcher(MatchConfig(same_threshold=0.5, possible_threshold=0.2))
    assert lenient.match(a, b).decision is MatchDecision.SAME_PRODUCT


def test_integration_with_normalizer() -> None:
    normalizer = Normalizer()
    a = normalizer.normalize(
        Listing(
            listing_id="1", title="Brand New NVIDIA RTX 4090", provider="ebay", url="https://e/1"
        )
    )
    b = normalizer.normalize(
        Listing(
            listing_id="2",
            title="nvidia  rtx 4090 graphics card",
            provider="donedeal",
            url="https://d/2",
        )
    )
    result = ProductMatcher().match(a, b)
    assert result.decision in {MatchDecision.SAME_PRODUCT, MatchDecision.POSSIBLE_MATCH}
    assert "4090" in result.matched_tokens
