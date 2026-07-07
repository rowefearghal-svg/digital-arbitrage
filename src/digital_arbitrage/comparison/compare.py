"""Deterministic comparison of two saved scan runs.

Opportunities are matched across runs by a stable *identity key* derived from the
best fields available on a snapshot: the provider plus a normalized title
(lower-cased, whitespace-collapsed). Matched pairs are classified as unchanged,
improved, or worsened by walking a fixed priority of metrics; unmatched
opportunities are new (only in the newer run) or disappeared (only in the older).
Standard library only - no external dependencies.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..persistence import StoredOpportunity, StoredRun
from .models import (
    ChangeCategory,
    MetricDelta,
    OpportunityDelta,
    RunComparison,
)

_MetricGetter = Callable[[StoredOpportunity], float | None]

# Metrics that define improvement/worsening, in decisive priority order. The
# first metric whose change exceeds the epsilon settles the verdict; the rest
# act as tie-breakers. ``recommendation_score`` leads because it already blends
# ROI, profit, confidence, and risk (ADR-012).
_METRICS: tuple[tuple[str, bool, _MetricGetter], ...] = (
    ("recommendation_score", True, lambda o: o.recommendation_score),
    ("roi_percentage", True, lambda o: o.roi_percentage),
    ("net_profit", True, lambda o: o.net_profit),
    ("confidence_score", True, lambda o: o.confidence_score),
    ("risk_score", False, lambda o: o.risk_score),
)

# Ordering of the rendered/serialized diff (most actionable first).
_CATEGORY_ORDER: dict[ChangeCategory, int] = {
    ChangeCategory.NEW: 0,
    ChangeCategory.IMPROVED: 1,
    ChangeCategory.WORSENED: 2,
    ChangeCategory.UNCHANGED: 3,
    ChangeCategory.DISAPPEARED: 4,
}


@dataclass(slots=True, frozen=True)
class ComparisonConfig:
    """Tuning for :func:`compare_runs`."""

    #: Metric changes with absolute value <= epsilon are treated as no change.
    epsilon: float = 1e-9


def identity_key(opportunity: StoredOpportunity) -> str:
    """Stable cross-run identity for an opportunity: provider + normalized title."""
    provider = opportunity.provider.strip().lower()
    title = " ".join(opportunity.title.split()).lower()
    return f"{provider}|{title}"


def _coalesce(value: float | None) -> float:
    return value if value is not None else 0.0


def _metric_deltas(
    old: StoredOpportunity | None, new: StoredOpportunity | None
) -> tuple[MetricDelta, ...]:
    deltas: list[MetricDelta] = []
    for name, higher_is_better, get in _METRICS:
        old_value = get(old) if old is not None else None
        new_value = get(new) if new is not None else None
        delta = round(_coalesce(new_value) - _coalesce(old_value), 6)
        deltas.append(
            MetricDelta(
                name=name,
                old=old_value,
                new=new_value,
                delta=delta,
                higher_is_better=higher_is_better,
            )
        )
    return tuple(deltas)


def _classify_pair(
    old: StoredOpportunity, new: StoredOpportunity, config: ComparisonConfig
) -> tuple[ChangeCategory, str]:
    for name, higher_is_better, get in _METRICS:
        delta = _coalesce(get(new)) - _coalesce(get(old))
        if abs(delta) <= config.epsilon:
            continue
        improved = delta > 0 if higher_is_better else delta < 0
        category = ChangeCategory.IMPROVED if improved else ChangeCategory.WORSENED
        reason = f"{name} {_coalesce(get(old)):.2f} -> {_coalesce(get(new)):.2f} ({delta:+.2f})"
        return category, reason
    return ChangeCategory.UNCHANGED, "no change in key metrics"


def _index(opportunities: Sequence[StoredOpportunity]) -> dict[str, StoredOpportunity]:
    """Map identity key -> opportunity, keeping the best-ranked on collision."""
    index: dict[str, StoredOpportunity] = {}
    for opportunity in sorted(opportunities, key=lambda o: o.rank):
        index.setdefault(identity_key(opportunity), opportunity)
    return index


def compare_runs(
    old_run: StoredRun,
    old_opportunities: Sequence[StoredOpportunity],
    new_run: StoredRun,
    new_opportunities: Sequence[StoredOpportunity],
    config: ComparisonConfig | None = None,
) -> RunComparison:
    """Diff two saved runs into an ordered :class:`RunComparison`."""
    config = config or ComparisonConfig()
    old_index = _index(old_opportunities)
    new_index = _index(new_opportunities)

    deltas: list[OpportunityDelta] = []
    for key in old_index.keys() | new_index.keys():
        old = old_index.get(key)
        new = new_index.get(key)
        if old is None and new is not None:
            category, reason = ChangeCategory.NEW, "new opportunity"
        elif old is not None and new is None:
            category, reason = ChangeCategory.DISAPPEARED, "no longer present"
        else:
            assert old is not None and new is not None
            category, reason = _classify_pair(old, new, config)
        source = new if new is not None else old
        assert source is not None
        deltas.append(
            OpportunityDelta(
                category=category,
                key=key,
                provider=source.provider,
                title=source.title,
                old=old,
                new=new,
                metrics=_metric_deltas(old, new),
                reason=reason,
            )
        )

    deltas.sort(key=lambda d: (_CATEGORY_ORDER[d.category], d.key))
    return RunComparison(old_run=old_run, new_run=new_run, deltas=tuple(deltas))
