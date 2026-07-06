"""Profit / opportunity engine.

Turns a listing's asking price and an estimated market price into a scored,
conservative arbitrage opportunity: an itemized cost breakdown, profit/ROI/margin
figures, and a STRONG_BUY / BUY / WATCH / REJECT recommendation with reasons.
Deterministic and fully typed; no scraping, AI/ML, or external APIs (ADR-008).

Quick start::

    from digital_arbitrage.opportunity import OpportunityAnalyzer

    opp = OpportunityAnalyzer().analyze(listing, market_price)
    print(opp.recommendation, opp.net_profit, opp.roi_percentage)
"""

from __future__ import annotations

from .analyzer import OpportunityAnalyzer, OpportunityConfig
from .models import CostBreakdown, Opportunity, ProfitEstimate, Recommendation
from .scoring import RecommendationScorer, ScoreBreakdown, ScoringConfig

__all__ = [
    "CostBreakdown",
    "Opportunity",
    "OpportunityAnalyzer",
    "OpportunityConfig",
    "ProfitEstimate",
    "Recommendation",
    "RecommendationScorer",
    "ScoreBreakdown",
    "ScoringConfig",
]
