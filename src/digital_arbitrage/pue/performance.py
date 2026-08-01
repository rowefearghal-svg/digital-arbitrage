"""Reproducible local performance/memory diagnostic (Sprint 3, brief
section 13).

Deterministic, title-only, synthetic listings - no provider acquisition, no
network. Uses only standard-library tooling (:mod:`tracemalloc`, :mod:`time`,
:mod:`platform`) - no new dependency, no distributed/queue infrastructure
(brief section 13's explicit non-goals).
"""

from __future__ import annotations

import platform
import random
import sys
import time
import tracemalloc
from dataclasses import dataclass

from ..normalization.models import NormalizedListing
from ..product_scanner.models import Condition, Listing
from .catalogue import JsonCandidateRepository
from .orchestration import build_default_context, process_one

#: Bounded reservoir size for latency percentile estimation (Sprint 3
#: pre-merge correction item 6): the diagnostic itself must not accumulate
#: an O(N) list of every latency observed, or its own memory footprint
#: would grow with ``count`` and confound the very memory-growth
#: measurement it is trying to make. A fixed-size reservoir gives a
#: statistically representative median/p95 estimate with O(1) memory in
#: ``count``.
_MAX_LATENCY_SAMPLES = 2000

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
    """Estimated from a bounded reservoir sample of at most
    :data:`_MAX_LATENCY_SAMPLES` latencies, not the full ``listing_count``
    set - the diagnostic itself must not hold an O(N) list (Sprint 3
    pre-merge correction item 6)."""
    p95_latency_ms: float
    latency_sample_size: int
    """How many latency observations the median/p95 estimate above is
    actually based on (``min(listing_count, _MAX_LATENCY_SAMPLES)``)."""
    peak_memory_bytes: int
    memory_growth_checkpoints_bytes: tuple[int, ...]
    """Traced memory at evenly-spaced checkpoints through the run. This
    reflects the *entire* process's traced allocations, including this
    diagnostic's own bounded reservoir and running totals - it is a raw
    measurement, not by itself proof that per-case reasoning memory is
    bounded (linear growth here is *consistent* with a leak just as much
    as with normal, expected allocator/bookkeeping growth; it does not
    *prove* boundedness either way). See ``possible_memory_growth`` for an
    explicit, honest signal computed only from checkpoints taken *after*
    the reservoir has filled (Sprint 3 pre-merge correction item 6)."""
    possible_memory_growth: bool
    """True if traced memory continued growing by more than
    ``_MEMORY_GROWTH_RATIO_THRESHOLD`` between the first and last
    checkpoint taken *after* the latency reservoir stopped growing (i.e.
    once this diagnostic's own memory footprint should be flat) - a
    genuine signal worth investigating, not dismissed."""
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
            "latency_sample_size": self.latency_sample_size,
            "peak_memory_bytes": self.peak_memory_bytes,
            "memory_growth_checkpoints_bytes": list(self.memory_growth_checkpoints_bytes),
            "possible_memory_growth": self.possible_memory_growth,
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


#: Ratio threshold beyond which post-reservoir-fill checkpoint growth is
#: flagged as ``possible_memory_growth`` rather than silently dismissed
#: (Sprint 3 pre-merge correction item 6) - deliberately generous to avoid
#: flaking on ordinary allocator/measurement noise while still catching a
#: genuine, sustained per-case leak.
_MEMORY_GROWTH_RATIO_THRESHOLD = 1.5


