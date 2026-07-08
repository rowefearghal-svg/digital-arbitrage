"""Config-aware creation for live providers.

The mock provider registry
(:mod:`digital_arbitrage.product_scanner.providers.base`) constructs providers
with **no arguments** (``create_provider(name)`` -> ``cls()``). A live provider
cannot be built that way: it needs a :class:`LiveProviderConfig` and usually an
:class:`AuthProvider`. Rather than change the mock registry (which must keep
working unchanged), this module adds a *separate*, config-aware registry and
factory for live providers.

Providers register with :func:`register_live_provider` and are built with
:func:`create_live_provider`. The first real provider,
:class:`~digital_arbitrage.providers.live.ebay_browse.EbayBrowseProvider`,
registers itself on import.
"""

from __future__ import annotations

from .auth import AuthProvider
from .base import LiveProvider
from .config import LiveProviderConfig
from .http import HttpClient, Transport

#: Registry mapping provider name -> live provider class (separate from the mock
#: ``PROVIDER_REGISTRY`` so the two never collide).
LIVE_PROVIDER_REGISTRY: dict[str, type[LiveProvider]] = {}


def register_live_provider(cls: type[LiveProvider]) -> type[LiveProvider]:
    """Class decorator registering a live provider under its ``name``."""
    name = cls.name
    if not name:
        raise ValueError(f"{cls.__name__} must define a non-empty 'name' before registering")
    existing = LIVE_PROVIDER_REGISTRY.get(name)
    if existing is not None and existing is not cls:
        raise ValueError(f"live provider name {name!r} is already registered")
    LIVE_PROVIDER_REGISTRY[name] = cls
    return cls


def create_live_provider(
    name: str,
    config: LiveProviderConfig,
    *,
    auth: AuthProvider | None = None,
    transport: Transport | None = None,
    http_client: HttpClient | None = None,
) -> LiveProvider:
    """Instantiate a registered live provider by name, wiring in config + auth.

    ``config`` and ``auth`` are forwarded to :meth:`LiveProvider.create`, which
    builds a :class:`HttpClient` (unless one is supplied) that consults ``auth``
    for the ``Authorization`` header.
    """
    try:
        cls = LIVE_PROVIDER_REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(LIVE_PROVIDER_REGISTRY)) or "<none>"
        raise KeyError(f"unknown live provider {name!r}; registered: {available}") from None
    return cls.create(config, auth=auth, transport=transport, http_client=http_client)
