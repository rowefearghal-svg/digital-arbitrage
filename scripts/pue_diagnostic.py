"""Local synthetic PUE performance diagnostic (spec section 20 / 4.4).

Generates a synthetic batch of title-only listings drawn from the mandatory
acceptance titles (cycled), runs them through the full PUE pipeline, and
reports:

* listings/second;
* median and p95 latency;
* per-stage timings (extraction, retrieval, evaluation, decision+explanation);
* serialized Reasoning Record size;
* peak memory during a 10,000-case run.

Usage (from repo root)::

    python scripts/pue_diagnostic.py --count 10000

Correctness remains the release gate; this script only measures throughput.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import time
import tracemalloc

from digital_arbitrage.normalization.models import NormalizedListing
from digital_arbitrage.product_scanner.models import Listing
from digital_arbitrage.pue import orchestration
from digital_arbitrage.pue.catalogue import JsonCandidateRepository
from digital_arbitrage.pue.persistence import reasoning_record_to_json

_TITLES = [
    "Samsung?",
    "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
    "ASUS TUF RTX 4090 OC TUF-RTX4090-O24G",
    "RTX 4090 Waterblock Full Cover GPU Cooling Block",
    "Empty RTX 4090 Founders Edition Box Only",
    "RTX 4090 replacement fan set",
    "12VHPWR power adapter for RTX 4090",
    "RTX 4090 GPU not included - water block only",
    "ASUS RTX 4090 with EK water block",
    "NVIDIA RTX 4090",
    "RTX 3060 12GB",
    "RTX 3060",
    "RTX 4080 Super Gaming OC",
    "Laptop RTX 4090 GPU",
    "Graphics card excellent condition",
    "Apple laptop good condition",
    "For parts RTX 4090 not working",
    "RTX 4090 retail box included",
    "RTX 5099 Ultra graphics card",
    "Compatible with RTX 4090",
    "RTX 4090 + PSU bundle",
]


def _make_listings(count: int) -> list[NormalizedListing]:
    listings = []
    for i, title in zip(range(count), itertools.cycle(_TITLES)):
        raw = Listing(
            listing_id=f"diag-{i}",
            title=title,
            provider="diagnostic",
            url="https://example.test/diag",
        )
        listings.append(NormalizedListing.from_listing(raw))
    return listings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    args = parser.parse_args()

    repository = JsonCandidateRepository()
    context = orchestration.build_default_context()
    listings = _make_listings(args.count)

    tracemalloc.start()
    latencies_ms: list[float] = []
    stage_totals = {
        "extraction_ms": 0.0,
        "retrieval_ms": 0.0,
        "evaluation_ms": 0.0,
        "decision_explanation_ms": 0.0,
    }
    record_sizes: list[int] = []

    start = time.perf_counter()
    for listing in listings:
        t0 = time.perf_counter()
        record = orchestration.process_one(listing, context, repository=repository)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000)
        for key in stage_totals:
            stage_totals[key] += record.operational_metrics.get(key, 0.0)
        if len(record_sizes) < 200:  # sampling is enough for a size estimate
            record_sizes.append(len(reasoning_record_to_json(record)))
    elapsed = time.perf_counter() - start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    latencies_ms.sort()
    n = len(latencies_ms)
    median = latencies_ms[n // 2]
    p95 = latencies_ms[int(n * 0.95)] if n else 0.0

    report = {
        "listings_processed": n,
        "elapsed_seconds": round(elapsed, 4),
        "listings_per_second": round(n / elapsed, 2) if elapsed else float("inf"),
        "median_latency_ms": round(median, 4),
        "p95_latency_ms": round(p95, 4),
        "mean_stage_ms": {k: round(v / n, 4) for k, v in stage_totals.items()} if n else {},
        "mean_record_size_bytes": round(statistics.mean(record_sizes), 1) if record_sizes else 0,
        "peak_memory_mb": round(peak_bytes / (1024 * 1024), 2),
        "target_listings_per_second": 25,
        "meets_target": (n / elapsed) >= 25 if elapsed else True,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
