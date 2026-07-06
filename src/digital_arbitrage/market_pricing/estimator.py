"""The market price estimator.

``MarketPriceEstimator`` is the valuation stage of the pipeline
(Scanner -> Normalization -> Product Matching -> Deduplication -> Market
Pricing). Given comparable listings (directly, or from a
:class:`DuplicateGroup` / normalized listings) it produces a deterministic
:class:`MarketPrice`: an estimate via a configurable strategy, robust summary
statistics, and a confidence score. No AI/ML.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..deduplication.models import DuplicateGroup
from ..normalization.models import NormalizedListing
from .models import ComparableListing, MarketPrice
from .strategies import PricingStrategy, create_strategy


@dataclass(slots=True, frozen=True)
class MarketPricingConfig:
    """Configuration for :class:`MarketPriceEstimator`."""

    #: Strategy name ("median", "trimmed_mean", "weighted_average") or instance.
    strategy: str | PricingStrategy = "median"
    #: Trim fraction used when ``strategy == "trimmed_mean"``.
    trim_fraction: float = 0.1
    #: Minimum comparables for the result to be considered reliable.
    min_comparables: int = 3
    #: Remove statistical outliers (IQR fences) before estimating.
    remove_outliers: bool = True
    #: IQR multiplier for the outlier fences.
    iqr_multiplier: float = 1.5
    #: Force a target currency; when None the dominant currency is inferred.
    currency: str | None = None
    #: Comparable count at which the count component of confidence saturates.
    confidence_full_count: int = 5
    #: Metadata slot for future extension (kept for forward-compat).
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.min_comparables < 1:
            raise ValueError("min_comparables must be >= 1")
        if self.iqr_multiplier <= 0:
            raise ValueError("iqr_multiplier must be positive")
        if self.confidence_full_count < 1:
            raise ValueError("confidence_full_count must be >= 1")


def _dominant_currency(comparables: list[ComparableListing]) -> str | None:
    """Return the most common currency (ties broken alphabetically)."""
    if not comparables:
        return None
    counts: dict[str, int] = {}
    for comparable in comparables:
        counts[comparable.currency] = counts.get(comparable.currency, 0) + 1
    return min(counts, key=lambda currency: (-counts[currency], currency))


class MarketPriceEstimator:
    """Estimate the market price of a product from comparable listings."""

    def __init__(self, config: MarketPricingConfig | None = None) -> None:
        self.config = config or MarketPricingConfig()
        if isinstance(self.config.strategy, PricingStrategy):
            self._strategy: PricingStrategy = self.config.strategy
        else:
            self._strategy = create_strategy(
                self.config.strategy, trim_fraction=self.config.trim_fraction
            )

    # -- public API -------------------------------------------------------- #
    def estimate(self, comparables: Iterable[ComparableListing]) -> MarketPrice:
        """Estimate a market price from explicit comparable listings."""
        selected = self._select_currency(list(comparables))
        if not selected:
            return self._empty_result(currency=self.config.currency)

        currency = selected[0].currency
        kept, removed = self._strip_outliers(selected)
        prices = [comparable.price for comparable in kept]
        weights = [comparable.weight for comparable in kept]

        estimate = round(self._strategy.estimate(prices, weights), 2)
        confidence = self._confidence(prices)
        count = len(kept)
        return MarketPrice(
            estimated_market_price=estimate,
            confidence_score=confidence,
            comparable_count=count,
            min_price=round(min(prices), 2),
            max_price=round(max(prices), 2),
            median_price=round(float(statistics.median(prices)), 2),
            mean_price=round(float(statistics.fmean(prices)), 2),
            currency=currency,
            strategy=self._strategy.name,
            outliers_removed=removed,
            reliable=count >= self.config.min_comparables,
        )

    def estimate_from_listings(self, listings: Iterable[NormalizedListing]) -> MarketPrice:
        """Estimate from normalized listings (those without a price are skipped)."""
        comparables = [
            comparable
            for listing in listings
            if (comparable := ComparableListing.try_from(listing)) is not None
        ]
        return self.estimate(comparables)

    def estimate_from_group(self, group: DuplicateGroup) -> MarketPrice:
        """Estimate from the members of a deduplicated group."""
        return self.estimate_from_listings(group.members)

    # -- internals --------------------------------------------------------- #
    def _select_currency(self, comparables: list[ComparableListing]) -> list[ComparableListing]:
        target = self.config.currency or _dominant_currency(comparables)
        if target is None:
            return []
        return [comparable for comparable in comparables if comparable.currency == target]

    def _strip_outliers(
        self, comparables: list[ComparableListing]
    ) -> tuple[list[ComparableListing], int]:
        if not self.config.remove_outliers or len(comparables) < 4:
            return comparables, 0
        prices = sorted(comparable.price for comparable in comparables)
        quartiles = statistics.quantiles(prices, n=4, method="inclusive")
        q1, q3 = quartiles[0], quartiles[2]
        iqr = q3 - q1
        low = q1 - self.config.iqr_multiplier * iqr
        high = q3 + self.config.iqr_multiplier * iqr
        kept = [c for c in comparables if low <= c.price <= high]
        if not kept:
            return comparables, 0
        return kept, len(comparables) - len(kept)

    def _confidence(self, prices: list[float]) -> float:
        count = len(prices)
        if count == 0:
            return 0.0
        count_conf = min(1.0, count / self.config.confidence_full_count)
        mean = statistics.fmean(prices)
        if count > 1 and mean > 0:
            spread = (max(prices) - min(prices)) / mean
            consistency = 1.0 / (1.0 + spread)
        else:
            consistency = 1.0
        return round(count_conf * consistency, 4)

    def _empty_result(self, *, currency: str | None) -> MarketPrice:
        return MarketPrice(
            estimated_market_price=None,
            confidence_score=0.0,
            comparable_count=0,
            min_price=None,
            max_price=None,
            median_price=None,
            mean_price=None,
            currency=currency,
            strategy=self._strategy.name,
            outliers_removed=0,
            reliable=False,
        )
