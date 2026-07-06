"""CLI tests for the persistence commands (scan --save, history, show)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.persistence import ResultStore
from digital_arbitrage.pipeline.cli import main


def _db(tmp_path: Path) -> str:
    return str(tmp_path / "history.db")


def test_scan_save_persists_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _db(tmp_path)
    code = main(["scan", "rtx 4090", "--limit", "2", "--save", "--db", db])
    assert code == 0
    err = capsys.readouterr().err
    assert "saved run 1" in err
    with ResultStore(db) as store:
        runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0].query == "rtx 4090"
    assert "limit=2" in runs[0].config_summary


def test_scan_without_save_writes_nothing(tmp_path: Path) -> None:
    db = _db(tmp_path)
    code = main(["scan", "rtx 4090", "--limit", "1", "--db", db])
    assert code == 0
    with ResultStore(db) as store:
        assert store.list_runs() == []


def test_history_table_lists_saved_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _db(tmp_path)
    main(["scan", "rtx 4090", "--limit", "1", "--save", "--db", db])
    capsys.readouterr()
    code = main(["history", "--db", db])
    assert code == 0
    out = capsys.readouterr().out
    assert "RUN" in out and "QUERY" in out
    assert "rtx 4090" in out


def test_history_json_is_parseable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _db(tmp_path)
    main(["scan", "rtx 4090", "--limit", "1", "--save", "--db", db])
    capsys.readouterr()
    code = main(["history", "--format", "json", "--db", db])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert payload[0]["query"] == "rtx 4090"


def test_history_empty_database(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["history", "--db", _db(tmp_path)])
    assert code == 0
    assert "no saved runs" in capsys.readouterr().out


def test_show_displays_stored_opportunities(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _db(tmp_path)
    main(["scan", "rtx 4090", "--limit", "2", "--save", "--db", db])
    capsys.readouterr()
    code = main(["show", "1", "--db", db])
    assert code == 0
    out = capsys.readouterr().out
    assert "run 1" in out
    assert "RANK" in out and "SCORE" in out and "RISK" in out


def test_show_json_includes_run_and_opportunities(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _db(tmp_path)
    main(["scan", "rtx 4090", "--limit", "2", "--save", "--db", db])
    capsys.readouterr()
    code = main(["show", "1", "--format", "json", "--db", db])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == 1
    assert len(payload["opportunities"]) >= 1
    assert "recommendation_score" in payload["opportunities"][0]


def test_show_csv_has_header(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _db(tmp_path)
    main(["scan", "rtx 4090", "--limit", "1", "--save", "--db", db])
    capsys.readouterr()
    code = main(["show", "1", "--format", "csv", "--db", db])
    assert code == 0
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line.startswith("rank,recommendation,recommendation_score")


def test_show_missing_run_returns_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["show", "42", "--db", _db(tmp_path)])
    assert code == 1
    assert "run 42 not found" in capsys.readouterr().err


def test_saved_scan_is_viewable_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _db(tmp_path)
    main(["scan", "rtx 4090", "--limit", "2", "--save", "--db", db])
    capsys.readouterr()
    main(["show", "1", "--format", "json", "--db", db])
    shown = json.loads(capsys.readouterr().out)
    with ResultStore(db) as store:
        stored = [o.to_dict() for o in store.list_opportunities(1)]
    assert shown["opportunities"] == stored
