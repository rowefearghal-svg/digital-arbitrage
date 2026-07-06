"""Unit tests for the recommendation scoring engine."""

from __future__ import annotations

import pytest

from digital_arbitrage.market_pricing.models import MarketPrice
from digital_arbitrage.opportunity import (
    CostBreakdown,
    Opportunity,
    ProfitEstimate,
    Recommendation,
    RecommendationScorer,
    ScoreBreakdown,
    ScoringConfig,
)


def make_opp(
    *,
    net: float | None = None,
    asking: float = 100.0,
    confidence: float = 1.0,
    recommendation: Recommendation = Recommendation.BUY,
) -> Opportunity:
    """Build an Opportunity whose net profit and ROI are fully controlled.

    With zero costs and ``market = asking + net``, ``net_profit == net`` and
    ``roi_percentage == net / asking * 100``. ``net=None`` yields an unpriced
    opportunity (``profit is None``).
    """
    profit = None
    if net is not None:
        profit = ProfitEstimate(
            asking_price=asking,
            estimated_market_price=asking + net,
            costs=CostBreakdown(),
        )
    return Opportunity(
        listing_id="1",
        title="rtx 4090",
        provider="ebay",
        currency="EUR",
        recommendation=recommendation,
        confidence_score=confidence,
        profit=profit,
    )


def make_mp(
    *,
    price: float | None = 1000.0,
    low: float | None = None,
    high: float | None = None,
    median: float | None = None,
    comparables: int = 5,
    confidence: float = 1.0,
) -> MarketPrice:
    return MarketPrice(
        estimated_market_price=price,
        confidence_score=confidence,
        comparable_count=comparables,
        min_price=low if low is not None else price,
        max_price=high if high is not None else price,
        median_price=median if median is not None else price,
        mean_price=price,
        currency="EUR",
        strategy="median",
        reliable=True,
    )


