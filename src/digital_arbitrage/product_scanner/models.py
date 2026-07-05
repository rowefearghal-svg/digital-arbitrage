"""Data models for the product scanner.

Only *listing* data is modelled here. No pricing, profit, or AI logic - those
are explicitly out of scope for this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Condition(StrEnum):
    """Coarse item condition, normalised across providers."""

    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Listing:
    """A single marketplace listing, normalised to a common shape.

    This is deliberately provider-agnostic: every provider maps its own raw
    response onto this model so the rest of the system never has to care where
    a listing came from.
    """

    listing_id: str
    title: str
    provider: str
    url: str
    price: float | None = None
    currency: str = "EUR"
    location: str | None = None
    condition: Condition = Condition.UNKNOWN
    posted_at: datetime | None = None
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Provider-specific extras that do not fit the common shape.
    extra: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.listing_id:
            raise ValueError("listing_id must not be empty")
        if not self.title:
            raise ValueError("title must not be empty")
        if self.price is not None and self.price < 0:
            raise ValueError("price must be non-negative")
