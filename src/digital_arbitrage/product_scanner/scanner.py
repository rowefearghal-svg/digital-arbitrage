"""The Scanner: query many providers, return a unified list of listings.

``Scanner`` is the public entry point of the module::

    from digital_arbitrage.product_scanner import build_scanner

    scanner = build_scanner()
    listings = scanner.scan("rtx 4090")

It aggregates results across providers, enforces per-provider limits, and
isolates provider failures so one bad provider cannot break a whole scan.
"""

from __future__ import annotations

from collections.abc import Iterable

from .config import ScannerConfig
from .logging_utils import get_logger
from .models import Listing
from .providers import create_provider
from .providers.base import Provider


class Scanner:
    """Aggregates listings from a set of providers."""

    def __init__(
        self,
        providers: Iterable[Provider],
        *,
        max_results_per_provider: int = 10,
    ) -> None:
        self._providers: list[Provider] = list(providers)
        if max_results_per_provider <= 0:
            raise ValueError("max_results_per_provider must be positive")
        self._max_results = max_results_per_provider
        self._log = get_logger("scanner")

    @property
    def providers(self) -> list[Provider]:
        """The providers this scanner will query."""
        return list(self._providers)

    def add_provider(self, provider: Provider) -> None:
        """Register an additional provider at runtime (extensibility hook)."""
        self._providers.append(provider)

    def scan(self, query: str, *, limit: int | None = None) -> list[Listing]:
        """Search every provider for ``query`` and return all listings.

        A failing provider is logged and skipped rather than aborting the scan.
        ``limit`` overrides the configured per-provider cap for this call.
        """
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        per_provider = limit if limit is not None else self._max_results
        results: list[Listing] = []
        for provider in self._providers:
            try:
                found = provider.search(query, limit=per_provider)
            except Exception:  # noqa: BLE001 - isolate provider failures
                self._log.exception("provider %r failed for query %r", provider.name, query)
                continue
            self._log.info("provider %r returned %d listings", provider.name, len(found))
            results.extend(found)
        self._log.info("scan for %r returned %d listings total", query, len(results))
        return results


def build_scanner(config: ScannerConfig | None = None) -> Scanner:
    """Construct a :class:`Scanner` from configuration.

    Providers are instantiated from the registry by name, so enabling a new
    marketplace is a config change once its provider is registered.
    """
    cfg = config or ScannerConfig()
    providers = [create_provider(name) for name in cfg.providers]
    return Scanner(providers, max_results_per_provider=cfg.max_results_per_provider)
