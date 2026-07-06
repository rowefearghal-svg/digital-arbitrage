"""Data models for comparing two saved scan runs.

A :class:`RunComparison` is the diff of two runs: a tuple of
:class:`OpportunityDelta` objects, each categorising one opportunity (matched by
identity key) as new, disappeared, unchanged, improved, or worsened, along with
the per-metric :class:`MetricDelta` values that explain the verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..persistence import StoredOpportunity, StoredRun


class ChangeCategory(StrEnum):
    """How an opportunity changed between two runs."""

    NEW = "new"
    DISAPPEARED = "disappeared"
    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    WORSENED = "worsened"


@dataclass(slots=True, frozen=True)
class MetricDelta:
    """The old/new values and signed change of a single metric."""

    name: str
    old: float | None
    new: float | None
    delta: float
    #: True if a higher value is better for this metric (False for risk).
    higher_is_better: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "old": self.old,
            "new": self.new,
            "delta": self.delta,
            "higher_is_better": self.higher_is_better,
        }


@dataclass(slots=True, frozen=True)
class OpportunityDelta:
    """The change for one opportunity between two runs."""

    category: ChangeCategory
    key: str
    provider: str
    title: str
    old: StoredOpportunity | None
    new: StoredOpportunity | None
    metrics: tuple[MetricDelta, ...]
    reason: str

    def metric(self, name: str) -> MetricDelta | None:
        """Return the named :class:`MetricDelta`, or ``None`` if absent."""
        for md in self.metrics:
            if md.name == name:
                return md
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "key": self.key,
            "provider": self.provider,
            "title": self.title,
            "reason": self.reason,
            "old": self.old.to_dict() if self.old is not None else None,
            "new": self.new.to_dict() if self.new is not None else None,
            "metrics": [md.to_dict() for md in self.metrics],
        }


@dataclass(slots=True, frozen=True)
class RunComparison:
    """The full, ordered diff between an older and a newer run."""

    old_run: StoredRun
    new_run: StoredRun
    deltas: tuple[OpportunityDelta, ...]

    def counts_by_category(self) -> dict[str, int]:
        """Count of deltas per :class:`ChangeCategory` (all keys present)."""
        counts = {category.value: 0 for category in ChangeCategory}
        for delta in self.deltas:
            counts[delta.category.value] += 1
        return counts

    def by_category(self, category: ChangeCategory) -> tuple[OpportunityDelta, ...]:
        """Return only the deltas in ``category`` (preserving order)."""
        return tuple(delta for delta in self.deltas if delta.category is category)

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_run": self.old_run.to_dict(),
            "new_run": self.new_run.to_dict(),
            "counts": self.counts_by_category(),
            "deltas": [delta.to_dict() for delta in self.deltas],
        }
