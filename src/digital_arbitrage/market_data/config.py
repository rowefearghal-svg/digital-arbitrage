"""TOML configuration for the collector: an optional ``[collection]`` table.

Kept separate from ``pipeline/config_file.py`` so collection settings cannot
accidentally alter scan/scoring behaviour. Unknown keys are rejected loudly.

Example::

    [collection]
    manifest = "configs/collection.gpu.json"
    db_path = "~/.digital_arbitrage/market_data.db"
    detail_fetch_top_n = 150
    fetch_stockx_variants = false
    raw_retention_days = 90
    stale_after_hours = 48
    ebay_marketplace_id = "EBAY_IE"
    ebay_search_filter = "buyingOptions:{AUCTION|FIXED_PRICE}"
    ebay_search_fieldgroups = "EXTENDED"

    [collection.daily_request_budget]
    ebay_browse = 4500
    stockx = 20000

    [collection.rate_limit_per_second]
    ebay_browse = 2.0
    stockx = 1.0
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .collector import CollectionConfig


class CollectionConfigError(ValueError):
    """The ``[collection]`` config is malformed."""


_SCALAR_KEYS: dict[str, type] = {
    "manifest": str,
    "db_path": str,
    "output_dir": str,
    "page_size_ebay": int,
    "page_size_stockx": int,
    "max_pages": int,
    "detail_fetch_top_n": int,
    "fetch_stockx_variants": bool,
    "raw_retention_days": int,
    "stale_after_hours": int,
    "keep_seller_usernames": bool,
    "ebay_search_filter": str,
    "ebay_search_fieldgroups": str,
    "ebay_search_sort": str,
    "ebay_marketplace_id": str,
    "ebay_base_url": str,
    "stockx_base_url": str,
    "stockx_currency_code": str,
    "request_timeout": float,
}
_NESTED_MAPS = {"daily_request_budget", "rate_limit_per_second"}
#: Non-CollectionConfig keys consumed by the CLI itself.
_CLI_KEYS = {"manifest", "db_path", "output_dir"}


def load_collection_config(path: str | Path) -> dict[str, Any]:
    """Parse ``[collection]`` from ``path``.

    Returns a dict with file paths under ``manifest``/``db_path``/
    ``output_dir`` and a ``collection_config`` entry holding the
    :class:`CollectionConfig`.
    """
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise CollectionConfigError(f"cannot read config {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CollectionConfigError(f"config {path} is not valid TOML: {exc}") from exc

    section = raw.get("collection", {})
    if not isinstance(section, dict):
        raise CollectionConfigError("[collection] must be a table")

    kwargs: dict[str, Any] = {}
    result: dict[str, Any] = {}
    for key, value in section.items():
        if key in _CLI_KEYS:
            expected = _SCALAR_KEYS[key]
            if not isinstance(value, expected):
                raise CollectionConfigError(f"[collection].{key} must be {expected.__name__}")
            result[key] = value
        elif key in _NESTED_MAPS:
            if not isinstance(value, dict) or not all(
                isinstance(k, str) and isinstance(v, (int, float)) for k, v in value.items()
            ):
                raise CollectionConfigError(
                    f"[collection.{key}] must be a table of provider -> number"
                )
            kwargs[key] = {
                k: (int(v) if key == "daily_request_budget" else float(v)) for k, v in value.items()
            }
        elif key in _SCALAR_KEYS:
            expected = _SCALAR_KEYS[key]
            if not isinstance(value, expected):
                raise CollectionConfigError(f"[collection].{key} must be {expected.__name__}")
            kwargs[key] = value
        else:
            raise CollectionConfigError(f"[collection].{key} is not a known key")
    result["collection_config"] = CollectionConfig(**kwargs)
    return result
