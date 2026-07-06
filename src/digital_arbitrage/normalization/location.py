"""Location normalization.

Cleans and canonicalises free-form location strings. Ships with a small map of
common Irish/UK aliases and falls back to a cleaned, title-cased form for
anything unknown so no information is lost. Extend via
:meth:`LocationNormalizer.register`.
"""

from __future__ import annotations

from .text import clean_text

# Aliases -> canonical display name (keys matched case-insensitively).
_DEFAULT_ALIASES: dict[str, str] = {
    "co dublin": "Dublin",
    "co. dublin": "Dublin",
    "county dublin": "Dublin",
    "dublin city": "Dublin",
    "baile atha cliath": "Dublin",
    "co cork": "Cork",
    "co. cork": "Cork",
    "county cork": "Cork",
    "co galway": "Galway",
    "co. galway": "Galway",
    "intl": "International",
    "international": "International",
}


class LocationNormalizer:
    """Resolve a location string to a canonical display name."""

    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases = {k.lower(): v for k, v in (aliases or _DEFAULT_ALIASES).items()}

    def register(self, alias: str, canonical: str) -> None:
        """Add or override an alias -> canonical name mapping."""
        if not alias or not canonical:
            raise ValueError("alias and canonical must be non-empty")
        self._aliases[alias.lower()] = canonical

    def normalize(self, value: str | None) -> str | None:
        """Return a canonical location, or ``None`` if there is nothing usable."""
        if not value:
            return None
        cleaned = clean_text(value)
        if not cleaned:
            return None
        key = cleaned.lower().rstrip(".")
        if key in self._aliases:
            return self._aliases[key]
        # Unknown location: return a tidy, title-cased version.
        return cleaned.title()
