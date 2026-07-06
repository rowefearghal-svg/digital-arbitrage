"""Low-level text cleaning helpers.

Pure functions with no knowledge of listings or providers - they operate on
plain strings so they can be composed by the normalization steps and reused
elsewhere. All functions are safe on empty input.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

#: The Unicode normalization forms accepted by :func:`normalize_unicode`.
UnicodeForm = Literal["NFC", "NFD", "NFKC", "NFKD"]

# Zero-width and BiDi control characters that frequently sneak into scraped
# marketplace text and would otherwise defeat equality/dedup.
_ZERO_WIDTH = "\u200b\u200c\u200d\u200e\u200f\ufeff\u2060"

# Map common "smart"/typographic characters onto plain ASCII equivalents.
_PUNCTUATION_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # non-breaking space
    "\u2026": "...",  # ellipsis
}

_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Precomputed translation table (code point -> replacement) for str.translate.
_PUNCTUATION_TABLE: dict[int, str] = {ord(k): v for k, v in _PUNCTUATION_MAP.items()}


def normalize_unicode(text: str, form: UnicodeForm = "NFKC") -> str:
    """Apply a Unicode normalization form (default NFKC)."""
    if not text:
        return ""
    return unicodedata.normalize(form, text)


def remove_control_characters(text: str) -> str:
    """Strip control/format characters (Unicode categories Cc/Cf) and zero-width
    marks, but keep ordinary whitespace (tab/newline become spaces later)."""
    if not text:
        return ""
    cleaned = []
    for ch in text:
        if ch in _ZERO_WIDTH:
            continue
        category = unicodedata.category(ch)
        if category in {"Cc", "Cf"} and ch not in "\t\n\r":
            continue
        cleaned.append(ch)
    return "".join(cleaned)


def normalize_punctuation(text: str) -> str:
    """Fold smart quotes, dashes, and similar typographic characters to ASCII."""
    if not text:
        return ""
    return text.translate(_PUNCTUATION_TABLE)


def remove_symbols_and_emoji(text: str) -> str:
    """Remove emoji and standalone symbol characters (categories So/Sk/Cs).

    Currency and maths symbols (Sc/Sm) are intentionally preserved because they
    can carry meaning (e.g. a price); callers that want them gone strip them via
    the token step instead.
    """
    if not text:
        return ""
    return "".join(ch for ch in text if unicodedata.category(ch) not in {"So", "Sk", "Cs"})


def collapse_whitespace(text: str) -> str:
    """Collapse any run of whitespace to a single space and trim the ends."""
    if not text:
        return ""
    return _WHITESPACE_RE.sub(" ", text).strip()


def clean_text(text: str, *, unicode_form: UnicodeForm = "NFKC") -> str:
    """Full cleaning pass: unicode-normalize, strip control chars, fold
    punctuation, then collapse whitespace."""
    text = normalize_unicode(text, unicode_form)
    text = remove_control_characters(text)
    text = normalize_punctuation(text)
    return collapse_whitespace(text)


def tokenize(text: str) -> tuple[str, ...]:
    """Return lowercase alphanumeric tokens, in order of appearance."""
    if not text:
        return ()
    return tuple(_TOKEN_RE.findall(text.lower()))
