"""Unit tests: Observation admission and source fingerprints."""

from __future__ import annotations

import pytest

from digital_arbitrage.pue.admission import admit_observation, compute_source_fingerprint
from digital_arbitrage.pue.validation import PueValidationError

from .conftest import make_normalized


def test_admit_preserves_raw_title(deterministic_context) -> None:
    listing = make_normalized("  RTX 4090   FE  ")
    obs = admit_observation(listing, deterministic_context)
    assert obs.raw_title == listing.source.title


def test_admit_sets_provider_and_listing_id(deterministic_context) -> None:
    listing = make_normalized("RTX 4090", listing_id="abc", provider="ebay")
    obs = admit_observation(listing, deterministic_context)
    assert obs.provider == "ebay"
    assert obs.provider_listing_id == "abc"


def test_admit_rejects_none_listing(deterministic_context) -> None:
    with pytest.raises(PueValidationError):
        admit_observation(None, deterministic_context)


def test_admit_rejects_missing_source(deterministic_context) -> None:
    class Empty:
        pass

    with pytest.raises(PueValidationError):
        admit_observation(Empty(), deterministic_context)


def test_fingerprint_is_deterministic() -> None:
    fp1 = compute_source_fingerprint(
        provider="p",
        provider_listing_id="1",
        normalized_title="rtx 4090",
        normalized_description=None,
        selected_attributes={},
    )
    fp2 = compute_source_fingerprint(
        provider="p",
        provider_listing_id="1",
        normalized_title="rtx 4090",
        normalized_description=None,
        selected_attributes={},
    )
    assert fp1 == fp2


def test_fingerprint_changes_with_title() -> None:
    fp1 = compute_source_fingerprint(
        provider="p",
        provider_listing_id="1",
        normalized_title="rtx 4090",
        normalized_description=None,
        selected_attributes={},
    )
    fp2 = compute_source_fingerprint(
        provider="p",
        provider_listing_id="1",
        normalized_title="rtx 4080",
        normalized_description=None,
        selected_attributes={},
    )
    assert fp1 != fp2


def test_two_observations_of_same_listing_share_fingerprint(deterministic_context) -> None:
    listing = make_normalized("RTX 4090 Founders Edition")
    obs1 = admit_observation(listing, deterministic_context)
    obs2 = admit_observation(listing, deterministic_context)
    assert obs1.source_fingerprint == obs2.source_fingerprint
    assert obs1.observation_id != obs2.observation_id
