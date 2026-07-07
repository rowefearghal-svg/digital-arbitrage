"""CLI tests for the `arb compare` command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.comparison import ChangeCategory
from digital_arbitrage.persistence import ResultStore
from digital_arbitrage.pipeline import PipelineResult
from digital_arbitrage.pipeline.cli import main
from tests.test_comparison import make_opp


def _seed_two_runs(tmp_path: Path) -> str:
    """Write two runs whose opportunities differ, returning the db path."""
    db = str(tmp_path / "history.db")
    empty = PipelineResult(query="rtx 4090", items=(), total_listings_scanned=0, total_groups=0)

    # Build the two runs by inserting opportunity rows directly so we control the deltas.
    with ResultStore(db) as store:
        store.save_run(empty, config_summary="run1")
        store.save_run(empty, config_summary="run2")
        # Overwrite opportunities with controlled snapshots.
        store._conn.execute("DELETE FROM opportunities")
        for run_id, score in ((1, 40.0), (2, 70.0)):
            opp = make_opp("rtx 4090 founders", score=score)
            store._conn.execute(
                "INSERT INTO opportunities (run_id, rank, title, provider, currency, "
                "asking_price, estimated_market_price, roi_percentage, net_profit, "
                "confidence_score, risk_score, recommendation_score, recommendation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    1,
                    opp.title,
                    opp.provider,
                    opp.currency,
                    opp.asking_price,
                    opp.estimated_market_price,
                    opp.roi_percentage,
                    opp.net_profit,
                    opp.confidence_score,
                    opp.risk_score,
                    opp.recommendation_score,
                    opp.recommendation,
                ),
            )
        # A run-2-only opportunity so we also exercise the NEW category.
        fresh = make_opp("rtx 4090 ti", provider="donedeal")
        store._conn.execute(
            "INSERT INTO opportunities (run_id, rank, title, provider, currency, "
            "asking_price, estimated_market_price, roi_percentage, net_profit, "
            "confidence_score, risk_score, recommendation_score, recommendation) "
            "VALUES (2, 2, ?, ?, 'EUR', 100.0, 200.0, 20.0, 100.0, 0.6, 0.3, 55.0, 'buy')",
            (fresh.title, fresh.provider),
        )
        store._conn.commit()
    return db


def test_compare_table_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_two_runs(tmp_path)
    code = main(["compare", "1", "2", "--db", db])
    assert code == 0
    out = capsys.readouterr().out
    assert "compare run 1" in out
    assert "CATEGORY" in out
    assert "improved" in out and "new" in out


def test_compare_json_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_two_runs(tmp_path)
    code = main(["compare", "1", "2", "--format", "json", "--db", db])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["old_run"]["run_id"] == 1
    assert payload["new_run"]["run_id"] == 2
    assert payload["counts"][ChangeCategory.IMPROVED.value] == 1
    assert payload["counts"][ChangeCategory.NEW.value] == 1


def test_compare_csv_header(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_two_runs(tmp_path)
    code = main(["compare", "1", "2", "--format", "csv", "--db", db])
    assert code == 0
    header = capsys.readouterr().out.splitlines()[0]
    assert header.startswith("category,key,provider,title,reason,recommendation_score_old")


def test_compare_markdown_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_two_runs(tmp_path)
    code = main(["compare", "1", "2", "--format", "markdown", "--db", db])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("# Comparison: run 1 -> run 2")
    assert "| CATEGORY |" in out


def test_compare_missing_run_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = _seed_two_runs(tmp_path)
    code = main(["compare", "1", "99", "--db", db])
    assert code == 1
    assert "run 99 not found" in capsys.readouterr().err


def test_compare_same_run_is_all_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = _seed_two_runs(tmp_path)
    code = main(["compare", "1", "1", "--format", "json", "--db", db])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"][ChangeCategory.UNCHANGED.value] == len(payload["deltas"])
