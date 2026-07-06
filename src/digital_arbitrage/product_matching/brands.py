"""Brand heuristics.

A small, extensible set of known brand tokens plus a helper to pull them out of
a token collection. This is intentionally a curated list rather than an ML model
- deterministic matching first (see ADR-005).
"""

from __future__ import annotations

from collections.abc import Iterable

# Lower-case brand tokens. Extend per-matcher via MatchConfig.brands.
DEFAULT_BRANDS: frozenset[str] = frozenset(
    {
        "nvidia",
        "amd",
        "intel",
        "apple",
        "samsung",
        "sony",
        "lg",
        "asus",
        "msi",
        "gigabyte",
        "evga",
        "zotac",
        "dell",
        "hp",
        "lenovo",
        "acer",
        "razer",
        "microsoft",
        "google",
        "huawei",
        "xiaomi",
        "oneplus",
        "nintendo",
        "logitech",
        "corsair",
    }
)


def extract_brands(
    tokens: Iterable[str], brands: frozenset[str] = DEFAULT_BRANDS
) -> frozenset[str]:
    """Return the brand tokens present in ``tokens``."""
    token_set = frozenset(tokens)
    return token_set & brands
