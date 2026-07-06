"""Deterministic recommendation scoring.

Where the :class:`Recommendation` is a *categorical* verdict (STRONG_BUY / BUY /
WATCH / REJECT), the recommendation *score* is a single continuous 0-100 quality
number that ranks opportunities within and across categories. It blends four
signals - ROI, net profit, confidence, and risk - each normalized to ``[0, 1]``
and combined with configurable weights from a single :class:`ScoringConfig`.

The maths is pure and deterministic: identical inputs always yield an identical
score, and there is no scraping, AI/ML, or external state (ADR-012). The class
is intentionally small and side-effect free so a future ML-based scorer can be
dropped in behind the same ``score`` interface.

Scoring in one line::

    weighted = w_roi*roi + w_profit*profit + w_conf*confidence - w_risk*risk
    score    = 100 * (weighted + w_risk) / (w_roi + w_profit + w_conf + w_risk)

which maps the worst case (all upside 0, full risk) to 0 and the best case (all
upside 1, no risk) to 100.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..market_pricing.models import MarketPrice
from .models import Opportunity


def _clamp01(value: float) -> float:
    """Clamp ``value`` into the closed unit interval ``[0, 1]``."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclass(slots=True, frozen=True)
class ScoringConfig:
    """Weights and reference points for :class:`RecommendationScorer`.

    This is the single source of truth for every tunable scoring value; nothing
    is hard-coded elsewhere. Weights need not sum to 1 - the score is normalized
    by their total - but at least one must be positive.
    """

    # -- component weights ------------------------------------------------- #
    #: Weight of the (normalized) ROI signal.
    roi_weight: float = 0.35
    #: Weight of the (normalized) net-profit signal.
    net_profit_weight: float = 0.25
    #: Weight of the confidence signal.
    confidence_weight: float = 0.25
    #: Weight of the risk *penalty* (subtracted from the score).
    risk_weight: float = 0.15

    # -- normalization reference points ------------------------------------ #
    #: ROI percentage that maps to a full (1.0) ROI signal.
    roi_reference: float = 30.0
    #: Net profit (listing currency) that maps to a full (1.0) profit signal.
    net_profit_reference: float = 200.0
    #: Price spread (``(max - min) / median``) that maps to full dispersion risk.
    risk_dispersion_reference: float = 1.0
    #: Comparable count at/above which coverage contributes no risk.
    risk_full_comparables: int = 5

    def __post_init__(self) -> None:
        for name in (
            "roi_weight",
            "net_profit_weight",
            "confidence_weight",
            "risk_weight",
        ):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name} must be non-negative")
        if self.total_weight <= 0.0:
            raise ValueError("at least one weight must be positive")
        for name in ("roi_reference", "net_profit_reference", "risk_dispersion_reference"):
            if getattr(self, name) <= 0.0:
                raise ValueError(f"{name} must be positive")
        if self.risk_full_comparables < 1:
            raise ValueError("risk_full_comparables must be >= 1")

    @property
    def total_weight(self) -> float:
        """Denominator used to normalize the weighted sum onto ``[0, 1]``."""
        return self.roi_weight + self.net_profit_weight + self.confidence_weight + self.risk_weight


@dataclass(slots=True, frozen=True)
class ScoreBreakdown:
    """The 0-100 score plus the normalized signals that produced it."""

    score: float
    roi_signal: float
    profit_signal: float
    confidence_signal: float
    risk_signal: float

    def to_dict(self) -> dict[str, float]:
        """JSON-serializable view of the score and its signals."""
        return {
            "score": self.score,
            "roi_signal": self.roi_signal,
            "profit_signal": self.profit_signal,
            "confidence_signal": self.confidence_signal,
            "risk_signal": self.risk_signal,
        }


class RecommendationScorer:
    """Combine ROI, net profit, confidence, and risk into a 0-100 score."""

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig()

    # -- public API -------------------------------------------------------- #
    def score(
        self, opportunity: Opportunity, market_price: MarketPrice | None = None
    ) -> ScoreBreakdown:
        """Score an :class:`Opportunity`, deriving risk from ``market_price``.

        ROI, net profit, and confidence are read from the opportunity. Risk is
        estimated from the market price's price dispersion and comparable
        coverage when available; without a market price it falls back to
        ``1 - confidence`` so a scorer used in isolation still penalizes
        low-confidence deals.
        """
        cfg = self.config
        roi = opportunity.roi_percentage
        net_profit = opportunity.net_profit
        confidence = _clamp01(opportunity.confidence_score)

        roi_signal = _clamp01(roi / cfg.roi_reference) if roi is not None else 0.0
        profit_signal = (
            _clamp01(net_profit / cfg.net_profit_reference) if net_profit is not None else 0.0
        )
        if market_price is not None:
            risk_signal = self.estimate_risk(market_price)
        else:
            risk_signal = _clamp01(1.0 - confidence)

        return self.score_signals(
            roi_signal=roi_signal,
            profit_signal=profit_signal,
            confidence_signal=confidence,
            risk_signal=risk_signal,
        )

    def score_signals(
        self,
        *,
        roi_signal: float,
        profit_signal: float,
        confidence_signal: float,
        risk_signal: float,
    ) -> ScoreBreakdown:
        """Combine pre-normalized ``[0, 1]`` signals into a :class:`ScoreBreakdown`."""
        cfg = self.config
        roi_s = _clamp01(roi_signal)
        profit_s = _clamp01(profit_signal)
        conf_s = _clamp01(confidence_signal)
        risk_s = _clamp01(risk_signal)

        weighted = (
            cfg.roi_weight * roi_s
            + cfg.net_profit_weight * profit_s
            + cfg.confidence_weight * conf_s
            - cfg.risk_weight * risk_s
        )
        # Shift by risk_weight so the minimum (full risk, no upside) maps to 0,
        # then normalize by the total weight so the maximum maps to 1.
        normalized = (weighted + cfg.risk_weight) / cfg.total_weight
        score = round(_clamp01(normalized) * 100.0, 2)
        return ScoreBreakdown(
            score=score,
            roi_signal=round(roi_s, 4),
            profit_signal=round(profit_s, 4),
            confidence_signal=round(conf_s, 4),
            risk_signal=round(risk_s, 4),
        )

    def estimate_risk(self, market_price: MarketPrice) -> float:
        """Estimate risk in ``[0, 1]`` from a market price (higher is riskier).

        Two deterministic components are averaged:

        * **Dispersion** - a wide price spread relative to the median implies a
          noisy, uncertain valuation. Measured as ``(max - min) / median`` and
          scaled by ``risk_dispersion_reference``.
        * **Coverage** - few comparables means a thin, fragile estimate. Scaled
          linearly to zero once ``risk_full_comparables`` is reached.

        An unpriced market price is maximally risky (``1.0``).
        """
        cfg = self.config
        if not market_price.is_priced or market_price.median_price in (None, 0):
            return 1.0

        median = market_price.median_price
        low = market_price.min_price
        high = market_price.max_price
        if median is None or low is None or high is None or median <= 0.0:
            dispersion_risk = 1.0
        else:
            dispersion_risk = _clamp01((high - low) / median / cfg.risk_dispersion_reference)

        coverage_risk = _clamp01(
            (cfg.risk_full_comparables - market_price.comparable_count) / cfg.risk_full_comparables
        )
        return _clamp01((dispersion_risk + coverage_risk) / 2.0)
