"""Cross-provider deduplication.

The :class:`Deduplicator` is the final stage of the pipeline
(Scanner -> Normalization -> Product Matching -> Deduplication). It groups
:class:`NormalizedListing` objects that refer to the same product - across
different providers - reusing the deterministic :class:`ProductMatcher`. It
never mutates or drops listings: every input ends up in exactly one group, and
each group exposes a single canonical representative.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..normalization.models import NormalizedListing
from ..product_matching import MatchConfig, MatchDecision, ProductMatcher
from .fingerprint import listing_fingerprint
from .models import DeduplicationResult, DuplicateGroup


@dataclass(slots=True, frozen=True)
class DeduplicationConfig:
    """Configuration for the :class:`Deduplicator`."""

    #: When False, deduplication is a no-op: every listing becomes its own group.
    enabled: bool = True
    #: Treat POSSIBLE_MATCH (not just SAME_PRODUCT) as a duplicate.
    include_possible_matches: bool = False
    #: Thresholds/weights passed to the underlying ProductMatcher.
    match_config: MatchConfig | None = None
    #: Optional provider preference order for canonical selection (earlier wins).
    provider_priority: tuple[str, ...] = field(default_factory=tuple)


def _stable_key(listing: NormalizedListing) -> tuple[str, str]:
    """Deterministic ordering key, independent of input order."""
    return (listing.listing_id, listing.provider)


class Deduplicator:
    """Group duplicate/near-duplicate listings across providers."""

    def __init__(self, config: DeduplicationConfig | None = None) -> None:
        self.config = config or DeduplicationConfig()
        self._matcher = ProductMatcher(self.config.match_config)

    def _qualifies(self, decision: MatchDecision) -> bool:
        if decision is MatchDecision.SAME_PRODUCT:
            return True
        return decision is MatchDecision.POSSIBLE_MATCH and self.config.include_possible_matches

    def _canonical_key(self, listing: NormalizedListing) -> tuple[int, int, str, str]:
        priority = self.config.provider_priority
        rank = priority.index(listing.provider) if listing.provider in priority else len(priority)
        # Prefer configured provider, then the richest title, then a stable id.
        return (rank, -len(set(listing.title_tokens)), listing.listing_id, listing.provider)

    def _select_canonical(self, members: list[NormalizedListing]) -> NormalizedListing:
        return min(members, key=self._canonical_key)

    def _build_group(self, members: list[NormalizedListing]) -> DuplicateGroup:
        canonical = self._select_canonical(members)
        ordered = tuple(sorted(members, key=_stable_key))
        return DuplicateGroup(
            fingerprint=listing_fingerprint(canonical),
            canonical=canonical,
            members=ordered,
        )

    def deduplicate(self, listings: Iterable[NormalizedListing]) -> DeduplicationResult:
        """Group ``listings`` and return a :class:`DeduplicationResult`."""
        items = list(listings)

        if not self.config.enabled:
            groups = tuple(self._build_group([listing]) for listing in items)
            return DeduplicationResult(groups=groups, total_input=len(items))

        clusters: list[list[NormalizedListing]] = []
        for listing in sorted(items, key=_stable_key):
            for cluster in clusters:
                decision = self._matcher.match(cluster[0], listing).decision
                if self._qualifies(decision):
                    cluster.append(listing)
                    break
            else:
                clusters.append([listing])

        groups = tuple(self._build_group(cluster) for cluster in clusters)
        return DeduplicationResult(groups=groups, total_input=len(items))
