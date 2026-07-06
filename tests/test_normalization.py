"""Unit tests for the normalization package."""

from __future__ import annotations

import pytest

from digital_arbitrage.normalization import (
    ConditionNormalizer,
    CurrencyNormalizer,
    LocationNormalizer,
    NormalizationConfig,
    NormalizationPipeline,
    NormalizationStep,
    NormalizedListing,
    Normalizer,
    TitleCleanupStep,
    UnicodeNormalizationStep,
    WhitespaceNormalizationStep,
    build_default_pipeline,
)
from digital_arbitrage.normalization import text as textmod
from digital_arbitrage.product_scanner import Condition, Listing, create_provider


def make_listing(**overrides: object) -> Listing:
    kwargs: dict[str, object] = {
        "listing_id": "x1",
        "title": "RTX 4090",
        "provider": "ebay",
        "url": "https://e/1",
    }
    kwargs.update(overrides)
    return Listing(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #
def test_normalize_unicode_folds_compatibility_chars() -> None:
    # Fullwidth "ＲＴＸ" -> ASCII "RTX" under NFKC.
    assert textmod.normalize_unicode("\uff32\uff34\uff38") == "RTX"


def test_remove_control_characters_strips_zero_width() -> None:
    assert textmod.remove_control_characters("a\u200bb\ufeffc") == "abc"


def test_normalize_punctuation_folds_smart_quotes_and_dashes() -> None:
    assert textmod.normalize_punctuation("\u201chi\u201d \u2013 x") == '"hi" - x'


def test_remove_symbols_and_emoji() -> None:
    assert textmod.remove_symbols_and_emoji("card \U0001f3ae here") == "card  here"


def test_collapse_whitespace() -> None:
    assert textmod.collapse_whitespace("  a\t b\n c  ") == "a b c"


def test_clean_text_is_composed() -> None:
    assert textmod.clean_text("  \u201cRTX\u201d\u200b   4090 ") == '"RTX" 4090'


def test_tokenize_returns_lowercase_alnum() -> None:
    assert textmod.tokenize("RTX-4090 Ti!!") == ("rtx", "4090", "ti")


@pytest.mark.parametrize("fn", [textmod.clean_text, textmod.collapse_whitespace, textmod.tokenize])
def test_text_helpers_handle_empty(fn) -> None:  # noqa: ANN001 - parametrized callables
    assert fn("") in ("", ())


# --------------------------------------------------------------------------- #
# CurrencyNormalizer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [("\u20ac", "EUR"), ("eur", "EUR"), ("Euro", "EUR"), ("$", "USD"), ("\u00a3", "GBP")],
)
def test_currency_known_aliases(value: str, expected: str) -> None:
    assert CurrencyNormalizer().normalize(value) == expected


def test_currency_unknown_three_letter_passthrough() -> None:
    assert CurrencyNormalizer().normalize("jpy") == "JPY"


def test_currency_unknown_symbol_is_none() -> None:
    assert CurrencyNormalizer().normalize("###") is None


def test_currency_empty_uses_default() -> None:
    assert CurrencyNormalizer(default="eur").normalize(None) == "EUR"
    assert CurrencyNormalizer(default="EUR").normalize("  ") == "EUR"


def test_currency_register_override() -> None:
    cur = CurrencyNormalizer()
    cur.register("bucks", "USD")
    assert cur.normalize("BUCKS") == "USD"


# --------------------------------------------------------------------------- #
# ConditionNormalizer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("brand new", Condition.NEW),
        ("BNIB", Condition.NEW),
        ("pre-owned", Condition.USED),
        ("Second Hand", Condition.USED),
        ("refurb", Condition.REFURBISHED),
        ("renewed", Condition.REFURBISHED),
        ("nonsense", Condition.UNKNOWN),
        (None, Condition.UNKNOWN),
    ],
)
def test_condition_aliases(value: str | None, expected: Condition) -> None:
    assert ConditionNormalizer().normalize(value) is expected


def test_condition_passthrough_enum() -> None:
    assert ConditionNormalizer().normalize(Condition.USED) is Condition.USED


def test_condition_register() -> None:
    cn = ConditionNormalizer()
    cn.register("ex-display", Condition.REFURBISHED)
    assert cn.normalize("ex-display") is Condition.REFURBISHED


# --------------------------------------------------------------------------- #
# LocationNormalizer
# --------------------------------------------------------------------------- #
def test_location_alias() -> None:
    assert LocationNormalizer().normalize("  co. dublin ") == "Dublin"


def test_location_unknown_is_title_cased() -> None:
    assert LocationNormalizer().normalize("some   town") == "Some Town"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_location_empty_is_none(value: str | None) -> None:
    assert LocationNormalizer().normalize(value) is None


def test_location_register() -> None:
    loc = LocationNormalizer()
    loc.register("blackrock", "Blackrock, Co. Dublin")
    assert loc.normalize("Blackrock") == "Blackrock, Co. Dublin"


