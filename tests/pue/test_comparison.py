"""Classifier/PUE comparison contract, categories, report rendering, and
persistence idempotency (Sprint 2, Task 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from digital_arbitrage.classification.classifier import ListingClassifier, build_search_profile
from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.comparison import (
    ClassifierPueComparison,
    ComparisonCategory,
    build_comparison_report,
    compare_classifier_and_pue,
    comparison_from_dict,
    comparison_from_json,
    comparison_to_dict,
    comparison_to_json,
    render_report_json,
    render_report_markdown,
)
from digital_arbitrage.pue.persistence import PueCaseStore

from .conftest import make_normalized


def _compare(title: str, *, query: str = "rtx 4090", repository=None) -> ClassifierPueComparison:
    listing = make_normalized(title)
    profile = build_search_profile(query)
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(
        listing, orchestration.build_default_context(), repository=repository
    )
    return compare_classifier_and_pue(verdict, record)


# --------------------------------------------------------------------------- #
# Pure function / contract shape
# --------------------------------------------------------------------------- #
def test_compare_is_pure_and_does_not_reclassify(repository) -> None:
    """The comparison function must not call the classifier or the PUE
    itself - it only combines two already-computed outputs."""
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(
        listing, orchestration.build_default_context(), repository=repository
    )
    comparison = compare_classifier_and_pue(verdict, record)

    assert comparison.case_id == record.case_id
    assert comparison.provider == record.observation.provider
    assert comparison.provider_listing_id == record.observation.provider_listing_id
    assert comparison.source_fingerprint == record.observation.source_fingerprint
    assert comparison.classifier_label == verdict.classification.value
    assert comparison.classifier_score == verdict.match_confidence
    assert comparison.classifier_reason == verdict.reason
    assert comparison.pue_decision_type == record.decision.decision_type.value
    assert comparison.pue_identification_level == record.decision.identification_level.value
    assert comparison.pue_product_form == record.decision.product_form.value
    assert comparison.pue_comparability_status == record.decision.comparability_status.value
    assert comparison.pue_capability_version == record.decision.capability_version


def test_compare_does_not_mutate_the_reasoning_record(repository) -> None:
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(
        listing, orchestration.build_default_context(), repository=repository
    )
    before = record.decision.decision_type
    compare_classifier_and_pue(verdict, record)
    assert record.decision.decision_type == before  # frozen dataclass; unchanged


# --------------------------------------------------------------------------- #
# Categories: one representative, empirically-verified case per category.
# None of these assert correctness - only the documented, observable
# category meaning (module docstring in pue.comparison).
# --------------------------------------------------------------------------- #
def test_category_agreement_both_reject_non_gpu_listing() -> None:
    """Classifier REJECTED and PUE OUTSIDE_SUPPORTED_DOMAIN: both decline
    the listing as not a relevant match - an observed agreement."""
    comparison = _compare("Samsung?")
    assert comparison.category == ComparisonCategory.AGREEMENT
    assert comparison.classifier_label == "rejected"
    assert comparison.pue_decision_type == "outside_supported_domain"


def test_category_agreement_coarse_accessory_match() -> None:
    """Classifier and PUE both agree this is a non-complete-product item,
    at the same (non-specific) level of granularity."""
    comparison = _compare("RTX 4090 Waterblock Full Cover GPU Cooling Block")
    assert comparison.category == ComparisonCategory.AGREEMENT
    assert comparison.product_form_conclusions_agree is True


def test_category_product_form_disagreement() -> None:
    """Classifier REJECTED (its title-exclusion path never learned
    'box only') while PUE explicitly classifies PACKAGING_ONLY - both
    reached a concrete, but different, conclusion."""
    comparison = _compare("Empty RTX 4090 Founders Edition Box Only")
    assert comparison.category == ComparisonCategory.PRODUCT_FORM_DISAGREEMENT
    assert comparison.product_form_conclusions_agree is False


def test_category_pue_abstained() -> None:
    comparison = _compare("Compatible with RTX 4090")
    assert comparison.category == ComparisonCategory.PUE_ABSTAINED
    assert comparison.pue_abstained is True
    assert comparison.pue_abstention_reason is not None


def test_category_pue_broader_identity() -> None:
    """Classifier commits to ACCESSORY; PUE declines to commit at all
    (AMBIGUOUS) because a genuinely ambiguous bundle-vs-component
    interpretation remains open - PUE's conclusion is broader/less
    committal than the classifier's."""
    comparison = _compare("ASUS RTX 4090 with EK water block")
    assert comparison.category == ComparisonCategory.PUE_BROADER_IDENTITY
    assert comparison.identity_breadth == "broader"


