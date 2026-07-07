"""Compare two saved scan runs and categorise what changed.

Opportunities are matched by a stable identity key (provider + normalized title)
and classified as new, disappeared, unchanged, improved, or worsened based on
recommendation score, ROI, net profit, confidence, and risk (ADR-014). Standard
library only.

Quick start::

    from digital_arbitrage.comparison import compare_runs
    from digital_arbitrage.persistence import ResultStore

    with ResultStore("history.db") as store:
        old, new = store.get_run(1), store.get_run(2)
        diff = compare_runs(old, store.list_opportunities(1),
                            new, store.list_opportunities(2))
    print(diff.counts_by_category())
"""

from __future__ import annotations

from .compare import ComparisonConfig, compare_runs, identity_key
from .models import (
    ChangeCategory,
    MetricDelta,
    OpportunityDelta,
    RunComparison,
)

__all__ = [
    "ChangeCategory",
    "ComparisonConfig",
    "MetricDelta",
    "OpportunityDelta",
    "RunComparison",
    "compare_runs",
    "identity_key",
]
