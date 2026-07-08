"""Assemble a :class:`Scanner` from mixed mock and live providers.

The mock scanner (:func:`digital_arbitrage.product_scanner.build_scanner`) builds
every provider with the zero-arg mock registry, which cannot construct a
config-taking, credential-needing :class:`LiveProvider`. This module bridges the
two: given a :class:`ScannerConfig` (the provider *names*) and per-provider
:class:`LiveProviderSetting` s (enable flag + config), it builds mock providers
from the mock registry and live providers from config + environment credentials.

It is the single place that knows a provider name might be *live*; the mock path
stays byte-for-byte unchanged (ADR-015/017/018), and no live call happens until a
scan actually runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ...product_scanner.config import ScannerConfig
from ...product_scanner.providers.base import Provider, create_provider
from ...product_scanner.scanner import Scanner
from .factory import LIVE_PROVIDER_REGISTRY, build_live_provider_from_env
from .http import Transport
from .logging_utils import get_logger

_log = get_logger("scanning")


@dataclass(frozen=True, slots=True)
class LiveProviderSetting:
    """Per-provider live settings: whether it is enabled and its config table.

    ``config`` is the raw ``[providers.<name>]`` mapping (minus ``enabled``),
    passed to the provider's registered config builder. Secrets never live here;
    credentials come only from the environment.
    """

    enabled: bool = True
    config: Mapping[str, Any] = field(default_factory=dict)


def build_scanner_from_config(
    scanner_config: ScannerConfig | None = None,
    live_settings: Mapping[str, LiveProviderSetting] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
    token_transport: Transport | None = None,
) -> Scanner:
    """Build a :class:`Scanner` mixing mock and live providers.

    Each configured provider name is resolved against the *live* registry first
    (built from its :class:`LiveProviderSetting` + ``env`` credentials) and
    otherwise from the mock registry. A live provider whose setting is disabled is
    skipped (logged, not built), so credentials are only required for the live
    providers actually in use. ``transport`` / ``token_transport`` are injectable
    for hermetic tests and unused in production.
    """
    cfg = scanner_config or ScannerConfig()
    settings = live_settings or {}
    providers: list[Provider] = []
    for name in cfg.providers:
        if name in LIVE_PROVIDER_REGISTRY:
            setting = settings.get(name, LiveProviderSetting())
            if not setting.enabled:
                _log.info("live provider %r is disabled; skipping", name)
                continue
            providers.append(
                build_live_provider_from_env(
                    name,
                    setting.config,
                    env=env,
                    transport=transport,
                    token_transport=token_transport,
                )
            )
        else:
            providers.append(create_provider(name))
    return Scanner(providers, max_results_per_provider=cfg.max_results_per_provider)
