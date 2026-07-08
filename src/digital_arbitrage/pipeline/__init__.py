"""End-to-end orchestration.

Wires every analytical stage into one call (Scanner -> Normalization -> Product
Matching -> Deduplication -> Market Pricing -> Opportunity) and exposes it via
``ArbitragePipeline.analyze(query)`` and the ``arb`` CLI. Deterministic and
provider-agnostic; mock providers by default (no scraping/AI/APIs, ADR-009), with
an opt-in live provider such as ``ebay_browse`` for real, read-only marketplace
scans (ADR-019/ADR-020).

Quick start::

    from digital_arbitrage.pipeline import ArbitragePipeline

    result = ArbitragePipeline().analyze("rtx 4090")
    for item in result.items:
        print(item.recommendation, item.title, item.roi_percentage)
"""

from __future__ import annotations

from .config_file import ConfigError, load_pipeline_config
from .models import PipelineItemResult, PipelineResult
from .pipeline import ArbitragePipeline, PipelineConfig

__all__ = [
    "ArbitragePipeline",
    "ConfigError",
    "PipelineConfig",
    "PipelineItemResult",
    "PipelineResult",
    "load_pipeline_config",
]
