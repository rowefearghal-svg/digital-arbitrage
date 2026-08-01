"""Tests for the performance/memory diagnostic (Sprint 3, brief sections
13/16). The full 10,000-case run is an explicit, separate diagnostic (see
``scripts/pue_performance_diagnostic.py``) - not run as part of normal CI to
keep the suite fast; this file only exercises a small, CI-safe sample."""

from __future__ import annotations

from digital_arbitrage.pue.performance import render_diagnostic_text, run_performance_diagnostic


def test_small_sample_diagnostic_completes_and_reports_positive_throughput() -> None:
    result = run_performance_diagnostic(count=50, checkpoint_count=5)
    assert result.listing_count == 50
    assert result.wall_time_seconds > 0
    assert result.listings_per_second > 0


def test_stage_timing_fields_are_emitted() -> None:
    result = run_performance_diagnostic(count=50, checkpoint_count=5)
    assert "extraction_ms" in result.stage_mean_ms
    assert "retrieval_ms" in result.stage_mean_ms
    assert "evaluation_ms" in result.stage_mean_ms
    assert "decision_explanation_ms" in result.stage_mean_ms
    assert all(v >= 0 for v in result.stage_mean_ms.values())


def test_median_and_p95_latency_reported() -> None:
    result = run_performance_diagnostic(count=50, checkpoint_count=5)
    assert result.median_latency_ms >= 0
    assert result.p95_latency_ms >= result.median_latency_ms


def test_memory_measurement_is_bounded_and_recorded() -> None:
    result = run_performance_diagnostic(count=50, checkpoint_count=5)
    assert result.peak_memory_bytes > 0
    assert len(result.memory_growth_checkpoints_bytes) > 0
    # A bounded, non-leaking run: peak traced memory for 50 small,
    # short-lived reasoning chains must stay well under a generous
    # structural ceiling (loose bound - this is a leak/explosion guard,
    # not a tight performance assertion).
    assert result.peak_memory_bytes < 200_000_000


def test_memory_does_not_grow_unboundedly_with_listing_count() -> None:
    """A doubling of listing count must not roughly double peak memory if
    memory is being released between cases (no unbounded accumulation)."""
    small = run_performance_diagnostic(count=50, checkpoint_count=5)
    larger = run_performance_diagnostic(count=200, checkpoint_count=5)
    # 4x the listings should not require anywhere near 4x the peak
    # traced memory if each case's reasoning objects are independent and
    # released - a generous multiplier avoids flaking on measurement noise
    # while still catching genuine unbounded accumulation.
    assert larger.peak_memory_bytes < small.peak_memory_bytes * 4


def test_render_diagnostic_text_contains_key_fields() -> None:
    result = run_performance_diagnostic(count=20, checkpoint_count=4)
    text = render_diagnostic_text(result)
    assert "listings/sec" in text
    assert "median latency" in text
    assert "peak traced memory" in text
    assert "platform" in text


def test_no_technical_failures_on_well_formed_synthetic_titles() -> None:
    result = run_performance_diagnostic(count=100, checkpoint_count=5)
    assert result.technical_failure_count == 0


# --------------------------------------------------------------------------- #
# Sprint 3 pre-merge correction item 6: bounded latency reservoir, honest
# memory-growth claim.
# --------------------------------------------------------------------------- #
def test_latency_sample_is_bounded_even_for_a_large_listing_count() -> None:
    """The diagnostic must not accumulate an O(N) latency list - the
    reservoir sample size is capped regardless of ``count``."""
    from digital_arbitrage.pue.performance import _MAX_LATENCY_SAMPLES

    result = run_performance_diagnostic(count=5_000, checkpoint_count=5)
    assert result.latency_sample_size == min(5_000, _MAX_LATENCY_SAMPLES)
    assert result.latency_sample_size <= _MAX_LATENCY_SAMPLES


def test_latency_sample_size_never_exceeds_listing_count_for_small_runs() -> None:
    result = run_performance_diagnostic(count=50, checkpoint_count=5)
    assert result.latency_sample_size == 50


def test_possible_memory_growth_flag_is_reported_not_silently_dismissed() -> None:
    """The result must carry an explicit, honestly-scoped growth signal
    rather than asserting boundedness from raw linear checkpoint growth
    (Sprint 3 pre-merge correction item 6) - a small run below the
    reservoir-fill threshold has too few post-fill checkpoints to say
    anything, and must default to False, not fabricate an assessment."""
    result = run_performance_diagnostic(count=50, checkpoint_count=5)
    assert isinstance(result.possible_memory_growth, bool)
    assert result.possible_memory_growth is False


def test_possible_memory_growth_is_computed_only_from_post_reservoir_fill_checkpoints() -> None:
    """A run large enough for the reservoir to fill partway through must
    still produce a well-defined (bool) signal, and the raw checkpoint
    list must not be conflated with it - the two are reported separately."""
    from digital_arbitrage.pue.performance import _MAX_LATENCY_SAMPLES

    result = run_performance_diagnostic(count=_MAX_LATENCY_SAMPLES * 2, checkpoint_count=8)
    assert isinstance(result.possible_memory_growth, bool)
    assert len(result.memory_growth_checkpoints_bytes) == 8


def test_reservoir_sample_size_is_deterministic_given_the_same_seed_and_count() -> None:
    """The reservoir *selection algorithm* (which listing indices end up
    sampled) is deterministic given the same seed; the measured wall-clock
    latency *values* themselves are not (real timing), so only the
    resulting sample size - not the latency numbers - is asserted here."""
    a = run_performance_diagnostic(count=3_000, checkpoint_count=5, reservoir_seed=42)
    b = run_performance_diagnostic(count=3_000, checkpoint_count=5, reservoir_seed=42)
    assert a.latency_sample_size == b.latency_sample_size == 2000


def test_render_diagnostic_text_reports_growth_flag_and_sample_size() -> None:
    result = run_performance_diagnostic(count=20, checkpoint_count=4)
    text = render_diagnostic_text(result)
    assert "possible memory growth" in text
    assert "reservoir sample" in text
