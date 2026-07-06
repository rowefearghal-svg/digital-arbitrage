"""Tests for CLI filtering, sorting, export formats, and --debug."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import replace

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
from digital_arbitrage.pipeline.cli import (
    _filter_items,
    _sort_items,
    build_parser,
    main,
    render_csv,
    render_markdown,
)
from digital_arbitrage.pipeline.models import PipelineItemResult, PipelineResult
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
        reasons=("because",),
    )
    return PipelineItemResult(group=group, market_price=market, opportunity=opp)


def parse(argv: list[str]):  # type: ignore[no-untyped-def]
    return build_parser().parse_args(argv)


def sample() -> list[PipelineItemResult]:
    return [
        make_item(Recommendation.STRONG_BUY, 40, 0.7, "a"),
        make_item(Recommendation.BUY, 20, 0.5, "b"),
        make_item(Recommendation.WATCH, 8, 0.9, "c"),
        make_item(Recommendation.REJECT, -50, 0.3, "d"),
    ]


def result_of(items: list[PipelineItemResult]) -> PipelineResult:
    return PipelineResult(
        query="rtx 4090",
        items=tuple(items),
        total_listings_scanned=8,
        total_groups=len(items),
    )


# --------------------------------------------------------------------------- #
# filtering
# --------------------------------------------------------------------------- #
def test_actionable_only() -> None:
    args = parse(["scan", "q", "--actionable-only"])
    ids = [i.opportunity.listing_id for i in _filter_items(sample(), args)]
    assert ids == ["a", "b"]


def test_min_recommendation() -> None:
    args = parse(["scan", "q", "--min-recommendation", "WATCH".lower()])
    ids = [i.opportunity.listing_id for i in _filter_items(sample(), args)]
    assert ids == ["a", "b", "c"]


def test_min_roi() -> None:
    args = parse(["scan", "q", "--min-roi", "20"])
    ids = [i.opportunity.listing_id for i in _filter_items(sample(), args)]
    assert ids == ["a", "b"]


def test_min_net_profit() -> None:
    args = parse(["scan", "q", "--min-net-profit", "30"])
    ids = [i.opportunity.listing_id for i in _filter_items(sample(), args)]
    assert ids == ["a"]


def test_filters_combine() -> None:
    args = parse(["scan", "q", "--min-recommendation", "buy", "--min-roi", "30"])
    ids = [i.opportunity.listing_id for i in _filter_items(sample(), args)]
    assert ids == ["a"]


# --------------------------------------------------------------------------- #
# sorting
# --------------------------------------------------------------------------- #
def test_sort_roi() -> None:
    ids = [i.opportunity.listing_id for i in _sort_items(sample(), "roi")]
    assert ids == ["a", "b", "c", "d"]


def test_sort_confidence() -> None:
    ids = [i.opportunity.listing_id for i in _sort_items(sample(), "confidence")]
    assert ids == ["c", "a", "b", "d"]


def test_sort_net_profit() -> None:
    ids = [i.opportunity.listing_id for i in _sort_items(sample(), "net_profit")]
    assert ids == ["a", "b", "c", "d"]


def test_sort_recommendation_is_identity() -> None:
    items = sample()
    assert _sort_items(items, "recommendation") == items


def test_sort_score_descending_with_listing_id_tiebreak() -> None:
    items = [
        replace(make_item(Recommendation.BUY, 20, 0.5, "b"), score=50.0),
        replace(make_item(Recommendation.BUY, 20, 0.5, "a"), score=50.0),
        replace(make_item(Recommendation.STRONG_BUY, 40, 0.7, "c"), score=80.0),
    ]
    ids = [i.opportunity.listing_id for i in _sort_items(items, "score")]
    assert ids == ["c", "a", "b"]


# --------------------------------------------------------------------------- #
# renderers
# --------------------------------------------------------------------------- #
def test_render_csv_parses() -> None:
    text = render_csv(result_of(sample()), sample())
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "recommendation"
    assert len(rows) == 5
    assert rows[1][0] == "strong_buy"


def test_render_csv_escapes_reasons() -> None:
    text = render_csv(result_of(sample()), sample())
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert parsed[0]["reasons"] == "because"


def test_render_markdown_table() -> None:
    md = render_markdown(result_of(sample()), sample())
    assert md.startswith("# Opportunities for 'rtx 4090'")
    assert "| RECOMMENDATION |" in md
    assert md.count("\n|") >= 5


def test_render_markdown_empty() -> None:
    md = render_markdown(result_of([]), [])
    assert "_No opportunities._" in md


# --------------------------------------------------------------------------- #
# CLI end-to-end (real pipeline, mock providers)
# --------------------------------------------------------------------------- #
def test_cli_csv(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--format", "csv", "--limit", "2"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("recommendation,")


def test_cli_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--format", "markdown", "--limit", "2"])
    assert code == 0
    assert "# Opportunities for" in capsys.readouterr().out


def test_cli_json_includes_shown(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--sort", "roi", "--format", "json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["shown"] == len(payload["items"])


def test_cli_table_shows_score_column(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--sort", "score", "--limit", "2"])
    assert code == 0
    assert "SCORE" in capsys.readouterr().out


def test_cli_json_includes_recommendation_score(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--format", "json", "--limit", "1"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    item = payload["items"][0]
    assert "recommendation_score" in item
    assert 0.0 <= item["recommendation_score"] <= 100.0
    assert "risk_score" in item


def test_cli_actionable_only_empty_table(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["scan", "rtx 4090", "--actionable-only"])
    assert code == 0
    assert "(no opportunities)" in capsys.readouterr().out


def test_cli_debug_shows_traceback(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "bad.toml"
    bad.write_text("[nonsense]\nx = 1\n", encoding="utf-8")
    code = main(["scan", "rtx 4090", "--config", str(bad), "--debug"])
    assert code == 1
    assert "Traceback (most recent call last)" in capsys.readouterr().err


def test_cli_clean_error_without_debug(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    bad = tmp_path / "bad.toml"
    bad.write_text("[nonsense]\nx = 1\n", encoding="utf-8")
    code = main(["scan", "rtx 4090", "--config", str(bad)])
    assert code == 1
    err = capsys.readouterr().err
    assert err.startswith("error:")
    assert "Traceback" not in err
