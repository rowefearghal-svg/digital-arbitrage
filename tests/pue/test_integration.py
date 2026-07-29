"""Integration tests: provider-style fixtures, batch semantics, persistence
round trip/reprocessing, and shadow isolation."""

from __future__ import annotations

from pathlib import Path

from digital_arbitrage.classification.classifier import ListingClassifier, build_search_profile
from digital_arbitrage.pipeline.pue_shadow import ShadowConfig, run_pue_shadow
from digital_arbitrage.pue.enums import DecisionType
from digital_arbitrage.pue.orchestration import process_many, process_one
from digital_arbitrage.pue.persistence import PueCaseStore

from .conftest import make_normalized


def test_ebay_style_fixture_exact_identification(deterministic_context, repository) -> None:
    listing = make_normalized(
        "ASUS TUF Gaming GeForce RTX 4090 OC 24GB TUF-RTX4090-O24G - Excellent Condition",
        provider="ebay_browse",
        listing_id="v1|123456789|0",
    )
    record = process_one(listing, deterministic_context, repository=repository)
    assert record.decision.decision_type == DecisionType.IDENTIFIED
    assert record.observation.provider == "ebay_browse"


def test_stockx_style_fixture_partial_identification(deterministic_context, repository) -> None:
    listing = make_normalized(
        "NVIDIA GeForce RTX 4090 Graphics Card", provider="stockx", listing_id="sku-4090-001"
    )
    record = process_one(listing, deterministic_context, repository=repository)
    assert record.decision.decision_type in (
        DecisionType.PARTIALLY_IDENTIFIED,
        DecisionType.IDENTIFIED,
    )


def test_batch_semantics_match_single_case(deterministic_context, repository) -> None:
    titles = ["RTX 4090 water block", "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", "Samsung?"]
    listings = [make_normalized(t) for t in titles]
    batch_results = process_many(listings, deterministic_context, repository=repository)
    assert len(batch_results) == len(titles)
    for record, title in zip(batch_results, titles, strict=True):
        assert record.observation.raw_title == title


def test_persistence_round_trip_and_reprocessing(
    tmp_path: Path, deterministic_context, repository
) -> None:
    listing = make_normalized("RTX 4080 Super Gaming OC")
    record = process_one(listing, deterministic_context, repository=repository)
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        reloaded = store.get_case(record.case_id)
    assert reloaded == record

    # Reprocessing the same listing creates a NEW case (new case_id), not a
    # mutation of the old one - historical records are immutable.
    second_pass = process_one(listing, deterministic_context, repository=repository)
    assert second_pass.case_id != record.case_id
    assert second_pass.observation.source_fingerprint == record.observation.source_fingerprint
    assert second_pass.decision.decision_type == record.decision.decision_type


def test_shadow_isolation_does_not_change_classifier_output() -> None:
    """The existing deterministic classifier's output must be identical
    whether or not the PUE shadow stage also runs (spec 5.3)."""
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    classifier = ListingClassifier()

    without_shadow = classifier.classify(listing, profile)

    config = ShadowConfig(enabled=True)
    shadow_result = run_pue_shadow([listing], config=config)
    with_shadow = classifier.classify(listing, profile)

    assert without_shadow == with_shadow
    assert shadow_result is not None


def test_shadow_disabled_by_default_is_a_no_op() -> None:
    listing = make_normalized("RTX 4090")
    config = ShadowConfig(enabled=False)
    result = run_pue_shadow([listing], config=config)
    assert result == ()


def test_shadow_exception_does_not_propagate(monkeypatch) -> None:
    """A PUE exception in shadow mode must never terminate the pipeline."""
    import digital_arbitrage.pipeline.pue_shadow as shadow_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated PUE failure")

    monkeypatch.setattr(shadow_module, "process_many", _boom)
    listing = make_normalized("RTX 4090")
    config = ShadowConfig(enabled=True)
    result = run_pue_shadow([listing], config=config)
    assert result == ()
