"""Deterministic product matching.

Estimates whether two normalized listings refer to the same underlying product
using token similarity plus brand/model heuristics. Every decision is explained
via :class:`MatchResult.reasons`. No scraping, pricing, or AI (see ADR-005).

Quick start::

    from digital_arbitrage.product_matching import ProductMatcher

    result = ProductMatcher().match(normalized_a, normalized_b)
    print(result.decision, result.score, result.reasons)
"""

from __future__ import annotations

from .brands import DEFAULT_BRANDS, extract_brands
from .matcher import MatchConfig, ProductMatcher
from .models import MatchDecision, MatchResult
from .scoring import is_model_token, jaccard, model_tokens, overlap_coefficient, token_set

__all__ = [
    "DEFAULT_BRANDS",
    "MatchConfig",
    "MatchDecision",
    "MatchResult",
    "ProductMatcher",
    "extract_brands",
    "is_model_token",
    "jaccard",
    "model_tokens",
    "overlap_coefficient",
    "token_set",
]
