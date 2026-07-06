"""Data models for the profit / opportunity engine.

The chain is: :class:`CostBreakdown` (what selling costs) feeds
:class:`ProfitEstimate` (the money maths), which is wrapped by
:class:`Opportunity` (the money maths plus a :class:`Recommendation` and the
reasons behind it). Every figure is deterministic and derived from explicit
inputs - no scraping, AI, or external calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Recommendation(StrEnum):
    """The categorical action suggested for an opportunity."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WATCH = "watch"
    REJECT = "reject"


@dataclass(slots=True, frozen=True)
class CostBreakdown:
    """Itemized costs incurred to resell an item, in the listing's currency."""

    marketplace_fee: float = 0.0
    payment_fee: float = 0.0
    shipping_cost: float = 0.0
    packaging_cost: float = 0.0
    buffer: float = 0.0
    tax: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "marketplace_fee",
            "payment_fee",
            "shipping_cost",
            "packaging_cost",
            "buffer",
            "tax",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")

    @property
    def total(self) -> float:
        """Sum of all cost components."""
        return round(
            self.marketplace_fee
            + self.payment_fee
            + self.shipping_cost
            + self.packaging_cost
            + self.buffer
            + self.tax,
            2,
        )


@dataclass(slots=True, frozen=True)
class ProfitEstimate:
    """Profit maths for buying at ``asking_price`` and reselling at market."""

    asking_price: float
    estimated_market_price: float
    costs: CostBreakdown

    @property
    def gross_profit(self) -> float:
        """Market price minus asking price, before costs."""
        return round(self.estimated_market_price - self.asking_price, 2)

    @property
    def net_profit(self) -> float:
        """Gross profit after all resale costs."""
        return round(self.estimated_market_price - self.asking_price - self.costs.total, 2)

    @property
    def roi_percentage(self) -> float:
        """Net profit as a percentage of the capital deployed (asking price)."""
        if self.asking_price <= 0:
            return 0.0
        return round(self.net_profit / self.asking_price * 100, 2)

    @property
    def margin_percentage(self) -> float:
        """Net profit as a percentage of the resale (market) price."""
        if self.estimated_market_price <= 0:
            return 0.0
        return round(self.net_profit / self.estimated_market_price * 100, 2)


@dataclass(slots=True, frozen=True)
class Opportunity:
    """A scored arbitrage opportunity for a single listing."""

    listing_id: str
    title: str
    provider: str
    currency: str
    recommendation: Recommendation
    confidence_score: float
    profit: ProfitEstimate | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_score <= 1.0:
            raise ValueError(f"confidence_score must be in [0, 1], got {self.confidence_score}")

    @property
    def asking_price(self) -> float | None:
        return self.profit.asking_price if self.profit else None

    @property
    def estimated_market_price(self) -> float | None:
        return self.profit.estimated_market_price if self.profit else None

    @property
    def gross_profit(self) -> float | None:
        return self.profit.gross_profit if self.profit else None

    @property
    def net_profit(self) -> float | None:
        return self.profit.net_profit if self.profit else None

    @property
    def roi_percentage(self) -> float | None:
        return self.profit.roi_percentage if self.profit else None

    @property
    def margin_percentage(self) -> float | None:
        return self.profit.margin_percentage if self.profit else None

    @property
    def is_actionable(self) -> bool:
        """True when the recommendation is BUY or STRONG_BUY."""
        return self.recommendation in (Recommendation.BUY, Recommendation.STRONG_BUY)
