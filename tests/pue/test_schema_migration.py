"""SQLite schema migration tests (final Sprint 2 correction).

Builds realistic pre-migration databases by hand, using the exact
historical DDL/JSON shapes for Sprint 1 (v1: ``pue_cases`` only) and the
first-attempt Sprint 2 (v2: ``pue_classifier_comparisons`` with ``case_id``
as its primary key and no comparison-equivalence columns), then opens them
through the current :class:`PueCaseStore` and asserts the migration to v3
is correct, transactional, and never destructive.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from digital_arbitrage.classification.classifier import ListingClassifier, build_search_profile
from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.comparison import compare_classifier_and_pue
from digital_arbitrage.pue.persistence import (
    LEGACY_V2_COMPARISON_SCHEMA_VERSION,
    LEGACY_V2_SEARCH_PROFILE_FINGERPRINT,
    SCHEMA_VERSION,
    PueCaseStore,
    reasoning_record_to_json,
)
from digital_arbitrage.pue.validation import PueValidationError

from .conftest import make_normalized

_V1_CASES_DDL = """
CREATE TABLE pue_cases (
    case_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_listing_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    knowledge_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    identification_level TEXT NOT NULL,
    product_form TEXT NOT NULL,
    selected_catalogue_product_id TEXT,
    comparability_status TEXT NOT NULL,
    reasoning_record_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_pue_cases_listing ON pue_cases(provider, provider_listing_id);
CREATE INDEX idx_pue_cases_fingerprint ON pue_cases(source_fingerprint);
CREATE INDEX idx_pue_cases_versions
ON pue_cases(capability_version, policy_version, knowledge_version);
"""

_V2_COMPARISONS_DDL = """
CREATE TABLE pue_classifier_comparisons (
    case_id TEXT PRIMARY KEY REFERENCES pue_cases(case_id),
    provider TEXT NOT NULL,
    provider_listing_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    classifier_capability_version TEXT NOT NULL,
    pue_capability_version TEXT NOT NULL,
    category TEXT NOT NULL,
    comparison_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_pue_comparisons_listing
ON pue_classifier_comparisons(provider, provider_listing_id);
CREATE INDEX idx_pue_comparisons_fingerprint
ON pue_classifier_comparisons(source_fingerprint);
CREATE INDEX idx_pue_comparisons_versions
ON pue_classifier_comparisons(classifier_capability_version, pue_capability_version);
"""


def _old_comparison_json(comparison) -> str:
    """The exact v2 (pre-correction) ``comparison_to_dict`` field set - no
    ``comparison_id``, ``comparison_schema_version``,
    ``classifier_search_profile_fingerprint``, ``pue_policy_version``, or
    ``pue_knowledge_version``. Hand-built here since that shape no longer
    exists in the current ``comparison.py``."""
    return json.dumps(
        {
            "case_id": comparison.case_id,
            "provider": comparison.provider,
            "provider_listing_id": comparison.provider_listing_id,
            "source_fingerprint": comparison.source_fingerprint,
            "classifier_label": comparison.classifier_label,
            "classifier_score": comparison.classifier_score,
            "classifier_reason": comparison.classifier_reason,
            "classifier_capability_version": comparison.classifier_capability_version,
            "pue_decision_type": comparison.pue_decision_type,
            "pue_identification_level": comparison.pue_identification_level,
            "pue_product_form": comparison.pue_product_form,
            "pue_comparability_status": comparison.pue_comparability_status,
            "pue_abstention_reason": comparison.pue_abstention_reason,
            "pue_identified_family": comparison.pue_identified_family,
            "pue_identified_model": comparison.pue_identified_model,
            "pue_capability_version": comparison.pue_capability_version,
            "product_form_conclusions_agree": comparison.product_form_conclusions_agree,
            "pue_abstained": comparison.pue_abstained,
            "classifier_complete_product_pue_blocked": (
                comparison.classifier_complete_product_pue_blocked
            ),
            "identity_breadth": comparison.identity_breadth,
            "category": comparison.category.value,
        },
        sort_keys=True,
    )


def _make_record(title: str):
    context = orchestration.build_default_context()
    listing = make_normalized(title)
    return context, listing, orchestration.process_one(listing, context)


def _insert_v1_case(conn: sqlite3.Connection, record) -> None:
    decision = record.decision
    conn.execute(
        "INSERT INTO pue_cases (case_id, observation_id, provider, provider_listing_id, "
        "source_fingerprint, capability_version, policy_version, knowledge_version, "
        "schema_version, decision_type, identification_level, product_form, "
        "selected_catalogue_product_id, comparability_status, reasoning_record_json, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            record.case_id,
            record.observation.observation_id,
            record.observation.provider,
            record.observation.provider_listing_id,
            record.observation.source_fingerprint,
            decision.capability_version,
            decision.policy_version,
            decision.knowledge_version,
            record.schema_version,
            decision.decision_type.value,
            decision.identification_level.value,
            decision.product_form.value,
            None,
            decision.comparability_status.value,
            reasoning_record_to_json(record),
            "2026-01-01T00:00:00",
        ),
    )


def _insert_v2_comparison(conn: sqlite3.Connection, comparison) -> None:
    conn.execute(
        "INSERT INTO pue_classifier_comparisons (case_id, provider, provider_listing_id, "
        "source_fingerprint, classifier_capability_version, pue_capability_version, "
        "category, comparison_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            comparison.case_id,
            comparison.provider,
            comparison.provider_listing_id,
            comparison.source_fingerprint,
            comparison.classifier_capability_version,
            comparison.pue_capability_version,
            comparison.category.value,
            _old_comparison_json(comparison),
            "2026-01-01T00:00:00",
        ),
    )


def _build_v1_db(path: Path, titles: list[str]) -> list:
    """A realistic Sprint 1 database: ``pue_cases`` only, no version
    tracking, no comparisons table at all."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_V1_CASES_DDL)
    records = []
    for title in titles:
        _, _, record = _make_record(title)
        _insert_v1_case(conn, record)
        records.append(record)
    conn.commit()
    conn.close()
    return records


def _build_v2_db(path: Path, titles: list[str]) -> tuple[list, list]:
    """A realistic first-attempt Sprint 2 database: both tables present,
    ``case_id`` still the comparisons primary key, no version tracking."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_V1_CASES_DDL)
    conn.executescript(_V2_COMPARISONS_DDL)
    records = []
    comparisons = []
    profile = build_search_profile("rtx 4090")
    classifier = ListingClassifier()
    for title in titles:
        context, listing, record = _make_record(title)
        _insert_v1_case(conn, record)
        verdict = classifier.classify(listing, profile)
        comparison = compare_classifier_and_pue(
            verdict, record, search_profile=profile, id_factory=context.id_factory
        )
        _insert_v2_comparison(conn, comparison)
        records.append(record)
        comparisons.append(comparison)
    conn.commit()
    conn.close()
    return records, comparisons


# --------------------------------------------------------------------------- #
# v1 -> v3
# --------------------------------------------------------------------------- #
def test_v1_database_migrates_preserving_cases(tmp_path: Path) -> None:
    db_path = tmp_path / "v1.db"
    records = _build_v1_db(
        db_path, ["ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", "RTX 4090 water block"]
    )

    with PueCaseStore(db_path) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert store._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        for record in records:
            reloaded = store.get_case(record.case_id)
            assert reloaded == record

        assert set(store.list_cases()) == {r.case_id for r in records}
        # The comparisons table now exists, correctly shaped, but empty -
        # v1 never had one.
        assert store.list_comparisons() == []
        columns = {
            row[1]
            for row in store._conn.execute(
                "PRAGMA table_info(pue_classifier_comparisons)"
            ).fetchall()
        }
        assert "comparison_id" in columns


def test_v1_migration_supports_immediate_shadow_processing(tmp_path: Path) -> None:
    """A case+comparison can be written normally right after migrating a
    v1 database - the migration does not leave the store in a broken
    state for ordinary use."""
    db_path = tmp_path / "v1.db"
    _build_v1_db(db_path, ["RTX 4090 water block"])

    with PueCaseStore(db_path) as store:
        context, listing, record = _make_record("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
        profile = build_search_profile("rtx 4090")
        verdict = ListingClassifier().classify(listing, profile)
        comparison = compare_classifier_and_pue(
            verdict, record, search_profile=profile, id_factory=context.id_factory
        )
        store.save_case_with_comparison(record, comparison)

        assert store.get_case(record.case_id) == record
        assert store.get_comparisons_for_case(record.case_id) == [comparison]


# --------------------------------------------------------------------------- #
# v2 -> v3
# --------------------------------------------------------------------------- #
def test_v2_database_migrates_preserving_comparisons(tmp_path: Path) -> None:
    db_path = tmp_path / "v2.db"
    records, comparisons = _build_v2_db(
        db_path, ["ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", "RTX 4090 water block"]
    )

    with PueCaseStore(db_path) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

        for record in records:
            assert store.get_case(record.case_id) == record

        migrated = store.list_comparisons()
        assert len(migrated) == len(comparisons)

        by_case = {c.case_id: c for c in migrated}
        for original in comparisons:
            m = by_case[original.case_id]
            # Recoverable fields carried across unchanged.
            assert m.classifier_label == original.classifier_label
            assert m.category == original.category
            assert m.classifier_capability_version == original.classifier_capability_version
            assert m.pue_capability_version == original.pue_capability_version
            # New fields synthesized: a real, unique comparison_id and the
            # documented legacy sentinels for genuinely unrecoverable data.
            assert m.comparison_id
            assert m.classifier_search_profile_fingerprint == (LEGACY_V2_SEARCH_PROFILE_FINGERPRINT)
            assert m.comparison_schema_version == LEGACY_V2_COMPARISON_SCHEMA_VERSION
            # Recoverable from the matching pue_cases row, not guessed.
            matching_record = next(r for r in records if r.case_id == original.case_id)
            assert m.pue_policy_version == matching_record.decision.policy_version
            assert m.pue_knowledge_version == matching_record.decision.knowledge_version

        comparison_ids = {c.comparison_id for c in migrated}
        assert len(comparison_ids) == len(migrated)  # all unique


def test_v2_migration_preserves_foreign_key_integrity(tmp_path: Path) -> None:
    db_path = tmp_path / "v2.db"
    _build_v2_db(db_path, ["RTX 4090 water block"])

    with PueCaseStore(db_path) as store:
        errors = store._conn.execute(
            "PRAGMA foreign_key_check(pue_classifier_comparisons)"
        ).fetchall()
        assert errors == []


def test_v2_migration_replay_and_idempotency_preserved(tmp_path: Path) -> None:
    """Comparison-equivalence detection (idempotency) and replay behaviour
    must work exactly as before, post-migration, for *new* comparisons."""
    db_path = tmp_path / "v2.db"
    _build_v2_db(db_path, ["RTX 4090 water block"])

    with PueCaseStore(db_path) as store:
        context, listing, record = _make_record("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
        profile = build_search_profile("rtx 4090")
        verdict = ListingClassifier().classify(listing, profile)
        comparison = compare_classifier_and_pue(
            verdict, record, search_profile=profile, id_factory=context.id_factory
        )
        store.save_case_with_comparison(record, comparison)

        # Non-replay: an equivalent comparison is rejected.
        duplicate = compare_classifier_and_pue(verdict, record, search_profile=profile)
        with pytest.raises(PueValidationError):
            store.save_comparison(duplicate)

        # Replay: an equivalent comparison is retained as an additional record.
        store.save_comparison(duplicate, replay=True)
        assert len(store.get_comparisons_for_case(record.case_id)) == 2


def test_interrupted_v2_migration_rolls_back_completely(tmp_path: Path) -> None:
    """A failure partway through the v2 -> v3 migration (corrupt legacy
    comparison_json here) must leave the database exactly as it was - no
    version bump, no renamed/dropped tables, no partially-migrated rows."""
    db_path = tmp_path / "v2.db"
    records, comparisons = _build_v2_db(
        db_path, ["ASUS TUF RTX 4090 OC TUF-RTX4090-O24G", "RTX 4090 water block"]
    )

    # Corrupt one row's comparison_json so json.loads() fails mid-migration.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE pue_classifier_comparisons SET comparison_json = ? WHERE case_id = ?",
        ("{not valid json", comparisons[0].case_id),
    )
    conn.commit()
    conn.close()

    with pytest.raises(json.JSONDecodeError):
        PueCaseStore(db_path)

    # The database must be untouched: still v2-shaped, same row counts,
    # no stray temp table, user_version still unset.
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert tables == {"pue_cases", "pue_classifier_comparisons"}
        assert "_pue_comparisons_v2" not in tables

        columns = {row[1] for row in conn.execute("PRAGMA table_info(pue_classifier_comparisons)")}
        assert "comparison_id" not in columns  # still the old v2 shape
        assert "case_id" in columns

        case_count = conn.execute("SELECT COUNT(*) FROM pue_cases").fetchone()[0]
        comparison_count = conn.execute(
            "SELECT COUNT(*) FROM pue_classifier_comparisons"
        ).fetchone()[0]
        assert case_count == len(records)
        assert comparison_count == len(comparisons)

        assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Empty / new database
# --------------------------------------------------------------------------- #
def test_empty_new_database_creates_current_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "new.db"
    assert not db_path.exists()

    with PueCaseStore(db_path) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert store._conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert store.list_cases() == []
        assert store.list_comparisons() == []


# --------------------------------------------------------------------------- #
# Unknown / future schema version
# --------------------------------------------------------------------------- #
def test_unknown_future_schema_version_is_rejected_without_changes(tmp_path: Path) -> None:
    db_path = tmp_path / "future.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_V1_CASES_DDL)
    conn.executescript(_V2_COMPARISONS_DDL)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    with pytest.raises(PueValidationError):
        PueCaseStore(db_path)

    # Nothing was modified: version and table shapes are exactly as left.
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99
        columns = {row[1] for row in conn.execute("PRAGMA table_info(pue_classifier_comparisons)")}
        assert "comparison_id" not in columns
    finally:
        conn.close()
