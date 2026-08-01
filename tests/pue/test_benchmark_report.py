"""Tests for benchmark report rendering (JSON/Markdown/CSV) and CLI exit
status (Sprint 3, brief sections 5/16)."""

from __future__ import annotations

import json
from pathlib import Path

from digital_arbitrage.pipeline.cli import main
from digital_arbitrage.pue.benchmark import dataset_file_hash, load_benchmark_dataset
from digital_arbitrage.pue.benchmark_report import (
    build_benchmark_report,
    render_report_csv,
    render_report_json,
    render_report_markdown,
    report_to_dict,
)
from digital_arbitrage.pue.benchmark_runner import run_benchmark
from digital_arbitrage.pue.version import CAPABILITY_VERSION

DATASET = load_benchmark_dataset()


def _build_report():
    run = run_benchmark(DATASET, run_classifier=True)
    return build_benchmark_report(
        DATASET,
        dataset_file_hash(),
        run.results,
        run.failures,
        capability_version=CAPABILITY_VERSION,
        policy_version=run.context.policy_version,
        knowledge_version=run.context.knowledge_version,
        schema_version=run.context.schema_version,
        wall_time_seconds=run.wall_time_seconds,
        mandatory_acceptance_pass=True,
        replay_equivalent=True,
        run_differential=True,
        generated_at="2026-08-01T00:00:00",
    )


def test_json_report_is_valid_json_and_deterministic() -> None:
    report = _build_report()
    text1 = render_report_json(report)
    text2 = render_report_json(report)
    assert text1 == text2
    payload = json.loads(text1)
    assert payload["total_cases"] == len(DATASET.cases)
    assert "release_gate" in payload
    assert "product_metrics" in payload


def test_markdown_report_contains_required_sections() -> None:
    report = _build_report()
    md = render_report_markdown(report)
    assert "# PUE GPU Release Benchmark Report" in md
    assert "## Release gate" in md
    assert "## Product metrics" in md
    assert "## Pipeline metrics" in md
    assert "## Operational metrics" in md
    assert "## Error taxonomy counts" in md
    assert "## Harmful results" in md


def test_csv_report_has_one_row_per_case() -> None:
    report = _build_report()
    csv_text = render_report_csv(report)
    lines = csv_text.splitlines()
    assert lines[0].startswith("case_id,")
    assert len(lines) - 1 == len(report.results)


def test_report_to_dict_includes_dataset_hash_and_versions() -> None:
    report = _build_report()
    d = report_to_dict(report)
    assert d["dataset_file_hash"] == dataset_file_hash()
    assert d["capability_version"] == CAPABILITY_VERSION
    assert d["knowledge_version"]
    assert d["policy_version"]
    assert d["schema_version"]


def test_zero_harmful_errors_in_release_report() -> None:
    report = _build_report()
    assert report.harmful_results == ()


#: The real release dataset currently has exactly one genuine,
#: pre-existing, already-documented gap: ``compat_01_case_fits_rtx4090``
#: ("PC Case - fits RTX 4090...") reaches ABSTAINED, which its own gold
#: label does not even declare as an allowed outcome at all (a
#: ``decision_type_allowed`` failure that predates this correction pass) -
#: so its abstention cannot be meaningfully hand-classified
#: justified/avoidable either, and
#: ``every_abstention_classified_justified_or_avoidable`` correctly fails.
#: Before the Sprint 3 final release-integrity correction, this was masked
#: by that check being hardcoded ``True``; it is now honestly visible. This
#: is the *only* currently-known gap - this test pins that fact so any
#: *additional* gate check regressing would still be caught.
_KNOWN_REMAINING_GATE_GAPS = frozenset({"every_abstention_classified_justified_or_avoidable"})


def test_release_gate_on_the_real_release_dataset_has_no_new_gaps() -> None:
    report = _build_report()
    failing = {c.name for c in report.gate.checks if not c.passed}
    assert failing == _KNOWN_REMAINING_GATE_GAPS, [
        c.to_dict() for c in report.gate.checks if not c.passed
    ]


def test_cli_benchmark_writes_reports_and_reflects_the_real_gate_outcome(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    exit_code = main(["pue", "benchmark", "--output-dir", str(out_dir)])
    # Exit code must genuinely reflect report.gate.passed (currently False
    # - see _KNOWN_REMAINING_GATE_GAPS) - never hardcoded to 0 regardless
    # of the real gate outcome.
    assert exit_code == (0 if _build_report().gate.passed else 1)
    assert (out_dir / "pue_benchmark_report.json").exists()
    assert (out_dir / "pue_benchmark_report.md").exists()


def test_cli_benchmark_supports_explicit_format_selection(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    exit_code = main(
        ["pue", "benchmark", "--output-dir", str(out_dir), "--format", "csv", "--no-classifier"]
    )
    assert exit_code == (0 if _build_report().gate.passed else 1)
    assert (out_dir / "pue_benchmark_report.csv").exists()
    assert not (out_dir / "pue_benchmark_report.json").exists()


def test_cli_benchmark_rejects_malformed_dataset(tmp_path: Path, capsys) -> None:
    bad_dataset = tmp_path / "bad.json"
    bad_dataset.write_text("{not json", encoding="utf-8")
    exit_code = main(["pue", "benchmark", str(bad_dataset)])
    assert exit_code == 1
