"""Configuration loading for the product scanner.

Config can come from a TOML file or a plain dict. The loader is intentionally
small and dependency-free (uses the stdlib ``tomllib``).

Example ``scanner.toml``::

    [scanner]
    default_currency = "EUR"
    max_results_per_provider = 10
    log_level = "INFO"
    providers = ["ebay", "facebook_marketplace", "adverts_ie", "donedeal"]
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PROVIDERS: tuple[str, ...] = (
    "ebay",
    "facebook_marketplace",
    "adverts_ie",
    "donedeal",
)


@dataclass(slots=True)
class ScannerConfig:
    """Runtime configuration for a :class:`~.scanner.Scanner`."""

    providers: list[str] = field(default_factory=lambda: list(DEFAULT_PROVIDERS))
    max_results_per_provider: int = 10
    default_currency: str = "EUR"
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.max_results_per_provider <= 0:
            raise ValueError("max_results_per_provider must be positive")
        if not self.providers:
            raise ValueError("at least one provider must be configured")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScannerConfig:
        """Build a config from a mapping, ignoring unknown keys.

        Accepts either the raw ``[scanner]`` table or a dict that contains a
        ``scanner`` key.
        """
        section = data.get("scanner", data)
        known = set(cls.__slots__)
        filtered = {k: v for k, v in section.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_toml(cls, path: str | Path) -> ScannerConfig:
        """Load config from a TOML file."""
        with Path(path).open("rb") as fh:
            data = tomllib.load(fh)
        return cls.from_dict(data)


def load_config(path: str | Path | None = None) -> ScannerConfig:
    """Load config from ``path`` if given, else return defaults."""
    if path is None:
        return ScannerConfig()
    return ScannerConfig.from_toml(path)
