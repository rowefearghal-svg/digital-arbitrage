"""Data models for deduplication results.

A :class:`DuplicateGroup` bundles listings judged to be the same product, with a
single ``canonical`` representative. A :class:`DeduplicationResult` is the full
output: every input listing is preserved inside exactly one group.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.models import NormalizedListing


@dataclass(slots=True, frozen=True)
class DuplicateGroup:
    """A set of listings considered the same product."""

    fingerprint: str
    canonical: NormalizedListing
    members: tuple[NormalizedListing, ...]

    def __post_init__(self) -> None:
        if not self.members:
            raise ValueError("a DuplicateGroup must have at least one member")
        if self.canonical not in self.members:
            raise ValueError("canonical listing must be one of the group members")

    @property
    def size(self) -> int:
        """Number of listings in the group."""
        return len(self.members)

    @property
    def is_duplicate(self) -> bool:
        """True when the group contains more than one listing."""
        return len(self.members) > 1

    @property
    def providers(self) -> tuple[str, ...]:
        """Distinct providers represented in the group, sorted."""
        return tuple(sorted({member.provider for member in self.members}))


@dataclass(slots=True, frozen=True)
class DeduplicationResult:
    """The outcome of deduplicating a collection of listings."""

    groups: tuple[DuplicateGroup, ...]
    total_input: int

    def __post_init__(self) -> None:
        grouped = sum(group.size for group in self.groups)
        if grouped != self.total_input:
            raise ValueError(
                f"listing count mismatch: {grouped} grouped vs {self.total_input} input "
                "(all listings must be preserved)"
            )

    @property
    def canonical_listings(self) -> tuple[NormalizedListing, ...]:
        """One representative listing per group."""
        return tuple(group.canonical for group in self.groups)

    @property
    def all_listings(self) -> tuple[NormalizedListing, ...]:
        """Every original listing, flattened across groups."""
        return tuple(member for group in self.groups for member in group.members)

    @property
    def total_groups(self) -> int:
        """Number of distinct product groups."""
        return len(self.groups)

    @property
    def duplicates_removed(self) -> int:
        """How many listings would be dropped by keeping only canonicals."""
        return self.total_input - self.total_groups
