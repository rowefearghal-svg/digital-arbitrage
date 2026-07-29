"""Shared fixtures for the PUE test suite.

Uses a deterministic, injectable id_factory and clock (spec: "UUID object
identity with injectable ID factory") so tests are reproducible.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime

import pytest

from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_scanner.models import Condition, Listing
from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.catalogue import JsonCandidateRepository


class DeterministicIdFactory:
    """Produces ``prefix-0001``, ``prefix-0002``, ... in call order."""

    def __init__(self, prefix: str = "id") -> None:
        self._counter = itertools.count(1)
        self._prefix = prefix

    def __call__(self) -> str:
        return f"{self._prefix}-{next(self._counter):06d}"


class FixedClock:
    def __init__(self, when: datetime | None = None) -> None:
        self._when = when or datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._when


@pytest.fixture
def deterministic_context():
    return orchestration.build_default_context(
        id_factory=DeterministicIdFactory(), clock=FixedClock()
    )


@pytest.fixture(scope="session")
def repository():
    return JsonCandidateRepository()


@pytest.fixture
def sample_reasoning_record(repository):
    """A representative, fully-populated ReasoningRecord for serialization tests."""
    context = orchestration.build_default_context(
        id_factory=DeterministicIdFactory(), clock=FixedClock()
    )
    listing = make_normalized("ASUS TUF RTX 4090 OC TUF-RTX4090-O24G")
    return orchestration.process_one(listing, context, repository=repository)


def make_listing(
    title: str,
    *,
    listing_id: str = "listing-1",
    provider: str = "test-provider",
    condition: Condition = Condition.USED,
    extra: dict | None = None,
) -> Listing:
    return Listing(
        listing_id=listing_id,
        title=title,
        provider=provider,
        url="https://example.test/listing",
        condition=condition,
        extra=extra or {},
    )


def make_normalized(
    title: str,
    *,
    listing_id: str = "listing-1",
    provider: str = "test-provider",
    condition: Condition = Condition.USED,
    extra: dict | None = None,
) -> NormalizedListing:
    listing = make_listing(
        title, listing_id=listing_id, provider=provider, condition=condition, extra=extra
    )
    normalized = NormalizedListing.from_listing(listing)
    normalized.title_tokens = tuple(title.lower().split())
    return normalized
