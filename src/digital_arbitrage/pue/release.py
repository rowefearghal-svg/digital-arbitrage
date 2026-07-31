"""Versioned, immutable PUE release manifests (Sprint 3, brief section 11).

A release manifest binds together every artifact version that materially
determines a Decision - capability, policy, knowledge, schema, comparison
schema, the exact benchmark dataset (by id *and* content hash), the exact
catalogue file (by content hash), and the policy/code Git commit (the
Decision Policy remains code, per ``pue/policies.py`` - not force-encoded
into JSON merely for appearance; the manifest instead identifies exactly
which commit implements it) - plus the release-gate outcome and known
limitations.

Manifests are write-once: :func:`save_release_manifest` refuses to
overwrite an existing file (brief: "Historical catalogue, policy and
release versions must not be overwritten"). :func:`load_release_manifest`
fails clearly - never silently substitutes the newest release - when the
requested version does not exist (brief: "Loading an unavailable or
unknown version must fail clearly").
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .validation import PueValidationError

#: Schema version of the release-manifest *format* itself.
RELEASE_MANIFEST_SCHEMA_VERSION = "pue-release-manifest-0.1.0"

#: Default directory for release manifests (brief section 11's suggested
#: location, generalized to a directory since more than one release will
#: eventually exist here).
DEFAULT_RELEASES_DIR = Path(__file__).resolve().parents[3] / "data" / "pue" / "releases"

_REQUIRED_FIELDS = (
    "release_id",
    "capability_version",
    "policy_version",
    "knowledge_version",
    "schema_version",
    "comparison_schema_version",
    "benchmark_dataset_id",
    "benchmark_dataset_version",
    "benchmark_dataset_hash",
    "catalogue_file_hash",
    "policy_code_git_commit",
    "release_benchmark_report_path",
    "release_gate_passed",
    "release_date",
    "known_limitations",
)


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    manifest_schema_version: str
    release_id: str
    capability_version: str
    policy_version: str
    knowledge_version: str
    schema_version: str
    comparison_schema_version: str
    benchmark_dataset_id: str
    benchmark_dataset_version: str
    benchmark_dataset_hash: str
    catalogue_file_hash: str
    policy_code_git_commit: str
    release_benchmark_report_path: str
    release_gate_passed: bool
    release_date: str
    known_limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "manifest_schema_version": self.manifest_schema_version,
            "release_id": self.release_id,
            "capability_version": self.capability_version,
            "policy_version": self.policy_version,
            "knowledge_version": self.knowledge_version,
            "schema_version": self.schema_version,
            "comparison_schema_version": self.comparison_schema_version,
            "benchmark_dataset_id": self.benchmark_dataset_id,
            "benchmark_dataset_version": self.benchmark_dataset_version,
            "benchmark_dataset_hash": self.benchmark_dataset_hash,
            "catalogue_file_hash": self.catalogue_file_hash,
            "policy_code_git_commit": self.policy_code_git_commit,
            "release_benchmark_report_path": self.release_benchmark_report_path,
            "release_gate_passed": self.release_gate_passed,
            "release_date": self.release_date,
            "known_limitations": list(self.known_limitations),
        }


def current_git_commit(repo_root: Path | None = None) -> str:
    """Best-effort exact Git commit hash for the running code.

    Returns ``"unknown"`` (never raises) if Git is unavailable or the
    working tree is not a Git repository - a manifest must still be
    buildable in a stripped-down environment; the field simply records
    that provenance could not be determined.
    """
    root = repo_root or Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


def build_release_manifest(
    *,
    release_id: str,
    capability_version: str,
    policy_version: str,
    knowledge_version: str,
    schema_version: str,
    comparison_schema_version: str,
    benchmark_dataset_id: str,
    benchmark_dataset_version: str,
    benchmark_dataset_hash: str,
    catalogue_file_hash: str,
    release_benchmark_report_path: str,
    release_gate_passed: bool,
    release_date: str,
    known_limitations: tuple[str, ...] = (),
    policy_code_git_commit: str | None = None,
) -> ReleaseManifest:
    return ReleaseManifest(
        manifest_schema_version=RELEASE_MANIFEST_SCHEMA_VERSION,
        release_id=release_id,
        capability_version=capability_version,
        policy_version=policy_version,
        knowledge_version=knowledge_version,
        schema_version=schema_version,
        comparison_schema_version=comparison_schema_version,
        benchmark_dataset_id=benchmark_dataset_id,
        benchmark_dataset_version=benchmark_dataset_version,
        benchmark_dataset_hash=benchmark_dataset_hash,
        catalogue_file_hash=catalogue_file_hash,
        policy_code_git_commit=policy_code_git_commit or current_git_commit(),
        release_benchmark_report_path=release_benchmark_report_path,
        release_gate_passed=release_gate_passed,
        release_date=release_date,
        known_limitations=tuple(known_limitations),
    )


def save_release_manifest(manifest: ReleaseManifest, path: Path | str) -> None:
    """Write ``manifest`` to ``path``. Refuses to overwrite an existing
    file: a release manifest is write-once (brief section 11)."""
    resolved = Path(path)
    if resolved.exists():
        raise PueValidationError(
            f"release manifest {resolved} already exists; release manifests are immutable "
            "and must never be overwritten - use a new release_id/path for a new release"
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


def _manifest_from_dict(raw: Mapping[str, object], *, source: str) -> ReleaseManifest:
    missing = [f for f in _REQUIRED_FIELDS if f not in raw]
    if missing:
        raise PueValidationError(f"release manifest {source}: missing required field(s) {missing}")
    limitations = raw["known_limitations"]
    if not isinstance(limitations, list):
        raise PueValidationError(f"release manifest {source}: 'known_limitations' must be a list")
    gate_passed = raw["release_gate_passed"]
    if not isinstance(gate_passed, bool):
        raise PueValidationError(f"release manifest {source}: 'release_gate_passed' must be a bool")
    return ReleaseManifest(
        manifest_schema_version=str(
            raw.get("manifest_schema_version", RELEASE_MANIFEST_SCHEMA_VERSION)
        ),
        release_id=str(raw["release_id"]),
        capability_version=str(raw["capability_version"]),
        policy_version=str(raw["policy_version"]),
        knowledge_version=str(raw["knowledge_version"]),
        schema_version=str(raw["schema_version"]),
        comparison_schema_version=str(raw["comparison_schema_version"]),
        benchmark_dataset_id=str(raw["benchmark_dataset_id"]),
        benchmark_dataset_version=str(raw["benchmark_dataset_version"]),
        benchmark_dataset_hash=str(raw["benchmark_dataset_hash"]),
        catalogue_file_hash=str(raw["catalogue_file_hash"]),
        policy_code_git_commit=str(raw["policy_code_git_commit"]),
        release_benchmark_report_path=str(raw["release_benchmark_report_path"]),
        release_gate_passed=gate_passed,
        release_date=str(raw["release_date"]),
        known_limitations=tuple(str(x) for x in limitations),
    )


def load_release_manifest(path: Path | str) -> ReleaseManifest:
    """Load and validate a release manifest file.

    Raises :class:`PueValidationError` clearly if the file does not exist,
    is not valid JSON, or is missing required fields - never silently
    substitutes a different release.
    """
    resolved = Path(path)
    if not resolved.exists():
        raise PueValidationError(
            f"release manifest {resolved} does not exist; loading an unavailable or unknown "
            "release must fail clearly rather than silently substitute a different one"
        )
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PueValidationError(f"release manifest {resolved} is not valid JSON: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise PueValidationError(f"release manifest {resolved} must be a JSON object")
    return _manifest_from_dict(raw, source=str(resolved))


def load_release_manifest_by_id(
    release_id: str, *, releases_dir: Path | str = DEFAULT_RELEASES_DIR
) -> ReleaseManifest:
    """Load the manifest for ``release_id`` from ``releases_dir`` by
    scanning every ``*.json`` file and matching ``release_id`` exactly.

    Fails clearly (never falls back to the newest release) if no manifest
    in the directory declares this exact ``release_id``.
    """
    directory = Path(releases_dir)
    if not directory.is_dir():
        raise PueValidationError(
            f"releases directory {directory} does not exist; cannot load release {release_id!r}"
        )
    for candidate in sorted(directory.glob("*.json")):
        try:
            manifest = load_release_manifest(candidate)
        except PueValidationError:
            continue
        if manifest.release_id == release_id:
            return manifest
    raise PueValidationError(
        f"no release manifest with release_id {release_id!r} found in {directory}; known "
        "releases must be requested by their exact id - an unavailable version fails clearly"
    )
