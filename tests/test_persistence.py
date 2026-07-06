"""Unit tests for the SQLite persistence layer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from digital_arbitrage.persistence import (
    SCHEMA_VERSION,
    ResultStore,
    StoredOpportunity,
    StoredRun,
)
from digital_arbitrage.pipeline import ArbitragePipeline, PipelineResult


def make_result() -> PipelineResult:
    return ArbitragePipeline().analyze("rtx 4090")


def empty_result() -> PipelineResult:
    return PipelineResult(query="empty", items=(), total_listings_scanned=0, total_groups=0)


# --------------------------------------------------------------------------- #
# schema / lifecycle
# --------------------------------------------------------------------------- #
def test_schema_version_is_recorded(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        version = store._conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == SCHEMA_VERSION


def test_creates_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "history.db"
    with ResultStore(nested):
        pass
    assert nested.exists()


def test_context_manager_closes_connection(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "h.db")
    with store:
        store.save_run(make_result())
    with pytest.raises(sqlite3.ProgrammingError):
        store._conn.execute("SELECT 1")


# --------------------------------------------------------------------------- #
# writes + reads
# --------------------------------------------------------------------------- #
def test_save_run_returns_incrementing_ids(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        first = store.save_run(make_result())
        second = store.save_run(make_result())
    assert (first, second) == (1, 2)


def test_get_run_summary_matches_result(tmp_path: Path) -> None:
    result = make_result()
    with ResultStore(tmp_path / "h.db") as store:
        run_id = store.save_run(result, config_summary="config=defaults")
        run = store.get_run(run_id)
    assert isinstance(run, StoredRun)
    assert run.query == "rtx 4090"
    assert run.config_summary == "config=defaults"
    assert run.total_listings_scanned == result.total_listings_scanned
    assert run.total_groups == result.total_groups
    assert run.total_opportunities == len(result.items)


def test_get_run_missing_returns_none(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        assert store.get_run(999) is None


def test_list_runs_newest_first(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        store.save_run(make_result(), config_summary="first")
        store.save_run(make_result(), config_summary="second")
        runs = store.list_runs()
    assert [r.run_id for r in runs] == [2, 1]
    assert runs[0].config_summary == "second"


def test_list_runs_respects_limit(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        for _ in range(3):
            store.save_run(make_result())
        runs = store.list_runs(limit=2)
    assert [r.run_id for r in runs] == [3, 2]


def test_opportunities_match_result_items(tmp_path: Path) -> None:
    result = make_result()
    with ResultStore(tmp_path / "h.db") as store:
        run_id = store.save_run(result)
        opps = store.list_opportunities(run_id)
    assert len(opps) == len(result.items)
    assert [o.rank for o in opps] == list(range(1, len(result.items) + 1))
    first_stored, first_item = opps[0], result.items[0]
    assert isinstance(first_stored, StoredOpportunity)
    assert first_stored.title == first_item.title
    assert first_stored.provider == first_item.provider
    assert first_stored.recommendation == first_item.recommendation.value
    assert first_stored.recommendation_score == pytest.approx(first_item.score)
    assert first_stored.risk_score == pytest.approx(first_item.risk_score)
    assert first_stored.asking_price == pytest.approx(first_item.opportunity.asking_price)


def test_created_at_is_stored_and_returned(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        run_id = store.save_run(make_result(), created_at="2020-01-01T00:00:00+00:00")
        run = store.get_run(run_id)
    assert run is not None
    assert run.created_at == "2020-01-01T00:00:00+00:00"


def test_empty_result_saves_zero_opportunities(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        run_id = store.save_run(empty_result())
        run = store.get_run(run_id)
        opps = store.list_opportunities(run_id)
    assert run is not None
    assert run.total_opportunities == 0
    assert opps == []


def test_data_persists_across_reopen(tmp_path: Path) -> None:
    path = tmp_path / "h.db"
    with ResultStore(path) as store:
        run_id = store.save_run(make_result())
    with ResultStore(path) as store:
        assert store.get_run(run_id) is not None
        assert len(store.list_opportunities(run_id)) > 0


def test_in_memory_store_works() -> None:
    with ResultStore(":memory:") as store:
        run_id = store.save_run(make_result())
        assert store.get_run(run_id) is not None


def test_stored_run_to_dict_roundtrips(tmp_path: Path) -> None:
    with ResultStore(tmp_path / "h.db") as store:
        run_id = store.save_run(make_result())
        run = store.get_run(run_id)
    assert run is not None
    payload = run.to_dict()
    assert payload["run_id"] == run_id
    assert set(payload) == {
        "run_id",
        "query",
        "created_at",
        "config_summary",
        "total_listings_scanned",
        "total_groups",
        "total_opportunities",
    }
