"""Unit tests for the title-based listing classifier.

Titles are real or lightly-sanitised marketplace strings. Coverage targets the
behaviours called out for the sprint: spacing, hyphens, capitalisation, false
positives, false negatives, multiple accessories, and unknown titles.
"""

from __future__ import annotations

import pytest

from digital_arbitrage.classification import (
    Classification,
    ClassificationConfig,
    ListingClassification,
    ListingClassifier,
    SearchProfile,
    build_search_profile,
    classify_title,
)
from digital_arbitrage.classification.matching import (
    all_word_matches,
    compact_match,
    first_word_match,
    prepare,
    word_match,
)


@pytest.fixture
def rtx_profile() -> SearchProfile:
    """The profile a search for 'rtx 4090' produces."""
    return build_search_profile("rtx 4090")


def classify(title: str, profile: SearchProfile) -> Classification:
    return classify_title(title, profile).classification


# --------------------------------------------------------------------------- #
# matching primitives
# --------------------------------------------------------------------------- #
def test_prepare_normalises_case_hyphens_and_spacing() -> None:
    text = prepare("  RTX-4090   Founders\tEdition  ")
    assert text.tokens == ("rtx", "4090", "founders", "edition")
    assert text.compact == "rtx4090foundersedition"


def test_word_match_is_token_bounded_no_substrings() -> None:
    text = prepare("Fantastic Graphics Card")
    # "fan" must NOT match inside "fantastic".
    assert not word_match("fan", text)
    assert word_match("card", text)


def test_word_match_supports_phrases() -> None:
    text = prepare("Original Power Cable Only")
    assert word_match("power cable", text)
    assert not word_match("cable power", text)  # order matters for phrases


def test_compact_match_ignores_spacing_and_hyphens() -> None:
    assert compact_match("rtx 4090", prepare("RTX4090"))
    assert compact_match("rtx-4090", prepare("rtx 4090"))
    assert not compact_match("rtx 4090", prepare("rtx 4080"))


def test_first_and_all_word_matches_preserve_order_and_dedup() -> None:
    text = prepare("Cable and adapter and cable")
    assert first_word_match(("adapter", "cable"), text) == "adapter"
    assert all_word_matches(("cable", "adapter", "cable"), text) == ["cable", "adapter"]


def test_empty_term_never_matches() -> None:
    text = prepare("anything")
    assert not word_match("", text)
    assert not compact_match("   ", text)


# --------------------------------------------------------------------------- #
# spec examples (verbatim from the sprint prompt)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Zotac RTX 4090 Trinity OC", Classification.COMPLETE_PRODUCT),
        ("Nvidia RTX4090 FE", Classification.COMPLETE_PRODUCT),
        ("12VHPWR Cable for RTX4090", Classification.ACCESSORY),
        ("RTX4090 Fan Replacement", Classification.PART),
        ("Graphics Card Box", Classification.REJECTED),
    ],
)
def test_spec_examples(title: str, expected: Classification, rtx_profile: SearchProfile) -> None:
    assert classify(title, rtx_profile) == expected


# --------------------------------------------------------------------------- #
# capitalisation / spacing / hyphen invariance
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "title",
    [
        "RTX 4090",
        "rtx 4090",
        "RtX 4090",
        "RTX4090",
        "rtx-4090",
        "RTX  4090",  # doubled space
        "MSI RTX-4090 SUPRIM X",
    ],
)
def test_model_variants_all_complete_product(title: str, rtx_profile: SearchProfile) -> None:
    assert classify(title, rtx_profile) == Classification.COMPLETE_PRODUCT


def test_strong_vs_scattered_confidence(rtx_profile: SearchProfile) -> None:
    strong = classify_title("Gigabyte RTX 4090 Gaming OC", rtx_profile)
    scattered = classify_title("RTX Graphics Card model 4090 boxed", rtx_profile)
    assert strong.classification == Classification.COMPLETE_PRODUCT
    assert scattered.classification == Classification.COMPLETE_PRODUCT
    assert strong.match_confidence > scattered.match_confidence


# --------------------------------------------------------------------------- #
# accessories & parts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "title",
    [
        "Power cable for RTX 4090",
        "RTX 4090 12VHPWR adapter",
        "GPU support bracket for RTX 4090",
        "RTX 4090 anti sag holder",
    ],
)
def test_accessory_titles(title: str, rtx_profile: SearchProfile) -> None:
    assert classify(title, rtx_profile) == Classification.ACCESSORY


@pytest.mark.parametrize(
    "title",
    [
        "RTX 4090 replacement fan",
        "RTX 4090 backplate only",
        "RTX 4090 heatsink for parts",
        "Faulty RTX 4090 spares or repair",
    ],
)
def test_part_titles(title: str, rtx_profile: SearchProfile) -> None:
    assert classify(title, rtx_profile) == Classification.PART


def test_multiple_accessories_are_all_reported(rtx_profile: SearchProfile) -> None:
    result = classify_title("RTX 4090 power cable and adapter bundle", rtx_profile)
    assert result.classification == Classification.ACCESSORY
    assert "cable" in result.reason and "adapter" in result.reason
    # A multi-keyword accessory match is at least as confident as a single one.
    single = classify_title("RTX 4090 power cable", rtx_profile)
    assert result.match_confidence >= single.match_confidence


def test_accessory_takes_precedence_over_part(rtx_profile: SearchProfile) -> None:
    # Contains both an accessory ("cable") and a part ("fan") keyword.
    result = classify_title("RTX 4090 replacement fan with power cable", rtx_profile)
    assert result.classification == Classification.ACCESSORY


