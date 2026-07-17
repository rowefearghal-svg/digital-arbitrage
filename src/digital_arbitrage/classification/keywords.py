"""Default, marketplace-independent keyword sets.

These are intentionally generic (add-ons, spares, and merchandise that show up
across many product searches) rather than tied to any single product or
provider. They seed a :class:`~digital_arbitrage.classification.models.SearchProfile`
when one is built from a bare query; callers can override any of them.

Terms may be single words or phrases; matching is case/spacing/hyphen
insensitive (see :mod:`digital_arbitrage.classification.matching`). Phrases are
preferred over ambiguous single words to avoid false positives - e.g.
``"empty box"`` rather than ``"box"``, since a genuine listing may mention its
original box.
"""

from __future__ import annotations

#: Add-ons sold alongside the product rather than the product itself.
DEFAULT_ACCESSORY_TERMS: tuple[str, ...] = (
    "cable",
    "cables",
    "power cable",
    "power lead",
    "power cord",
    "adapter",
    "adaptor",
    "connector",
    "extension",
    "riser",
    "riser cable",
    "bracket",
    "mount",
    "stand",
    "holder",
    "sleeve",
    "bag",
    "cover",
    "dust cover",
    "skin",
    "waterblock",
    "water block",
    "anti sag",
    "support bracket",
)

#: Components or spares - a piece of the product, not the whole item.
DEFAULT_PART_TERMS: tuple[str, ...] = (
    "fan",
    "fans",
    "replacement",
    "replacement fan",
    "spare",
    "spares",
    "spare part",
    "spare parts",
    "for parts",
    "spares or repair",
    "faulty",
    "not working",
    "repair",
    "pcb",
    "heatsink",
    "heat sink",
    "cooler",
    "shroud",
    "backplate",
    "thermal pad",
    "thermal pads",
    "capacitor",
    "vram",
)

#: Clearly-not-the-product listings (merchandise / empties). Kept conservative
#: and phrase-based so real product listings are never disqualified.
DEFAULT_EXCLUDED_TERMS: tuple[str, ...] = (
    "empty box",
    "box only",
    "just the box",
    "poster",
    "sticker",
    "stickers",
    "keyring",
    "keychain",
    "mug",
    "t shirt",
    "tshirt",
    "case badge",
    "figurine",
    "mouse mat",
    "mousemat",
    "mouse pad",
    "coaster",
)
