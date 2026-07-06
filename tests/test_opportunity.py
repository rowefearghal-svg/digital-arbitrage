"""Unit tests for the opportunity (profit) engine."""

from __future__ import annotations

from typing import Any

import pytest

from digital_arbitrage.market_pricing.models import MarketPrice
from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.opportunity import (
    CostBreakdown,
    Opportunity,
    OpportunityAnalyzer,
    OpportunityConfig,
    ProfitEstimate,
    Recommendation,
)
from digital_arbitrage.product_scanner import Listing


def listing(price: float | None, *, currency: str = "EUR", lid: str = "1") -> Listing:
    return Listing(
        listing_id=lid,
        title="rtx 4090",
        provider="ebay",
        url=f"https://x/{lid}",
        price=price,
        currency=currency,
    )


def mp(
    price: float | None, *, currency: str | None = "EUR", confidence: float = 1.0
) -> MarketPrice:
    return MarketPrice(
        estimated_market_price=price,
        confidence_score=confidence,
        comparable_count=5,
        min_price=price,
        max_price=price,
        median_price=price,
        mean_price=price,
        currency=currency,
        strategy="median",
        outliers_removed=0,
        reliable=True,
    )


def zero_cost(**overrides: Any) -> OpportunityConfig:
    base: dict[str, Any] = dict(
        marketplace_fee_rate=0.0,
        payment_fee_rate=0.0,
        payment_fee_flat=0.0,
        shipping_cost=0.0,
        packaging_cost=0.0,
        buffer_rate=0.0,
        buffer_flat=0.0,
        tax_rate=0.0,
    )
    base.update(overrides)
    return OpportunityConfig(**base)


# --------------------------------------------------------------------------- #
# CostBreakdown / ProfitEstimate
# --------------------------------------------------------------------------- #
def test_cost_breakdown_total() -> None:
    costs = CostBreakdown(marketplace_fee=10, payment_fee=3, shipping_cost=5, buffer=2)
    assert costs.total == 20.0


def test_cost_breakdown_rejects_negative() -> None:
    with pytest.raises(ValueError, match="shipping_cost must be non-negative"):
        CostBreakdown(shipping_cost=-1)


def test_profit_estimate_math() -> None:
    profit = ProfitEstimate(asking_price=800, estimated_market_price=1000, costs=CostBreakdown())
    assert profit.gross_profit == 200.0
    assert profit.net_profit == 200.0
    assert profit.roi_percentage == 25.0
    assert profit.margin_percentage == 20.0


def test_profit_estimate_with_costs() -> None:
    profit = ProfitEstimate(
        asking_price=800, estimated_market_price=1000, costs=CostBreakdown(marketplace_fee=100)
    )
    assert profit.net_profit == 100.0


def test_profit_estimate_zero_division_guards() -> None:
    assert ProfitEstimate(0, 100, CostBreakdown()).roi_percentage == 0.0
    assert ProfitEstimate(100, 0, CostBreakdown()).margin_percentage == 0.0


# --------------------------------------------------------------------------- #
# Opportunity model
# --------------------------------------------------------------------------- #
def test_opportunity_validates_confidence() -> None:
    with pytest.raises(ValueError, match="confidence_score must be in"):
        Opportunity(
            listing_id="1",
            title="t",
            provider="ebay",
            currency="EUR",
            recommendation=Recommendation.REJECT,
            confidence_score=1.5,
        )


def test_opportunity_convenience_props_none_when_unpriced() -> None:
    opp = Opportunity(
        listing_id="1",
        title="t",
        provider="ebay",
        currency="EUR",
        recommendation=Recommendation.REJECT,
        confidence_score=0.0,
        profit=None,
    )
    assert opp.asking_price is None
    assert opp.net_profit is None
    assert opp.is_actionable is False


