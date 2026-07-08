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

from collections.abc import Callable, Mapping
from typing import Any

from .auth import AuthProvider
from .base import LiveProvider
from .config import LiveProviderConfig
from .http import HttpClient, Transport

#: Registry mapping provider name -> live provider class (separate from the mock
#: ``PROVIDER_REGISTRY`` so the two never collide).
LIVE_PROVIDER_REGISTRY: dict[str, type[LiveProvider]] = {}

#: Builds a validated :class:`LiveProviderConfig` from a plain (TOML-parsed)
#: mapping. Registered per provider so a live provider can be configured by name.
LiveProviderConfigBuilder = Callable[[Mapping[str, Any]], LiveProviderConfig]

#: Builds a ready-to-use live provider from a config object, reading any
#: credentials from ``env`` (never the repo). ``transport`` / ``token_transport``
#: are injectable so tests drive the whole flow without touching the network.
LiveProviderEnvBuilder = Callable[..., LiveProvider]

#: Registries mapping provider name -> its config / env builders (parallel to
#: :data:`LIVE_PROVIDER_REGISTRY`, so name-based construction stays declarative).
LIVE_PROVIDER_CONFIG_BUILDERS: dict[str, LiveProviderConfigBuilder] = {}
LIVE_PROVIDER_ENV_BUILDERS: dict[str, LiveProviderEnvBuilder] = {}


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


def register_live_provider_config_builder(name: str, builder: LiveProviderConfigBuilder) -> None:
    """Register the config builder used to configure ``name`` from a mapping."""
    if not name:
        raise ValueError("a config builder must be registered under a non-empty name")
    LIVE_PROVIDER_CONFIG_BUILDERS[name] = builder


def register_live_provider_env_builder(name: str, builder: LiveProviderEnvBuilder) -> None:
    """Register the env-aware builder used to construct ``name`` from a config."""
    if not name:
        raise ValueError("an env builder must be registered under a non-empty name")
    LIVE_PROVIDER_ENV_BUILDERS[name] = builder


def _lookup(registry: dict[str, Any], name: str, kind: str) -> Any:
    try:
        return registry[name]
    except KeyError:
        available = ", ".join(sorted(registry)) or "<none>"
        raise KeyError(f"no {kind} for live provider {name!r}; registered: {available}") from None


def build_live_provider_config(name: str, config_data: Mapping[str, Any]) -> LiveProviderConfig:
    """Build and validate a live provider's config from a plain mapping."""
    builder = _lookup(LIVE_PROVIDER_CONFIG_BUILDERS, name, "config builder")
    return builder(config_data)


def build_live_provider_from_env(
    name: str,
    config_data: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
    token_transport: Transport | None = None,
) -> LiveProvider:
    """Build a live provider by name from config + environment credentials.

    Combines the registered config builder (which validates ``config_data``) with
    the registered env builder (which reads credentials from ``env`` and wires
    auth). ``transport`` / ``token_transport`` are forwarded for hermetic tests.
    """
    config = build_live_provider_config(name, config_data)
    builder = _lookup(LIVE_PROVIDER_ENV_BUILDERS, name, "env builder")
    return builder(config, env=env, transport=transport, token_transport=token_transport)


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
