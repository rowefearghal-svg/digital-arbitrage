"""The public Normalizer and its default pipeline.

``Normalizer`` is provider-agnostic: it accepts any
:class:`~digital_arbitrage.product_scanner.models.Listing` (real or mocked) and
returns a :class:`NormalizedListing`. Behaviour is driven by
:class:`NormalizationConfig`, or a fully custom pipeline can be supplied.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..product_scanner.models import Condition, Listing
from .conditions import ConditionNormalizer
from .currency import CurrencyNormalizer
from .location import LocationNormalizer
from .models import NormalizedListing
from .pipeline import NormalizationPipeline
from .steps import (
    ConditionNormalizationStep,
    CurrencyNormalizationStep,
    LocationNormalizationStep,
    TextCleaningStep,
    TitleCleanupStep,
    UnicodeNormalizationStep,
    WhitespaceNormalizationStep,
)
from .text import UnicodeForm


@dataclass(slots=True)
class NormalizationConfig:
    """Tunable options for the default pipeline."""

    unicode_form: UnicodeForm = "NFKC"
    remove_emoji: bool = True
    lowercase_title: bool = True
    remove_filler_words: bool = True
    filler_words: frozenset[str] | None = None
    default_currency: str | None = None
    currency_aliases: dict[str, str] | None = None
    condition_aliases: dict[str, Condition] | None = None
    location_aliases: dict[str, str] | None = None


def build_default_pipeline(config: NormalizationConfig | None = None) -> NormalizationPipeline:
    """Construct the standard normalization pipeline from ``config``."""
    cfg = config or NormalizationConfig()
    currency = CurrencyNormalizer(default=cfg.default_currency, aliases=cfg.currency_aliases)
    condition = ConditionNormalizer(aliases=cfg.condition_aliases)
    location = LocationNormalizer(aliases=cfg.location_aliases)
    return NormalizationPipeline(
        [
            UnicodeNormalizationStep(form=cfg.unicode_form),
            TextCleaningStep(remove_emoji=cfg.remove_emoji),
            WhitespaceNormalizationStep(),
            TitleCleanupStep(
                lowercase=cfg.lowercase_title,
                remove_filler=cfg.remove_filler_words,
                filler_words=cfg.filler_words,
            ),
            CurrencyNormalizationStep(currency),
            ConditionNormalizationStep(condition),
            LocationNormalizationStep(location),
        ]
    )


class Normalizer:
    """Turn raw listings into consistent :class:`NormalizedListing` objects."""

    def __init__(
        self,
        *,
        config: NormalizationConfig | None = None,
        pipeline: NormalizationPipeline | None = None,
    ) -> None:
        self.config = config or NormalizationConfig()
        self.pipeline = pipeline or build_default_pipeline(self.config)

    def normalize(self, listing: Listing) -> NormalizedListing:
        """Normalize a single listing."""
        normalized = NormalizedListing.from_listing(listing)
        self.pipeline.run(normalized)
        return normalized

    def normalize_many(self, listings: Iterable[Listing]) -> list[NormalizedListing]:
        """Normalize an iterable of listings."""
        return [self.normalize(listing) for listing in listings]
