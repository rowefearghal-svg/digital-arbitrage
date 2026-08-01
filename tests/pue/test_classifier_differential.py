"""Tests for the gold-grounded classifier/PUE differential (Sprint 3
pre-merge correction item 2): correctness for both systems must be graded
independently against the benchmark's gold labels, never inferred from
:class:`~digital_arbitrage.pue.comparison.ComparisonCategory.AGREEMENT`
(which is an *observable-difference* category, not a correctness claim -
see the ``comparison.py`` module docstring)."""

from __future__ import annotations

import dataclasses

from digital_arbitrage.classification.models import Classification
from digital_arbitrage.pue.benchmark import load_benchmark_dataset
from digital_arbitrage.pue.benchmark_metrics import classifier_gold_correct
from digital_arbitrage.pue.benchmark_report import compute_differential_metrics
from digital_arbitrage.pue.benchmark_runner import run_benchmark
from digital_arbitrage.pue.comparison import ComparisonCategory

DATASET = load_benchmark_dataset()
_RUN = run_benchmark(DATASET, run_classifier=True)

#: A real, gradable complete-product case (expected_product_form ==
#: "complete_product") with a real comparison record, used as the base for
#: every constructed scenario below.
_BASE = next(
    r
    for r in _RUN.results
    if r.comparison is not None and r.case.expected_product_form == "complete_product"
)


def _scenario(*, category: ComparisonCategory, classifier_label: Classification, pue_correct: bool):
    assert _BASE.comparison is not None
    comparison = dataclasses.replace(
        _BASE.comparison, category=category, classifier_label=classifier_label.value
    )
    result = dataclasses.replace(_BASE, comparison=comparison, correct=pue_correct)
    return result


def test_classifier_gold_correct_is_not_agreement() -> None:
    """The classifier can be independently graded correct/incorrect
    regardless of the comparison's observable AGREEMENT category."""
    assert classifier_gold_correct(_BASE.case, Classification.COMPLETE_PRODUCT.value) is True
    assert classifier_gold_correct(_BASE.case, Classification.ACCESSORY.value) is False


def test_scenario_both_agree_and_both_wrong() -> None:
    """Two systems can *agree* (same observable category) while both are
    gold-incorrect - AGREEMENT must never be read as correctness."""
    result = _scenario(
        category=ComparisonCategory.AGREEMENT,
        classifier_label=Classification.ACCESSORY,  # wrong: case is complete_product
        pue_correct=False,
    )
    metrics = compute_differential_metrics([result])
    assert metrics.both_wrong == 1
    assert metrics.both_correct == 0
    assert metrics.pue_corrects_classifier == 0
    assert metrics.classifier_correct_pue_worsens == 0


def test_scenario_both_agree_and_both_correct() -> None:
    result = _scenario(
        category=ComparisonCategory.AGREEMENT,
        classifier_label=Classification.COMPLETE_PRODUCT,  # correct
        pue_correct=True,
    )
    metrics = compute_differential_metrics([result])
    assert metrics.both_correct == 1
    assert metrics.both_wrong == 0


def test_scenario_pue_corrects_classifier() -> None:
    result = _scenario(
        category=ComparisonCategory.PRODUCT_FORM_DISAGREEMENT,
        classifier_label=Classification.ACCESSORY,  # wrong
        pue_correct=True,
    )
    metrics = compute_differential_metrics([result])
    assert metrics.pue_corrects_classifier == 1
    assert metrics.both_correct == 0
    assert metrics.both_wrong == 0
    assert metrics.classifier_correct_pue_worsens == 0


def test_scenario_classifier_correct_pue_worsens() -> None:
    result = _scenario(
        category=ComparisonCategory.PRODUCT_FORM_DISAGREEMENT,
        classifier_label=Classification.COMPLETE_PRODUCT,  # correct
        pue_correct=False,
    )
    metrics = compute_differential_metrics([result])
    assert metrics.classifier_correct_pue_worsens == 1
    assert metrics.both_correct == 0
    assert metrics.both_wrong == 0
    assert metrics.pue_corrects_classifier == 0


def test_scenario_both_differ_and_both_wrong() -> None:
    """Two systems can *disagree* (different observable category) while
    both are still gold-incorrect - disagreement must not be read as "one
    of them must be right"."""
    result = _scenario(
        category=ComparisonCategory.PRODUCT_FORM_DISAGREEMENT,
        classifier_label=Classification.ACCESSORY,  # wrong
        pue_correct=False,
    )
    metrics = compute_differential_metrics([result])
    assert metrics.both_wrong == 1
    assert metrics.both_correct == 0
    assert metrics.pue_corrects_classifier == 0
    assert metrics.classifier_correct_pue_worsens == 0


def test_ungradable_cases_are_excluded_not_silently_counted() -> None:
    """A case with no clear classifier-gradable gold judgment (no
    expected_product_form, not misleading-similarity/unsupported-domain)
    must be excluded from every quadrant, tracked separately."""
    ungradable_case = next(
        r
        for r in _RUN.results
        if r.comparison is not None
        and r.case.expected_product_form is None
        and "misleading_similarity" not in r.case.case_tags
        and not r.case.unsupported_domain
    )
    metrics = compute_differential_metrics([ungradable_case])
    assert metrics.classifier_ungradable == 1
    assert metrics.classifier_gradable == 0
    assert metrics.both_correct == 0
    assert metrics.both_wrong == 0
    assert metrics.pue_corrects_classifier == 0
    assert metrics.classifier_correct_pue_worsens == 0


def test_misleading_similarity_cases_are_gradable_on_declined_semantics() -> None:
    case = next(c for c in DATASET.cases if "misleading_similarity" in c.case_tags)
    assert classifier_gold_correct(case, Classification.REJECTED.value) is True
    assert classifier_gold_correct(case, Classification.UNKNOWN.value) is True
    assert classifier_gold_correct(case, Classification.COMPLETE_PRODUCT.value) is False


def test_unsupported_domain_cases_are_gradable_on_declined_semantics() -> None:
    case = next(c for c in DATASET.cases if c.unsupported_domain)
    assert classifier_gold_correct(case, Classification.REJECTED.value) is True
    assert classifier_gold_correct(case, Classification.COMPLETE_PRODUCT.value) is False


def test_differential_denominators_are_internally_consistent() -> None:
    metrics = compute_differential_metrics(_RUN.results)
    assert metrics.classifier_gradable + metrics.classifier_ungradable == metrics.total_compared
    quadrant_total = (
        metrics.both_correct
        + metrics.both_wrong
        + metrics.pue_corrects_classifier
        + metrics.classifier_correct_pue_worsens
    )
    assert quadrant_total == metrics.classifier_gradable
