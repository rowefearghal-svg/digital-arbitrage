"""The deterministic product matcher.

``ProductMatcher`` compares two :class:`NormalizedListing` objects and estimates
whether they describe the same underlying product. It combines token similarity
with brand/model heuristics, applies configurable thresholds, and returns a
fully-explained :class:`MatchResult`. No scraping, pricing, or AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..normalization.models import NormalizedListing
from .brands import DEFAULT_BRANDS, extract_brands
from .models import MatchDecision, MatchResult
from .scoring import jaccard, model_tokens, overlap_coefficient, token_set


@dataclass(slots=True, frozen=True)
class MatchConfig:
    """Tunable thresholds and weights for :class:`ProductMatcher`.

    ``same_threshold`` and ``possible_threshold`` bound the three decisions.
    The remaining weights shape how brand/model agreement or conflict pulls the
    base token-similarity score up or down.
    """

    same_threshold: float = 0.72
    possible_threshold: float = 0.45
    #: Blend of Jaccard vs overlap coefficient for the base token score.
    overlap_weight: float = 0.35
    #: Score is capped at this value when model identifiers conflict.
    model_conflict_cap: float = 0.30
    #: Score is multiplied by this when brands conflict.
    brand_conflict_factor: float = 0.45
    #: Fraction of the remaining headroom added when models agree.
    shared_model_boost: float = 0.40
    #: Fraction of the remaining headroom added when brands agree.
    shared_brand_boost: float = 0.15
    brands: frozenset[str] = field(default=DEFAULT_BRANDS)

    def __post_init__(self) -> None:
        if not 0.0 <= self.possible_threshold <= self.same_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= possible <= same <= 1")
        if not 0.0 <= self.overlap_weight <= 1.0:
            raise ValueError("overlap_weight must be in [0, 1]")


def _tri_state(a: frozenset[str], b: frozenset[str]) -> bool | None:
    """Compare two feature sets: True=agree (share ≥1), False=conflict (both
    present but disjoint), None=not enough information."""
    if not a or not b:
        return None
    return bool(a & b)


class ProductMatcher:
    """Estimate whether two normalized listings are the same product."""

    def __init__(self, config: MatchConfig | None = None) -> None:
        self.config = config or MatchConfig()

    def _decide(self, score: float) -> MatchDecision:
        cfg = self.config
        if score >= cfg.same_threshold:
            return MatchDecision.SAME_PRODUCT
        if score >= cfg.possible_threshold:
            return MatchDecision.POSSIBLE_MATCH
        return MatchDecision.DIFFERENT_PRODUCT

    def match(self, listing_a: NormalizedListing, listing_b: NormalizedListing) -> MatchResult:
        """Compare two listings and return an explained :class:`MatchResult`."""
        cfg = self.config
        tokens_a = token_set(listing_a.title_tokens)
        tokens_b = token_set(listing_b.title_tokens)

        matched = tuple(sorted(tokens_a & tokens_b))
        unmatched = tuple(sorted(tokens_a ^ tokens_b))
        reasons: list[str] = []

        if not tokens_a or not tokens_b:
            reasons.append("one or both listings have no comparable tokens")
            return MatchResult(
                score=0.0,
                decision=MatchDecision.DIFFERENT_PRODUCT,
                reasons=tuple(reasons),
                matched_tokens=matched,
                unmatched_tokens=unmatched,
            )

        # Base similarity: blend Jaccard with the overlap coefficient.
        jac = jaccard(tokens_a, tokens_b)
        ovl = overlap_coefficient(tokens_a, tokens_b)
        score = (1.0 - cfg.overlap_weight) * jac + cfg.overlap_weight * ovl
        reasons.append(
            f"token similarity {score:.2f} "
            f"(jaccard={jac:.2f}, overlap={ovl:.2f}; {len(matched)} shared)"
        )

        # Model identifiers are the strongest deterministic signal.
        models_a = model_tokens(tokens_a)
        models_b = model_tokens(tokens_b)
        model_state = _tri_state(models_a, models_b)
        if model_state is True:
            shared = ", ".join(sorted(models_a & models_b))
            score += (1.0 - score) * cfg.shared_model_boost
            reasons.append(f"shared model identifier(s): {shared}")
        elif model_state is False:
            score = min(score, cfg.model_conflict_cap)
            reasons.append(
                f"conflicting model identifiers: {sorted(models_a)} vs {sorted(models_b)}"
            )

        # Brand agreement/conflict adjusts, but never dominates the model signal.
        brands_a = extract_brands(tokens_a, cfg.brands)
        brands_b = extract_brands(tokens_b, cfg.brands)
        brand_state = _tri_state(brands_a, brands_b)
        if brand_state is True:
            shared = ", ".join(sorted(brands_a & brands_b))
            score += (1.0 - score) * cfg.shared_brand_boost
            reasons.append(f"shared brand: {shared}")
        elif brand_state is False:
            score *= cfg.brand_conflict_factor
            reasons.append(f"conflicting brands: {sorted(brands_a)} vs {sorted(brands_b)}")

        score = round(max(0.0, min(1.0, score)), 4)
        decision = self._decide(score)
        reasons.append(f"decision {decision.value} at score {score:.2f}")

        return MatchResult(
            score=score,
            decision=decision,
            reasons=tuple(reasons),
            matched_tokens=matched,
            unmatched_tokens=unmatched,
        )
