"""The end-to-end arbitrage pipeline.

``ArbitragePipeline`` wires every stage into a single call::

    Scanner -> Normalization -> Product Matching -> Deduplication
            -> Market Pricing -> Opportunity

``analyze(query)`` returns a :class:`PipelineResult` whose items are ranked by
recommendation, then ROI, then confidence. Deterministic, provider-agnostic, and
built on the existing mock providers - no scraping, AI/ML, or external APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..deduplication import DeduplicationConfig, Deduplicator
from ..market_pricing import MarketPriceEstimator, MarketPricingConfig
from ..normalization import NormalizationConfig, Normalizer
from ..opportunity import OpportunityAnalyzer, OpportunityConfig, Recommendation
from ..product_scanner import ScannerConfig, build_scanner
from .models import PipelineItemResult, PipelineResult

#: Sort priority for recommendations (higher is better).
_RECOMMENDATION_RANK: dict[Recommendation, int] = {
    Recommendation.STRONG_BUY: 3,
    Recommendation.BUY: 2,
    Recommendation.WATCH: 1,
    Recommendation.REJECT: 0,
}


def _sort_key(item: PipelineItemResult) -> tuple[int, float, float, str]:
    """Rank by recommendation, then ROI, then confidence (all descending)."""
    roi = item.roi_percentage if item.roi_percentage is not None else float("-inf")
    return (
        -_RECOMMENDATION_RANK[item.recommendation],
        -roi,
        -item.confidence_score,
        item.group.canonical.listing_id,
    )


@dataclass(slots=True, frozen=True)
class PipelineConfig:
    """Configuration for every stage of the pipeline."""

    scanner_config: ScannerConfig | None = None
    normalization_config: NormalizationConfig | None = None
    deduplication_config: DeduplicationConfig | None = None
    pricing_config: MarketPricingConfig | None = None
    opportunity_config: OpportunityConfig | None = None
    #: Optional per-provider result cap passed to the scanner.
    scan_limit: int | None = None


class ArbitragePipeline:
    """Run the full scan-to-opportunity analysis for a query."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self._scanner = build_scanner(self.config.scanner_config)
        self._normalizer = Normalizer(config=self.config.normalization_config)
        self._deduplicator = Deduplicator(self.config.deduplication_config)
        self._estimator = MarketPriceEstimator(self.config.pricing_config)
        self._analyzer = OpportunityAnalyzer(self.config.opportunity_config)

    def analyze(self, query: str) -> PipelineResult:
        """Scan, normalize, group, price, and score opportunities for ``query``."""
        listings = self._scanner.scan(query, limit=self.config.scan_limit)
        normalized = self._normalizer.normalize_many(listings)
        deduped = self._deduplicator.deduplicate(normalized)

        items = []
        for group in deduped.groups:
            market_price = self._estimator.estimate_from_group(group)
            opportunity = self._analyzer.analyze(group.canonical, market_price)
            items.append(
                PipelineItemResult(group=group, market_price=market_price, opportunity=opportunity)
            )

        ranked = tuple(sorted(items, key=_sort_key))
        return PipelineResult(
            query=query,
            items=ranked,
            total_listings_scanned=len(listings),
            total_groups=deduped.total_groups,
        )
