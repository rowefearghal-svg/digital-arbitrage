"""ProductUnderstandingResult publication tests (Sprint 2, Task 2):
field-by-field coverage of ``publish_result`` and its wiring into the real
shadow execution path."""

from __future__ import annotations

from pathlib import Path

from digital_arbitrage.classification.classifier import ListingClassifier, build_search_profile
from digital_arbitrage.pipeline.pue_shadow import PueShadowCaseResult, ShadowConfig, run_pue_shadow
from digital_arbitrage.pue.enums import DecisionType
from digital_arbitrage.pue.orchestration import build_default_context, process_one, publish_result
from digital_arbitrage.pue.persistence import PueCaseStore

from .conftest import make_normalized


def test_publish_result_exact_identification_fields(repository) -> None:
    context = build_default_context()
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    record = process_one(listing, context, repository=repository)
    result = publish_result(record)

    decision = record.decision
    assert decision.decision_type == DecisionType.IDENTIFIED

    # IDs.
    assert result.case_id == record.case_id
    assert result.observation_id == record.observation.observation_id
    assert result.decision_id == decision.decision_id
    assert result.reasoning_record_ref == record.case_id

    # Status / identification level / product form.
    assert result.status == decision.decision_type
    assert result.identification_level == decision.identification_level
    assert result.product_form == decision.product_form
    assert result.product_type == decision.product_type

    # Catalogue product ID resolved from the selected Candidate.
    expected_catalogue_id = next(
        c.catalogue_product_id
        for c in record.candidates
        if c.candidate_instance_id == decision.selected_candidate_instance_id
    )
    assert result.catalogue_product_id == expected_catalogue_id

    # Identity mapping.
    assert result.identity["brand"] == decision.identified_brand
    assert result.identity["family"] == decision.identified_family
    assert result.identity["model"] == decision.identified_model
    assert result.identity["variant"] == decision.identified_variant

    # Comparability / unresolved fields / review recommendation.
    assert result.comparability_status == decision.comparability_status
    assert result.unresolved_fields == decision.unresolved_fields
    assert result.review_recommended == decision.review_recommended

    # Explanation summary.
    assert result.explanation_summary == record.explanation.summary
    assert result.explanation_summary != ""

    # Schema version.
    assert result.result_schema_version == record.schema_version


def test_publish_result_catalogue_product_id_is_none_without_a_selection(
    repository,
) -> None:
    """A CLASSIFIED/PARTIALLY_IDENTIFIED/ABSTAINED Decision with no selected
    Candidate must publish ``catalogue_product_id=None``, never a guess."""
    context = build_default_context()
    listing = make_normalized("NVIDIA RTX 4090")
    record = process_one(listing, context, repository=repository)
    assert record.decision.selected_candidate_instance_id is None

    result = publish_result(record)
    assert result.catalogue_product_id is None
    assert result.identity["family"] == "rtx 4090"


def test_publish_result_abstained_case_has_no_identity_claims(repository) -> None:
    context = build_default_context()
    # "Compatible with RTX 4090" no longer abstains (Sprint 3 final narrow
    # correction to the COMPATIBLE_ITEM decision branch: a compatibility-
    # only listing is now CLASSIFIED, not ABSTAINED) - an empty/whitespace-
    # only title (genuinely zero evidence of any kind) is a still-valid,
    # still-genuinely-abstaining case.
    listing = make_normalized("   ")
    record = process_one(listing, context, repository=repository)
    assert record.decision.decision_type == DecisionType.ABSTAINED

    result = publish_result(record)
    assert result.status == DecisionType.ABSTAINED
    assert result.catalogue_product_id is None
    assert result.identity["brand"] is None
    assert result.identity["family"] is None
    assert result.review_recommended is True


# --------------------------------------------------------------------------- #
# Wired into the real shadow path (Task 2)
# --------------------------------------------------------------------------- #
def test_shadow_path_exposes_reasoning_record_result_and_comparison(
    tmp_path: Path,
) -> None:
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    ListingClassifier().classify(listing, profile)  # sets listing.classification

    db_path = tmp_path / "shadow.db"
    config = ShadowConfig(enabled=True, db_path=db_path)
    case_results = run_pue_shadow([listing], config=config, search_profile=profile)

    assert len(case_results) == 1
    case_result = case_results[0]
    assert isinstance(case_result, PueShadowCaseResult)

    assert case_result.reasoning_record.case_id == case_result.result.case_id
    assert case_result.result.decision_id == case_result.reasoning_record.decision.decision_id
    assert case_result.comparison is not None
    assert case_result.comparison.case_id == case_result.reasoning_record.case_id

    # The published result and the comparison are derived from - not
    # independent of - the same persisted ReasoningRecord.
    with PueCaseStore(db_path) as store:
        persisted = store.get_case(case_result.reasoning_record.case_id)
        persisted_comparisons = store.get_comparisons_for_case(case_result.reasoning_record.case_id)
    assert persisted == case_result.reasoning_record
    assert persisted_comparisons == [case_result.comparison]


