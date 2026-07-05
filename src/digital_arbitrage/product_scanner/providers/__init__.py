"""Marketplace providers.

Importing this package registers all built-in providers in
:data:`~digital_arbitrage.product_scanner.providers.base.PROVIDER_REGISTRY`.
"""

from __future__ import annotations

from .adverts import AdvertsIeProvider
from .base import PROVIDER_REGISTRY, Provider, create_provider, register_provider
from .donedeal import DoneDealProvider
from .ebay import EbayProvider
from .facebook import FacebookMarketplaceProvider

__all__ = [
    "PROVIDER_REGISTRY",
    "AdvertsIeProvider",
    "DoneDealProvider",
    "EbayProvider",
    "FacebookMarketplaceProvider",
    "Provider",
    "create_provider",
    "register_provider",
]
