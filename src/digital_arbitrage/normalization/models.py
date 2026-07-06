"""The normalized representation of a listing.

:class:`NormalizedListing` is the consistent internal shape produced by the
:class:`~digital_arbitrage.normalization.normalizer.Normalizer`. It keeps a
reference to the original :class:`Listing` so nothing is lost, while exposing
cleaned, comparable fields for downstream logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..product_scanner.models import Condition, Listing


@dataclass(slots=True)
class NormalizedListing:
    """A cleaned, provider-agnostic view over a raw :class:`Listing`."""

    source: Listing
    title: str
    title_tokens: tuple[str, ...] = ()
    currency: str | None = None
    condition: Condition = Condition.UNKNOWN
    location: str | None = None

    @classmethod
    def from_listing(cls, listing: Listing) -> NormalizedListing:
        """Seed a NormalizedListing from raw values (before the pipeline runs)."""
        return cls(
            source=listing,
            title=listing.title,
            currency=listing.currency,
            condition=listing.condition,
            location=listing.location,
        )

    @property
    def listing_id(self) -> str:
        """Convenience passthrough to the source listing id."""
        return self.source.listing_id

    @property
    def provider(self) -> str:
        """Convenience passthrough to the source provider."""
        return self.source.provider
