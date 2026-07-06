"""Data models for market price estimation.

:class:`ComparableListing` is the priced input the estimator works from (a
normalized listing plus the price/currency/weight used for valuation).
:class:`MarketPrice` is the deterministic output: an estimate plus the summary
statistics and confidence that justify it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.models import NormalizedListing


@dataclass(slots=True, frozen=True)
class ComparableListing:
    """A single priced data point used to value a product."""

    listing: NormalizedListing
    price: float
    currency: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError("price must be non-negative")
        if self.weight <= 0:
            raise ValueError("weight must be positive")

    @classmethod
    def try_from(
        cls, listing: NormalizedListing, *, weight: float = 1.0
    ) -> ComparableListing | None:
        """Build a comparable from a listing, or ``None`` if it has no price."""
        price = listing.source.price
        if price is None:
            return None
        currency = listing.currency or listing.source.currency
        return cls(listing=listing, price=float(price), currency=currency, weight=weight)


@dataclass(slots=True, frozen=True)
class MarketPrice:
    """The estimated market value of a product with supporting statistics."""

    estimated_market_price: float | None
    confidence_score: float
    comparable_count: int
    min_price: float | None
    max_price: float | None
    median_price: float | None
    mean_price: float | None
    currency: str | None
    strategy: str
    outliers_removed: int = 0
    reliable: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"confidence_score must be in [0, 1], got {self.confidence_score}")
        if self.comparable_count < 0:
            raise ValueError("comparable_count must be non-negative")

    @property
    def is_priced(self) -> bool:
        """True when an estimate could be produced."""
        return self.estimated_market_price is not None
