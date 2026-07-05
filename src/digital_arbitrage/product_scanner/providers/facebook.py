"""Facebook Marketplace provider (mocked)."""

from __future__ import annotations

from ..models import Listing
from ._mock import make_mock_listings
from .base import Provider, register_provider


@register_provider
class FacebookMarketplaceProvider(Provider):
    name = "facebook_marketplace"
    base_url = "https://www.facebook.com/marketplace"

    def fetch(self, query: str, *, limit: int) -> list[Listing]:
        return make_mock_listings(
            provider=self.name,
            query=query,
            count=limit,
            base_url=self.base_url,
            currency="EUR",
            locations=("Dublin", "Limerick", "Waterford", "Belfast"),
        )
