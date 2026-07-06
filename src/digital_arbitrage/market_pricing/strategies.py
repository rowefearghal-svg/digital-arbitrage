"""Pricing strategies.

Each strategy is a small, deterministic function object that reduces a set of
prices (and optional weights) to a single estimate. They are intentionally
decoupled from the estimator so new strategies can be dropped in without
touching orchestration - register a subclass or pass an instance to the config.
No AI/ML.
"""

from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar


class PricingStrategy(ABC):
    """Reduce prices to a single estimated value."""

    name: ClassVar[str] = ""

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define a non-empty 'name'")

    @abstractmethod
    def estimate(self, prices: Sequence[float], weights: Sequence[float]) -> float:
        """Return the estimated price for ``prices`` (with parallel ``weights``)."""


class MedianStrategy(PricingStrategy):
    """The median price - robust to outliers."""

    name = "median"

    def estimate(self, prices: Sequence[float], weights: Sequence[float]) -> float:
        return float(statistics.median(prices))


class TrimmedMeanStrategy(PricingStrategy):
    """Mean after discarding a fraction of the lowest and highest prices."""

    name = "trimmed_mean"

    def __init__(self, trim_fraction: float = 0.1) -> None:
        super().__init__()
        if not 0.0 <= trim_fraction < 0.5:
            raise ValueError("trim_fraction must be in [0, 0.5)")
        self.trim_fraction = trim_fraction

    def estimate(self, prices: Sequence[float], weights: Sequence[float]) -> float:
        ordered = sorted(prices)
        n = len(ordered)
        k = int(n * self.trim_fraction)
        trimmed = ordered[k : n - k] if n - 2 * k > 0 else ordered
        return float(statistics.fmean(trimmed))


class WeightedAverageStrategy(PricingStrategy):
    """Weighted mean; falls back to a plain mean when weights sum to zero."""

    name = "weighted_average"

    def estimate(self, prices: Sequence[float], weights: Sequence[float]) -> float:
        total_weight = sum(weights)
        if total_weight <= 0:
            return float(statistics.fmean(prices))
        weighted = sum(price * weight for price, weight in zip(prices, weights, strict=True))
        return float(weighted / total_weight)


#: Built-in strategy names.
STRATEGY_NAMES: tuple[str, ...] = ("median", "trimmed_mean", "weighted_average")


def create_strategy(name: str, *, trim_fraction: float = 0.1) -> PricingStrategy:
    """Instantiate a built-in strategy by name."""
    if name == "median":
        return MedianStrategy()
    if name == "trimmed_mean":
        return TrimmedMeanStrategy(trim_fraction=trim_fraction)
    if name == "weighted_average":
        return WeightedAverageStrategy()
    available = ", ".join(STRATEGY_NAMES)
    raise ValueError(f"unknown strategy {name!r}; available: {available}")