# --------------------------------------------------------------------------- #
# config validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kwargs",
    [
        {"marketplace_fee_rate": 1.5},
        {"shipping_cost": -1},
        {"watch_roi": 0.4, "buy_roi": 0.2},
        {"min_confidence": 2.0},
    ],
)
def test_config_validation(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        OpportunityConfig(**kwargs)


# --------------------------------------------------------------------------- #
# analyzer: recommendation tiers (zero-cost so ROI is controlled)
# --------------------------------------------------------------------------- #
def test_strong_buy() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(200))
    assert opp.recommendation is Recommendation.STRONG_BUY
    assert opp.is_actionable
    assert opp.net_profit == 100.0
    assert opp.roi_percentage == 100.0


def test_buy() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(120))
    assert opp.recommendation is Recommendation.BUY


def test_watch() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(110))
    assert opp.recommendation is Recommendation.WATCH


def test_reject_low_roi() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(103))
    assert opp.recommendation is Recommendation.REJECT


def test_reject_non_positive_net() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(100))
    assert opp.recommendation is Recommendation.REJECT


# --------------------------------------------------------------------------- #
# analyzer: confidence gating
# --------------------------------------------------------------------------- #
def test_low_confidence_caps_strong_buy_to_buy() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(200, confidence=0.5))
    assert opp.recommendation is Recommendation.BUY


def test_very_low_confidence_caps_to_watch() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(200, confidence=0.3))
    assert opp.recommendation is Recommendation.WATCH


# --------------------------------------------------------------------------- #
# analyzer: costs, tax, currency, missing data
# --------------------------------------------------------------------------- #
def test_conservative_defaults_reject_thin_margin() -> None:
    opp = OpportunityAnalyzer().analyze(listing(100), mp(120))
    assert opp.recommendation is Recommendation.REJECT
    assert opp.net_profit is not None and opp.net_profit < 0


def test_default_costs_profitable_case() -> None:
    opp = OpportunityAnalyzer().analyze(listing(500), mp(1000))
    assert opp.profit is not None
    assert opp.profit.costs.total == pytest.approx(191.35, abs=0.01)
    assert opp.recommendation is Recommendation.STRONG_BUY


def test_tax_placeholder_applied_to_gross() -> None:
    opp = OpportunityAnalyzer(zero_cost(tax_rate=0.2)).analyze(listing(100), mp(200))
    assert opp.profit is not None
    assert opp.profit.costs.tax == 20.0
    assert opp.net_profit == 80.0


def test_currency_mismatch_rejected() -> None:
    opp = OpportunityAnalyzer().analyze(listing(100, currency="EUR"), mp(200, currency="USD"))
    assert opp.recommendation is Recommendation.REJECT
    assert opp.profit is None


def test_missing_asking_price_rejected() -> None:
    opp = OpportunityAnalyzer().analyze(listing(None), mp(200))
    assert opp.recommendation is Recommendation.REJECT
    assert opp.profit is None


def test_unpriced_market_rejected() -> None:
    opp = OpportunityAnalyzer().analyze(listing(100), mp(None))
    assert opp.recommendation is Recommendation.REJECT
    assert opp.profit is None


def test_accepts_normalized_listing() -> None:
    raw = listing(500)
    normalized = NormalizedListing(
        source=raw, title="rtx 4090", title_tokens=("rtx", "4090"), currency="EUR"
    )
    opp = OpportunityAnalyzer().analyze(normalized, mp(1000))
    assert opp.recommendation is Recommendation.STRONG_BUY
    assert opp.listing_id == raw.listing_id


def test_reasons_are_populated() -> None:
    opp = OpportunityAnalyzer(zero_cost()).analyze(listing(100), mp(200))
    assert opp.reasons
    assert any("ROI" in reason for reason in opp.reasons)


def test_deterministic() -> None:
    a = OpportunityAnalyzer().analyze(listing(500), mp(1000))
    b = OpportunityAnalyzer().analyze(listing(500), mp(1000))
    assert a == b
