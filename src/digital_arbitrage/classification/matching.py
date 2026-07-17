"""Deterministic, marketplace-independent text matching for classification.

All matching is done on *titles only* (no images, no LLMs, no external
services). Titles are normalised so that case, spacing, punctuation, hyphens,
and repeated whitespace never change the outcome: ``"RTX-4090"``,
``"RTX 4090"``, and ``"rtx4090"`` all match a requirement for ``rtx 4090``.

Two matching modes are provided:

* **word/phrase matching** - a term matches only on whole-token boundaries, so
  ``"fan"`` matches ``"stock fan"`` but not ``"fantastic"``. Multi-word phrases
  (``"power supply"``) match a contiguous run of tokens. Used for accessory,
  part, and excluded keywords, where substring matching would be dangerous.
* **compact matching** - the term's alphanumeric characters must appear as a
  substring of the title's alphanumerics. This deliberately ignores token
  boundaries so glued model numbers (``"rtx4090"``) still match ``"rtx 4090"``.
  Used only for required model tokens.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..normalization.text import tokenize


@dataclass(slots=True, frozen=True)
class MatchableText:
    """A title reduced to the forms the matchers need.

    ``tokens`` are the lowercase alphanumeric tokens in order; ``compact`` is
    those tokens concatenated with no separators.
    """

    tokens: tuple[str, ...]
    compact: str


def prepare(text: str) -> MatchableText:
    """Normalise ``text`` into a :class:`MatchableText`.

    Lower-casing, punctuation/hyphen folding, and whitespace collapsing all
    fall out of :func:`~digital_arbitrage.normalization.text.tokenize`, which
    keeps this consistent with the rest of the pipeline and adds no new
    dependencies.
    """
    tokens = tokenize(text)
    return MatchableText(tokens=tokens, compact="".join(tokens))


def term_tokens(term: str) -> tuple[str, ...]:
    """Tokenise a single search term (word or phrase)."""
    return tokenize(term)


def word_match(term: str, text: MatchableText) -> bool:
    """True if ``term`` occurs in ``text`` on whole-token boundaries.

    A single-word term matches an equal token; a multi-word phrase matches a
    contiguous run of tokens. Empty terms never match.
    """
    needle = term_tokens(term)
    if not needle:
        return False
    haystack = text.tokens
    if len(needle) == 1:
        return needle[0] in haystack
    span = len(needle)
    return any(haystack[i : i + span] == needle for i in range(len(haystack) - span + 1))


def compact_match(term: str, text: MatchableText) -> bool:
    """True if ``term``'s alphanumerics are a substring of ``text.compact``.

    Ignores token boundaries so ``"rtx 4090"`` matches a glued ``"rtx4090"``.
    Empty terms never match.
    """
    needle = "".join(term_tokens(term))
    if not needle:
        return False
    return needle in text.compact


def first_word_match(terms: tuple[str, ...], text: MatchableText) -> str | None:
    """Return the first term (in ``terms`` order) that word-matches ``text``."""
    for term in terms:
        if word_match(term, text):
            return term
    return None


def all_word_matches(terms: tuple[str, ...], text: MatchableText) -> list[str]:
    """Return every term that word-matches ``text``, preserving ``terms`` order.

    De-duplicates while keeping first-seen order so a repeated keyword (or two
    aliases of the same word) is only reported once.
    """
    seen: dict[str, None] = {}
    for term in terms:
        if term not in seen and word_match(term, text):
            seen[term] = None
    return list(seen)
