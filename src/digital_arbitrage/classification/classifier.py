"""The deterministic, title-only listing classifier.

The classifier takes a listing title and a
:class:`~digital_arbitrage.classification.models.SearchProfile` and returns a
:class:`~digital_arbitrage.classification.models.ListingClassification`. It is
pure and marketplace-independent: no images, no LLMs, no external services, and
no provider-specific logic (see ADR-022).

Decision order (first match wins)::

    excluded keyword         -> REJECTED
    no required term present -> REJECTED   ("Missing required term")
    some required missing    -> UNKNOWN    ("Partial match")
    accessory keyword        -> ACCESSORY
    part keyword             -> PART
    otherwise                -> COMPLETE_PRODUCT

``match_confidence`` is a deterministic 0-100 score describing how sure we are
of the assigned label, driven by how tightly the required terms matched.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..normalization.text import tokenize
from .keywords import (
    DEFAULT_ACCESSORY_TERMS,
    DEFAULT_EXCLUDED_TERMS,
    DEFAULT_PART_TERMS,
)
from .matching import (
    MatchableText,
    all_word_matches,
    compact_match,
    first_word_match,
    prepare,
)
from .models import Classification, ListingClassification, SearchProfile

if TYPE_CHECKING:
    from ..normalization.models import NormalizedListing

# Confidence constants (0-100). Grouped here so the scoring is easy to audit.
_CONF_EXCLUDED = 95
_CONF_MISSING = 90
_CONF_PARTIAL = 45
_CONF_ACCESSORY = 90
_CONF_ACCESSORY_MULTI = 92
_CONF_PART = 90
_CONF_STRONG_PRODUCT = 95
_CONF_ALL_PRODUCT = 80
_CONF_UNCONSTRAINED_PRODUCT = 60


@dataclass(slots=True, frozen=True)
class ClassificationConfig:
    """Seeds the keyword sets used when building a profile from a query.

    ``required_terms`` overrides the query-derived required tokens when set;
    otherwise required terms are the query's own tokens. The remaining sets
    default to the generic, marketplace-independent lists in
    :mod:`digital_arbitrage.classification.keywords`.
    """

    accessory_terms: tuple[str, ...] = DEFAULT_ACCESSORY_TERMS
    part_terms: tuple[str, ...] = DEFAULT_PART_TERMS
    excluded_terms: tuple[str, ...] = DEFAULT_EXCLUDED_TERMS
    required_terms: tuple[str, ...] | None = None


def build_search_profile(query: str, config: ClassificationConfig | None = None) -> SearchProfile:
    """Build a :class:`SearchProfile` for ``query`` using ``config`` defaults.

    Required terms are the query's tokens (so ``"RTX 4090"`` requires both
    ``rtx`` and ``4090``) unless the config overrides them.
    """
    cfg = config or ClassificationConfig()
    required = cfg.required_terms if cfg.required_terms is not None else tokenize(query)
    return SearchProfile(
        required_terms=tuple(required),
        excluded_terms=tuple(cfg.excluded_terms),
        accessory_terms=tuple(cfg.accessory_terms),
        part_terms=tuple(cfg.part_terms),
    )


def _required_tokens(profile: SearchProfile) -> tuple[str, ...]:
    """Flatten the profile's required terms into individual tokens."""
    return tuple(tok for term in profile.required_terms for tok in tokenize(term))


def _phrase(tokens: tuple[str, ...]) -> str:
    return " ".join(tokens)


def classify_title(title: str, profile: SearchProfile) -> ListingClassification:
    """Classify a single ``title`` against ``profile`` (the core algorithm)."""
    text = prepare(title)

    excluded = first_word_match(profile.excluded_terms, text)
    if excluded is not None:
        return ListingClassification(
            Classification.REJECTED, _CONF_EXCLUDED, f"Excluded keyword: {excluded}"
        )

    required = _required_tokens(profile)
    if required:
        present = [tok for tok in required if compact_match(tok, text)]
        if not present:
            return ListingClassification(
                Classification.REJECTED,
                _CONF_MISSING,
                f"Missing required term: {_phrase(required)}",
            )
        if len(present) < len(required):
            missing = [tok for tok in required if tok not in present]
            return ListingClassification(
                Classification.UNKNOWN,
                _CONF_PARTIAL,
                f"Partial match; missing required term: {_phrase(tuple(missing))}",
            )

    keyword_verdict = _keyword_verdict(profile, text)
    if keyword_verdict is not None:
        return keyword_verdict

    return _complete_product(required, text)


def _keyword_verdict(profile: SearchProfile, text: MatchableText) -> ListingClassification | None:
    """Accessory/part verdict, or ``None`` if neither keyword type is present."""
    accessories = all_word_matches(profile.accessory_terms, text)
    if accessories:
        confidence = _CONF_ACCESSORY if len(accessories) == 1 else _CONF_ACCESSORY_MULTI
        label = "keyword" if len(accessories) == 1 else "keywords"
        return ListingClassification(
            Classification.ACCESSORY, confidence, f"Accessory {label}: {', '.join(accessories)}"
        )

    parts = all_word_matches(profile.part_terms, text)
    if parts:
        label = "keyword" if len(parts) == 1 else "keywords"
        return ListingClassification(
            Classification.PART, _CONF_PART, f"Part {label}: {', '.join(parts)}"
        )

    return None


def _complete_product(required: tuple[str, ...], text: MatchableText) -> ListingClassification:
    """Score a listing that passed the required-term gate with no add-on keyword."""
    if not required:
        return ListingClassification(
            Classification.COMPLETE_PRODUCT,
            _CONF_UNCONSTRAINED_PRODUCT,
            "No required terms defined",
        )
    if compact_match(_phrase(required), text):
        return ListingClassification(
            Classification.COMPLETE_PRODUCT, _CONF_STRONG_PRODUCT, "Strong model match"
        )
    return ListingClassification(
        Classification.COMPLETE_PRODUCT, _CONF_ALL_PRODUCT, "All required terms present"
    )


class ListingClassifier:
    """Stateful convenience wrapper around :func:`classify_title`.

    Holds a :class:`ClassificationConfig` (keyword defaults), builds a
    :class:`SearchProfile` per query, and can classify normalized listings in
    place. Deterministic and side-effect free apart from setting each listing's
    ``classification`` attribute.
    """

    def __init__(self, config: ClassificationConfig | None = None) -> None:
        self.config = config or ClassificationConfig()

    def profile_for(self, query: str) -> SearchProfile:
        """Build the search profile this classifier will use for ``query``."""
        return build_search_profile(query, self.config)

    def classify(self, listing: NormalizedListing, profile: SearchProfile) -> ListingClassification:
        """Classify ``listing`` by its title and store the verdict on it."""
        result = classify_title(listing.title, profile)
        listing.classification = result
        return result

    def classify_many(
        self, listings: Iterable[NormalizedListing], profile: SearchProfile
    ) -> list[ListingClassification]:
        """Classify every listing in place, returning the verdicts in order."""
        return [self.classify(listing, profile) for listing in listings]
