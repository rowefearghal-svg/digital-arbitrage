"""Tests for the GPU release benchmark dataset schema/loader/validator
(Sprint 3, brief section 16 "Dataset and benchmark")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digital_arbitrage.pue.benchmark import (
    BENCHMARK_DATASET_SCHEMA_VERSION,
    DEFAULT_BENCHMARK_PATH,
    case_coverage_by_tag,
    dataset_file_hash,
    load_benchmark_dataset,
)
from digital_arbitrage.pue.validation import PueValidationError

MINIMAL_VALID = {
    "dataset_schema_version": BENCHMARK_DATASET_SCHEMA_VERSION,
    "dataset_id": "test-dataset",
    "benchmark_version": "test-0.1.0",
    "created_date": "2026-08-01",
    "curator": "test",
    "domain": "gpu",
    "knowledge_version": "gpu-seed-0.1.0",
    "policy_version": "gpu-policy-0.1.0",
    "provenance_note": "test fixture",
    "cases": [
        {
            "case_id": "c1",
            "title": "NVIDIA RTX 4090",
            "allowed_decision_types": ["partially_identified"],
        }
    ],
}


def _write(tmp_path: Path, payload: dict, name: str = "dataset.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_valid_dataset_loading(tmp_path: Path) -> None:
    path = _write(tmp_path, MINIMAL_VALID)
    dataset = load_benchmark_dataset(path)
    assert dataset.dataset_id == "test-dataset"
    assert len(dataset.cases) == 1
    assert dataset.cases[0].case_id == "c1"


def test_the_real_release_benchmark_loads_and_has_100_to_150_cases() -> None:
    dataset = load_benchmark_dataset(DEFAULT_BENCHMARK_PATH)
    assert 100 <= len(dataset.cases) <= 150


def test_malformed_json_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(PueValidationError):
        load_benchmark_dataset(path)


def test_unsupported_schema_version_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID, dataset_schema_version="some-future-version-9.9.9")
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="unsupported"):
        load_benchmark_dataset(path)


def test_missing_required_dataset_field_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    del payload["curator"]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="missing required"):
        load_benchmark_dataset(path)


def test_empty_cases_list_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID, cases=[])
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError):
        load_benchmark_dataset(path)


def test_duplicate_case_id_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [MINIMAL_VALID["cases"][0], MINIMAL_VALID["cases"][0]]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="duplicate case_id"):
        load_benchmark_dataset(path)


def test_case_missing_allowed_decision_types_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [{"case_id": "c1", "title": "RTX 4090"}]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="allowed_decision_types"):
        load_benchmark_dataset(path)


def test_case_missing_title_when_not_malformed_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [{"case_id": "c1", "allowed_decision_types": ["classified"]}]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="title"):
        load_benchmark_dataset(path)


def test_malformed_case_allows_null_title(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": None,
            "malformed": True,
            "allowed_decision_types": ["processing_failed"],
        }
    ]
    path = _write(tmp_path, payload)
    dataset = load_benchmark_dataset(path)
    assert dataset.cases[0].malformed is True
    assert dataset.cases[0].title is None


def test_invalid_annotation_confidence_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "RTX 4090",
            "allowed_decision_types": ["classified"],
            "annotation_confidence": "extremely_high",
        }
    ]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="annotation_confidence"):
        load_benchmark_dataset(path)


def test_unknown_forbidden_harmful_outcome_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "RTX 4090",
            "allowed_decision_types": ["classified"],
            "forbidden_harmful_outcomes": ["not_a_real_harmful_kind"],
        }
    ]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="forbidden_harmful_outcomes"):
        load_benchmark_dataset(path)


def test_catalogue_gap_with_acceptable_ids_rejected(tmp_path: Path) -> None:
    """catalogue_gap=true asserts no acceptable Candidate exists at all;
    combining it with acceptable_catalogue_product_ids is an invalid gold
    label combination (brief section 16 "invalid gold-label combinations")."""
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "RTX 4090",
            "allowed_decision_types": ["classified"],
            "catalogue_gap": True,
            "acceptable_catalogue_product_ids": ["gpu-nvidia-rtx4090-fe"],
        }
    ]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="catalogue_gap"):
        load_benchmark_dataset(path)


def test_abstention_classification_without_abstained_allowed_rejected(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "RTX 4090",
            "allowed_decision_types": ["classified"],
            "abstention_classification": "avoidable",
        }
    ]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="abstention_classification"):
        load_benchmark_dataset(path)


def test_abstention_classification_rejects_unknown_value(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "RTX 4090",
            "allowed_decision_types": ["classified", "abstained"],
            "abstention_classification": "sometimes",
        }
    ]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="abstention_classification"):
        load_benchmark_dataset(path)


def test_multiple_acceptable_outcomes_supported(tmp_path: Path) -> None:
    """A case may define multiple acceptable outcomes (brief section 4.3)."""
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "ASUS RTX 4090 with EK water block",
            "allowed_decision_types": ["ambiguous", "partially_identified", "identified"],
        }
    ]
    path = _write(tmp_path, payload)
    dataset = load_benchmark_dataset(path)
    assert dataset.cases[0].outcome_options() == 3


def test_forbidden_harmful_outcomes_round_trip(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["cases"] = [
        {
            "case_id": "c1",
            "title": "RTX 4090 replacement fan",
            "allowed_decision_types": ["classified"],
            "forbidden_harmful_outcomes": ["accessory_to_complete_product"],
        }
    ]
    path = _write(tmp_path, payload)
    dataset = load_benchmark_dataset(path)
    assert dataset.cases[0].forbidden_harmful_outcomes == ("accessory_to_complete_product",)


def test_correction_entry_requires_full_adjudication_fields(tmp_path: Path) -> None:
    """Label integrity: a correction must include case_id, prior_label,
    corrected_label, adjudication_reason, evidence, and
    benchmark_version_change (brief section 4.4)."""
    payload = dict(MINIMAL_VALID)
    payload["corrections"] = [{"case_id": "c1", "prior_label": {}}]
    path = _write(tmp_path, payload)
    with pytest.raises(PueValidationError, match="missing required"):
        load_benchmark_dataset(path)


def test_valid_correction_entry_accepted(tmp_path: Path) -> None:
    payload = dict(MINIMAL_VALID)
    payload["corrections"] = [
        {
            "case_id": "c1",
            "prior_label": {"annotation_confidence": "low"},
            "corrected_label": {"annotation_confidence": "medium"},
            "adjudication_reason": "test",
            "evidence": "test evidence",
            "benchmark_version_change": "test-0.1.0 -> test-0.1.1",
        }
    ]
    path = _write(tmp_path, payload)
    dataset = load_benchmark_dataset(path)
    assert len(dataset.corrections) == 1


def test_stable_dataset_hash_is_deterministic(tmp_path: Path) -> None:
    path = _write(tmp_path, MINIMAL_VALID)
    h1 = dataset_file_hash(path)
    h2 = dataset_file_hash(path)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex digest


def test_dataset_hash_changes_when_content_changes(tmp_path: Path) -> None:
    path1 = _write(tmp_path, MINIMAL_VALID, "a.json")
    payload2 = dict(MINIMAL_VALID, dataset_id="different-id")
    path2 = _write(tmp_path, payload2, "b.json")
    assert dataset_file_hash(path1) != dataset_file_hash(path2)


def test_case_coverage_by_tag() -> None:
    dataset = load_benchmark_dataset(DEFAULT_BENCHMARK_PATH)
    coverage = case_coverage_by_tag(dataset.cases)
    assert coverage.get("exact_identification", 0) > 0
    assert coverage.get("water_block", 0) > 0
    assert coverage.get("catalogue_gap", 0) > 0
    assert coverage.get("unsupported_domain", 0) > 0


def test_missing_file_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(PueValidationError):
        load_benchmark_dataset(tmp_path / "does_not_exist.json")
