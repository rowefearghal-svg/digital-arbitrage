"""Cross-provider deduplication.

Groups duplicate/near-duplicate normalized listings across providers, reusing
the deterministic product matcher. Provider-agnostic, deterministic, and
lossless: every input listing is preserved inside exactly one group, each with a
single canonical representative. No pricing, scraping, or AI (see ADR-006).

Quick start::

    from digital_arbitrage.deduplication import Deduplicator

    result = Deduplicator().deduplicate(normalized_listings)
    for group in result.groups:
        print(group.fingerprint, group.canonical.title, group.size)
"""

from __future__ import annotations

from .deduplicator import DeduplicationConfig, Deduplicator
from .fingerprint import listing_fingerprint, signature
from .models import DeduplicationResult, DuplicateGroup

__all__ = [
    "DeduplicationConfig",
    "DeduplicationResult",
    "Deduplicator",
    "DuplicateGroup",
    "listing_fingerprint",
    "signature",
]
