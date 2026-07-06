"""Unit tests for the run-comparison engine."""

from __future__ import annotations

from digital_arbitrage.comparison import (
    ChangeCategory,
    ComparisonConfig,
    OpportunityDelta,
    RunComparison,
    compare_runs,
    identity_key,
)
from digital_arbitrage.persistence import StoredOpportunity, StoredRun


def make_run(run_id: int, query: str = "rtx 4090") -> StoredRun:
    return StoredRun(
        run_id=run_id,
        query=query,
        created_at=f"2020-01-0{run_id}T00:00:00+00:00",
        config_summary="config=defaults",
        total_listings_scanned=10,
        total_groups=3,
        total_opportunities=3,
    )


def make_opp(
    title: str,
    *,
    provider: str = "ebay",
    score: float = 50.0,
    roi: float | None = 20.0,
    net: float | None = 100.0,
    confidence: float = 0.6,
    risk: float = 0.3,
    rank: int = 1,
    recommendation: str = "buy",
) -> StoredOpportunity:
    return StoredOpportunity(
        id=rank,
        run_id=0,
        rank=rank,
        title=title,
        provider=provider,
        currency="EUR",
        asking_price=100.0,
        estimated_market_price=200.0,
        roi_percentage=roi,
        net_profit=net,
        confidence_score=confidence,
        risk_score=risk,
        recommendation_score=score,
        recommendation=recommendation,
    )


def compare(old: list[StoredOpportunity], new: list[StoredOpportunity]) -> RunComparison:
    return compare_runs(make_run(1), old, make_run(2), new)


def category_of(comparison: RunComparison, title: str) -> ChangeCategory:
    for delta in comparison.deltas:
        if delta.title == title:
            return delta.category
    raise AssertionError(f"no delta for {title!r}")


# --------------------------------------------------------------------------- #
# identity key
# --------------------------------------------------------------------------- #
def test_identity_key_normalizes_case_and_whitespace() -> None:
    a = make_opp("RTX  4090   Founders", provider="eBay")
    b = make_opp("rtx 4090 founders", provider="ebay")
    assert identity_key(a) == identity_key(b)


def test_identity_key_includes_provider() -> None:
    a = make_opp("rtx 4090", provider="ebay")
    b = make_opp("rtx 4090", provider="donedeal")
    assert identity_key(a) != identity_key(b)


# --------------------------------------------------------------------------- #
# categorisation
# --------------------------------------------------------------------------- #
def test_new_opportunity() -> None:
    comparison = compare([], [make_opp("rtx 4090")])
    assert category_of(comparison, "rtx 4090") is ChangeCategory.NEW


def test_disappeared_opportunity() -> None:
    comparison = compare([make_opp("rtx 4090")], [])
    assert category_of(comparison, "rtx 4090") is ChangeCategory.DISAPPEARED


def test_unchanged_opportunity() -> None:
    comparison = compare([make_opp("rtx 4090")], [make_opp("rtx 4090")])
    assert category_of(comparison, "rtx 4090") is ChangeCategory.UNCHANGED


def test_improved_by_recommendation_score() -> None:
    comparison = compare([make_opp("rtx 4090", score=40.0)], [make_opp("rtx 4090", score=60.0)])
    delta = comparison.deltas[0]
    assert delta.category is ChangeCategory.IMPROVED
    assert "recommendation_score" in delta.reason


def test_worsened_by_recommendation_score() -> None:
    comparison = compare([make_opp("rtx 4090", score=60.0)], [make_opp("rtx 4090", score=40.0)])
    assert comparison.deltas[0].category is ChangeCategory.WORSENED


def test_improved_by_roi_tiebreak_when_score_equal() -> None:
    comparison = compare(
        [make_opp("rtx 4090", score=50.0, roi=10.0)],
        [make_opp("rtx 4090", score=50.0, roi=25.0)],
    )
    delta = comparison.deltas[0]
    assert delta.category is ChangeCategory.IMPROVED
    assert "roi_percentage" in delta.reason


def test_worsened_by_higher_risk_when_others_equal() -> None:
    comparison = compare(
        [make_opp("rtx 4090", risk=0.2)],
        [make_opp("rtx 4090", risk=0.8)],
    )
    delta = comparison.deltas[0]
    assert delta.category is ChangeCategory.WORSENED
    assert "risk_score" in delta.reason


