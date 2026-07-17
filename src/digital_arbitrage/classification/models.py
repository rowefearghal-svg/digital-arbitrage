"""Data models for listing classification.

These types are deliberately marketplace-independent: a
:class:`SearchProfile` describes *what the user is looking for* in terms of
plain keyword sets, and a :class:`ListingClassification` is the verdict the
classifier attaches to a single listing. Nothing here knows about eBay (or any
other provider) - future providers reuse the same objects. See ADR-022.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Classification(StrEnum):
    """How a listing relates to the product the user searched for.

    Ordered loosely from "most desirable" to "least": a
    :attr:`COMPLETE_PRODUCT` is the actual item, an :attr:`ACCESSORY` or
    :attr:`PART` is related-but-not-the-item, :attr:`UNKNOWN` is ambiguous, and
    :attr:`REJECTED` is confidently unrelated.
    """

    COMPLETE_PRODUCT = "complete_product"
    ACCESSORY = "accessory"
    PART = "part"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


@dataclass(slots=True, frozen=True)
class ListingClassification:
    """The classifier's verdict for a single listing.

    ``match_confidence`` is a deterministic 0-100 score expressing how sure the
    classifier is about the assigned ``classification`` (not a probability).
    ``reason`` is a short, human-readable justification, e.g.
    ``"Accessory keyword: cable"`` or ``"Strong model match"``.
    """

    classification: Classification
    match_confidence: int
    reason: str

    def __post_init__(self) -> None:
        if not 0 <= self.match_confidence <= 100:
            raise ValueError("match_confidence must be in [0, 100]")
        if not self.reason:
            raise ValueError("reason must not be empty")

    def to_dict(self) -> dict[str, str | int]:
        """JSON-serialisable view of the classification."""
        return {
            "classification": self.classification.value,
            "match_confidence": self.match_confidence,
            "reason": self.reason,
        }


@dataclass(slots=True, frozen=True)
class SearchProfile:
    """Marketplace-independent description of the searched-for product.

    Every field is a tuple of plain terms; a term may be a single word
    (``"cable"``) or a multi-word phrase (``"power supply"``). Matching is
    case-, spacing-, punctuation-, and hyphen-insensitive (see
    :mod:`digital_arbitrage.classification.matching`).

    * ``required_terms`` - tokens that must be present for the listing to be the
      product at all (typically derived from the search query, e.g.
      ``("rtx", "4090")``). Absence drives ``REJECTED`` / ``UNKNOWN``.
    * ``excluded_terms`` - terms that disqualify a listing outright (e.g.
      ``"empty box"``, ``"sticker"``).
    * ``accessory_terms`` - terms marking an add-on rather than the item itself
      (e.g. ``"cable"``, ``"adapter"``).
    * ``part_terms`` - terms marking a component / spare rather than the whole
      item (e.g. ``"fan"``, ``"replacement"``).
    """

    required_terms: tuple[str, ...] = ()
    excluded_terms: tuple[str, ...] = ()
    accessory_terms: tuple[str, ...] = ()
    part_terms: tuple[str, ...] = ()