# --------------------------------------------------------------------------- #
# config validation
# --------------------------------------------------------------------------- #
def test_default_config_is_valid() -> None:
    scorer = RecommendationScorer()
    assert scorer.config.total_weight == pytest.approx(1.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"roi_weight": -0.1},
        {"roi_weight": 0.0, "net_profit_weight": 0.0, "confidence_weight": 0.0, "risk_weight": 0.0},
        {"roi_reference": 0.0},
        {"net_profit_reference": -5.0},
        {"risk_dispersion_reference": 0.0},
        {"risk_full_comparables": 0},
    ],
)
def test_invalid_config_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        ScoringConfig(**kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# score_signals: bounds and extremes
# --------------------------------------------------------------------------- #
def test_perfect_signals_score_100() -> None:
    scorer = RecommendationScorer()
    out = scorer.score_signals(
        roi_signal=1.0, profit_signal=1.0, confidence_signal=1.0, risk_signal=0.0
    )
    assert out.score == 100.0


def test_worst_signals_score_0() -> None:
    scorer = RecommendationScorer()
    out = scorer.score_signals(
        roi_signal=0.0, profit_signal=0.0, confidence_signal=0.0, risk_signal=1.0
    )
    assert out.score == 0.0


@pytest.mark.parametrize(
    "signals",
    [
        (0.0, 0.0, 0.0, 0.0),
        (0.5, 0.5, 0.5, 0.5),
        (1.0, 0.0, 1.0, 0.5),
        (2.0, -1.0, 5.0, 3.0),  # out-of-range inputs are clamped
    ],
)
def test_score_always_within_bounds(signals: tuple[float, float, float, float]) -> None:
    scorer = RecommendationScorer()
    roi, profit, conf, risk = signals
    out = scorer.score_signals(
        roi_signal=roi, profit_signal=profit, confidence_signal=conf, risk_signal=risk
    )
    assert 0.0 <= out.score <= 100.0
    for signal in (out.roi_signal, out.profit_signal, out.confidence_signal, out.risk_signal):
        assert 0.0 <= signal <= 1.0


def test_signals_are_clamped() -> None:
    scorer = RecommendationScorer()
    out = scorer.score_signals(
        roi_signal=5.0, profit_signal=-2.0, confidence_signal=1.5, risk_signal=-3.0
    )
    assert out.roi_signal == 1.0
    assert out.profit_signal == 0.0
    assert out.confidence_signal == 1.0
    assert out.risk_signal == 0.0


# --------------------------------------------------------------------------- #
# component trade-offs
# --------------------------------------------------------------------------- #
def test_high_roi_low_confidence_beats_low_roi_high_confidence_by_default() -> None:
    # Default roi_weight (0.35) exceeds confidence_weight (0.25), so a strong ROI
    # with weak confidence out-scores the mirror image at equal profit/risk.
    scorer = RecommendationScorer()
    high_roi = scorer.score_signals(
        roi_signal=1.0, profit_signal=0.5, confidence_signal=0.1, risk_signal=0.3
    )
    high_conf = scorer.score_signals(
        roi_signal=0.1, profit_signal=0.5, confidence_signal=1.0, risk_signal=0.3
    )
    assert high_roi.score > high_conf.score


def test_confidence_weighting_can_be_flipped() -> None:
    # Make confidence dominate and the ordering reverses - proves weights drive it.
    scorer = RecommendationScorer(
        ScoringConfig(roi_weight=0.1, confidence_weight=0.8, net_profit_weight=0.1, risk_weight=0.0)
    )
    high_roi = scorer.score_signals(
        roi_signal=1.0, profit_signal=0.5, confidence_signal=0.1, risk_signal=0.0
    )
    high_conf = scorer.score_signals(
        roi_signal=0.1, profit_signal=0.5, confidence_signal=1.0, risk_signal=0.0
    )
    assert high_conf.score > high_roi.score


def test_higher_net_profit_raises_score() -> None:
    scorer = RecommendationScorer()
    low = scorer.score_signals(
        roi_signal=0.2, profit_signal=0.0, confidence_signal=0.5, risk_signal=0.2
    )
    high = scorer.score_signals(
        roi_signal=0.2, profit_signal=1.0, confidence_signal=0.5, risk_signal=0.2
    )
    assert high.score > low.score


def test_higher_risk_lowers_score() -> None:
    scorer = RecommendationScorer()
    safe = scorer.score_signals(
        roi_signal=0.5, profit_signal=0.5, confidence_signal=0.5, risk_signal=0.1
    )
    risky = scorer.score_signals(
        roi_signal=0.5, profit_signal=0.5, confidence_signal=0.5, risk_signal=0.9
    )
    assert safe.score > risky.score


# --------------------------------------------------------------------------- #
# determinism / tie-breaking
# --------------------------------------------------------------------------- #
def test_scoring_is_deterministic() -> None:
    scorer = RecommendationScorer()
    a = scorer.score_signals(
        roi_signal=0.4, profit_signal=0.6, confidence_signal=0.7, risk_signal=0.2
    )
    b = scorer.score_signals(
        roi_signal=0.4, profit_signal=0.6, confidence_signal=0.7, risk_signal=0.2
    )
    assert a == b


def test_equal_signals_produce_equal_scores() -> None:
    # Ties are genuine: identical signals -> identical score, so downstream
    # ranking must break ties itself (the pipeline uses listing_id).
    scorer = RecommendationScorer()
    left = scorer.score(make_opp(net=30.0, asking=100.0, confidence=0.8), make_mp())
    right = scorer.score(make_opp(net=30.0, asking=100.0, confidence=0.8), make_mp())
    assert left.score == right.score


# --------------------------------------------------------------------------- #
# risk estimation
# --------------------------------------------------------------------------- #
def test_unpriced_market_is_maximally_risky() -> None:
    scorer = RecommendationScorer()
    assert scorer.estimate_risk(make_mp(price=None)) == 1.0


def test_tight_well_covered_market_is_low_risk() -> None:
    scorer = RecommendationScorer()
    risk = scorer.estimate_risk(
        make_mp(price=1000.0, low=990.0, high=1010.0, median=1000.0, comparables=5)
    )
    assert risk < 0.05


def test_wide_spread_raises_risk() -> None:
    scorer = RecommendationScorer()
    tight = scorer.estimate_risk(
        make_mp(price=1000.0, low=950.0, high=1050.0, median=1000.0, comparables=5)
    )
    wide = scorer.estimate_risk(
        make_mp(price=1000.0, low=200.0, high=1800.0, median=1000.0, comparables=5)
    )
    assert wide > tight


def test_sparse_comparables_raise_risk() -> None:
    scorer = RecommendationScorer()
    many = scorer.estimate_risk(
        make_mp(price=1000.0, low=990.0, high=1010.0, median=1000.0, comparables=5)
    )
    few = scorer.estimate_risk(
        make_mp(price=1000.0, low=990.0, high=1010.0, median=1000.0, comparables=1)
    )
    assert few > many


# --------------------------------------------------------------------------- #
# score(opportunity, market_price)
# --------------------------------------------------------------------------- #
def test_score_returns_breakdown() -> None:
    scorer = RecommendationScorer()
    out = scorer.score(make_opp(net=30.0, asking=100.0), make_mp())
    assert isinstance(out, ScoreBreakdown)
    assert 0.0 <= out.score <= 100.0


def test_unpriced_opportunity_zeroes_upside_signals() -> None:
    scorer = RecommendationScorer()
    out = scorer.score(
        make_opp(net=None, confidence=0.9, recommendation=Recommendation.REJECT),
        make_mp(price=None),
    )
    assert out.roi_signal == 0.0
    assert out.profit_signal == 0.0
    assert out.risk_signal == 1.0


def test_score_without_market_price_falls_back_to_confidence_risk() -> None:
    scorer = RecommendationScorer()
    out = scorer.score(make_opp(net=30.0, asking=100.0, confidence=0.75))
    assert out.risk_signal == pytest.approx(0.25)


def test_negative_deal_still_scores_from_confidence() -> None:
    # A loss-making deal has zero ROI/profit signal but confidence still counts.
    scorer = RecommendationScorer()
    out = scorer.score(
        make_opp(net=-500.0, asking=1000.0, confidence=1.0, recommendation=Recommendation.REJECT),
        make_mp(price=500.0, low=500.0, high=500.0, median=500.0, comparables=5),
    )
    assert out.roi_signal == 0.0
    assert out.profit_signal == 0.0
    assert out.score > 0.0


def test_breakdown_to_dict_round_trips() -> None:
    scorer = RecommendationScorer()
    out = scorer.score_signals(
        roi_signal=0.5, profit_signal=0.5, confidence_signal=0.5, risk_signal=0.2
    )
    data = out.to_dict()
    assert data["score"] == out.score
    assert set(data) == {
        "score",
        "roi_signal",
        "profit_signal",
        "confidence_signal",
        "risk_signal",
    }
