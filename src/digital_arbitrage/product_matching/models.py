"""Data model for a product-matching decision.

A :class:`MatchResult` captures *why* two listings were (or were not) judged the
same product, not just the verdict - the ``reasons`` and token breakdown make
every decision auditable and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MatchDecision(StrEnum):
    """The categorical outcome of a match comparison."""

    SAME_PRODUCT = "same_product"
    POSSIBLE_MATCH = "possible_match"
    DIFFERENT_PRODUCT = "different_product"


@dataclass(slots=True, frozen=True)
class MatchResult:
    """The outcome of comparing two normalized listings."""

    score: float
    decision: MatchDecision
    reasons: tuple[str, ...] = ()
    matched_tokens: tuple[str, ...] = ()
    unmatched_tokens: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")

    @property
    def is_match(self) -> bool:
        """True when the decision is a confident same-product match."""
        return self.decision is MatchDecision.SAME_PRODUCT
