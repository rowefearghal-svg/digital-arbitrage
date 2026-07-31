"""Reproducible local performance/memory diagnostic (Sprint 3, brief
section 13).

Deterministic, title-only, synthetic listings - no provider acquisition, no
network. Uses only standard-library tooling (:mod:`tracemalloc`, :mod:`time`,
:mod:`platform`) - no new dependency, no distributed/queue infrastructure
(brief section 13's explicit non-goals).
"""

from __future__ import annotations

import platform
import sys
import time
import tracemalloc
from dataclasses import dataclass

from ..normalization.models import NormalizedListing
from ..product_scanner.models import Condition, Listing
from .catalogue import JsonCandidateRepository
from .orchestration import build_default_context, process_one

#: Deterministic synthetic title templates - varied enough to exercise every
#: reasoning stage (exact/partial identification, accessories, packaging,
#: unknown domain) without depending on any live marketplace data.
_TITLE_TEMPLATES = (
    "NVIDIA GeForce RTX 4090 Founders Edition 24GB #{n}",
    "ASUS TUF Gaming GeForce RTX 4090 OC 24GB TUF-RTX4090-O24G variant {n}",
    "RTX {n} Graphics Card",
    "AMD Radeon RX 7900 XTX Reference 24GB unit {n}",
    "RTX 4090 replacement fan set batch {n}",
    "Empty RTX 4090 Founders Edition Box Only lot {n}",
    "Intel Arc A770 Limited Edition 16GB #{n}",
    "Samsung Galaxy S23 case {n}",
    "12VHPWR power adapter for RTX 4090 pack {n}",
    "MSI GeForce RTX 3060 Ventus 2X 12GB unit {n}",
)


def _synthetic_listing(index: int) -> NormalizedListing:
    template = _TITLE_TEMPLATES[index % len(_TITLE_TEMPLATES)]
    title = template.format(n=index)
    listing = Listing(
        listing_id=f"perf-{index:07d}",
        title=title,
        provider="perf-diagnostic",
        url="https://example.test/perf",
        condition=Condition.USED,
        extra={},
    )
    normalized = NormalizedListing.from_listing(listing)
    normalized.title_tokens = tuple(title.lower().split())
    return normalized


@dataclass(frozen=True, slots=True)
class PerformanceDiagnosticResult:
    listing_count: int
    wall_time_seconds: float
    listings_per_second: float
    median_latency_ms: float
    p95_latency_ms: float
    peak_memory_bytes: int
    memory_growth_checkpoints_bytes: tuple[int, ...]
    """Cumulative traced memory at evenly-spaced checkpoints through the
    run - used to verify memory does not grow unboundedly with listing
    count (brief: "verify no unbounded memory growth")."""
    stage_mean_ms: dict[str, float]
    technical_failure_count: int
    python_version: str
    platform_description: str

    def to_dict(self) -> dict:
        return {
            "listing_count": self.listing_count,
            "wall_time_seconds": self.wall_time_seconds,
            "listings_per_second": self.listings_per_second,
            "median_latency_ms": self.median_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "peak_memory_bytes": self.peak_memory_bytes,
            "memory_growth_checkpoints_bytes": list(self.memory_growth_checkpoints_bytes),
            "stage_mean_ms": self.stage_mean_ms,
            "technical_failure_count": self.technical_failure_count,
            "python_version": self.python_version,
            "platform_description": self.platform_description,
        }


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f, c = int(k), min(int(k) + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def run_performance_diagnostic(
    count: int = 10_000, *, checkpoint_count: int = 10
) -> PerformanceDiagnosticResult:
    """Process ``count`` deterministic synthetic listings title-only
    (persistence excluded - brief section 13) and report throughput,
    latency percentiles, stage timings, and peak/traced memory.
    """
    repo = JsonCandidateRepository()
    context = build_default_context()

    tracemalloc.start()
    checkpoints: list[int] = []
    checkpoint_every = max(1, count // checkpoint_count)

    latencies_ms: list[float] = []
    stage_totals: dict[str, float] = {}
    technical_failures = 0

    start = time.perf_counter()
    for i in range(count):
        listing = _synthetic_listing(i)
        t0 = time.perf_counter()
        record = process_one(listing, context, repository=repo)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

        if record.decision.decision_type.value == "processing_failed":
            technical_failures += 1

        for key, value in record.operational_metrics.items():
            if key.endswith("_ms") and isinstance(value, (int, float)):
                stage_totals[key] = stage_totals.get(key, 0.0) + float(value)

        if (i + 1) % checkpoint_every == 0:
            current, _peak = tracemalloc.get_traced_memory()
            checkpoints.append(current)

    wall_time = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    sorted_latencies = sorted(latencies_ms)
    stage_mean_ms = {key: round(total / count, 4) for key, total in stage_totals.items()}

    return PerformanceDiagnosticResult(
        listing_count=count,
        wall_time_seconds=round(wall_time, 4),
        listings_per_second=round(count / wall_time, 3) if wall_time > 0 else 0.0,
        median_latency_ms=round(_percentile(sorted_latencies, 0.5), 4),
        p95_latency_ms=round(_percentile(sorted_latencies, 0.95), 4),
        peak_memory_bytes=peak,
        memory_growth_checkpoints_bytes=tuple(checkpoints),
        stage_mean_ms=stage_mean_ms,
        technical_failure_count=technical_failures,
        python_version=sys.version,
        platform_description=platform.platform(),
    )


def render_diagnostic_text(result: PerformanceDiagnosticResult) -> str:
    lines = [
        "PUE Performance Diagnostic",
        f"  listings processed:     {result.listing_count}",
        f"  wall time (s):          {result.wall_time_seconds}",
        f"  listings/sec:           {result.listings_per_second}",
        f"  median latency (ms):    {result.median_latency_ms}",
        f"  p95 latency (ms):       {result.p95_latency_ms}",
        f"  peak traced memory:     {result.peak_memory_bytes} bytes",
        f"  memory checkpoints:     {list(result.memory_growth_checkpoints_bytes)}",
        f"  technical failures:     {result.technical_failure_count}",
        f"  python:                 {result.python_version.splitlines()[0]}",
        f"  platform:               {result.platform_description}",
        "  stage mean (ms):",
    ]
    for key, value in sorted(result.stage_mean_ms.items()):
        lines.append(f"    {key}: {value}")
    return "\n".join(lines)
