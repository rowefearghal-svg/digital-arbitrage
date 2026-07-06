"""Unit tests for the pipeline orchestrator and CLI."""

from __future__ import annotations

import json

import pytest

from digital_arbitrage.deduplication.models import DuplicateGroup
from digital_arbitrage.market_pricing.models import MarketPrice
from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.opportunity.models import (
    CostBreakdown,
    Opportunity,
    ProfitEstimate,
    Recommendation,
)
from digital_arbitrage.pipeline import ArbitragePipeline, PipelineConfig, PipelineResult
from digital_arbitrage.pipeline.cli import main, render_json, render_table
from digital_arbitrage.pipeline.models import PipelineItemResult
from digital_arbitrage.pipeline.pipeline import _sort_key
from digital_arbitrage.product_scanner import Listing


def make_item(
    recommendation: Recommendation, roi: float, confidence: float, lid: str = "1"
) -> PipelineItemResult:
    raw = Listing(listing_id=lid, title="t", provider="ebay", url="https://x", price=100.0)
    nl = NormalizedListing(source=raw, title="t", title_tokens=("t",), currency="EUR")
    group = DuplicateGroup(fingerprint=f"fp{lid}", canonical=nl, members=(nl,))
    market = MarketPrice(
        estimated_market_price=100.0 + roi,
        confidence_score=confidence,
        comparable_count=3,
        min_price=100.0,
        max_price=100.0 + roi,
        median_price=100.0 + roi,
        mean_price=100.0 + roi,
        currency="EUR",
        strategy="median",
    )
    profit = ProfitEstimate(
        asking_price=100.0, estimated_market_price=100.0 + roi, costs=CostBreakdown()
    )
    opp = Opportunity(
        listing_id=lid,
        title="t",
        provider="ebay",
        currency="EUR",
        recommendation=recommendation,
        confidence_score=confidence,
        profit=profit,
    )
    return PipelineItemResult(group=group, market_price=market, opportunity=opp)


# --------------------------------------------------------------------------- #
# sorting
# --------------------------------------------------------------------------- #
def test_sort_by_recommendation_then_roi_then_confidence() -> None:
    items = [
        make_item(Recommendation.REJECT, 5, 0.9, "a"),
        make_item(Recommendation.STRONG_BUY, 40, 0.7, "b"),
        make_item(Recommendation.BUY, 20, 0.5, "c"),
        make_item(Recommendation.BUY, 30, 0.5, "d"),
        make_item(Recommendation.WATCH, 10, 0.5, "e"),
    ]
    order = [item.opportunity.listing_id for item in sorted(items, key=_sort_key)]
    assert order == ["b", "d", "c", "e", "a"]


def test_sort_confidence_tiebreak() -> None:
    items = [
        make_item(Recommendation.BUY, 20, 0.4, "low"),
        make_item(Recommendation.BUY, 20, 0.8, "high"),
    ]
    order = [item.opportunity.listing_id for item in sorted(items, key=_sort_key)]
    assert order == ["high", "low"]


# --------------------------------------------------------------------------- #
# pipeline integration
# --------------------------------------------------------------------------- #
def test_analyze_returns_ranked_result() -> None:
    result = ArbitragePipeline().analyze("rtx 4090")
    assert isinstance(result, PipelineResult)
    assert result.query == "rtx 4090"
    assert result.total_listings_scanned > 0
    assert result.total_groups == len(result.items)
    ranks = [_sort_key(item)[0] for item in result.items]
    assert ranks == sorted(ranks)


def test_analyze_is_deterministic() -> None:
    a = ArbitragePipeline().analyze("rtx 4090")
    b = ArbitragePipeline().analyze("rtx 4090")
    assert a.to_dict() == b.to_dict()


def test_pipeline_populates_recommendation_score() -> None:
    result = ArbitragePipeline().analyze("rtx 4090")
    for item in result.items:
        assert 0.0 <= item.score <= 100.0
        assert 0.0 <= item.risk_score <= 1.0
        assert item.to_dict()["recommendation_score"] == round(item.score, 2)


def test_scan_limit_reduces_listings() -> None:
    full = ArbitragePipeline().analyze("rtx 4090")
    limited = ArbitragePipeline(PipelineConfig(scan_limit=1)).analyze("rtx 4090")
    assert limited.total_listings_scanned < full.total_listings_scanned


def test_counts_by_recommendation_sums_to_items() -> None:
    result = ArbitragePipeline().analyze("rtx 4090")
    counts = result.counts_by_recommendation()
    assert sum(counts.values()) == len(result.items)
    assert set(counts) == {rec.value for rec in Recommendation}


def test_result_to_dict_is_json_serializable() -> None:
    result = ArbitragePipeline().analyze("rtx 4090")
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["query"] == "rtx 4090"
    assert len(payload["items"]) == len(result.items)
    if payload["items"]:
        assert "recommendation" in payload["items"][0]


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def test_render_table_has_header_and_columns() -> None:
    result = ArbitragePipeline().analyze("rtx 4090")
    text = render_table(result, result.items)
    assert "query: 'rtx 4090'" in text
    assert "RECOMMENDATION" in text
    assert "TITLE" in text


def test_render_json_roundtrips() -> None:
    result = ArbitragePipeline().analyze("rtx 4090")
    assert json.loads(render_json(result, result.items))["query"] == "rtx 4090"


def test_render_table_empty_items() -> None:
    empty = PipelineResult(query="none", items=(), total_listings_scanned=0, total_groups=0)
    assert "(no opportunities)" in render_table(empty, empty.items)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "rtx 4090"


def test_cli_table(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090"])
    assert code == 0
    assert "RECOMMENDATION" in capsys.readouterr().out


def test_cli_limit(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--limit", "1"])
    assert code == 0


def test_cli_bad_format_exits() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["scan", "rtx 4090", "--format", "yaml"])
    assert exc.value.code == 2


def test_cli_missing_command_exits() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
