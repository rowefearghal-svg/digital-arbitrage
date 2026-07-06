"""End-to-end orchestration.

Wires every analytical stage into one call (Scanner -> Normalization -> Product
Matching -> Deduplication -> Market Pricing -> Opportunity) and exposes it via
``ArbitragePipeline.analyze(query)`` and the ``arb`` CLI. Deterministic and
provider-agnostic; mock providers only, no scraping/AI/APIs (ADR-009).

Quick start::

    from digital_arbitrage.pipeline import ArbitragePipeline

    result = ArbitragePipeline().analyze("rtx 4090")
    for item in result.items:
        print(item.recommendation, item.title, item.roi_percentage)
"""

from __future__ import annotations

from .models import PipelineItemResult, PipelineResult
from .pipeline import ArbitragePipeline, PipelineConfig

__all__ = [
    "ArbitragePipeline",
    "PipelineConfig",
    "PipelineItemResult",
    "PipelineResult",
]
