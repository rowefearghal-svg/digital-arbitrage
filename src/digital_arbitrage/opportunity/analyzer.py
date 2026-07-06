"""The profit / opportunity analyzer.

``OpportunityAnalyzer`` is the decision stage of the pipeline (Scanner ->
Normalization -> Product Matching -> Deduplication -> Market Pricing ->
Opportunity). Given a listing (its asking price) and a :class:`MarketPrice`
(the estimated resale value), it computes a conservative, itemized profit
estimate and a :class:`Recommendation`. Deterministic; no scraping, AI, or
external APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..market_pricing.models import MarketPrice
from ..normalization.models import NormalizedListing
from ..product_scanner import Listing
from .models import CostBreakdown, Opportunity, ProfitEstimate, Recommendation


@dataclass(slots=True, frozen=True)
class OpportunityConfig:
    """Cost model and decision thresholds (conservative by default)."""

    # -- resale cost model ------------------------------------------------- #
    #: Marketplace commission as a fraction of the resale price.
    marketplace_fee_rate: float = 0.10
    #: Payment processing as a fraction of the resale price...
    payment_fee_rate: float = 0.029
    #: ...plus a flat per-transaction payment fee.
    payment_fee_flat: float = 0.35
    #: Flat shipping cost.
    shipping_cost: float = 10.0
    #: Flat packaging cost.
    packaging_cost: float = 2.0
    #: Risk allowance as a fraction of the resale price.
    buffer_rate: float = 0.05
    #: Flat risk allowance added on top of ``buffer_rate``.
    buffer_flat: float = 0.0
    #: VAT/tax placeholder: fraction of gross profit (margin scheme). Default off.
    tax_rate: float = 0.0

    # -- decision thresholds ---------------------------------------------- #
    #: ROI (fraction) required for STRONG_BUY / BUY / WATCH.
    strong_buy_roi: float = 0.30
    buy_roi: float = 0.15
    watch_roi: float = 0.05
    #: Net profit must strictly exceed this floor to be anything but REJECT.
    min_net_profit: float = 0.0
    #: Confidence below this caps the recommendation at WATCH.
    min_confidence: float = 0.40
    #: Confidence at/above this is required for STRONG_BUY (else capped at BUY).
    strong_buy_confidence: float = 0.60
    #: Reject when the listing and market-price currencies differ (no FX).
    require_same_currency: bool = True

    def __post_init__(self) -> None:
        for name in ("marketplace_fee_rate", "payment_fee_rate", "buffer_rate", "tax_rate"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        for name in (
            "payment_fee_flat",
            "shipping_cost",
            "packaging_cost",
            "buffer_flat",
            "min_net_profit",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if not 0.0 <= self.watch_roi <= self.buy_roi <= self.strong_buy_roi:
            raise ValueError("ROI thresholds must satisfy 0 <= watch <= buy <= strong_buy")
        for name in ("min_confidence", "strong_buy_confidence"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")


class OpportunityAnalyzer:
    """Turn a listing + market price into a scored :class:`Opportunity`."""

    def __init__(self, config: OpportunityConfig | None = None) -> None:
        self.config = config or OpportunityConfig()

    # -- public API -------------------------------------------------------- #
    def analyze(
        self, listing: Listing | NormalizedListing, market_price: MarketPrice
    ) -> Opportunity:
        """Analyze a single listing against its estimated market price."""
        base = listing.source if isinstance(listing, NormalizedListing) else listing
        confidence = market_price.confidence_score

        if base.price is None:
            return self._rejected(base, confidence, "listing has no asking price")
        sale = market_price.estimated_market_price
        if sale is None:
            return self._rejected(base, confidence, "no market price estimate available")
        if (
            self.config.require_same_currency
            and market_price.currency is not None
            and base.currency != market_price.currency
        ):
            return self._rejected(
                base,
                confidence,
                f"currency mismatch: asking {base.currency} vs market {market_price.currency}",
            )

        asking = round(float(base.price), 2)
        sale = round(float(sale), 2)
        costs = self._build_costs(sale=sale, gross_profit=sale - asking)
        profit = ProfitEstimate(asking_price=asking, estimated_market_price=sale, costs=costs)
        recommendation, reasons = self._recommend(profit, confidence)

        return Opportunity(
            listing_id=base.listing_id,
            title=base.title,
            provider=base.provider,
            currency=base.currency,
            recommendation=recommendation,
            confidence_score=confidence,
            profit=profit,
            reasons=reasons,
        )

    # -- internals --------------------------------------------------------- #
    def _build_costs(self, *, sale: float, gross_profit: float) -> CostBreakdown:
        cfg = self.config
        return CostBreakdown(
            marketplace_fee=round(sale * cfg.marketplace_fee_rate, 2),
            payment_fee=round(sale * cfg.payment_fee_rate + cfg.payment_fee_flat, 2),
            shipping_cost=round(cfg.shipping_cost, 2),
            packaging_cost=round(cfg.packaging_cost, 2),
            buffer=round(sale * cfg.buffer_rate + cfg.buffer_flat, 2),
            tax=round(max(0.0, gross_profit) * cfg.tax_rate, 2),
        )

    def _recommend(
        self, profit: ProfitEstimate, confidence: float
    ) -> tuple[Recommendation, tuple[str, ...]]:
        cfg = self.config
        reasons = [
            f"net profit {profit.net_profit:.2f} "
            f"({profit.roi_percentage:.1f}% ROI, {profit.margin_percentage:.1f}% margin); "
            f"costs {profit.costs.total:.2f}"
        ]

        if profit.net_profit <= cfg.min_net_profit:
            reasons.append(f"net profit <= floor {cfg.min_net_profit:.2f} -> REJECT")
            return Recommendation.REJECT, tuple(reasons)

        roi = profit.roi_percentage / 100
        if roi >= cfg.strong_buy_roi:
            tier = Recommendation.STRONG_BUY
        elif roi >= cfg.buy_roi:
            tier = Recommendation.BUY
        elif roi >= cfg.watch_roi:
            tier = Recommendation.WATCH
        else:
            reasons.append(f"ROI {profit.roi_percentage:.1f}% below watch threshold -> REJECT")
            return Recommendation.REJECT, tuple(reasons)

        if tier is Recommendation.STRONG_BUY and confidence < cfg.strong_buy_confidence:
            tier = Recommendation.BUY
            reasons.append(
                f"confidence {confidence:.2f} < {cfg.strong_buy_confidence:.2f} -> capped at BUY"
            )
        if (
            tier in (Recommendation.STRONG_BUY, Recommendation.BUY)
            and confidence < cfg.min_confidence
        ):
            tier = Recommendation.WATCH
            reasons.append(
                f"confidence {confidence:.2f} < {cfg.min_confidence:.2f} -> capped at WATCH"
            )

        reasons.append(f"ROI {profit.roi_percentage:.1f}% -> {tier.value}")
        return tier, tuple(reasons)

    def _rejected(self, base: Listing, confidence: float, reason: str) -> Opportunity:
        return Opportunity(
            listing_id=base.listing_id,
            title=base.title,
            provider=base.provider,
            currency=base.currency,
            recommendation=Recommendation.REJECT,
            confidence_score=confidence,
            profit=None,
            reasons=(reason,),
        )
