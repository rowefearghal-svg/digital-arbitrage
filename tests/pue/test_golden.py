"""Golden Reasoning Record tests (spec section 23.3).

Five stable cases with deterministic ids/times covering IDENTIFIED,
PARTIALLY_IDENTIFIED, CLASSIFIED, ABSTAINED and OUTSIDE_SUPPORTED_DOMAIN.
Regenerate with ``python scripts/gen_pue_golden.py`` (repo root) only when a
deliberate, reviewed behavior change requires it - a diff here should
always be inspected carefully (spec 23.3).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_scanner.models import Listing
from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.persistence import reasoning_record_to_dict

from .conftest import DeterministicIdFactory, FixedClock

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pue" / "golden"

#: Wall-clock stage timings are inherently non-deterministic; everything
#: else in operational_metrics (counts) is deterministic and kept.
_VOLATILE_METRIC_KEYS = {
    "extraction_ms",
    "claims_hypotheses_ms",
    "retrieval_ms",
    "evaluation_ms",
    "decision_explanation_ms",
    "total_ms",
}


def _stable(payload: dict) -> dict:
    payload = dict(payload)
    metrics = dict(payload.get("operational_metrics", {}))
    for key in _VOLATILE_METRIC_KEYS:
        metrics.pop(key, None)
    payload["operational_metrics"] = metrics
    return payload


GOLDEN_CASES = {
    "golden_exact_identification": "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G",
    "golden_partial_identification": "NVIDIA RTX 4090",
    "golden_classified_accessory": "RTX 4090 Waterblock Full Cover GPU Cooling Block",
    "golden_abstained": "   ",
    "golden_outside_domain": "Samsung?",
}


@pytest.mark.parametrize("name,title", list(GOLDEN_CASES.items()), ids=list(GOLDEN_CASES))
def test_golden_record_matches(name: str, title: str, repository) -> None:
    context = orchestration.build_default_context(
        id_factory=DeterministicIdFactory(), clock=FixedClock()
    )
    listing = Listing(
        listing_id="golden-1",
        title=title,
        provider="golden-provider",
        url="https://example.test/golden",
    )
    normalized = NormalizedListing.from_listing(listing)
    record = orchestration.process_one(normalized, context, repository=repository)
    actual = _stable(reasoning_record_to_dict(record))

    expected = _stable(json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8")))
    assert actual == expected, f"golden record {name} changed - review before regenerating"


def test_golden_fixtures_are_deterministic_across_two_runs(repository) -> None:
    """Deterministic replay: same inputs/versions -> equivalent Decision."""
    for title in GOLDEN_CASES.values():
        context_a = orchestration.build_default_context(
            id_factory=DeterministicIdFactory(), clock=FixedClock()
        )
        context_b = orchestration.build_default_context(
            id_factory=DeterministicIdFactory(), clock=FixedClock()
        )
        listing = Listing(
            listing_id="golden-1",
            title=title,
            provider="golden-provider",
            url="https://example.test/golden",
        )
        normalized = NormalizedListing.from_listing(listing)
        record_a = orchestration.process_one(normalized, context_a, repository=repository)
        record_b = orchestration.process_one(normalized, context_b, repository=repository)
        assert _stable(reasoning_record_to_dict(record_a)) == _stable(
            reasoning_record_to_dict(record_b)
        )
