"""Listing normalization.

Converts raw marketplace :class:`Listing` objects into a consistent internal
:class:`NormalizedListing` representation via a configurable, provider-agnostic
pipeline.

Quick start::

    from digital_arbitrage.normalization import Normalizer

    normalizer = Normalizer()
    normalized = normalizer.normalize(listing)
    print(normalized.title, normalized.currency, normalized.condition)
"""

from __future__ import annotations

from .conditions import ConditionNormalizer
from .currency import CurrencyNormalizer
from .location import LocationNormalizer
from .models import NormalizedListing
from .normalizer import NormalizationConfig, Normalizer, build_default_pipeline
from .pipeline import NormalizationPipeline, NormalizationStep
from .steps import (
    ConditionNormalizationStep,
    CurrencyNormalizationStep,
    LocationNormalizationStep,
    TextCleaningStep,
    TitleCleanupStep,
    UnicodeNormalizationStep,
    WhitespaceNormalizationStep,
)

__all__ = [
    "ConditionNormalizationStep",
    "ConditionNormalizer",
    "CurrencyNormalizationStep",
    "CurrencyNormalizer",
    "LocationNormalizationStep",
    "LocationNormalizer",
    "NormalizationConfig",
    "NormalizationPipeline",
    "NormalizationStep",
    "NormalizedListing",
    "Normalizer",
    "TextCleaningStep",
    "TitleCleanupStep",
    "UnicodeNormalizationStep",
    "WhitespaceNormalizationStep",
    "build_default_pipeline",
]