def run_performance_diagnostic(
    count: int = 10_000, *, checkpoint_count: int = 10, reservoir_seed: int = 0
) -> PerformanceDiagnosticResult:
    """Process ``count`` deterministic synthetic listings title-only
    (persistence excluded - brief section 13) and report throughput,
    latency percentiles, stage timings, and peak/traced memory.

    Latency percentiles are estimated from a fixed-size (``_MAX_LATENCY_
    SAMPLES``) reservoir sample, not a full ``count``-sized list, so the
    diagnostic's own memory footprint does not grow with ``count`` (Sprint
    3 pre-merge correction item 6) - a growing latency list would itself
    produce the "linear growth" the memory checkpoints previously (and
    wrongly) treated as *proof* of bounded per-case memory.
    """
    repo = JsonCandidateRepository()
    context = build_default_context()
    rng = random.Random(reservoir_seed)

    tracemalloc.start()
    checkpoints: list[tuple[int, int]] = []  # (listing index, traced bytes)
    checkpoint_every = max(1, count // checkpoint_count)

    latency_reservoir: list[float] = []
    stage_totals: dict[str, float] = {}
    technical_failures = 0

    start = time.perf_counter()
    for i in range(count):
        listing = _synthetic_listing(i)
        t0 = time.perf_counter()
        record = process_one(listing, context, repository=repo)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        if len(latency_reservoir) < _MAX_LATENCY_SAMPLES:
            latency_reservoir.append(latency_ms)
        else:
            j = rng.randint(0, i)
            if j < _MAX_LATENCY_SAMPLES:
                latency_reservoir[j] = latency_ms

        if record.decision.decision_type.value == "processing_failed":
            technical_failures += 1

        for key, value in record.operational_metrics.items():
            if key.endswith("_ms") and isinstance(value, (int, float)):
                stage_totals[key] = stage_totals.get(key, 0.0) + float(value)

        if (i + 1) % checkpoint_every == 0:
            current, _peak = tracemalloc.get_traced_memory()
            checkpoints.append((i + 1, current))

    wall_time = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    sorted_latencies = sorted(latency_reservoir)
    stage_mean_ms = {key: round(total / count, 4) for key, total in stage_totals.items()}

    # Only checkpoints taken *after* the reservoir stopped growing are
    # meaningful evidence about the underlying reasoning pipeline's memory
    # behaviour - earlier checkpoints necessarily include the reservoir
    # itself still filling up, which is expected, bounded growth, not a
    # signal about per-case reasoning memory.
    post_fill = [(idx, mem) for idx, mem in checkpoints if idx >= min(_MAX_LATENCY_SAMPLES, count)]
    possible_memory_growth = False
    if len(post_fill) >= 2:
        first_mem = max(post_fill[0][1], 1)
        last_mem = post_fill[-1][1]
        possible_memory_growth = (last_mem / first_mem) > _MEMORY_GROWTH_RATIO_THRESHOLD

    return PerformanceDiagnosticResult(
        listing_count=count,
        wall_time_seconds=round(wall_time, 4),
        listings_per_second=round(count / wall_time, 3) if wall_time > 0 else 0.0,
        median_latency_ms=round(_percentile(sorted_latencies, 0.5), 4),
        p95_latency_ms=round(_percentile(sorted_latencies, 0.95), 4),
        latency_sample_size=len(latency_reservoir),
        peak_memory_bytes=peak,
        memory_growth_checkpoints_bytes=tuple(mem for _idx, mem in checkpoints),
        possible_memory_growth=possible_memory_growth,
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
        f"  median latency (ms):    {result.median_latency_ms} "
        f"(reservoir sample n={result.latency_sample_size})",
        f"  p95 latency (ms):       {result.p95_latency_ms}",
        f"  peak traced memory:     {result.peak_memory_bytes} bytes",
        f"  memory checkpoints:     {list(result.memory_growth_checkpoints_bytes)}",
        f"  possible memory growth: {result.possible_memory_growth} "
        "(computed only from checkpoints after the latency reservoir filled; "
        "this is a leak-investigation flag, not proof of boundedness either way)",
        f"  technical failures:     {result.technical_failure_count}",
        f"  python:                 {result.python_version.splitlines()[0]}",
        f"  platform:               {result.platform_description}",
        "  stage mean (ms):",
    ]
    for key, value in sorted(result.stage_mean_ms.items()):
        lines.append(f"    {key}: {value}")
    return "\n".join(lines)
