"""Currency normalization framework.

Maps free-form currency inputs (symbols, names, or ISO codes in any case) onto
canonical ISO 4217 codes. This is a *framework*, not an exchange-rate engine -
no monetary conversion happens here (that belongs to pricing, which is out of
scope). New mappings are added via :meth:`CurrencyNormalizer.register`.
"""

from __future__ import annotations

# Default aliases -> ISO 4217. Keys are matched case-insensitively.
_DEFAULT_ALIASES: dict[str, str] = {
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "$": "USD",
    "us$": "USD",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "£": "GBP",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
    "stg": "GBP",
}


class CurrencyNormalizer:
    """Resolve currency aliases to ISO 4217 codes.

    ``default`` is returned when the input is empty; ``None`` when the input is
    non-empty but unrecognised (so callers can distinguish "missing" from
    "unknown").
    """

    def __init__(
        self, *, default: str | None = None, aliases: dict[str, str] | None = None
    ) -> None:
        self._aliases = {k.lower(): v for k, v in (aliases or _DEFAULT_ALIASES).items()}
        self.default = default.upper() if default else None

    def register(self, alias: str, iso_code: str) -> None:
        """Add or override a single alias -> ISO code mapping."""
        if not alias or not iso_code:
            raise ValueError("alias and iso_code must be non-empty")
        self._aliases[alias.lower()] = iso_code.upper()

    def normalize(self, value: str | None) -> str | None:
        """Return the canonical ISO code for ``value`` (or default/None)."""
        if value is None:
            return self.default
        token = value.strip().lower()
        if not token:
            return self.default
        if token in self._aliases:
            return self._aliases[token]
        # A bare 3-letter code we do not know about is still a plausible ISO
        # code; pass it through upper-cased rather than dropping information.
        if len(token) == 3 and token.isalpha():
            return token.upper()
        return None
