"""Row models for persisted scan history.

:class:`StoredRun` is the summary of one saved :class:`PipelineResult`;
:class:`StoredOpportunity` is a single opportunity snapshot belonging to a run.
Both are plain, fully typed dataclasses so callers never touch raw
:class:`sqlite3.Row` objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class StoredRun:
    """Summary of a persisted scan run."""

    run_id: int
    query: str
    created_at: str
    config_summary: str
    total_listings_scanned: int
    total_groups: int
    total_opportunities: int

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view of the run summary."""
        return {
            "run_id": self.run_id,
            "query": self.query,
            "created_at": self.created_at,
            "config_summary": self.config_summary,
            "total_listings_scanned": self.total_listings_scanned,
            "total_groups": self.total_groups,
            "total_opportunities": self.total_opportunities,
        }


@dataclass(slots=True, frozen=True)
class StoredOpportunity:
    """A single opportunity snapshot belonging to a stored run."""

    id: int
    run_id: int
    rank: int
    title: str
    provider: str
    currency: str
    asking_price: float | None
    estimated_market_price: float | None
    roi_percentage: float | None
    net_profit: float | None
    confidence_score: float
    risk_score: float
    recommendation_score: float
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable view of the opportunity snapshot."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "rank": self.rank,
            "title": self.title,
            "provider": self.provider,
            "currency": self.currency,
            "asking_price": self.asking_price,
            "estimated_market_price": self.estimated_market_price,
            "roi_percentage": self.roi_percentage,
            "net_profit": self.net_profit,
            "confidence_score": self.confidence_score,
            "risk_score": self.risk_score,
            "recommendation_score": self.recommendation_score,
            "recommendation": self.recommendation,
        }
