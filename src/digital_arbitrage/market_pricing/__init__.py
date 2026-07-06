"""Market price estimation.

Estimates the current market price of a product from comparable listings, using
deterministic, swappable statistical strategies (median, trimmed mean, weighted
average) with optional IQR outlier removal. Provider-agnostic and fully typed;
no AI/ML (see ADR-007).

Quick start::

    from digital_arbitrage.market_pricing import MarketPriceEstimator

    price = MarketPriceEstimator().estimate_from_group(group)
    print(price.estimated_market_price, price.currency, price.confidence_score)
"""

from __future__ import annotations

from .estimator import MarketPriceEstimator, MarketPricingConfig
from .models import ComparableListing, MarketPrice
from .strategies import (
    STRATEGY_NAMES,
    MedianStrategy,
    PricingStrategy,
    TrimmedMeanStrategy,
    WeightedAverageStrategy,
    create_strategy,
)

__all__ = [
    "STRATEGY_NAMES",
    "ComparableListing",
    "MarketPrice",
    "MarketPriceEstimator",
    "MarketPricingConfig",
    "MedianStrategy",
    "PricingStrategy",
    "TrimmedMeanStrategy",
    "WeightedAverageStrategy",
    "create_strategy",
]
