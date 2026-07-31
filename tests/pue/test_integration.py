"""Integration tests: provider-style fixtures, batch semantics, persistence
round trip/reprocessing, and shadow isolation."""

from __future__ import annotations

from pathlib import Path

from digital_arbitrage.classification.classifier import ListingClassifier, build_search_profile
from digital_arbitrage.pipeline.pipeline import ArbitragePipeline, PipelineConfig
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
    shadow_result = run_pue_shadow([listing], config=config, search_profile=profile)
    with_shadow = classifier.classify(listing, profile)

    assert without_shadow == with_shadow
    assert len(shadow_result) == 1
    # The classifier ran exactly the two times above (before and after
    # shadow execution) - shadow mode itself never re-invokes it - yet a
    # comparison record is still produced, because it reuses the
    # already-set ``listing.classification`` from the first call.
    assert shadow_result[0].comparison is not None
    assert shadow_result[0].comparison.classifier_label == without_shadow.classification.value


def test_shadow_custom_policy_version_is_recorded_end_to_end(tmp_path: Path) -> None:
    """A caller-injected DecisionPolicy with a custom ``policy_version``
    (e.g. via ShadowConfig.policy) must be reflected in the resulting
    Decision, the persisted DB row, and the equivalent-record key - not
    silently replaced by the ProcessingContext's static default (pre-merge
    correction)."""
    from digital_arbitrage.pue.policies import DecisionPolicy

    custom_policy = DecisionPolicy(policy_version="custom-policy-9.9.9")
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    db_path = tmp_path / "shadow.db"
    config = ShadowConfig(enabled=True, db_path=db_path, policy=custom_policy)

    case_results = run_pue_shadow([listing], config=config)
    assert len(case_results) == 1
    record = case_results[0].reasoning_record
    assert record.decision.policy_version == "custom-policy-9.9.9"

    with PueCaseStore(db_path) as store:
        row = store._conn.execute(
            "SELECT policy_version FROM pue_cases WHERE case_id = ?", (record.case_id,)
        ).fetchone()
        assert row["policy_version"] == "custom-policy-9.9.9"

        equivalent = store.find_equivalent(
            source_fingerprint=record.observation.source_fingerprint,
            capability_version=record.decision.capability_version,
            policy_version="custom-policy-9.9.9",
            knowledge_version=record.decision.knowledge_version,
        )
        assert equivalent is not None
        assert equivalent.case_id == record.case_id

        # The default policy version never matches this custom-policy run.
        assert (
            store.find_equivalent(
                source_fingerprint=record.observation.source_fingerprint,
                capability_version=record.decision.capability_version,
                policy_version="gpu-policy-0.1.0",
                knowledge_version=record.decision.knowledge_version,
            )
            is None
        )


def test_repeated_shadow_run_avoids_duplicate_completed_records(tmp_path: Path) -> None:
    """Running shadow mode twice over the identical listing must not
    accumulate a second completed record for the same source_fingerprint
    (normal, non-replay processing; see PueCaseStore.save_case)."""
    listing = make_normalized("RTX 4090 water block")
    db_path = tmp_path / "shadow.db"
    config = ShadowConfig(enabled=True, db_path=db_path)

    first_run = run_pue_shadow([listing], config=config)
    second_run = run_pue_shadow([listing], config=config)
    assert len(first_run) == 1
    assert len(second_run) == 1
    first_record = first_run[0].reasoning_record
    second_record = second_run[0].reasoning_record
    assert first_record.case_id != second_record.case_id

    with PueCaseStore(db_path) as store:
        persisted = store.find_by_fingerprint(first_record.observation.source_fingerprint)
    assert len(persisted) == 1
    assert persisted[0].case_id == first_record.case_id


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


def test_arbitrage_pipeline_analyze_identical_with_shadow_enabled(tmp_path: Path) -> None:
    """A real end-to-end ArbitragePipeline.analyze() call must return an
    identical PipelineResult whether PUE shadow mode is disabled or enabled
    (spec 5.3): the PUE must never influence deduplication, pricing,
    opportunity analysis, or scoring. Uses the default mock providers (no
    network) for a fully deterministic comparison."""
    query = "rtx 4090"

    disabled = ArbitragePipeline(PipelineConfig(pue_shadow_config=None)).analyze(query)

    shadow_db = tmp_path / "shadow.db"
    enabled_pipeline = ArbitragePipeline(
        PipelineConfig(pue_shadow_config=ShadowConfig(enabled=True, db_path=shadow_db))
    )
    enabled = enabled_pipeline.analyze(query)

    assert disabled.query == enabled.query
    assert disabled.total_listings_scanned == enabled.total_listings_scanned
    assert disabled.total_groups == enabled.total_groups
    assert len(disabled.items) == len(enabled.items)
    for a, b in zip(disabled.items, enabled.items, strict=True):
        assert a.group.canonical.source.listing_id == b.group.canonical.source.listing_id
        assert a.recommendation == b.recommendation
        assert a.score == b.score
        assert a.opportunity == b.opportunity
        assert a.market_price == b.market_price

    # Shadow mode actually ran and produced output for this call, otherwise
    # the comparison above would be vacuous.
    assert enabled_pipeline.last_pue_shadow_records != ()


def test_last_pue_shadow_results_and_records_are_both_exposed(tmp_path: Path) -> None:
    """Sprint 2 pre-merge correction item 6: ``run_pue_shadow`` returns
    ``PueShadowCaseResult`` envelopes, not bare ``ReasoningRecord``s.
    ``last_pue_shadow_results`` is the authoritative attribute holding
    those envelopes; ``last_pue_shadow_records`` is a genuine compatibility
    projection restoring its original Sprint 1 meaning - a tuple of plain
    ``ReasoningRecord``s, never the envelope itself."""
    from digital_arbitrage.pipeline.pue_shadow import PueShadowCaseResult
    from digital_arbitrage.pue.models import ReasoningRecord

    pipeline = ArbitragePipeline(
        PipelineConfig(pue_shadow_config=ShadowConfig(enabled=True, db_path=tmp_path / "shadow.db"))
    )
    pipeline.analyze("rtx 4090")

    assert pipeline.last_pue_shadow_results != ()
    assert all(isinstance(r, PueShadowCaseResult) for r in pipeline.last_pue_shadow_results)
    assert pipeline.last_pue_shadow_records != ()
    assert all(isinstance(r, ReasoningRecord) for r in pipeline.last_pue_shadow_records)
    assert len(pipeline.last_pue_shadow_records) == len(pipeline.last_pue_shadow_results)
    assert pipeline.last_pue_shadow_records == tuple(
        r.reasoning_record for r in pipeline.last_pue_shadow_results
    )
