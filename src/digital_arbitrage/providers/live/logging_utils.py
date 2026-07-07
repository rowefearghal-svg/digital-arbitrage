"""Structured logging helpers for live providers.

A thin wrapper over the standard library so every live provider logs under one
namespace with consistent, greppable ``key=value`` fields. Application code
calls :func:`get_logger`; :func:`format_fields` renders structured context.
"""

from __future__ import annotations

import logging
from typing import Any

_LOGGER_NAMESPACE = "digital_arbitrage.providers"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the live-provider namespace.

    ``get_logger("ebay")`` -> ``digital_arbitrage.providers.ebay``.
    """
    if not name:
        return logging.getLogger(_LOGGER_NAMESPACE)
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{name}")


def format_fields(**fields: Any) -> str:
    """Render keyword fields as a stable, space-separated ``key=value`` string.

    Keys are emitted in the order given; ``None`` values are skipped so optional
    context does not clutter the line. Values containing spaces are quoted.
    """
    parts: list[str] = []
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value)
        if " " in text:
            text = f'"{text}"'
        parts.append(f"{key}={text}")
    return " ".join(parts)