def test_shadow_path_comparison_is_none_without_prior_classification(
    tmp_path: Path,
) -> None:
    """A listing that was never classified before shadow mode ran (no
    ``.classification`` set) must still produce a ReasoningRecord and a
    ProductUnderstandingResult, with ``comparison=None`` rather than an
    error - the classifier is never invoked from within shadow mode."""
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    assert listing.classification is None

    profile = build_search_profile("rtx 4090")
    config = ShadowConfig(enabled=True, db_path=tmp_path / "shadow.db")
    case_results = run_pue_shadow([listing], config=config, search_profile=profile)

    assert len(case_results) == 1
    assert case_results[0].comparison is None
    assert case_results[0].result is not None


def test_shadow_path_comparison_is_none_without_a_search_profile(tmp_path: Path) -> None:
    """Even a classified listing must not produce a comparison when no
    search profile is supplied - the classifier's verdict is meaningless
    without knowing what it was matched against (Sprint 2 pre-merge
    correction item 1)."""
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    ListingClassifier().classify(listing, profile)

    config = ShadowConfig(enabled=True, db_path=tmp_path / "shadow.db")
    case_results = run_pue_shadow([listing], config=config)  # no search_profile

    assert len(case_results) == 1
    assert case_results[0].comparison is None


def test_shadow_path_comparison_is_none_for_processing_failed_case(
    tmp_path: Path, monkeypatch
) -> None:
    """A PROCESSING_FAILED case must never receive a fabricated comparison
    record, even if a classifier verdict happens to be present."""
    import digital_arbitrage.pipeline.pue_shadow as shadow_module
    from digital_arbitrage.pue.enums import ProcessingFailureCategory
    from digital_arbitrage.pue.orchestration import _failure_record

    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    profile = build_search_profile("rtx 4090")
    ListingClassifier().classify(listing, profile)

    def _fake_process_many(listings, context, *, policy=None):
        return tuple(
            _failure_record(item, context, ProcessingFailureCategory.UNEXPECTED_EXCEPTION, "boom")
            for item in listings
        )

    monkeypatch.setattr(shadow_module, "process_many", _fake_process_many)
    config = ShadowConfig(enabled=True, db_path=tmp_path / "shadow.db")
    case_results = run_pue_shadow([listing], config=config, search_profile=profile)

    assert len(case_results) == 1
    assert case_results[0].reasoning_record.decision.decision_type == DecisionType.PROCESSING_FAILED
    assert case_results[0].comparison is None


def test_shadow_path_same_case_two_search_profiles_yield_distinct_comparisons(
    tmp_path: Path,
) -> None:
    """Sprint 2 pre-merge correction item 1: the same PUE case classified
    under two different search profiles must retain two distinct,
    independently persisted comparison records - never silently
    deduplicated into one merely because ``pue_capability_version`` is
    unchanged. Proven directly at the persistence layer against one real,
    already-persisted case, isolating this from case-level dedup."""
    from digital_arbitrage.pue.comparison import compare_classifier_and_pue
    from digital_arbitrage.pue.orchestration import process_one

    context = build_default_context()
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    record = process_one(listing, context)

    profile_4090 = build_search_profile("rtx 4090")
    profile_4080 = build_search_profile("rtx 4080")
    classifier = ListingClassifier()
    verdict_4090 = classifier.classify(listing, profile_4090)
    verdict_4080 = classifier.classify(listing, profile_4080)

    comparison_4090 = compare_classifier_and_pue(
        verdict_4090, record, search_profile=profile_4090, id_factory=context.id_factory
    )
    comparison_4080 = compare_classifier_and_pue(
        verdict_4080, record, search_profile=profile_4080, id_factory=context.id_factory
    )
    assert comparison_4090.classifier_search_profile_fingerprint != (
        comparison_4080.classifier_search_profile_fingerprint
    )

    db_path = tmp_path / "shadow.db"
    with PueCaseStore(db_path) as store:
        store.save_case(record)
        store.save_comparison(comparison_4090)
        # Must NOT be rejected as a duplicate/equivalent comparison, even
        # though it targets the same case_id, same source_fingerprint, and
        # the same classifier/PUE capability versions - only the search
        # profile differs, and that alone is enough to make it a distinct
        # comparison (replay=False; no special-casing needed).
        store.save_comparison(comparison_4080)

        persisted = store.get_comparisons_for_case(record.case_id)

    assert len(persisted) == 2
    assert {c.comparison_id for c in persisted} == {
        comparison_4090.comparison_id,
        comparison_4080.comparison_id,
    }