def test_category_pue_more_specific_identity() -> None:
    """Classifier only says COMPLETE_PRODUCT; PUE reaches a family/exact
    catalogue identity - genuine added specificity."""
    comparison = _compare("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    assert comparison.category == ComparisonCategory.PUE_MORE_SPECIFIC_IDENTITY
    assert comparison.identity_breadth == "more_specific"


def test_category_pue_blocked_direct_comparability() -> None:
    """Classifier says COMPLETE_PRODUCT (a bundle title still contains all
    required tokens); PUE recognizes the bundle and blocks direct
    comparability - exactly the safety property Sprint 2 exists to prove."""
    comparison = _compare("RTX 4090 + PSU bundle")
    assert comparison.category == ComparisonCategory.PUE_BLOCKED_DIRECT_COMPARABILITY
    assert comparison.classifier_complete_product_pue_blocked is True
    assert comparison.classifier_label == "complete_product"


def test_category_other_disagreement_classifier_inconclusive() -> None:
    """Classifier reaches UNKNOWN (partial required-term match against the
    query profile) while PUE reaches a concrete product-type conclusion -
    an observable difference that is neither agreement nor a genuine
    product-form contradiction (the classifier asserted nothing to
    contradict)."""
    comparison = _compare("RTX 3060", query="rtx 4090")
    assert comparison.category == ComparisonCategory.OTHER_DISAGREEMENT
    assert comparison.classifier_label == "unknown"
    assert comparison.product_form_conclusions_agree is None


def test_category_other_disagreement_processing_failed(deterministic_context) -> None:
    """A PROCESSING_FAILED case carries no product-understanding signal;
    it must never be silently treated as PUE_ABSTAINED or an agreement."""
    malformed_listing = object()
    record = orchestration.process_one(malformed_listing, deterministic_context)
    listing = make_normalized("Samsung?")
    profile = build_search_profile("rtx 4090")
    verdict = ListingClassifier().classify(listing, profile)
    comparison = compare_classifier_and_pue(verdict, record)
    assert comparison.category == ComparisonCategory.OTHER_DISAGREEMENT
    assert comparison.pue_decision_type == "processing_failed"


def test_no_category_asserts_correctness_labels() -> None:
    """Regression: category names must never imply a correctness verdict."""
    forbidden_substrings = ("corrected", "was_right", "was_wrong", "classifier_error", "pue_error")
    for category in ComparisonCategory:
        lowered = category.value.lower()
        assert not any(bad in lowered for bad in forbidden_substrings)


# --------------------------------------------------------------------------- #
# Serialization round trip
# --------------------------------------------------------------------------- #
def test_comparison_json_round_trip() -> None:
    comparison = _compare("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    payload = comparison_to_json(comparison)
    restored = comparison_from_json(payload)
    assert restored == comparison


def test_comparison_dict_round_trip() -> None:
    comparison = _compare("RTX 4090 + PSU bundle")
    restored = comparison_from_dict(comparison_to_dict(comparison))
    assert restored == comparison


# --------------------------------------------------------------------------- #
# Deterministic aggregate report + rendering
# --------------------------------------------------------------------------- #
def _sample_comparisons() -> tuple[ClassifierPueComparison, ...]:
    titles = [
        "Samsung?",  # AGREEMENT
        "RTX 4090 Waterblock Full Cover GPU Cooling Block",  # AGREEMENT
        "Empty RTX 4090 Founders Edition Box Only",  # PRODUCT_FORM_DISAGREEMENT
        "Compatible with RTX 4090",  # PUE_ABSTAINED
        "ASUS RTX 4090 with EK water block",  # PUE_BROADER_IDENTITY
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G",  # PUE_MORE_SPECIFIC_IDENTITY
        "RTX 4090 + PSU bundle",  # PUE_BLOCKED_DIRECT_COMPARABILITY
        "RTX 3060",  # OTHER_DISAGREEMENT
    ]
    return tuple(_compare(t) for t in titles)


def test_build_comparison_report_counts_are_deterministic_and_exhaustive() -> None:
    comparisons = _sample_comparisons()
    fixed_clock = lambda: __import__("datetime").datetime(2026, 8, 1)  # noqa: E731
    report = build_comparison_report(comparisons, clock=fixed_clock)

    assert report.total_cases == 8
    assert report.agreements == 2
    assert report.product_form_disagreements == 1
    assert report.pue_abstentions == 1
    assert report.pue_blocked_direct_comparability == 1
    assert report.pue_broader_identity == 1
    assert report.pue_more_specific_identity == 1
    assert report.other_disagreements == 1
    # Every case must land in exactly one bucket.
    assert (
        report.agreements
        + report.product_form_disagreements
        + report.pue_abstentions
        + report.pue_blocked_direct_comparability
        + report.pue_broader_identity
        + report.pue_more_specific_identity
        + report.other_disagreements
        == report.total_cases
    )


def test_build_comparison_report_is_deterministic_given_same_inputs() -> None:
    comparisons = _sample_comparisons()
    fixed_clock = lambda: __import__("datetime").datetime(2026, 8, 1)  # noqa: E731
    first = build_comparison_report(comparisons, clock=fixed_clock)
    second = build_comparison_report(comparisons, clock=fixed_clock)
    assert first == second


def test_render_report_markdown_contains_counts_and_no_correctness_language() -> None:
    comparisons = _sample_comparisons()
    report = build_comparison_report(comparisons)
    markdown = render_report_markdown(report, comparisons)

    assert "Total cases | 8" in markdown
    assert "pue_blocked_direct_comparability" in markdown or "PUE blocked" in markdown
    for forbidden in ("corrected", "was right", "was wrong"):
        assert forbidden not in markdown.lower()


def test_render_report_json_round_trips_counts() -> None:
    import json

    comparisons = _sample_comparisons()
    report = build_comparison_report(comparisons)
    payload = json.loads(render_report_json(report))
    assert payload["total_cases"] == report.total_cases
    assert payload["agreements"] == report.agreements
    assert payload["pue_blocked_direct_comparability"] == report.pue_blocked_direct_comparability


# --------------------------------------------------------------------------- #
# Persistence + idempotency (same SQLite database as pue_cases)
# --------------------------------------------------------------------------- #
def test_comparison_persists_alongside_case_in_same_database(tmp_path: Path, repository) -> None:
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(
        listing, orchestration.build_default_context(), repository=repository
    )
    comparison = compare_classifier_and_pue(verdict, record)

    db_path = tmp_path / "pue.db"
    with PueCaseStore(db_path) as store:
        store.save_case(record)
        store.save_comparison(comparison)
        reloaded = store.get_comparison(record.case_id)

    assert reloaded == comparison
    # Same database file - no second database introduced.
    assert db_path.exists()


def test_duplicate_comparison_for_same_case_id_is_rejected(tmp_path: Path, repository) -> None:
    from digital_arbitrage.pue.validation import PueValidationError

    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(
        listing, orchestration.build_default_context(), repository=repository
    )
    comparison = compare_classifier_and_pue(verdict, record)

    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        store.save_comparison(comparison)
        with pytest.raises(PueValidationError):
            store.save_comparison(comparison)


def test_repeated_processing_does_not_duplicate_comparison_records(tmp_path: Path) -> None:
    """Same source fingerprint + same classifier/PUE versions, processed
    twice, must not accumulate two comparison records (mirrors
    PueCaseStore.save_case's equivalent-record detection)."""
    from digital_arbitrage.pue.validation import PueValidationError

    db_path = tmp_path / "pue.db"
    listing1 = make_normalized("RTX 4090 water block")
    listing2 = make_normalized("RTX 4090 water block")
    profile = build_search_profile("rtx 4090")
    classifier = ListingClassifier()

    with PueCaseStore(db_path) as store:
        for listing in (listing1, listing2):
            verdict = classifier.classify(listing, profile)
            record = orchestration.process_one(listing, orchestration.build_default_context())
            comparison = compare_classifier_and_pue(verdict, record)
            try:
                store.save_case(record)
            except PueValidationError:
                continue
            try:
                store.save_comparison(comparison)
            except PueValidationError:
                continue

        all_comparisons = store.list_comparisons()

    assert len(all_comparisons) == 1


def test_comparison_replay_may_retain_additional_record(tmp_path: Path) -> None:
    from digital_arbitrage.pue.validation import PueValidationError

    db_path = tmp_path / "pue.db"
    listing1 = make_normalized("RTX 4090 water block")
    listing2 = make_normalized("RTX 4090 water block")
    profile = build_search_profile("rtx 4090")
    classifier = ListingClassifier()

    with PueCaseStore(db_path) as store:
        verdict1 = classifier.classify(listing1, profile)
        record1 = orchestration.process_one(listing1, orchestration.build_default_context())
        comparison1 = compare_classifier_and_pue(verdict1, record1)
        store.save_case(record1)
        store.save_comparison(comparison1)

        verdict2 = classifier.classify(listing2, profile)
        record2 = orchestration.process_one(listing2, orchestration.build_default_context())
        comparison2 = compare_classifier_and_pue(verdict2, record2)
        store.save_case(record2, replay=True)
        store.save_comparison(comparison2, replay=True)

        assert len(store.list_comparisons()) == 2

        # Without replay=True, saving an equivalent comparison again raises.
        with pytest.raises(PueValidationError):
            store.save_comparison(
                compare_classifier_and_pue(
                    classifier.classify(make_normalized("RTX 4090 water block"), profile),
                    orchestration.process_one(
                        make_normalized("RTX 4090 water block"),
                        orchestration.build_default_context(),
                    ),
                )
            )
