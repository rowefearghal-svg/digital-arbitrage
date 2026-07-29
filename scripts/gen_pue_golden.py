"""Regenerate the PUE golden Reasoning Records.

Usage (from repo root): ``python _gen_golden.py``

Only run this after a deliberate, reviewed behavior change. Diff the
resulting files carefully before committing (spec 23.3) - a golden-record
diff is a signal that Decision behavior changed, not just IDs/timestamps
(both are already fixed via a deterministic id factory and clock).
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.pue.conftest import DeterministicIdFactory, FixedClock

from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_scanner.models import Listing
from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.catalogue import JsonCandidateRepository
from digital_arbitrage.pue.persistence import reasoning_record_to_dict

GOLDEN_DIR = Path("tests/fixtures/pue/golden")
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

CASES = {
    "golden_exact_identification": "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G",
    "golden_partial_identification": "NVIDIA RTX 4090",
    "golden_classified_accessory": "RTX 4090 Waterblock Full Cover GPU Cooling Block",
    "golden_abstained": "   ",
    "golden_outside_domain": "Samsung?",
}


def main() -> None:
    repo = JsonCandidateRepository()
    for name, title in CASES.items():
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
        record = orchestration.process_one(normalized, context, repository=repo)
        payload = reasoning_record_to_dict(record)
        (GOLDEN_DIR / f"{name}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        print("wrote", name, record.decision.decision_type)


if __name__ == "__main__":
    main()
