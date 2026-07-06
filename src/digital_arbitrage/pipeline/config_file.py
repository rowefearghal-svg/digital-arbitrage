"""Load a :class:`PipelineConfig` from a TOML file.

The file has one table per stage; every key and table is optional and falls back
to that stage's own defaults. Unknown tables/keys and wrong types are rejected
with a clear, section-prefixed message so misconfigurations fail loudly at load
time rather than surfacing as confusing behaviour later.

Example (see ``configs/default.toml`` for the full, documented version)::

    [pipeline]
    scan_limit = 10

    [scanner]
    providers = ["ebay", "donedeal"]

    [opportunity]
    marketplace_fee_rate = 0.10
    buy_roi = 0.15
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Final, get_args

from ..deduplication import DeduplicationConfig
from ..market_pricing import STRATEGY_NAMES, MarketPricingConfig
from ..normalization import NormalizationConfig
from ..normalization.text import UnicodeForm
from ..opportunity import OpportunityConfig
from ..product_matching import MatchConfig
from ..product_scanner import ScannerConfig
from .pipeline import PipelineConfig

_MISSING: Final[Any] = object()

_SECTIONS: Final[frozenset[str]] = frozenset(
    {
        "pipeline",
        "scanner",
        "normalization",
        "matching",
        "deduplication",
        "market_pricing",
        "opportunity",
    }
)


class ConfigError(ValueError):
    """Raised when a pipeline config file is missing, malformed, or invalid."""


class _Section:
    """Typed, validating accessor over a single TOML table."""

    def __init__(self, name: str, data: dict[str, Any]) -> None:
        self.name = name
        self._data = data
        self._used: set[str] = set()

    def _fail(self, message: str) -> None:
        raise ConfigError(f"[{self.name}] {message}")

    def _get(self, key: str) -> Any:
        if key not in self._data:
            return _MISSING
        self._used.add(key)
        return self._data[key]

    def number(self, key: str) -> Any:
        value = self._get(key)
        if value is _MISSING:
            return _MISSING
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self._fail(f"'{key}' must be a number")
        return float(value)

    def integer(self, key: str) -> Any:
        value = self._get(key)
        if value is _MISSING:
            return _MISSING
        if isinstance(value, bool) or not isinstance(value, int):
            self._fail(f"'{key}' must be an integer")
        return value

    def boolean(self, key: str) -> Any:
        value = self._get(key)
        if value is _MISSING:
            return _MISSING
        if not isinstance(value, bool):
            self._fail(f"'{key}' must be a boolean")
        return value

    def string(self, key: str) -> Any:
        value = self._get(key)
        if value is _MISSING:
            return _MISSING
        if not isinstance(value, str):
            self._fail(f"'{key}' must be a string")
        return value

    def string_list(self, key: str) -> Any:
        value = self._get(key)
        if value is _MISSING:
            return _MISSING
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            self._fail(f"'{key}' must be a list of strings")
        return value

    def string_map(self, key: str) -> Any:
        value = self._get(key)
        if value is _MISSING:
            return _MISSING
        if not isinstance(value, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in value.items()
        ):
            self._fail(f"'{key}' must be a table of string -> string")
        return value

    def finish(self) -> None:
        unknown = set(self._data) - self._used
        if unknown:
            self._fail(f"unknown key(s): {', '.join(sorted(unknown))}")


def _put(kwargs: dict[str, Any], key: str, value: Any) -> None:
    if value is not _MISSING:
        kwargs[key] = value


def _construct(section: _Section, cls: Any, kwargs: dict[str, Any]) -> Any:
    try:
        return cls(**kwargs)
    except ValueError as error:
        raise ConfigError(f"[{section.name}] {error}") from error


def _build_scanner(data: dict[str, Any] | None) -> ScannerConfig | None:
    if data is None:
        return None
    section = _Section("scanner", data)
    kwargs: dict[str, Any] = {}
    _put(kwargs, "providers", section.string_list("providers"))
    _put(kwargs, "max_results_per_provider", section.integer("max_results_per_provider"))
    _put(kwargs, "default_currency", section.string("default_currency"))
    _put(kwargs, "log_level", section.string("log_level"))
    section.finish()
    return _construct(section, ScannerConfig, kwargs)


def _build_normalization(data: dict[str, Any] | None) -> NormalizationConfig | None:
    if data is None:
        return None
    section = _Section("normalization", data)
    kwargs: dict[str, Any] = {}
    unicode_form = section.string("unicode_form")
    if unicode_form is not _MISSING:
        valid = get_args(UnicodeForm)
        if unicode_form not in valid:
            section._fail(f"'unicode_form' must be one of {', '.join(valid)}")
        kwargs["unicode_form"] = unicode_form
    _put(kwargs, "remove_emoji", section.boolean("remove_emoji"))
    _put(kwargs, "lowercase_title", section.boolean("lowercase_title"))
    _put(kwargs, "remove_filler_words", section.boolean("remove_filler_words"))
    filler = section.string_list("filler_words")
    if filler is not _MISSING:
        kwargs["filler_words"] = frozenset(filler)
    _put(kwargs, "default_currency", section.string("default_currency"))
    _put(kwargs, "currency_aliases", section.string_map("currency_aliases"))
    _put(kwargs, "location_aliases", section.string_map("location_aliases"))
    section.finish()
    return _construct(section, NormalizationConfig, kwargs)


def _build_matching(data: dict[str, Any] | None) -> MatchConfig | None:
    if data is None:
        return None
    section = _Section("matching", data)
    kwargs: dict[str, Any] = {}
    for key in (
        "same_threshold",
        "possible_threshold",
        "overlap_weight",
        "model_conflict_cap",
        "brand_conflict_factor",
        "shared_model_boost",
        "shared_brand_boost",
    ):
        _put(kwargs, key, section.number(key))
    brands = section.string_list("brands")
    if brands is not _MISSING:
        kwargs["brands"] = frozenset(brands)
    section.finish()
    return _construct(section, MatchConfig, kwargs)


def _build_deduplication(
    data: dict[str, Any] | None, match_config: MatchConfig | None
) -> DeduplicationConfig | None:
    if data is None and match_config is None:
        return None
    section = _Section("deduplication", data or {})
    kwargs: dict[str, Any] = {}
    _put(kwargs, "enabled", section.boolean("enabled"))
    _put(kwargs, "include_possible_matches", section.boolean("include_possible_matches"))
    priority = section.string_list("provider_priority")
    if priority is not _MISSING:
        kwargs["provider_priority"] = tuple(priority)
    section.finish()
    if match_config is not None:
        kwargs["match_config"] = match_config
    return _construct(section, DeduplicationConfig, kwargs)


def _build_market_pricing(data: dict[str, Any] | None) -> MarketPricingConfig | None:
    if data is None:
        return None
    section = _Section("market_pricing", data)
    kwargs: dict[str, Any] = {}
    strategy = section.string("strategy")
    if strategy is not _MISSING:
        if strategy not in STRATEGY_NAMES:
            section._fail(f"'strategy' must be one of {', '.join(STRATEGY_NAMES)}")
        kwargs["strategy"] = strategy
    _put(kwargs, "trim_fraction", section.number("trim_fraction"))
    _put(kwargs, "min_comparables", section.integer("min_comparables"))
    _put(kwargs, "remove_outliers", section.boolean("remove_outliers"))
    _put(kwargs, "iqr_multiplier", section.number("iqr_multiplier"))
    _put(kwargs, "currency", section.string("currency"))
    _put(kwargs, "confidence_full_count", section.integer("confidence_full_count"))
    section.finish()
    return _construct(section, MarketPricingConfig, kwargs)


def _build_opportunity(data: dict[str, Any] | None) -> OpportunityConfig | None:
    if data is None:
        return None
    section = _Section("opportunity", data)
    kwargs: dict[str, Any] = {}
    for key in (
        "marketplace_fee_rate",
        "payment_fee_rate",
        "payment_fee_flat",
        "shipping_cost",
        "packaging_cost",
        "buffer_rate",
        "buffer_flat",
        "tax_rate",
        "strong_buy_roi",
        "buy_roi",
        "watch_roi",
        "min_net_profit",
        "min_confidence",
        "strong_buy_confidence",
    ):
        _put(kwargs, key, section.number(key))
    _put(kwargs, "require_same_currency", section.boolean("require_same_currency"))
    section.finish()
    return _construct(section, OpportunityConfig, kwargs)


def _build_scan_limit(data: dict[str, Any] | None) -> Any:
    if data is None:
        return _MISSING
    section = _Section("pipeline", data)
    scan_limit = section.integer("scan_limit")
    section.finish()
    return scan_limit


def _read_toml(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        raise ConfigError(f"config file not found: {file_path}")
    try:
        with file_path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"invalid TOML in {file_path}: {error}") from error


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    """Load and validate a :class:`PipelineConfig` from a TOML file."""
    raw = _read_toml(path)
    unknown_sections = set(raw) - _SECTIONS
    if unknown_sections:
        raise ConfigError(
            f"unknown section(s): {', '.join(sorted(unknown_sections))}; "
            f"allowed: {', '.join(sorted(_SECTIONS))}"
        )

    match_config = _build_matching(raw.get("matching"))
    scan_limit = _build_scan_limit(raw.get("pipeline"))
    return PipelineConfig(
        scanner_config=_build_scanner(raw.get("scanner")),
        normalization_config=_build_normalization(raw.get("normalization")),
        deduplication_config=_build_deduplication(raw.get("deduplication"), match_config),
        pricing_config=_build_market_pricing(raw.get("market_pricing")),
        opportunity_config=_build_opportunity(raw.get("opportunity")),
        scan_limit=None if scan_limit is _MISSING else scan_limit,
    )
