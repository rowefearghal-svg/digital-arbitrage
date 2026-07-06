"""Condition normalization.

Maps free-form condition strings from any provider onto the shared
:class:`~digital_arbitrage.product_scanner.models.Condition` enum. Extend via
:meth:`ConditionNormalizer.register`.
"""

from __future__ import annotations

from ..product_scanner.models import Condition

# Substring-free exact aliases (matched after lowercasing/cleaning).
_DEFAULT_ALIASES: dict[str, Condition] = {
    "new": Condition.NEW,
    "brand new": Condition.NEW,
    "bnib": Condition.NEW,
    "new with tags": Condition.NEW,
    "new with box": Condition.NEW,
    "sealed": Condition.NEW,
    "used": Condition.USED,
    "pre-owned": Condition.USED,
    "preowned": Condition.USED,
    "second hand": Condition.USED,
    "secondhand": Condition.USED,
    "open box": Condition.USED,
    "refurbished": Condition.REFURBISHED,
    "refurb": Condition.REFURBISHED,
    "renewed": Condition.REFURBISHED,
    "reconditioned": Condition.REFURBISHED,
}


class ConditionNormalizer:
    """Resolve condition text to a :class:`Condition`."""

    def __init__(self, aliases: dict[str, Condition] | None = None) -> None:
        self._aliases = {k.lower(): v for k, v in (aliases or _DEFAULT_ALIASES).items()}

    def register(self, alias: str, condition: Condition) -> None:
        """Add or override an alias -> Condition mapping."""
        if not alias:
            raise ValueError("alias must be non-empty")
        self._aliases[alias.lower()] = condition

    def normalize(self, value: str | Condition | None) -> Condition:
        """Return the matching Condition, or ``Condition.UNKNOWN``."""
        if isinstance(value, Condition):
            return value
        if not value:
            return Condition.UNKNOWN
        token = " ".join(value.strip().lower().split())
        return self._aliases.get(token, Condition.UNKNOWN)
