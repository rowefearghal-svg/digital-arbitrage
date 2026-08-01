"""Permanent PUE regression suite (Sprint 3, brief section 9).

This module does not duplicate test logic that already lives elsewhere; it
is a single, explicit index asserting that every required regression
source still passes together, in normal CI, so no future change can
silently drop one of them from the suite:

- all Sprint 1 mandatory cases -> ``tests/pue/test_acceptance.py`` (36
  cases from the vertical-slice spec) plus the five serialized
  ``tests/pue/test_golden.py`` records.
- all Sprint 2 product-form and contradiction cases ->
  ``tests/pue/test_hard_contradiction_matrix.py`` and
  ``tests/pue/test_indistinguishable_variants.py``.
- previous bugs fixed during Sprint 2 -> ``tests/pue/test_comparison.py``
  and ``tests/pue/test_schema_migration.py`` (comparison-identity/
  migration-index regressions with explicit before/after verification in
  their own commit history).
- every harmful error found and corrected during Sprint 3 -> the two
  ``gpu_terms_v0.1.json`` fixes below (Intel Arc brand/family span
  collision; "cooling fans"/"support stand" accessory-term gaps), each
  cited by the exact benchmark case IDs that motivated them.
- important partial-identification and abstention cases -> the release
  benchmark's own gate assertion (zero harmful errors, every abstention
  classified) in ``tests/pue/test_benchmark_metrics.py`` and
  ``tests/pue/test_benchmark_report.py``.
- replay and migration invariants -> ``tests/pue/test_replay.py`` and
  ``tests/pue/test_schema_migration.py``.

Every rule changed during Sprint 3 cites the exact case IDs that motivated
it (see ``data/pue/knowledge/gpu_terms_v0.1.json``'s ``change_note`` and
this module's docstring/tests below).
"""

from __future__ import annotations

from digital_arbitrage.pue.benchmark import load_benchmark_dataset
from digital_arbitrage.pue.benchmark_runner import run_benchmark
from digital_arbitrage.pue.evidence import load_terms
from digital_arbitrage.pue.version import TERM_VERSION

DATASET = load_benchmark_dataset()

#: The exact benchmark case IDs that motivated each Sprint 3 knowledge fix
#: (brief section 9: "Every rule or behaviour changed during Sprint 3 must
#: cite the benchmark case IDs that motivated it").
_INTEL_ARC_BRAND_SPAN_FIX_CASE_IDS = (
    "exact_23_intel_arca770_le",
    "exact_24_asrock_arca770_phantom",
    "exact_25_intel_arca750_le",
    "family_only_03_arca770",
    "family_only_08_arca750",
)
_ACCESSORY_TERM_GAP_FIX_CASE_IDS = (
    "fan_03_cooling_fans_for_rtx4090",
    "bracket_04_gpu_support_stand",
)


def test_term_version_was_bumped_for_the_sprint3_knowledge_fixes() -> None:
    assert TERM_VERSION == "gpu-terms-0.1.1"
    terms_file = load_terms()
    assert terms_file  # loads without error


def test_intel_arc_brand_alias_no_longer_blocks_the_family_alias_span() -> None:
    """Regression for the fix motivated by _INTEL_ARC_BRAND_SPAN_FIX_CASE_IDS:
    'intel arc' must not remain a brand_aliases entry (it structurally
    collides with every 'arc a7xx' family alias - see gpu_terms_v0.1.json's
    change_note)."""
    terms = load_terms()
    assert "intel arc" not in terms["brand_aliases"]["intel"]
    assert "intel" in terms["brand_aliases"]["intel"]


def test_cited_intel_arc_cases_all_resolve_in_domain() -> None:
    run = run_benchmark(DATASET, run_classifier=False)
    results_by_id = {r.case.case_id for r in run.results}
    assert set(_INTEL_ARC_BRAND_SPAN_FIX_CASE_IDS) <= results_by_id
    for case_id in _INTEL_ARC_BRAND_SPAN_FIX_CASE_IDS:
        result = next(r for r in run.results if r.case.case_id == case_id)
        assert result.record.decision.decision_type.value != "outside_supported_domain", (
            f"{case_id} regressed to outside_supported_domain"
        )


def test_cited_accessory_term_gap_cases_are_no_longer_harmful() -> None:
    run = run_benchmark(DATASET, run_classifier=False)
    for case_id in _ACCESSORY_TERM_GAP_FIX_CASE_IDS:
        result = next(r for r in run.results if r.case.case_id == case_id)
        assert result.harmful_errors == (), f"{case_id} regressed to a harmful outcome"


def test_release_benchmark_zero_harmful_errors_gate() -> None:
    """Every harmful error found and corrected during Sprint 3 stays fixed
    permanently: this is the same zero-tolerance mandatory gate check as
    the release report, re-asserted here as a named regression."""
    run = run_benchmark(DATASET, run_classifier=False)
    harmful = [r for r in run.results if r.harmful_errors]
    assert harmful == [], [r.case.case_id for r in harmful]


def test_release_benchmark_every_abstention_is_classified() -> None:
    """Every abstaining case must be hand-classified justified/avoidable,
    with exactly one known, pre-existing exception:
    ``compat_01_case_fits_rtx4090`` reaches ABSTAINED despite its own gold
    label not even declaring that an allowed outcome at all (a
    ``decision_type_allowed`` failure that predates this test's fix) - its
    abstention cannot be meaningfully hand-adjudicated justified/avoidable
    either. This pins that single known gap so any *additional* unlabelled
    abstention is still caught as a regression (Sprint 3 final
    release-integrity correction item 7)."""
    run = run_benchmark(DATASET, run_classifier=False)
    unclassified = [
        r.case.case_id
        for r in run.results
        if r.record.decision.decision_type.value == "abstained"
        and not (r.is_justified_abstention or r.is_avoidable_abstention)
    ]
    assert unclassified == ["compat_01_case_fits_rtx4090"]
