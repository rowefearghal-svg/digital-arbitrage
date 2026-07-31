"""The end-to-end arbitrage pipeline.

``ArbitragePipeline`` wires every stage into a single call::

    Scanner -> Normalization -> Product Matching -> Deduplication
            -> Market Pricing -> Opportunity

``analyze(query)`` returns a :class:`PipelineResult` whose items are ranked by
recommendation, then ROI, then confidence. Deterministic and provider-agnostic:
by default it uses the mock providers (no scraping, AI/ML, or external APIs), but
a live provider (e.g. ``ebay_browse``) can be enabled via configuration, in which
case the scan makes a real, read-only API call using credentials from the
environment. See ADR-019/ADR-020.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..classification import ClassificationConfig, ListingClassifier
from ..deduplication import DeduplicationConfig, Deduplicator
from ..market_pricing import MarketPriceEstimator, MarketPricingConfig
from ..normalization import NormalizationConfig, Normalizer
from ..opportunity import (
    OpportunityAnalyzer,
    OpportunityConfig,
    Recommendation,
    RecommendationScorer,
    ScoringConfig,
)
from ..product_scanner import Scanner, ScannerConfig
from ..providers.live import LiveProviderSetting, build_scanner_from_config
from .models import PipelineItemResult, PipelineResult
from .pue_shadow import PueShadowCaseResult, ShadowConfig, run_pue_shadow

#: Sort priority for recommendations (higher is better).
_RECOMMENDATION_RANK: dict[Recommendation, int] = {
    Recommendation.STRONG_BUY: 3,
    Recommendation.BUY: 2,
    Recommendation.WATCH: 1,
    Recommendation.REJECT: 0,
}


def recommendation_rank(recommendation: Recommendation) -> int:
    """Ordinal priority of a recommendation (STRONG_BUY highest, REJECT lowest)."""
    return _RECOMMENDATION_RANK[recommendation]


def _sort_key(item: PipelineItemResult) -> tuple[int, float, float, str]:
    """Rank by recommendation, then ROI, then confidence (all descending)."""
    roi = item.roi_percentage if item.roi_percentage is not None else float("-inf")
    return (
        -recommendation_rank(item.recommendation),
        -roi,
        -item.confidence_score,
        item.group.canonical.listing_id,
    )


@dataclass(slots=True, frozen=True)
class PipelineConfig:
    """Configuration for every stage of the pipeline."""

    scanner_config: ScannerConfig | None = None
    normalization_config: NormalizationConfig | None = None
    classification_config: ClassificationConfig | None = None
    deduplication_config: DeduplicationConfig | None = None
    pricing_config: MarketPricingConfig | None = None
    opportunity_config: OpportunityConfig | None = None
    scoring_config: ScoringConfig | None = None
    #: Optional per-provider result cap passed to the scanner.
    scan_limit: int | None = None
    #: Per-live-provider settings (enable flag + config), keyed by provider name.
    #: Empty by default, so the pipeline is mock-only unless a live provider is
    #: configured. Credentials are read from the environment, never from here.
    live_provider_settings: Mapping[str, LiveProviderSetting] = field(default_factory=dict)
    #: Optional Product Understanding Engine shadow-mode configuration (see
    #: docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md section 5.3).
    #: Disabled by default: ``None`` and ``ShadowConfig(enabled=False)`` are
    #: both complete no-ops that never alter this pipeline's output.
    pue_shadow_config: ShadowConfig | None = None


class ArbitragePipeline:
    """Run the full scan-to-opportunity analysis for a query."""

    def __init__(
        self, config: PipelineConfig | None = None, *, scanner: Scanner | None = None
    ) -> None:
        self.config = config or PipelineConfig()
        # A pre-built scanner can be injected (e.g. one wired to a fake
        # ``Transport``) so the whole pipeline can be exercised end-to-end
        # without any network call; otherwise it is built from the config,
        # mixing mock and (optionally) live providers.
        self._scanner = scanner or build_scanner_from_config(
            self.config.scanner_config,
            self.config.live_provider_settings,
        )
        self._normalizer = Normalizer(config=self.config.normalization_config)
        self._classifier = ListingClassifier(self.config.classification_config)
        self._deduplicator = Deduplicator(self.config.deduplication_config)
        self._estimator = MarketPriceEstimator(self.config.pricing_config)
        self._analyzer = OpportunityAnalyzer(self.config.opportunity_config)
        self._scorer = RecommendationScorer(self.config.scoring_config)
        #: PUE shadow-mode output from the most recent ``analyze()`` call, if
        #: shadow mode is enabled (see ``PipelineConfig.pue_shadow_config``).
        #: Each element is a ``PueShadowCaseResult`` (ReasoningRecord +
        #: ProductUnderstandingResult + optional classifier/PUE comparison).
        #: Never influences ``PipelineResult``. This is the authoritative
        #: attribute as of Sprint 2 Task 2 (``run_pue_shadow`` now returns
        #: ``PueShadowCaseResult``, not bare ``ReasoningRecord``).
        self.last_pue_shadow_results: tuple[PueShadowCaseResult, ...] = ()
        #: Compatibility projection of ``last_pue_shadow_results`` restoring
        #: this attribute's original Sprint 1 meaning: a tuple of the
        #: ``ReasoningRecord`` for each shadow-processed listing (never the
        #: ``PueShadowCaseResult`` envelope itself). Sprint 2 pre-merge
        #: correction: before this fix, this attribute silently held
        #: ``PueShadowCaseResult`` objects while its name and Sprint 1
        #: history implied bare records - a caller doing
        #: ``record.decision`` on an element would have broken. Prefer
        #: ``last_pue_shadow_results`` in new code.
        self.last_pue_shadow_records: tuple = ()

    def analyze(self, query: str) -> PipelineResult:
        """Scan, normalize, group, price, and score opportunities for ``query``."""
        listings = self._scanner.scan(query, limit=self.config.scan_limit)
        normalized = self._normalizer.normalize_many(listings)
        # Classify every listing by title (see ADR-022). This is additive: it
        # annotates each listing's ``classification`` and never drops any, so
        # deduplication and later stages are unchanged. How classifications
        # affect scoring is deferred to a future sprint.
        search_profile = self._classifier.profile_for(query)
        self._classifier.classify_many(normalized, search_profile)

        # Product Understanding Engine shadow execution (see
        # docs/architecture/PUE_v0.1_VERTICAL_SLICE_SPECIFICATION.md section
        # 5.3). Disabled by default; when enabled, runs after normalization
        # and persists its own output without altering anything below this
        # line. A PUE exception never reaches this pipeline (see
        # ``run_pue_shadow``), so ``self.last_pue_shadow_results`` may be
        # empty even when shadow mode is enabled.
        self.last_pue_shadow_results = run_pue_shadow(
            normalized,
            config=self.config.pue_shadow_config or ShadowConfig(enabled=False),
            search_profile=search_profile,
        )
        self.last_pue_shadow_records = tuple(
            r.reasoning_record for r in self.last_pue_shadow_results
        )

        deduped = self._deduplicator.deduplicate(normalized)

        items = []
        for group in deduped.groups:
            market_price = self._estimator.estimate_from_group(group)
            opportunity = self._analyzer.analyze(group.canonical, market_price)
            breakdown = self._scorer.score(opportunity, market_price)
            items.append(
                PipelineItemResult(
                    group=group,
                    market_price=market_price,
                    opportunity=opportunity,
                    score=breakdown.score,
                    risk_score=breakdown.risk_signal,
                )
            )

        ranked = tuple(sorted(items, key=_sort_key))
        return PipelineResult(
            query=query,
            items=ranked,
            total_listings_scanned=len(listings),
            total_groups=deduped.total_groups,
        )
