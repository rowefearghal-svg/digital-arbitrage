"""Tests for versioned, immutable release manifests (Sprint 3, brief
sections 11/16)."""

from __future__ import annotations

from pathlib import Path

import pytest

from digital_arbitrage.pue.release import (
    build_release_manifest,
    load_release_manifest,
    load_release_manifest_by_id,
    save_release_manifest,
)
from digital_arbitrage.pue.validation import PueValidationError


def _manifest(**overrides):
    defaults = dict(
        release_id="pue-v0.1.0-test",
        capability_version="pue-0.1.0",
        policy_version="gpu-policy-0.1.0",
        knowledge_version="gpu-seed-0.1.0",
        schema_version="0.1",
        comparison_schema_version="pue-comparison-0.1.0",
        benchmark_dataset_id="gpu-release-benchmark-v0.1",
        benchmark_dataset_version="gpu-release-benchmark-0.1.0",
        benchmark_dataset_hash="a" * 64,
        catalogue_file_hash="b" * 64,
        release_benchmark_report_path="reports/pue_benchmark_report.json",
        release_gate_passed=True,
        release_date="2026-08-01",
        known_limitations=("seed catalogue is small",),
        policy_code_git_commit="deadbeef",
    )
    defaults.update(overrides)
    return build_release_manifest(**defaults)


def test_build_and_save_and_load_round_trip(tmp_path: Path) -> None:
    manifest = _manifest()
    path = tmp_path / "pue_v0.1.0.json"
    save_release_manifest(manifest, path)
    loaded = load_release_manifest(path)
    assert loaded == manifest


def test_save_refuses_to_overwrite_existing_manifest(tmp_path: Path) -> None:
    manifest = _manifest()
    path = tmp_path / "pue_v0.1.0.json"
    save_release_manifest(manifest, path)
    with pytest.raises(PueValidationError, match="already exists"):
        save_release_manifest(manifest, path)


def test_historical_manifest_untouched_after_failed_overwrite_attempt(tmp_path: Path) -> None:
    manifest = _manifest()
    path = tmp_path / "pue_v0.1.0.json"
    save_release_manifest(manifest, path)
    original_bytes = path.read_bytes()

    different = _manifest(release_gate_passed=False, known_limitations=("changed",))
    with pytest.raises(PueValidationError):
        save_release_manifest(different, path)

    assert path.read_bytes() == original_bytes


def test_loading_nonexistent_manifest_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(PueValidationError, match="does not exist"):
        load_release_manifest(tmp_path / "no_such_file.json")


def test_loading_manifest_missing_required_field_fails_clearly(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text('{"release_id": "x"}', encoding="utf-8")
    with pytest.raises(PueValidationError, match="missing required"):
        load_release_manifest(path)


def test_load_by_id_finds_the_matching_manifest(tmp_path: Path) -> None:
    manifest_a = _manifest(release_id="pue-v0.1.0")
    manifest_b = _manifest(release_id="pue-v0.2.0")
    save_release_manifest(manifest_a, tmp_path / "pue_v0.1.0.json")
    save_release_manifest(manifest_b, tmp_path / "pue_v0.2.0.json")

    found = load_release_manifest_by_id("pue-v0.2.0", releases_dir=tmp_path)
    assert found.release_id == "pue-v0.2.0"


def test_load_by_id_unavailable_version_fails_clearly_not_fallback(tmp_path: Path) -> None:
    """brief section 11: loading an unavailable or unknown version must
    fail clearly - never silently substitute the newest release."""
    save_release_manifest(_manifest(release_id="pue-v0.1.0"), tmp_path / "pue_v0.1.0.json")
    with pytest.raises(PueValidationError, match="no release manifest"):
        load_release_manifest_by_id("pue-v9.9.9-nonexistent", releases_dir=tmp_path)


def test_load_by_id_missing_directory_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(PueValidationError):
        load_release_manifest_by_id("anything", releases_dir=tmp_path / "does_not_exist")


def test_manifest_binds_dataset_and_catalogue_hashes() -> None:
    manifest = _manifest()
    assert len(manifest.benchmark_dataset_hash) == 64
    assert len(manifest.catalogue_file_hash) == 64


def test_manifest_records_policy_code_git_commit_when_policy_is_code_based() -> None:
    manifest = _manifest()
    assert manifest.policy_code_git_commit == "deadbeef"


def test_current_git_commit_never_raises() -> None:
    from digital_arbitrage.pue.release import current_git_commit

    # Never raises even outside a git repo / without git installed.
    result = current_git_commit(repo_root=Path("/nonexistent/path/for/testing"))
    assert isinstance(result, str)
