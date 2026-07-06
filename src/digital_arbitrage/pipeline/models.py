"""Result models for the end-to-end pipeline.

A :class:`PipelineItemResult` bundles everything computed for one deduplicated
product group: the group, its estimated :class:`MarketPrice`, and the scored
:class:`Opportunity`. A :class:`PipelineResult` is the full, ranked run output
plus run-level counts, with JSON-friendly ``to_dict`` serialization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..deduplication.models import DuplicateGroup
from ..market_pricing.models import MarketPrice
from ..opportunity.models import Opportunity, Recommendation


@dataclass(slots=True, frozen=True)
class PipelineItemResult:
    """The full analysis for a single product group."""

    group: DuplicateGroup
    market_price: MarketPrice
    opportunity: Opportunity

    @property
    def recommendation(self) -> Recommendation:
        return self.opportunity.recommendation

    @property
    def title(self) -> str:
        return self.opportunity.title

    @property
    def provider(self) -> str:
        return self.opportunity.provider

    @property
    def roi_percentage(self) -> float | None:
        return self.opportunity.roi_percentage

    @property
    def net_profit(self) -> float | None:
        return self.opportunity.net_profit

    @property
    def confidence_score(self) -> float:
        return self.opportunity.confidence_score

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view of this item."""
        opp = self.opportunity
        return {
            "recommendation": opp.recommendation.value,
            "title": opp.title,
            "provider": opp.provider,
            "currency": opp.currency,
            "asking_price": opp.asking_price,
            "estimated_market_price": opp.estimated_market_price,
            "gross_profit": opp.gross_profit,
            "net_profit": opp.net_profit,
            "roi_percentage": opp.roi_percentage,
            "margin_percentage": opp.margin_percentage,
            "confidence_score": round(opp.confidence_score, 4),
            "comparable_count": self.market_price.comparable_count,
            "group_size": self.group.size,
            "fingerprint": self.group.fingerprint,
            "reasons": list(opp.reasons),
        }


@dataclass(slots=True, frozen=True)
class PipelineResult:
    """The ranked output of an :class:`ArbitragePipeline` run."""

    query: str
    items: tuple[PipelineItemResult, ...]
    total_listings_scanned: int
    total_groups: int

    @property
    def actionable(self) -> tuple[PipelineItemResult, ...]:
        """Items recommended BUY or STRONG_BUY."""
        return tuple(item for item in self.items if item.opportunity.is_actionable)

    def counts_by_recommendation(self) -> dict[str, int]:
        """Count of items per recommendation category."""
        counts = {rec.value: 0 for rec in Recommendation}
        for item in self.items:
            counts[item.recommendation.value] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view of the whole run."""
        return {
            "query": self.query,
            "total_listings_scanned": self.total_listings_scanned,
            "total_groups": self.total_groups,
            "counts_by_recommendation": self.counts_by_recommendation(),
            "items": [item.to_dict() for item in self.items],
        }
