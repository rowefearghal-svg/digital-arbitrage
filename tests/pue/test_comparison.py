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
    return compare_classifier_and_pue(verdict, record, search_profile=profile)


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
    comparison = compare_classifier_and_pue(verdict, record, search_profile=profile)

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
    assert comparison.pue_policy_version == record.decision.policy_version
    assert comparison.pue_knowledge_version == record.decision.knowledge_version
    assert comparison.comparison_schema_version
    assert comparison.comparison_id
    from digital_arbitrage.pue.comparison import compute_search_profile_fingerprint

    assert comparison.classifier_search_profile_fingerprint == (
        compute_search_profile_fingerprint(profile)
    )


def test_compare_does_not_mutate_the_reasoning_record(repository) -> None:
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(
        listing, orchestration.build_default_context(), repository=repository
    )
    before = record.decision.decision_type
    compare_classifier_and_pue(verdict, record, search_profile=profile)
    assert record.decision.decision_type == before  # frozen dataclass; unchanged


def test_compare_two_different_search_profiles_yield_different_fingerprints() -> None:
    """Sprint 2 pre-merge correction item 1: distinct search profiles must
    produce distinct ``classifier_search_profile_fingerprint`` values so
    the same listing/case never silently collapses two different
    comparison contexts into one."""
    comparison_a = _compare("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", query="rtx 4090")
    comparison_b = _compare("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", query="rtx 4080")
    assert comparison_a.classifier_search_profile_fingerprint != (
        comparison_b.classifier_search_profile_fingerprint
    )
    assert comparison_a.comparison_id != comparison_b.comparison_id


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
    """Classifier commits to ACCESSORY ('stand' keyword) while the PUE has
    no notion of a bundled stand and reaches a plain COMPLETE_PRODUCT
    conclusion - both reached a concrete, but different, product-form
    conclusion (unlike REJECTED, which asserts no product form at all -
    see test_category_classifier_declined_pue_classified below)."""
    comparison = _compare("RTX 4090 with GPU stand included")
    assert comparison.category == ComparisonCategory.PRODUCT_FORM_DISAGREEMENT
    assert comparison.product_form_conclusions_agree is False
    assert comparison.classifier_label == "accessory"
    assert comparison.pue_product_form == "complete_product"


def test_category_classifier_declined_pue_classified() -> None:
    """Sprint 2 pre-merge correction item 3: REJECTED is not itself a
    product-form assertion. A classifier REJECTED verdict (its title-
    exclusion path never learned 'box only') against a PUE PACKAGING_ONLY
    conclusion must never be scored as a PRODUCT_FORM_DISAGREEMENT - the
    classifier never asserted an alternative form to disagree with."""
    comparison = _compare("Empty RTX 4090 Founders Edition Box Only")
    assert comparison.classifier_label == "rejected"
    assert comparison.pue_product_form == "packaging_only"
    assert comparison.category == ComparisonCategory.CLASSIFIER_DECLINED_PUE_CLASSIFIED
    assert comparison.product_form_conclusions_agree is None


