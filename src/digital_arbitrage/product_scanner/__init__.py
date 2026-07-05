"""Product Scanner v0.1.

First working module of the Digital Arbitrage Engine. It searches multiple
marketplaces through a common provider interface and returns a unified list of
:class:`Listing` objects.

Providers currently return **mocked** listings (no scraping). Pricing, profit,
and AI logic are intentionally out of scope.

Quick start::

    from digital_arbitrage.product_scanner import build_scanner

    scanner = build_scanner()
    for listing in scanner.scan("rtx 4090"):
        print(listing.provider, listing.title, listing.price)
"""

from __future__ import annotations

from .config import ScannerConfig, load_config
from .logging_utils import configure_logging, get_logger
from .models import Condition, Listing
from .providers import PROVIDER_REGISTRY, Provider, create_provider, register_provider
from .scanner import Scanner, build_scanner

__all__ = [
    "PROVIDER_REGISTRY",
    "Condition",
    "Listing",
    "Provider",
    "Scanner",
    "ScannerConfig",
    "build_scanner",
    "configure_logging",
    "create_provider",
    "get_logger",
    "load_config",
    "register_provider",
]
