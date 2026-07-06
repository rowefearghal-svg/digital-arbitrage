"""Deterministic listing fingerprints.

A fingerprint is a stable, content-derived identifier for a normalized listing.
Two listings with the same comparable title tokens produce the same fingerprint
regardless of provider, casing, or ordering - it is used as a group identity and
as a fast pre-grouping key. Fingerprints never depend on runtime state, so they
are reproducible across runs and machines.
"""

from __future__ import annotations

import hashlib

from ..normalization.models import NormalizedListing

#: Length of the hex digest exposed as the fingerprint.
_FINGERPRINT_LENGTH = 16


def signature(listing: NormalizedListing) -> str:
    """Return the human-readable signature a fingerprint is derived from."""
    tokens = " ".join(sorted(set(listing.title_tokens)))
    return f"tokens={tokens}|currency={listing.currency or ''}|condition={listing.condition.value}"


def listing_fingerprint(listing: NormalizedListing) -> str:
    """Return a deterministic fingerprint for ``listing``."""
    digest = hashlib.sha256(signature(listing).encode("utf-8")).hexdigest()
    return digest[:_FINGERPRINT_LENGTH]