def test_category_pue_abstained() -> None:
    # "Compatible with RTX 4090" no longer abstains (Sprint 3 final narrow
    # correction to the COMPATIBLE_ITEM decision branch: a compatibility-
    # only listing is now CLASSIFIED, not ABSTAINED) - an empty/whitespace-
    # only title (genuinely zero evidence of any kind) is a still-valid,
    # still-genuinely-abstaining case.
    comparison = _compare("   ")
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
    comparison = compare_classifier_and_pue(verdict, record, search_profile=profile)
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
        "RTX 4090 with GPU stand included",  # PRODUCT_FORM_DISAGREEMENT
        "Empty RTX 4090 Founders Edition Box Only",  # CLASSIFIER_DECLINED_PUE_CLASSIFIED
        "   ",  # PUE_ABSTAINED
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

    assert report.total_cases == 9
    assert report.agreements == 2
    assert report.product_form_disagreements == 1
    assert report.classifier_declined_pue_classified == 1
    assert report.pue_abstentions == 1
    assert report.pue_blocked_direct_comparability == 1
    assert report.pue_broader_identity == 1
    assert report.pue_more_specific_identity == 1
    assert report.other_disagreements == 1
    # Every case must land in exactly one bucket.
    assert (
        report.agreements
        + report.product_form_disagreements
        + report.classifier_declined_pue_classified
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

    assert "Total cases | 9" in markdown
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
def _build_case_and_comparison(title: str, *, query: str = "rtx 4090", repository=None):
    listing = make_normalized(title)
    profile = build_search_profile(query)
    context = orchestration.build_default_context()
    verdict = ListingClassifier().classify(listing, profile)
    record = orchestration.process_one(listing, context, repository=repository)
    comparison = compare_classifier_and_pue(
        verdict, record, search_profile=profile, id_factory=context.id_factory
    )
    return record, comparison


def test_comparison_persists_alongside_case_in_same_database(tmp_path: Path, repository) -> None:
    record, comparison = _build_case_and_comparison(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", repository=repository
    )

    db_path = tmp_path / "pue.db"
    with PueCaseStore(db_path) as store:
        store.save_case(record)
        store.save_comparison(comparison)
        reloaded = store.get_comparison_by_id(comparison.comparison_id)
        for_case = store.get_comparisons_for_case(record.case_id)

    assert reloaded == comparison
    assert for_case == [comparison]
    # Same database file - no second database introduced.
    assert db_path.exists()


def test_save_case_with_comparison_is_transactional(tmp_path: Path, repository) -> None:
    """Both writes commit together, or neither does (Sprint 2 pre-merge
    correction item 2)."""
    record, comparison = _build_case_and_comparison(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case_with_comparison(record, comparison)
        assert store.get_case(record.case_id) == record
        assert store.get_comparisons_for_case(record.case_id) == [comparison]


def test_save_case_with_comparison_rejects_mismatched_case_id(tmp_path: Path, repository) -> None:
    from digital_arbitrage.pue.validation import PueValidationError

    record, comparison = _build_case_and_comparison(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", repository=repository
    )
    other_record, _ = _build_case_and_comparison("RTX 4090 water block", repository=repository)
    with PueCaseStore(tmp_path / "pue.db") as store:
        with pytest.raises(PueValidationError):
            store.save_case_with_comparison(other_record, comparison)


def test_comparison_cannot_reference_a_nonexistent_case_via_public_api(
    tmp_path: Path, repository
) -> None:
    """Sprint 2 pre-merge correction item 2: a comparison cannot be
    persisted for a case that was never (or not yet) saved."""
    from digital_arbitrage.pue.validation import PueValidationError

    _, comparison = _build_case_and_comparison(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        with pytest.raises(PueValidationError):
            store.save_comparison(comparison)  # record.case_id was never save_case'd


def test_foreign_keys_pragma_is_actually_enabled(tmp_path: Path, repository) -> None:
    """Prove ``PRAGMA foreign_keys = ON`` is really active on the
    connection, not merely declared in the DDL (Sprint 2 pre-merge
    correction item 2): a raw INSERT that bypasses the application-level
    check must be rejected by SQLite itself."""
    import sqlite3

    record, comparison = _build_case_and_comparison(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        assert store._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(
                "INSERT INTO pue_classifier_comparisons ("
                "comparison_id, case_id, provider, provider_listing_id, source_fingerprint, "
                "classifier_search_profile_fingerprint, classifier_capability_version, "
                "pue_capability_version, pue_policy_version, pue_knowledge_version, "
                "comparison_schema_version, category, comparison_json, created_at"
                ") VALUES (?, 'no-such-case', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    comparison.comparison_id,
                    comparison.provider,
                    comparison.provider_listing_id,
                    comparison.source_fingerprint,
                    comparison.classifier_search_profile_fingerprint,
                    comparison.classifier_capability_version,
                    comparison.pue_capability_version,
                    comparison.pue_policy_version,
                    comparison.pue_knowledge_version,
                    comparison.comparison_schema_version,
                    comparison.category.value,
                    comparison_to_json(comparison),
                    "2026-01-01T00:00:00",
                ),
            )


def test_duplicate_comparison_id_is_rejected(tmp_path: Path, repository) -> None:
    from digital_arbitrage.pue.validation import PueValidationError

    record, comparison = _build_case_and_comparison(
        "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", repository=repository
    )

    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        store.save_comparison(comparison)
        with pytest.raises(PueValidationError):
            store.save_comparison(comparison)


def test_repeated_processing_does_not_duplicate_comparison_records(tmp_path: Path) -> None:
    """Same source fingerprint + same full classifier/PUE version and
    search-profile key, processed twice, must not accumulate two
    comparison records (mirrors PueCaseStore.save_case's equivalent-record
    detection)."""
    from digital_arbitrage.pue.validation import PueValidationError

    db_path = tmp_path / "pue.db"
    with PueCaseStore(db_path) as store:
        for _ in range(2):
            record, comparison = _build_case_and_comparison("RTX 4090 water block")
            try:
                store.save_case_with_comparison(record, comparison)
            except PueValidationError:
                continue

        all_comparisons = store.list_comparisons()

    assert len(all_comparisons) == 1


def test_comparison_replay_may_retain_additional_record(tmp_path: Path) -> None:
    from digital_arbitrage.pue.validation import PueValidationError

    db_path = tmp_path / "pue.db"
    with PueCaseStore(db_path) as store:
        record1, comparison1 = _build_case_and_comparison("RTX 4090 water block")
        store.save_case_with_comparison(record1, comparison1)

        record2, comparison2 = _build_case_and_comparison("RTX 4090 water block")
        store.save_case_with_comparison(record2, comparison2, replay=True)

        assert len(store.list_comparisons()) == 2

        # Without replay=True, saving an equivalent comparison again raises
        # (against its own, already-persisted case).
        record3, comparison3 = _build_case_and_comparison("RTX 4090 water block")
        store.save_case(record3, replay=True)
        with pytest.raises(PueValidationError):
            store.save_comparison(comparison3)


# --------------------------------------------------------------------------- #
# Migration / backfill behaviour (Sprint 2 pre-merge correction item 2)
# --------------------------------------------------------------------------- #
def test_backfill_comparison_onto_existing_case_with_none(tmp_path: Path) -> None:
    """A pre-existing case (e.g. a Sprint 1 case, or any case saved without
    ``save_case_with_comparison``) that has no comparison yet must still be
    able to receive one via a direct :meth:`save_comparison` call."""
    db_path = tmp_path / "pue.db"
    record, comparison = _build_case_and_comparison("RTX 4090 water block")
    with PueCaseStore(db_path) as store:
        store.save_case(record)  # Sprint-1-style: case only, no comparison.
        assert store.get_comparisons_for_case(record.case_id) == []

        store.save_comparison(comparison)
        assert store.get_comparisons_for_case(record.case_id) == [comparison]


def test_backfill_repeated_identical_processing_still_yields_one_comparison(
    tmp_path: Path,
) -> None:
    from digital_arbitrage.pue.validation import PueValidationError

    db_path = tmp_path / "pue.db"
    record1, comparison1 = _build_case_and_comparison("RTX 4090 water block")
    with PueCaseStore(db_path) as store:
        store.save_case(record1)  # simulate a pre-existing, comparison-less case
        store.save_comparison(comparison1)

        # Re-processing the identical listing produces an equivalent (but
        # differently-case-id'd) record/comparison; save_case rejects the
        # duplicate case, and the already-backfilled comparison must not
        # be duplicated either.
        record2, comparison2 = _build_case_and_comparison("RTX 4090 water block")
        with pytest.raises(PueValidationError):
            store.save_case(record2)
        equivalent = store.find_equivalent(
            source_fingerprint=record2.observation.source_fingerprint,
            capability_version=record2.decision.capability_version,
            policy_version=record2.decision.policy_version,
            knowledge_version=record2.decision.knowledge_version,
        )
        assert equivalent is not None and equivalent.case_id == record1.case_id
        assert store.get_comparisons_for_case(record1.case_id) == [comparison1]


def test_backfill_different_search_profiles_for_same_listing(tmp_path: Path) -> None:
    """A comparison-less pre-existing case must be able to receive
    comparisons for two different search profiles, not just one."""
    db_path = tmp_path / "pue.db"
    with PueCaseStore(db_path) as store:
        record, comparison_a = _build_case_and_comparison("RTX 4090 water block", query="rtx 4090")
        store.save_case(record)
        store.save_comparison(comparison_a)

        listing = make_normalized("RTX 4090 water block")
        profile_b = build_search_profile("rtx 4080")
        verdict_b = ListingClassifier().classify(listing, profile_b)
        comparison_b = compare_classifier_and_pue(verdict_b, record, search_profile=profile_b)
        store.save_comparison(comparison_b)

        assert len(store.get_comparisons_for_case(record.case_id)) == 2


def test_backfill_changed_pue_policy_version_is_not_equivalent(tmp_path: Path) -> None:
    """A comparison computed under a different PUE policy version must not
    be treated as equivalent to one already persisted under the original
    policy version, even for the same case/listing."""
    from dataclasses import replace as dc_replace

    db_path = tmp_path / "pue.db"
    record, comparison = _build_case_and_comparison("RTX 4090 water block")
    with PueCaseStore(db_path) as store:
        store.save_case(record)
        store.save_comparison(comparison)

        changed_policy_comparison = dc_replace(
            comparison, comparison_id="different-policy-id", pue_policy_version="policy-9.9.9"
        )
        store.save_comparison(changed_policy_comparison)
        assert len(store.get_comparisons_for_case(record.case_id)) == 2


def test_backfill_changed_knowledge_version_is_not_equivalent(tmp_path: Path) -> None:
    from dataclasses import replace as dc_replace

    db_path = tmp_path / "pue.db"
    record, comparison = _build_case_and_comparison("RTX 4090 water block")
    with PueCaseStore(db_path) as store:
        store.save_case(record)
        store.save_comparison(comparison)

        changed_knowledge_comparison = dc_replace(
            comparison,
            comparison_id="different-knowledge-id",
            pue_knowledge_version="gpu-catalogue-9.9.9",
        )
        store.save_comparison(changed_knowledge_comparison)
        assert len(store.get_comparisons_for_case(record.case_id)) == 2


def test_backfill_replay_mode_never_backfills(tmp_path: Path) -> None:
    """Replay/evaluation runs intentionally retain independent records and
    must not participate in the backfill-onto-existing-case behaviour."""
    from digital_arbitrage.pipeline.pue_shadow import (
        PueShadowCaseResult,
        ShadowConfig,
        _persist_case_result,
    )

    db_path = tmp_path / "pue.db"
    record1, comparison1 = _build_case_and_comparison("RTX 4090 water block")
    record2, comparison2 = _build_case_and_comparison("RTX 4090 water block")
    context = orchestration.build_default_context()

    with PueCaseStore(db_path) as store:
        store.save_case(record1)
        store.save_comparison(comparison1)

        replay_config = ShadowConfig(enabled=True, db_path=db_path, replay=True)
        case_result = PueShadowCaseResult(
            reasoning_record=record2,
            result=orchestration.publish_result(record2),
            comparison=comparison2,
        )
        _persist_case_result(store, case_result, context, replay_config)

        # A brand-new case_id was inserted (replay never dedupes cases),
        # each with its own single comparison - no backfill occurred.
        assert store.get_case(record2.case_id) == record2
        assert store.get_comparisons_for_case(record1.case_id) == [comparison1]
        assert store.get_comparisons_for_case(record2.case_id) == [comparison2]
