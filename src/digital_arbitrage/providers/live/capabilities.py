"""Provider capability metadata.

Capabilities describe *what a provider can do* so the rest of the system can
adapt without provider-specific branching (e.g. skip pagination for a provider
that does not support it, or refuse to construct one that needs an API key when
none is configured). It is pure data - no behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Static description of a provider's supported features and limits."""

    supports_free_text_search: bool = True
    supports_pagination: bool = False
    supports_price_filter: bool = False
    supports_condition_filter: bool = False
    supports_sorting: bool = False
    requires_api_key: bool = False
    #: Largest page the provider accepts in a single request.
    max_page_size: int = 50
    #: Hard cap on results the provider will return, or ``None`` for unbounded.
    max_results: int | None = None
    #: Currencies the provider can report prices in (empty = unspecified).
    supported_currencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.max_page_size <= 0:
            raise ValueError("max_page_size must be positive")
        if self.max_results is not None and self.max_results <= 0:
            raise ValueError("max_results must be positive when set")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-friendly mapping."""
        return {
            "supports_free_text_search": self.supports_free_text_search,
            "supports_pagination": self.supports_pagination,
            "supports_price_filter": self.supports_price_filter,
            "supports_condition_filter": self.supports_condition_filter,
            "supports_sorting": self.supports_sorting,
            "requires_api_key": self.requires_api_key,
            "max_page_size": self.max_page_size,
            "max_results": self.max_results,
            "supported_currencies": list(self.supported_currencies),
        }
