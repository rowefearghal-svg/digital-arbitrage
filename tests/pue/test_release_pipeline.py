"""Tests for reproducible PUE release generation and verification (Sprint 3
pre-merge correction items 1 and 4).

Most tests inject a fast, controlled pytest ``runner`` for the mandatory-
acceptance check (avoiding a real, slow ``python -m pytest`` subprocess per
test) while still exercising the *real*, unmodified benchmark run and the
*real*, unmodified replay-equivalence verification - only the IO boundary
(spawning a pytest subprocess) is faked, never the production decision
logic that interprets its result. One test (``test_...default_real_pytest``)
exercises the true, unmocked default end to end.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from digital_arbitrage.pue.policies import DecisionPolicy
from digital_arbitrage.pue.release import load_release_manifest
from digital_arbitrage.pue.release_pipeline import (
    generate_release_artifacts,
    run_release_pipeline,
    verify_mandatory_acceptance,
    verify_release_reproducibility,
    verify_replay_equivalence,
)
from digital_arbitrage.pue.validation import PueValidationError


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""


def _passing_runner(paths, cwd):  # noqa: ANN001, ARG001
    return _FakeCompletedProcess(returncode=0, stdout="")


def _failing_runner(paths, cwd):  # noqa: ANN001, ARG001
    return _FakeCompletedProcess(returncode=1, stdout="FAKE FAILURE: 3 failed, 0 passed")


# --------------------------------------------------------------------------- #
# Item 1: real release-gate evidence
# --------------------------------------------------------------------------- #
def test_verify_mandatory_acceptance_reports_real_injected_pass() -> None:
    passed, detail = verify_mandatory_acceptance(runner=_passing_runner)
    assert passed is True
    assert "exit code 0" in detail


def test_verify_mandatory_acceptance_reports_real_injected_failure() -> None:
    passed, detail = verify_mandatory_acceptance(runner=_failing_runner)
    assert passed is False
    assert "exit code 1" in detail
    assert "FAKE FAILURE" in detail


def test_verify_replay_equivalence_passes_under_identical_policy() -> None:
    equivalent, detail = verify_replay_equivalence()
    assert equivalent is True
    assert "equivalent=True" in detail


def test_verify_replay_equivalence_fails_under_a_genuinely_different_replay_policy() -> None:
    """A mismatched replay policy forces a real, unmocked version mismatch
    through the actual replay code path - not a stubbed failure."""
    equivalent, detail = verify_replay_equivalence(
        replay_policy=DecisionPolicy(policy_version="deliberately-different-test-policy")
    )
    assert equivalent is False
    assert "equivalent=False" in detail


def test_run_release_pipeline_refuses_when_acceptance_fails() -> None:
    with pytest.raises(PueValidationError, match="mandatory acceptance"):
        run_release_pipeline(release_id="x", pytest_runner=_failing_runner)


def test_run_release_pipeline_refuses_when_replay_fails() -> None:
    with pytest.raises(PueValidationError, match="replay"):
        run_release_pipeline(
            release_id="x",
            pytest_runner=_passing_runner,
            replay_policy=DecisionPolicy(policy_version="deliberately-different-test-policy"),
        )


def test_run_release_pipeline_succeeds_with_real_evidence_when_both_pass() -> None:
    artifacts = run_release_pipeline(release_id="x", pytest_runner=_passing_runner)
    gate_by_name = {c.name: c for c in artifacts.report.gate.checks}
    assert gate_by_name["all_mandatory_acceptance_cases_pass"].passed is True
    assert gate_by_name["deterministic_replay_equivalent"].passed is True
    # The detail strings carry real, non-generic evidence, not a bare "True".
    assert "exit code 0" in gate_by_name["all_mandatory_acceptance_cases_pass"].detail
    assert "equivalent=True" in gate_by_name["deterministic_replay_equivalent"].detail


def test_run_release_pipeline_default_uses_the_real_pytest_subprocess() -> None:
    """No injected runner at all - exercises the true production default
    (a real ``python -m pytest`` subprocess for mandatory acceptance).

    The mandatory-acceptance/replay evidence (this function's actual
    purpose) must be real and passing; the *overall* release gate on the
    current real dataset has one known, pre-existing, already-documented
    gap unrelated to this pipeline function (see
    tests/pue/test_benchmark_report.py's _KNOWN_REMAINING_GATE_GAPS) -
    asserted narrowly here rather than via the aggregate ``gate.passed``.
    """
    artifacts = run_release_pipeline(release_id="x")
    checks_by_name = {c.name: c for c in artifacts.report.gate.checks}
    assert checks_by_name["all_mandatory_acceptance_cases_pass"].passed is True
    assert checks_by_name["deterministic_replay_equivalent"].passed is True


# --------------------------------------------------------------------------- #
# Item 4: reproducible, immutable release artefacts
# --------------------------------------------------------------------------- #
def test_run_release_pipeline_is_reproducible_across_calls() -> None:
    a1 = run_release_pipeline(release_id="x", pytest_runner=_passing_runner)
    a2 = run_release_pipeline(release_id="x", pytest_runner=_passing_runner)
    assert a1.manifest.release_report_semantic_hash == a2.manifest.release_report_semantic_hash
    assert a1.manifest.policy_code_content_hash == a2.manifest.policy_code_content_hash
    assert a1.dataset_hash == a2.dataset_hash
    assert a1.catalogue_hash == a2.catalogue_hash
    # The artifact hash is *not* expected to reproduce: it covers real,
    # measured wall-clock operational timing (Sprint 3 final
    # release-integrity correction item 5).
    assert a1.manifest.release_report_artifact_hash != a2.manifest.release_report_artifact_hash


def test_generate_release_artifacts_writes_manifest_and_reports(tmp_path: Path) -> None:
    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    artifacts = generate_release_artifacts(
        release_id="x",
        manifest_path=manifest_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        pytest_runner=_passing_runner,
    )
    assert manifest_path.exists()
    assert report_json_path.exists()
    assert report_md_path.exists()
    loaded = load_release_manifest(manifest_path)
    assert loaded.release_report_semantic_hash == artifacts.manifest.release_report_semantic_hash
    assert loaded.release_report_artifact_hash == artifacts.manifest.release_report_artifact_hash
    # release_gate_passed must genuinely reflect the real dataset's gate
    # outcome (currently False - one known, pre-existing gap; see
    # tests/pue/test_benchmark_report.py's _KNOWN_REMAINING_GATE_GAPS) -
    # never hardcoded, and round-trips exactly through save/load.
    assert loaded.release_gate_passed == artifacts.report.gate.passed


def test_generate_release_artifacts_refuses_if_manifest_already_exists(tmp_path: Path) -> None:
    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    manifest_path.write_text("{}", encoding="utf-8")

    with pytest.raises(PueValidationError, match="already exist"):
        generate_release_artifacts(
            release_id="x",
            manifest_path=manifest_path,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            pytest_runner=_passing_runner,
        )
    # Nothing else was written either - refusal happens before any write.
    assert not report_json_path.exists()
    assert not report_md_path.exists()


def test_generate_release_artifacts_refuses_if_report_already_exists_without_touching_manifest(
    tmp_path: Path,
) -> None:
    """The manifest must never be written first and the report overwritten
    second (or vice versa) - refusal is checked for *every* target before
    *any* of them is written (Sprint 3 pre-merge correction item 4)."""
    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    report_json_path.write_text("{}", encoding="utf-8")

    with pytest.raises(PueValidationError, match="already exist"):
        generate_release_artifacts(
            release_id="x",
            manifest_path=manifest_path,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            pytest_runner=_passing_runner,
        )
    assert not manifest_path.exists()
    assert not report_md_path.exists()


def test_verify_release_reproducibility_passes_for_a_just_generated_release(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    artifacts = generate_release_artifacts(
        release_id="x",
        manifest_path=manifest_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        pytest_runner=_passing_runner,
    )
    result = verify_release_reproducibility(
        artifacts.manifest,
        committed_report_path=report_json_path,
        pytest_runner=_passing_runner,
    )
    assert result.passed, [c.to_dict() for c in result.checks if not c.passed]


def test_verify_release_reproducibility_detects_a_tampered_catalogue_hash(
    tmp_path: Path,
) -> None:
    import dataclasses

    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    artifacts = generate_release_artifacts(
        release_id="x",
        manifest_path=manifest_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        pytest_runner=_passing_runner,
    )
    tampered = dataclasses.replace(artifacts.manifest, catalogue_file_hash="0" * 64)
    result = verify_release_reproducibility(tampered, pytest_runner=_passing_runner)
    assert result.passed is False
    failing_names = {c.name for c in result.checks if not c.passed}
    assert "catalogue_file_hash_matches" in failing_names


def test_verify_release_reproducibility_detects_a_tampered_report_hash(tmp_path: Path) -> None:
    import dataclasses

    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    artifacts = generate_release_artifacts(
        release_id="x",
        manifest_path=manifest_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        pytest_runner=_passing_runner,
    )
    tampered = dataclasses.replace(artifacts.manifest, release_report_semantic_hash="0" * 64)
    result = verify_release_reproducibility(tampered, pytest_runner=_passing_runner)
    assert result.passed is False
    failing_names = {c.name for c in result.checks if not c.passed}
    assert "release_report_semantic_hash_matches" in failing_names


def test_verify_release_reproducibility_checks_git_commit_matches() -> None:
    """Uses the real, current git commit - so a manifest claiming a
    different commit must fail verification."""
    import dataclasses

    from digital_arbitrage.pue.release_pipeline import run_release_pipeline

    artifacts = run_release_pipeline(release_id="x", pytest_runner=_passing_runner)
    tampered = dataclasses.replace(
        artifacts.manifest, policy_code_git_commit="0000000000000000000000000000000000000000"
    )
    result = verify_release_reproducibility(tampered, pytest_runner=_passing_runner)
    failing_names = {c.name for c in result.checks if not c.passed}
    assert "policy_code_git_commit_matches_running_code" in failing_names
    # A git-commit mismatch alone (expected after a squash merge) must
    # never fail overall verification - it is informational only.
    assert result.passed is True


def test_verify_release_reproducibility_detects_a_tampered_policy_code_content_hash() -> None:
    """Unlike the Git commit, the content hash is authoritative and
    blocking - a mismatch here must fail verification (Sprint 3 final
    release-integrity correction item 4)."""
    import dataclasses

    artifacts2 = run_release_pipeline(release_id="x", pytest_runner=_passing_runner)
    tampered = dataclasses.replace(artifacts2.manifest, policy_code_content_hash="0" * 64)
    result = verify_release_reproducibility(tampered, pytest_runner=_passing_runner)
    assert result.passed is False
    failing_names = {c.name for c in result.checks if not c.passed}
    assert "policy_code_content_hash_matches" in failing_names


def test_verify_release_reproducibility_detects_tampered_operational_metrics(
    tmp_path: Path,
) -> None:
    """The artifact hash must catch a hand-edited operational metric in
    the committed report file - a case the semantic hash deliberately
    cannot catch (it excludes operational_metrics entirely) (Sprint 3
    final release-integrity correction item 5)."""
    import json

    manifest_path = tmp_path / "r.json"
    report_json_path = tmp_path / "r_report.json"
    report_md_path = tmp_path / "r_report.md"
    artifacts = generate_release_artifacts(
        release_id="x",
        manifest_path=manifest_path,
        report_json_path=report_json_path,
        report_md_path=report_md_path,
        pytest_runner=_passing_runner,
    )
    report_dict = json.loads(report_json_path.read_text(encoding="utf-8"))
    report_dict["operational_metrics"]["listings_per_second"] = 999999.0
    report_json_path.write_text(json.dumps(report_dict), encoding="utf-8")

    result = verify_release_reproducibility(
        artifacts.manifest,
        committed_report_path=report_json_path,
        pytest_runner=_passing_runner,
    )
    assert result.passed is False
    failing_names = {c.name for c in result.checks if not c.passed}
    assert "release_report_artifact_hash_matches_committed_file" in failing_names
    # The semantic hash must *not* catch this - operational_metrics is
    # deliberately excluded from it.
    assert "semantic_report_content_matches_committed_report" not in failing_names
