"""Shared helpers for generating deterministic mock listings.

Keeps the concrete providers small and consistent. Mock data is derived
deterministically from the query so tests are stable and results reflect the
searched term. This is placeholder data only - no network access.
"""

from __future__ import annotations

import hashlib

from ..models import Condition, Listing

_CONDITIONS = (Condition.NEW, Condition.USED, Condition.REFURBISHED)


def _seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(digest[:8], 16)


def make_mock_listings(
    *,
    provider: str,
    query: str,
    count: int,
    base_url: str,
    currency: str,
    locations: tuple[str, ...],
) -> list[Listing]:
    """Return ``count`` deterministic mock listings for ``query``."""
    listings: list[Listing] = []
    for i in range(count):
        seed = _seed(provider, query, str(i))
        price = round(50 + (seed % 195000) / 100.0, 2)
        listing = Listing(
            listing_id=f"{provider}-{seed:08x}",
            title=f"{query.title()} - {provider} listing #{i + 1}",
            provider=provider,
            url=f"{base_url}/item/{seed:08x}",
            price=price,
            currency=currency,
            location=locations[seed % len(locations)],
            condition=_CONDITIONS[seed % len(_CONDITIONS)],
            extra={"mock": "true", "rank": str(i)},
        )
        listings.append(listing)
    return listings
