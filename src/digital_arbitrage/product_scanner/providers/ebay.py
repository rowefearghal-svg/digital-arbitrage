"""eBay provider (mocked)."""

from __future__ import annotations

from ..models import Listing
from ._mock import make_mock_listings
from .base import Provider, register_provider


@register_provider
class EbayProvider(Provider):
    name = "ebay"
    base_url = "https://www.ebay.ie"

    def fetch(self, query: str, *, limit: int) -> list[Listing]:
        return make_mock_listings(
            provider=self.name,
            query=query,
            count=limit,
            base_url=self.base_url,
            currency="EUR",
            locations=("Dublin", "Cork", "Galway", "International"),
        )
