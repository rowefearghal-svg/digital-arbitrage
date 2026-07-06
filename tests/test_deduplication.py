"""Unit tests for the deduplication package."""

from __future__ import annotations

import pytest

from digital_arbitrage.deduplication import (
    DeduplicationConfig,
    DeduplicationResult,
    Deduplicator,
    DuplicateGroup,
    listing_fingerprint,
    signature,
)
from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_scanner import Listing


def make_nl(
    listing_id: str,
    tokens: tuple[str, ...],
    *,
    provider: str = "ebay",
    currency: str = "EUR",
) -> NormalizedListing:
    display = " ".join(tokens) or "untitled"
    listing = Listing(
        listing_id=listing_id,
        title=display,
        provider=provider,
        url=f"https://x/{listing_id}",
        currency=currency,
    )
    return NormalizedListing(source=listing, title=display, title_tokens=tokens, currency=currency)


# --------------------------------------------------------------------------- #
# fingerprint
# --------------------------------------------------------------------------- #
def test_fingerprint_is_deterministic_and_order_independent() -> None:
    a = make_nl("1", ("nvidia", "rtx", "4090"))
    b = make_nl("2", ("4090", "rtx", "nvidia"), provider="donedeal")
    assert listing_fingerprint(a) == listing_fingerprint(b)


def test_fingerprint_differs_for_different_products() -> None:
    a = make_nl("1", ("rtx", "4090"))
    b = make_nl("2", ("rtx", "4080"))
    assert listing_fingerprint(a) != listing_fingerprint(b)


def test_signature_contains_currency_and_condition() -> None:
    sig = signature(make_nl("1", ("rtx", "4090")))
    assert "currency=EUR" in sig
    assert "condition=" in sig


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #
def test_duplicate_group_requires_canonical_in_members() -> None:
    a = make_nl("1", ("rtx", "4090"))
    b = make_nl("2", ("rtx", "4080"))
    with pytest.raises(ValueError, match="canonical listing must be one of"):
        DuplicateGroup(fingerprint="f", canonical=a, members=(b,))


def test_duplicate_group_rejects_empty() -> None:
    a = make_nl("1", ("rtx", "4090"))
    with pytest.raises(ValueError, match="at least one member"):
        DuplicateGroup(fingerprint="f", canonical=a, members=())


def test_duplicate_group_properties() -> None:
    a = make_nl("1", ("rtx", "4090"), provider="ebay")
    b = make_nl("2", ("rtx", "4090"), provider="donedeal")
    group = DuplicateGroup(fingerprint="f", canonical=a, members=(a, b))
    assert group.size == 2
    assert group.is_duplicate
    assert group.providers == ("donedeal", "ebay")


def test_result_rejects_listing_count_mismatch() -> None:
    a = make_nl("1", ("rtx", "4090"))
    group = DuplicateGroup(fingerprint="f", canonical=a, members=(a,))
    with pytest.raises(ValueError, match="listing count mismatch"):
        DeduplicationResult(groups=(group,), total_input=5)


# --------------------------------------------------------------------------- #
# Deduplicator
# --------------------------------------------------------------------------- #
def test_groups_identical_listings_across_providers() -> None:
    a = make_nl("1", ("nvidia", "rtx", "4090"), provider="ebay")
    b = make_nl("2", ("nvidia", "rtx", "4090"), provider="donedeal")
    result = Deduplicator().deduplicate([a, b])
    assert result.total_groups == 1
    assert result.total_input == 2
    assert result.duplicates_removed == 1
    assert result.groups[0].size == 2
    assert result.groups[0].providers == ("donedeal", "ebay")


def test_keeps_different_products_separate() -> None:
    a = make_nl("1", ("rtx", "4090"))
    b = make_nl("2", ("rtx", "4080"))
    result = Deduplicator().deduplicate([a, b])
    assert result.total_groups == 2
    assert result.duplicates_removed == 0


def test_all_listings_preserved() -> None:
    listings = [
        make_nl("1", ("rtx", "4090"), provider="ebay"),
        make_nl("2", ("rtx", "4090"), provider="donedeal"),
        make_nl("3", ("rtx", "4080"), provider="adverts_ie"),
    ]
    result = Deduplicator().deduplicate(listings)
    assert len(result.all_listings) == 3
    assert {nl.listing_id for nl in result.all_listings} == {"1", "2", "3"}


def test_disabled_config_is_no_op() -> None:
    listings = [
        make_nl("1", ("rtx", "4090")),
        make_nl("2", ("rtx", "4090")),
    ]
    result = Deduplicator(DeduplicationConfig(enabled=False)).deduplicate(listings)
    assert result.total_groups == 2
    assert result.duplicates_removed == 0
    assert all(group.size == 1 for group in result.groups)


def test_include_possible_matches_toggle() -> None:
    a = make_nl("1", ("apple", "macbook", "pro"))
    b = make_nl("2", ("apple", "macbook", "air"))
    strict = Deduplicator().deduplicate([a, b])
    assert strict.total_groups == 2
    lenient = Deduplicator(DeduplicationConfig(include_possible_matches=True)).deduplicate([a, b])
    assert lenient.total_groups == 1


def test_canonical_prefers_richest_title() -> None:
    a = make_nl("1", ("rtx", "4090"), provider="ebay")
    b = make_nl("2", ("nvidia", "rtx", "4090", "founders"), provider="donedeal")
    result = Deduplicator().deduplicate([a, b])
    assert result.total_groups == 1
    assert result.groups[0].canonical.listing_id == "2"


def test_canonical_respects_provider_priority() -> None:
    a = make_nl("1", ("rtx", "4090"), provider="ebay")
    b = make_nl("2", ("rtx", "4090"), provider="donedeal")
    cfg = DeduplicationConfig(provider_priority=("donedeal", "ebay"))
    result = Deduplicator(cfg).deduplicate([a, b])
    assert result.groups[0].canonical.provider == "donedeal"


def test_deduplication_is_order_independent() -> None:
    a = make_nl("1", ("rtx", "4090"), provider="ebay")
    b = make_nl("2", ("rtx", "4090"), provider="donedeal")
    c = make_nl("3", ("rtx", "4080"), provider="adverts_ie")
    forward = Deduplicator().deduplicate([a, b, c])
    reverse = Deduplicator().deduplicate([c, b, a])
    assert [g.fingerprint for g in forward.groups] == [g.fingerprint for g in reverse.groups]
    assert [g.canonical.listing_id for g in forward.groups] == [
        g.canonical.listing_id for g in reverse.groups
    ]


def test_empty_input() -> None:
    result = Deduplicator().deduplicate([])
    assert result.total_groups == 0
    assert result.total_input == 0
    assert result.all_listings == ()