def test_lower_risk_is_improvement() -> None:
    comparison = compare(
        [make_opp("rtx 4090", risk=0.8)],
        [make_opp("rtx 4090", risk=0.2)],
    )
    assert comparison.deltas[0].category is ChangeCategory.IMPROVED


# --------------------------------------------------------------------------- #
# edge cases
# --------------------------------------------------------------------------- #
def test_empty_runs_produce_no_deltas() -> None:
    comparison = compare([], [])
    assert comparison.deltas == ()
    assert comparison.counts_by_category() == {c.value: 0 for c in ChangeCategory}


def test_none_metric_values_are_coalesced() -> None:
    # roi/net None on the old (rejected) side, present on the new -> improvement.
    comparison = compare(
        [make_opp("rtx 4090", score=50.0, roi=None, net=None)],
        [make_opp("rtx 4090", score=50.0, roi=15.0, net=80.0)],
    )
    delta = comparison.deltas[0]
    assert delta.category is ChangeCategory.IMPROVED
    roi = delta.metric("roi_percentage")
    assert roi is not None and roi.old is None and roi.new == 15.0


def test_epsilon_treats_tiny_change_as_unchanged() -> None:
    comparison = compare_runs(
        make_run(1),
        [make_opp("rtx 4090", score=50.0)],
        make_run(2),
        [make_opp("rtx 4090", score=50.0000001)],
        ComparisonConfig(epsilon=1e-3),
    )
    assert comparison.deltas[0].category is ChangeCategory.UNCHANGED


def test_duplicate_identity_keeps_best_ranked() -> None:
    old = [make_opp("rtx 4090", score=10.0, rank=2), make_opp("rtx 4090", score=90.0, rank=1)]
    comparison = compare(old, [make_opp("rtx 4090", score=90.0)])
    # rank 1 (score 90) is retained, so the pair is unchanged, not worsened.
    assert len(comparison.deltas) == 1
    assert comparison.deltas[0].category is ChangeCategory.UNCHANGED


# --------------------------------------------------------------------------- #
# ordering + serialization
# --------------------------------------------------------------------------- #
def test_deltas_ordered_by_category_then_key() -> None:
    old = [
        make_opp("gone", provider="a"),
        make_opp("same", provider="b"),
        make_opp("down", provider="c", score=90.0),
    ]
    new = [
        make_opp("fresh", provider="d"),
        make_opp("same", provider="b"),
        make_opp("down", provider="c", score=10.0),
    ]
    comparison = compare(old, new)
    categories = [d.category for d in comparison.deltas]
    assert categories == [
        ChangeCategory.NEW,
        ChangeCategory.WORSENED,
        ChangeCategory.UNCHANGED,
        ChangeCategory.DISAPPEARED,
    ]


def test_comparison_is_deterministic() -> None:
    old = [make_opp("a"), make_opp("b", provider="x")]
    new = [make_opp("a", score=70.0), make_opp("c", provider="y")]
    first = compare(old, new).to_dict()
    second = compare(old, new).to_dict()
    assert first == second


def test_counts_by_category_sums_to_deltas() -> None:
    comparison = compare([make_opp("a"), make_opp("b")], [make_opp("a"), make_opp("c")])
    counts = comparison.counts_by_category()
    assert sum(counts.values()) == len(comparison.deltas)


def test_to_dict_structure() -> None:
    comparison = compare([make_opp("a")], [make_opp("a", score=70.0)])
    payload = comparison.to_dict()
    assert set(payload) == {"old_run", "new_run", "counts", "deltas"}
    delta = payload["deltas"][0]
    assert set(delta) == {"category", "key", "provider", "title", "reason", "old", "new", "metrics"}
    assert {m["name"] for m in delta["metrics"]} == {
        "recommendation_score",
        "roi_percentage",
        "net_profit",
        "confidence_score",
        "risk_score",
    }


def test_by_category_filters() -> None:
    comparison = compare([make_opp("gone")], [make_opp("fresh")])
    new_only = comparison.by_category(ChangeCategory.NEW)
    assert all(isinstance(d, OpportunityDelta) for d in new_only)
    assert [d.title for d in new_only] == ["fresh"]
