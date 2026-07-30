"""Unit tests: SQLite persistence for PUE Reasoning Records."""

from __future__ import annotations

from pathlib import Path

import pytest

from digital_arbitrage.pue.orchestration import process_one
from digital_arbitrage.pue.persistence import (
    PueCaseStore,
    reasoning_record_from_json,
    reasoning_record_to_json,
)
from digital_arbitrage.pue.validation import PueValidationError

from .conftest import make_normalized


def test_save_and_get_case(tmp_path: Path, deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G"),
        deterministic_context,
        repository=repository,
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        restored = store.get_case(record.case_id)
    assert restored == record


def test_duplicate_case_id_is_never_overwritten(
    tmp_path: Path, deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("RTX 4090 water block"), deterministic_context, repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        with pytest.raises(PueValidationError):
            store.save_case(record)


def test_find_by_fingerprint(tmp_path: Path, deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("RTX 3060 12GB"), deterministic_context, repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        found = store.find_by_fingerprint(record.observation.source_fingerprint)
    assert len(found) == 1
    assert found[0].case_id == record.case_id


def test_find_by_listing(tmp_path: Path, deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("RTX 4080 Super Gaming OC", listing_id="L42", provider="ebay"),
        deterministic_context,
        repository=repository,
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        found = store.find_by_listing("ebay", "L42")
    assert len(found) == 1


def test_json_round_trip_equivalence(deterministic_context, repository) -> None:
    record = process_one(
        make_normalized("RTX 4090 for parts not working"),
        deterministic_context,
        repository=repository,
    )
    payload = reasoning_record_to_json(record)
    restored = reasoning_record_from_json(payload)
    assert restored == record


def test_schema_created_with_expected_columns(tmp_path: Path) -> None:
    with PueCaseStore(tmp_path / "pue.db") as store:
        cols = {row[1] for row in store._conn.execute("PRAGMA table_info(pue_cases)").fetchall()}
    assert {
        "case_id",
        "observation_id",
        "provider",
        "provider_listing_id",
        "source_fingerprint",
        "capability_version",
        "policy_version",
        "knowledge_version",
        "schema_version",
        "decision_type",
        "identification_level",
        "product_form",
        "selected_catalogue_product_id",
        "comparability_status",
        "reasoning_record_json",
        "created_at",
    }.issubset(cols)


def test_in_memory_store_works(deterministic_context, repository) -> None:
    record = process_one(make_normalized("RTX 4090"), deterministic_context, repository=repository)
    with PueCaseStore(":memory:") as store:
        store.save_case(record)
        assert store.get_case(record.case_id) is not None


def test_find_equivalent_matches_fingerprint_and_versions(
    tmp_path: Path, deterministic_context, repository
) -> None:
    record = process_one(
        make_normalized("RTX 4080 Super Gaming OC"), deterministic_context, repository=repository
    )
    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(record)
        found = store.find_equivalent(
            source_fingerprint=record.observation.source_fingerprint,
            capability_version=record.decision.capability_version,
            policy_version=record.decision.policy_version,
            knowledge_version=record.decision.knowledge_version,
        )
        assert found is not None
        assert found.case_id == record.case_id

        # A different fingerprint never matches.
        assert (
            store.find_equivalent(
                source_fingerprint="not-a-real-fingerprint",
                capability_version=record.decision.capability_version,
                policy_version=record.decision.policy_version,
                knowledge_version=record.decision.knowledge_version,
            )
            is None
        )


def test_repeated_shadow_run_does_not_duplicate_completed_record(
    tmp_path: Path, deterministic_context, repository
) -> None:
    """Normal (non-replay) processing of the identical listing under the
    identical capability/policy/knowledge versions must not accumulate a
    second completed record for the same source_fingerprint."""
    listing = make_normalized("RTX 4090 water block")
    first = process_one(listing, deterministic_context, repository=repository)
    second = process_one(listing, deterministic_context, repository=repository)
    # Same content -> same fingerprint; different process_one() calls ->
    # different case_id (spec: historical records are never overwritten).
    assert first.case_id != second.case_id
    assert first.observation.source_fingerprint == second.observation.source_fingerprint

    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(first)
        with pytest.raises(PueValidationError):
            store.save_case(second)
        # Exactly one completed record persisted for this fingerprint.
        assert len(store.find_by_fingerprint(first.observation.source_fingerprint)) == 1


def test_replay_flag_retains_another_record_for_same_fingerprint(
    tmp_path: Path, deterministic_context, repository
) -> None:
    """Explicitly marked replay/evaluation activity (``replay=True``) may
    retain another record for a fingerprint/version triple that already has
    a completed record."""
    listing = make_normalized("RTX 4090 water block")
    first = process_one(listing, deterministic_context, repository=repository)
    second = process_one(listing, deterministic_context, repository=repository)

    with PueCaseStore(tmp_path / "pue.db") as store:
        store.save_case(first)
        store.save_case(second, replay=True)
        assert len(store.find_by_fingerprint(first.observation.source_fingerprint)) == 2