# --------------------------------------------------------------------------- #
# rejected / unknown
# --------------------------------------------------------------------------- #
def test_excluded_keyword_rejects_even_with_model(rtx_profile: SearchProfile) -> None:
    result = classify_title("RTX 4090 poster print A2", rtx_profile)
    assert result.classification == Classification.REJECTED
    assert "poster" in result.reason


def test_missing_all_required_is_rejected(rtx_profile: SearchProfile) -> None:
    result = classify_title("Nvidia GeForce graphics card", rtx_profile)
    assert result.classification == Classification.REJECTED
    assert "Missing required term" in result.reason


def test_partial_required_is_unknown(rtx_profile: SearchProfile) -> None:
    # Has "4090" but not "rtx" -> ambiguous, neither confidently product nor not.
    result = classify_title("4090 graphics card boxed", rtx_profile)
    assert result.classification == Classification.UNKNOWN
    assert "rtx" in result.reason


def test_false_positive_guarded_against_substrings() -> None:
    # "fan" appears inside "fantastic" but must not trigger a PART verdict.
    profile = build_search_profile("gpu")
    result = classify_title("Fantastic gpu, great condition", profile)
    assert result.classification == Classification.COMPLETE_PRODUCT


def test_real_ebay_titles(rtx_profile: SearchProfile) -> None:
    # Sanitised titles taken from the eBay Browse fixtures.
    assert classify("NVIDIA GeForce RTX 4090 Founders Edition 24GB", rtx_profile) == (
        Classification.COMPLETE_PRODUCT
    )
    assert classify("RTX 4090 Gaming OC 24GB (Certified Refurbished)", rtx_profile) == (
        Classification.COMPLETE_PRODUCT
    )
    assert classify("Used RTX 4090 - fully tested and working", rtx_profile) == (
        Classification.COMPLETE_PRODUCT
    )


# --------------------------------------------------------------------------- #
# profile building & config
# --------------------------------------------------------------------------- #
def test_build_profile_derives_required_from_query() -> None:
    profile = build_search_profile("Sony WH-1000XM5")
    assert profile.required_terms == ("sony", "wh", "1000xm5")


def test_config_can_override_required_terms() -> None:
    config = ClassificationConfig(required_terms=("iphone", "15", "pro"))
    profile = build_search_profile("anything at all", config)
    assert profile.required_terms == ("iphone", "15", "pro")


def test_config_can_extend_accessory_terms(rtx_profile: SearchProfile) -> None:
    config = ClassificationConfig(accessory_terms=("gpu block",))
    profile = build_search_profile("rtx 4090", config)
    assert classify("RTX 4090 gpu block custom loop", profile) == Classification.ACCESSORY
    # The default profile has no such term, so the same title is a product.
    assert classify("RTX 4090 gpu block custom loop", rtx_profile) == (
        Classification.COMPLETE_PRODUCT
    )


def test_empty_profile_treats_everything_as_product() -> None:
    profile = SearchProfile()
    result = classify_title("literally anything", profile)
    assert result.classification == Classification.COMPLETE_PRODUCT
    assert result.reason == "No required terms defined"


# --------------------------------------------------------------------------- #
# model validation & serialisation
# --------------------------------------------------------------------------- #
def test_listing_classification_validates_confidence() -> None:
    with pytest.raises(ValueError):
        ListingClassification(Classification.UNKNOWN, 101, "x")
    with pytest.raises(ValueError):
        ListingClassification(Classification.UNKNOWN, 50, "")


def test_listing_classification_to_dict() -> None:
    result = classify_title("RTX 4090 power cable", build_search_profile("rtx 4090"))
    payload = result.to_dict()
    assert payload == {
        "classification": "accessory",
        "match_confidence": result.match_confidence,
        "reason": result.reason,
    }


def test_classification_is_deterministic() -> None:
    profile = build_search_profile("rtx 4090")
    a = classify_title("Zotac RTX 4090 Trinity OC", profile)
    b = classify_title("Zotac RTX 4090 Trinity OC", profile)
    assert a == b


# --------------------------------------------------------------------------- #
# classifier convenience wrapper
# --------------------------------------------------------------------------- #
def test_classifier_annotates_normalized_listing_in_place() -> None:
    from digital_arbitrage.normalization import Normalizer
    from digital_arbitrage.product_scanner import Listing

    listing = Listing(
        listing_id="1", title="12VHPWR Cable for RTX4090", provider="ebay", url="https://x"
    )
    normalized = Normalizer().normalize(listing)
    assert normalized.classification is None

    classifier = ListingClassifier()
    verdict = classifier.classify(normalized, classifier.profile_for("rtx 4090"))
    assert verdict.classification == Classification.ACCESSORY
    assert normalized.classification is verdict


def test_classifier_classify_many_returns_one_verdict_per_listing() -> None:
    from digital_arbitrage.normalization import Normalizer
    from digital_arbitrage.product_scanner import Listing

    titles = ["Zotac RTX 4090", "RTX4090 fan", "random unrelated item"]
    normalized = [
        Normalizer().normalize(Listing(listing_id=str(i), title=t, provider="p", url="https://x"))
        for i, t in enumerate(titles)
    ]
    classifier = ListingClassifier()
    verdicts = classifier.classify_many(normalized, classifier.profile_for("rtx 4090"))
    assert [v.classification for v in verdicts] == [
        Classification.COMPLETE_PRODUCT,
        Classification.PART,
        Classification.REJECTED,
    ]
    assert all(nl.classification is v for nl, v in zip(normalized, verdicts, strict=True))
