"""Concrete normalization steps.

Each step handles one concern from the spec and is independently testable. They
delegate the actual string work to :mod:`.text` and the domain mappings to the
currency/condition/location normalizers.
"""

from __future__ import annotations

from typing import ClassVar

from .conditions import ConditionNormalizer
from .currency import CurrencyNormalizer
from .location import LocationNormalizer
from .models import NormalizedListing
from .pipeline import NormalizationStep
from .text import (
    UnicodeForm,
    collapse_whitespace,
    normalize_punctuation,
    normalize_unicode,
    remove_control_characters,
    remove_symbols_and_emoji,
    tokenize,
)


class UnicodeNormalizationStep(NormalizationStep):
    """Apply a Unicode normalization form to the title."""

    name = "unicode"

    def __init__(self, form: UnicodeForm = "NFKC") -> None:
        super().__init__()
        self.form = form

    def apply(self, listing: NormalizedListing) -> None:
        listing.title = normalize_unicode(listing.title, self.form)


class TextCleaningStep(NormalizationStep):
    """Strip control characters, fold punctuation, and (optionally) drop emoji."""

    name = "text_cleaning"

    def __init__(self, *, remove_emoji: bool = True) -> None:
        super().__init__()
        self.remove_emoji = remove_emoji

    def apply(self, listing: NormalizedListing) -> None:
        title = remove_control_characters(listing.title)
        title = normalize_punctuation(title)
        if self.remove_emoji:
            title = remove_symbols_and_emoji(title)
        listing.title = title


class WhitespaceNormalizationStep(NormalizationStep):
    """Collapse runs of whitespace and trim the title."""

    name = "whitespace"

    def apply(self, listing: NormalizedListing) -> None:
        listing.title = collapse_whitespace(listing.title)


class TitleCleanupStep(NormalizationStep):
    """Finalise the title (optional lowercasing) and derive comparison tokens."""

    name = "title_cleanup"

    #: Low-signal words dropped from tokens (not from the display title).
    DEFAULT_FILLER: ClassVar[frozenset[str]] = frozenset(
        {"the", "a", "an", "for", "with", "and", "brand", "new", "genuine", "official"}
    )

    def __init__(
        self,
        *,
        lowercase: bool = True,
        remove_filler: bool = True,
        filler_words: frozenset[str] | None = None,
    ) -> None:
        super().__init__()
        self.lowercase = lowercase
        self.remove_filler = remove_filler
        self.filler_words = filler_words if filler_words is not None else self.DEFAULT_FILLER

    def apply(self, listing: NormalizedListing) -> None:
        title = collapse_whitespace(listing.title)
        if self.lowercase:
            title = title.lower()
        listing.title = title
        tokens = tokenize(title)
        if self.remove_filler:
            tokens = tuple(t for t in tokens if t not in self.filler_words)
        listing.title_tokens = tokens


class CurrencyNormalizationStep(NormalizationStep):
    """Resolve the currency to an ISO 4217 code."""

    name = "currency"

    def __init__(self, normalizer: CurrencyNormalizer | None = None) -> None:
        super().__init__()
        self.normalizer = normalizer or CurrencyNormalizer()

    def apply(self, listing: NormalizedListing) -> None:
        listing.currency = self.normalizer.normalize(listing.currency)


class ConditionNormalizationStep(NormalizationStep):
    """Resolve the condition to the shared Condition enum."""

    name = "condition"

    def __init__(self, normalizer: ConditionNormalizer | None = None) -> None:
        super().__init__()
        self.normalizer = normalizer or ConditionNormalizer()

    def apply(self, listing: NormalizedListing) -> None:
        listing.condition = self.normalizer.normalize(listing.condition)


class LocationNormalizationStep(NormalizationStep):
    """Clean and canonicalise the location."""

    name = "location"

    def __init__(self, normalizer: LocationNormalizer | None = None) -> None:
        super().__init__()
        self.normalizer = normalizer or LocationNormalizer()

    def apply(self, listing: NormalizedListing) -> None:
        listing.location = self.normalizer.normalize(listing.location)
