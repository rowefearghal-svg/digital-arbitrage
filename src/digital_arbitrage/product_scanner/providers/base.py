"""Provider interface and registry.

A *provider* knows how to search one marketplace and return normalised
:class:`~digital_arbitrage.product_scanner.models.Listing` objects. Real
network scraping is intentionally NOT implemented here - concrete providers in
this module return mocked data. New marketplaces are added by subclassing
:class:`Provider` and decorating with :func:`register_provider`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from ..logging_utils import get_logger
from ..models import Listing


class Provider(ABC):
    """Abstract marketplace provider.

    Subclasses set a unique :attr:`name` and implement :meth:`fetch`. Callers
    use :meth:`search`, which wraps :meth:`fetch` with limit enforcement and a
    stable, provider-agnostic contract.
    """

    #: Unique, stable identifier used in config and the registry.
    name: ClassVar[str] = ""

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"{type(self).__name__} must define a non-empty 'name'")
        self.log = get_logger(self.name)

    @abstractmethod
    def fetch(self, query: str, *, limit: int) -> list[Listing]:
        """Return up to ``limit`` listings for ``query``.

        Concrete providers implement this. Must return a list of
        :class:`Listing`; may return fewer than ``limit`` items.
        """

    def search(self, query: str, *, limit: int = 10) -> list[Listing]:
        """Public entry point: validate input, delegate to :meth:`fetch`."""
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if limit <= 0:
            raise ValueError("limit must be positive")
        self.log.debug("searching %r (limit=%d)", query, limit)
        listings = self.fetch(query.strip(), limit=limit)
        return listings[:limit]


#: Global registry mapping provider name -> provider class.
PROVIDER_REGISTRY: dict[str, type[Provider]] = {}


def register_provider(cls: type[Provider]) -> type[Provider]:
    """Class decorator that registers a provider under its ``name``."""
    name = cls.name
    if not name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name' before registering")
    if name in PROVIDER_REGISTRY and PROVIDER_REGISTRY[name] is not cls:
        raise ValueError(f"provider name {name!r} is already registered")
    PROVIDER_REGISTRY[name] = cls
    return cls


def create_provider(name: str) -> Provider:
    """Instantiate a registered provider by name."""
    try:
        cls = PROVIDER_REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(PROVIDER_REGISTRY)) or "<none>"
        raise KeyError(f"unknown provider {name!r}; registered: {available}") from None
    return cls()
