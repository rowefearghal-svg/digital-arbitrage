"""Pure token-similarity helpers.

These functions operate on plain token collections so they can be unit tested in
isolation and reused by the matcher. They contain no domain knowledge beyond a
lightweight heuristic for spotting "model identifier" tokens (e.g. ``4090``,
``s24``, ``512gb``).
"""

from __future__ import annotations

from collections.abc import Iterable


def token_set(tokens: Iterable[str]) -> frozenset[str]:
    """Return a set of non-empty tokens."""
    return frozenset(t for t in tokens if t)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity: |A n B| / |A u B|. Empty/empty is 0."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def overlap_coefficient(a: frozenset[str], b: frozenset[str]) -> float:
    """Overlap (Szymkiewicz-Simpson) coefficient: |A n B| / min(|A|, |B|).

    Useful when one title is a superset of the other (extra marketing words).
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def is_model_token(token: str) -> bool:
    """Heuristic: does this token look like a model/spec identifier?

    A model token contains a digit and is either alphanumeric (``s24``,
    ``512gb``) or at least three characters long (``4090``). This deliberately
    excludes short bare numbers such as listing ranks (``1``, ``2``) and
    two-digit noise.
    """
    if not any(ch.isdigit() for ch in token):
        return False
    has_alpha = any(ch.isalpha() for ch in token)
    return has_alpha or len(token) >= 3


def model_tokens(tokens: Iterable[str]) -> frozenset[str]:
    """Return the subset of tokens that look like model identifiers."""
    return frozenset(t for t in tokens if is_model_token(t))