# --------------------------------------------------------------------------- #
# NormalizedListing model
# --------------------------------------------------------------------------- #
def test_normalized_listing_from_listing_seeds_raw_values() -> None:
    listing = make_listing(title="Foo", currency="EUR", location="Cork")
    nl = NormalizedListing.from_listing(listing)
    assert nl.title == "Foo"
    assert nl.currency == "EUR"
    assert nl.location == "Cork"
    assert nl.source is listing
    assert nl.listing_id == "x1"
    assert nl.provider == "ebay"


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def test_pipeline_default_order() -> None:
    pipeline = build_default_pipeline()
    assert pipeline.step_names == [
        "unicode",
        "text_cleaning",
        "whitespace",
        "title_cleanup",
        "currency",
        "condition",
        "location",
    ]


def test_pipeline_add_and_remove_step() -> None:
    pipeline = NormalizationPipeline([WhitespaceNormalizationStep()])
    pipeline.add_step(UnicodeNormalizationStep(), index=0)
    assert pipeline.step_names == ["unicode", "whitespace"]
    pipeline.remove_step("unicode")
    assert pipeline.step_names == ["whitespace"]


def test_pipeline_remove_missing_step_raises() -> None:
    with pytest.raises(KeyError, match="no step named"):
        NormalizationPipeline().remove_step("nope")


def test_step_requires_name() -> None:
    class Nameless(NormalizationStep):
        def apply(self, listing: NormalizedListing) -> None:
            return None

    with pytest.raises(ValueError, match="non-empty 'name'"):
        Nameless()


def test_custom_step_runs_in_pipeline() -> None:
    class Shout(NormalizationStep):
        name = "shout"

        def apply(self, listing: NormalizedListing) -> None:
            listing.title = listing.title.upper()

    pipeline = NormalizationPipeline([Shout()])
    nl = pipeline.run(NormalizedListing.from_listing(make_listing(title="hi")))
    assert nl.title == "HI"


# --------------------------------------------------------------------------- #
# Individual steps
# --------------------------------------------------------------------------- #
def test_title_cleanup_lowercases_and_tokenizes_dropping_filler() -> None:
    nl = NormalizedListing.from_listing(make_listing(title="Brand New RTX 4090 Card"))
    TitleCleanupStep().apply(nl)
    assert nl.title == "brand new rtx 4090 card"
    assert nl.title_tokens == ("rtx", "4090", "card")


def test_title_cleanup_can_disable_lowercase_and_filler() -> None:
    nl = NormalizedListing.from_listing(make_listing(title="Brand New RTX"))
    TitleCleanupStep(lowercase=False, remove_filler=False).apply(nl)
    assert nl.title == "Brand New RTX"
    assert nl.title_tokens == ("brand", "new", "rtx")


# --------------------------------------------------------------------------- #
# Normalizer (end to end)
# --------------------------------------------------------------------------- #
def test_normalizer_end_to_end() -> None:
    listing = make_listing(
        title="  Brand New RTX 4090 \u2013 Graphics  Card!! \U0001f3ae ",
        currency="\u20ac",
        condition=Condition.USED,
        location="co. dublin",
    )
    nl = Normalizer().normalize(listing)
    assert "\U0001f3ae" not in nl.title
    assert nl.title == nl.title.lower()
    assert "  " not in nl.title
    assert nl.title_tokens == ("rtx", "4090", "graphics", "card")
    assert nl.currency == "EUR"
    assert nl.condition is Condition.USED
    assert nl.location == "Dublin"
    assert nl.source is listing


def test_normalizer_is_provider_agnostic() -> None:
    normalizer = Normalizer()
    for name in ("ebay", "facebook_marketplace", "adverts_ie", "donedeal"):
        listings = create_provider(name).search("RTX 4090", limit=2)
        results = normalizer.normalize_many(listings)
        assert len(results) == 2
        assert all(isinstance(item, NormalizedListing) for item in results)
        assert all(item.title == item.title.lower() for item in results)
        assert all(item.currency == "EUR" for item in results)


def test_normalizer_respects_config_toggles() -> None:
    cfg = NormalizationConfig(lowercase_title=False, remove_filler_words=False)
    nl = Normalizer(config=cfg).normalize(make_listing(title="Brand New GPU"))
    assert nl.title == "Brand New GPU"
    assert nl.title_tokens == ("brand", "new", "gpu")


def test_normalizer_default_currency_fallback() -> None:
    cfg = NormalizationConfig(default_currency="EUR")
    listing = make_listing(currency="")
    assert Normalizer(config=cfg).normalize(listing).currency == "EUR"


def test_normalizer_accepts_custom_pipeline() -> None:
    pipeline = NormalizationPipeline([WhitespaceNormalizationStep()])
    nl = Normalizer(pipeline=pipeline).normalize(make_listing(title="  a   b  "))
    assert nl.title == "a b"
    # currency step not in pipeline, so raw value is untouched
    assert nl.currency == "EUR"
