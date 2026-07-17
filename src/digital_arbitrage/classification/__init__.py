"""Marketplace-independent listing classification.

Classifies each listing by *title only* (deterministic; no images, LLMs, or
external services) into one of :class:`Classification` -
``COMPLETE_PRODUCT`` / ``ACCESSORY`` / ``PART`` / ``UNKNOWN`` / ``REJECTED`` -
so downstream stages can tell the real product apart from cables, adapters,
spare fans, and unrelated keyword matches. The same classifier serves every
provider (see ADR-022).

Quick start::

    from digital_arbitrage.classification import build_search_profile, classify_title

    profile = build_search_profile("rtx 4090")
    verdict = classify_title("12VHPWR Cable for RTX4090", profile)
    print(verdict.classification, verdict.match_confidence, verdict.reason)
"""

from __future__ import annotations

from .classifier import (
    ClassificationConfig,
    ListingClassifier,
    build_search_profile,
    classify_title,
)
from .keywords import (
    DEFAULT_ACCESSORY_TERMS,
    DEFAULT_EXCLUDED_TERMS,
    DEFAULT_PART_TERMS,
)
from .matching import MatchableText, compact_match, prepare, word_match
from .models import Classification, ListingClassification, SearchProfile

__all__ = [
    "DEFAULT_ACCESSORY_TERMS",
    "DEFAULT_EXCLUDED_TERMS",
    "DEFAULT_PART_TERMS",
    "Classification",
    "ClassificationConfig",
    "ListingClassification",
    "ListingClassifier",
    "MatchableText",
    "SearchProfile",
    "build_search_profile",
    "classify_title",
    "compact_match",
    "prepare",
    "word_match",
]
