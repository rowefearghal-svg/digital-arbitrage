"""Observation admission: ``NormalizedListing`` -> :class:`Observation`.

This is the smallest safe shadow-insertion point identified during
repository reconnaissance: it reads an existing
:class:`~digital_arbitrage.normalization.models.NormalizedListing` without
mutating it and never writes back into upstream models (see
``docs/decisions`` ADR-PUE-001).

The current ``Listing``/``NormalizedListing`` models do not carry a
description, provider category or structured-attributes field. Those PUE
`Observation` fields are populated as ``None``/empty where the upstream data
does not exist; ``listing.source.extra`` (provider-specific extras) is used
as the best-available structured-attributes source. This is a documented,
non-blocking deviation - see the Sprint 1 completion report.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from .models import Observation, ProcessingContext
from .validation import PueValidationError

if TYPE_CHECKING:
    from ..normalization.models import NormalizedListing


class IdFactory(Protocol):
    """Injectable UUID/identifier factory."""

    def __call__(self) -> str: ...


class Clock(Protocol):
    """Injectable clock, returning a timezone-aware ``datetime``."""

    def __call__(self) -> datetime: ...


def compute_source_fingerprint(
    *,
    provider: str,
    provider_listing_id: str,
    normalized_title: str,
    normalized_description: str | None,
    selected_attributes: Mapping[str, object],
) -> str:
    """Deterministic fingerprint over stable normalized fields (spec 7.2).

    Same inputs always produce the same fingerprint; used for duplicate/
    idempotency checks. It is *not* a substitute for object identity.
    """
    payload = {
        "provider": provider,
        "provider_listing_id": provider_listing_id,
        "normalized_title": normalized_title,
        "normalized_description": normalized_description or "",
        "attributes": {k: selected_attributes[k] for k in sorted(selected_attributes)},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def admit_observation(listing: NormalizedListing, context: ProcessingContext) -> Observation:
    """Admit a ``NormalizedListing`` into the PUE as an :class:`Observation`.

    Raises :class:`PueValidationError` on a malformed/unusable input (see
    mandatory acceptance case 25: malformed object -> ``PROCESSING_FAILED``).
    """
    if listing is None:
        raise PueValidationError("listing must not be None")

    source = getattr(listing, "source", None)
    if source is None:
        raise PueValidationError("listing.source must be present")

    provider = getattr(source, "provider", None)
    provider_listing_id = getattr(source, "listing_id", None)
    if not isinstance(provider, str) or not provider:
        raise PueValidationError("listing.source.provider must be a non-empty string")
    if not isinstance(provider_listing_id, str) or not provider_listing_id:
        raise PueValidationError("listing.source.listing_id must be a non-empty string")

    raw_title = getattr(source, "title", None)
    if not isinstance(raw_title, str):
        raise PueValidationError("listing.source.title must be a string")
    # Empty title is a valid *input* (acceptance case 24) but not admissible
    # into a usable Observation for extraction; callers handle abstention.
    normalized_title = getattr(listing, "title", raw_title)
    if not isinstance(normalized_title, str):
        raise PueValidationError("listing.title must be a string")

    raw_condition = None
    condition = getattr(listing, "condition", None)
    if condition is not None:
        raw_condition = getattr(condition, "value", str(condition))

    extra = getattr(source, "extra", None) or {}
    raw_attributes: dict[str, object] = dict(extra) if isinstance(extra, Mapping) else {}

    case_id = context.id_factory()
    observation_id = context.id_factory()

    fingerprint = compute_source_fingerprint(
        provider=provider,
        provider_listing_id=provider_listing_id,
        normalized_title=normalized_title,
        normalized_description=None,
        selected_attributes=raw_attributes,
    )

    return Observation(
        observation_id=observation_id,
        case_id=case_id,
        provider=provider,
        provider_listing_id=provider_listing_id,
        raw_title=raw_title,
        normalized_title=normalized_title,
        raw_description=None,
        raw_category=None,
        raw_condition=raw_condition,
        raw_attributes=raw_attributes,
        image_refs=(),
        acquired_at=context.clock(),
        source_fingerprint=fingerprint,
        schema_version=context.schema_version,
    )
