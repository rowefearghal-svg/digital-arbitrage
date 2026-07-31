"""Benchmark execution harness (Sprint 3, brief section 5).

Wires a validated :class:`~digital_arbitrage.pue.benchmark.BenchmarkDataset`
through the *real* PUE orchestration path
(:func:`digital_arbitrage.pue.orchestration.process_one`) - never a
parallel, benchmark-only implementation (brief section 2: "Do not create an
independent benchmark-only PUE implementation").
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from ..classification.classifier import ListingClassifier, build_search_profile
from ..normalization.models import NormalizedListing
from ..product_scanner.models import Condition, Listing
from .benchmark import BenchmarkCase, BenchmarkDataset
from .benchmark_metrics import CaseFailure, CaseResult, classify_failure, evaluate_case
from .catalogue import CandidateRepository, JsonCandidateRepository
from .comparison import ClassifierPueComparison, compare_classifier_and_pue
from .models import ProcessingContext, ReasoningRecord
from .orchestration import build_default_context, process_one
from .policies import DecisionPolicy


def case_to_listing(case: BenchmarkCase) -> NormalizedListing:
    """Build a :class:`NormalizedListing` for one benchmark case.

    A ``malformed`` case (``title`` may be ``None``) intentionally produces
    a listing whose title is not a string when ``case.title`` is ``None``,
    matching the Sprint 1 acceptance fixture's "malformed input" convention
    (``process_one(object(), ...)`` in ``tests/pue/test_acceptance.py``) -
    but the benchmark harness always passes a real ``NormalizedListing`` so
    ``admit_observation`` fails on the *title*, not on a missing ``source``.
    """
    listing = Listing(
        listing_id=case.case_id,
        title=case.title if case.title is not None else "",
        provider="benchmark",
        url="https://example.test/benchmark",
        condition=Condition.USED,
        extra=(
            {str(k): str(v) for k, v in case.structured_attributes.items()}
            if case.structured_attributes
            else {}
        ),
    )
    normalized = NormalizedListing.from_listing(listing)
    if case.title is not None:
        normalized.title_tokens = tuple(case.title.lower().split())
    return normalized


@dataclass(frozen=True, slots=True)
class BenchmarkRunResult:
    """The complete, unaggregated output of one benchmark execution."""

    context: ProcessingContext
    results: tuple[CaseResult, ...]
    failures: tuple[CaseFailure, ...]
    wall_time_seconds: float


def run_benchmark(
    dataset: BenchmarkDataset,
    *,
    repository: CandidateRepository | None = None,
    policy: DecisionPolicy | None = None,
    context: ProcessingContext | None = None,
    run_classifier: bool = True,
    id_factory: Callable[[], str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> BenchmarkRunResult:
    """Run every case in ``dataset`` through the real PUE orchestration
    path, optionally also through the existing title classifier on the
    same normalized listing (brief section 5).

    Deterministic given a deterministic ``id_factory``/``clock`` (brief
    section 5: "emit deterministic machine-readable JSON").
    """
    repo = repository or JsonCandidateRepository()
    active_policy = policy or DecisionPolicy()
    ctx = context or build_default_context(id_factory=id_factory, clock=clock)
    classifier = ListingClassifier() if run_classifier else None

    results: list[CaseResult] = []
    start = time.perf_counter()
    for case in dataset.cases:
        if case.malformed:
            malformed_input: NormalizedListing = object()  # type: ignore[assignment]
            record: ReasoningRecord = process_one(
                malformed_input, ctx, repository=repo, policy=active_policy
            )
            comparison: ClassifierPueComparison | None = None
        else:
            listing = case_to_listing(case)
            record = process_one(listing, ctx, repository=repo, policy=active_policy)
            comparison = None
            if classifier is not None and case.title:
                profile = build_search_profile(case.title)
                classification = classifier.classify(listing, profile)
                comparison = compare_classifier_and_pue(
                    classification, record, search_profile=profile, id_factory=ctx.id_factory
                )
        results.append(evaluate_case(case, record, comparison))
    wall_time = time.perf_counter() - start

    failures = tuple(
        f
        for r in results
        if (f := classify_failure(r, repo, knowledge_version=ctx.knowledge_version)) is not None
    )

    return BenchmarkRunResult(
        context=ctx, results=tuple(results), failures=failures, wall_time_seconds=wall_time
    )
