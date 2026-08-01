"""Reproducible PUE release generation and verification (Sprint 3
pre-merge correction items 1 and 4).

Two hard requirements this module exists to satisfy:

1. **Real release-gate evidence.** The mandatory-acceptance and
   deterministic-replay gate checks (see
   :mod:`digital_arbitrage.pue.benchmark_report`) must be the outcome of
   *actually executing* the mandatory Sprint 1/2 acceptance/regression test
   suite and an *actual* identical-version persisted replay - never a
   hardcoded literal passed by a caller. :func:`verify_mandatory_acceptance`
   and :func:`verify_replay_equivalence` are that real evidence; a caller
   that wants a different answer must make the real tests/replay actually
   behave differently (e.g. via dependency injection at the IO boundary),
   not simply pass a different boolean.
2. **Reproducible, immutable release artefacts.** :func:`run_release_pipeline`
   uses a deterministic id_factory/clock so two regenerations from the same
   code, dataset, and catalogue produce byte-identical (canonically-hashed)
   report content. :func:`generate_release_artifacts` refuses to write
   *anything* if any target file already exists - checked before any write,
   so a later failure never leaves some targets overwritten and others not.
   :func:`verify_release_reproducibility` regenerates into a fresh directory
   and compares canonical hashes, semantic report content, and the exact
   Git commit against a previously published manifest.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..normalization.models import NormalizedListing
from ..product_scanner.models import Condition, Listing
from .benchmark import (
    DEFAULT_BENCHMARK_PATH,
    BenchmarkDataset,
    dataset_file_hash,
    load_benchmark_dataset,
)
from .benchmark_report import (
    VOLATILE_REPORT_KEYS,
    BenchmarkReport,
    GateCheck,
    build_benchmark_report,
    canonical_report_artifact_hash,
    canonical_report_semantic_hash,
    render_report_json,
    render_report_markdown,
    report_semantic_dict,
)
from .benchmark_runner import run_benchmark
from .canonical import canonical_json_hash, policy_code_content_hash
from .catalogue import DEFAULT_CATALOGUE_PATH, JsonCandidateRepository, catalogue_file_hash
from .comparison import COMPARISON_SCHEMA_VERSION
from .orchestration import build_default_context, process_one
from .persistence import PueCaseStore
from .policies import DecisionPolicy
from .release import (
    ReleaseManifest,
    build_release_manifest,
    current_git_commit,
    save_release_manifest,
)
from .replay import replay_case
from .validation import PueValidationError
from .version import CAPABILITY_VERSION

#: Repository root, resolved the same way every other PUE module resolves
#: its default data paths (``pue/<module>.py`` -> repo root is 3 parents up).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The mandatory Sprint 1/2 acceptance/regression test files, plus the
#: structural no-commercial-data invariant - run together as one real,
#: executed pytest invocation (Sprint 3 pre-merge correction item 1).
DEFAULT_MANDATORY_TEST_PATHS: tuple[str, ...] = (
    "tests/pue/test_acceptance.py",
    "tests/pue/test_golden.py",
    "tests/pue/test_invariants.py",
)

#: Small, fixed sample of titles used only to exercise a real
#: persist-then-replay round trip for release-gate evidence - not a
#: benchmark case set (see ``tests/fixtures/pue/gpu_release_benchmark_v0.1.json``
#: for that).
DEFAULT_REPLAY_SAMPLE_TITLES: tuple[str, ...] = (
    "ASUS TUF Gaming GeForce RTX 4090 OC 24GB TUF-RTX4090-O24G",
    "NVIDIA GeForce RTX 4090 Founders Edition 24GB",
    "EK Quantum Vector2 RTX 4090 Water Block Full Cover",
)


class DeterministicSequentialIdFactory:
    """Deterministic, sequential id factory for reproducible release
    generation (production code, not a test fixture): two regenerations
    from the same code/dataset/catalogue must assign the exact same ids to
    the exact same reasoning steps in the exact same order, so their
    canonical report hashes match (Sprint 3 pre-merge correction item 4)."""

    def __init__(self, prefix: str = "release") -> None:
        self._n = 0
        self._prefix = prefix

    def __call__(self) -> str:
        self._n += 1
        return f"{self._prefix}-{self._n:08d}"


def _fixed_clock() -> datetime:
    """A fixed, deterministic clock for reproducible release generation."""
    return datetime(2026, 1, 1, tzinfo=UTC)


PytestRunner = Callable[[Sequence[str], Path], "subprocess.CompletedProcess[str]"]


def _default_pytest_runner(paths: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *paths],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def verify_mandatory_acceptance(
    *,
    test_paths: Sequence[str] = DEFAULT_MANDATORY_TEST_PATHS,
    repo_root: Path | None = None,
    runner: PytestRunner | None = None,
) -> tuple[bool, str]:
    """Actually execute the mandatory acceptance/regression test files and
    return their real pass/fail outcome (Sprint 3 pre-merge correction item
    1) - never a hardcoded literal.

    ``runner`` is an injectable IO boundary (defaults to a real
    ``python -m pytest`` subprocess) so tests can exercise this function's
    real pass/fail/detail-construction logic against a controlled,
    deterministic result without needing an actually-broken test file
    committed to the repository.
    """
    root = repo_root or _REPO_ROOT
    run = runner or _default_pytest_runner
    result = run(list(test_paths), root)
    passed = result.returncode == 0
    tail = (result.stdout or "")[-2000:]
    detail = f"pytest -q {' '.join(test_paths)} -> exit code {result.returncode}"
    if not passed:
        detail += f"; output tail: {tail!r}"
    return passed, detail


def verify_replay_equivalence(
    *,
    policy: DecisionPolicy | None = None,
    replay_policy: DecisionPolicy | None = None,
    repository: JsonCandidateRepository | None = None,
    sample_titles: Sequence[str] = DEFAULT_REPLAY_SAMPLE_TITLES,
    id_factory: Callable[[], str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[bool, str]:
    """Persist ``sample_titles`` through the real PUE orchestration path
    into a throwaway SQLite database, then replay each persisted case
    through the real :func:`digital_arbitrage.pue.replay.replay_case` and
    require every one to report semantic equivalence (Sprint 3 pre-merge
    correction item 1) - never a hardcoded literal.

    ``replay_policy``, if given and different from ``policy``, is passed to
    the replay step only - this genuinely forces a version mismatch (and
    therefore non-equivalence) through the real, unmodified replay code
    path, used by the negative test proving release generation fails when
    replay does not report equivalence.

    ``id_factory``/``clock`` default to a real, non-deterministic UUID4/
    wall-clock context; :func:`run_release_pipeline` passes deterministic
    ones so the resulting evidence detail string (which embeds these ids)
    is itself reproducible across regenerations (Sprint 3 pre-merge
    correction item 4).
    """
    repo = repository or JsonCandidateRepository()
    context = build_default_context(id_factory=id_factory, clock=clock)
    active_policy = policy or DecisionPolicy()
    details: list[str] = []
    all_equivalent = True

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "release_replay_verification.db"
        case_ids: list[str] = []
        with PueCaseStore(db_path) as store:
            for i, title in enumerate(sample_titles):
                listing = Listing(
                    listing_id=f"replay-verify-{i:03d}",
                    title=title,
                    provider="release-verification",
                    url="https://example.test/release-verification",
                    condition=Condition.USED,
                    extra={},
                )
                normalized = NormalizedListing.from_listing(listing)
                normalized.title_tokens = tuple(title.lower().split())
                record = process_one(normalized, context, repository=repo, policy=active_policy)
                store.save_case(record)
                case_ids.append(record.case_id)

            for case_id in case_ids:
                comparison = replay_case(
                    case_id,
                    database_path=str(db_path),
                    repository=repo,
                    policy=replay_policy if replay_policy is not None else active_policy,
                )
                details.append(f"{case_id}: equivalent={comparison.equivalent}")
                if not comparison.equivalent:
                    all_equivalent = False

    return all_equivalent, "; ".join(details)


@dataclass(frozen=True, slots=True)
class ReleaseArtifacts:
    """Everything one release pipeline run produces, before anything is
    written to disk."""

    dataset: BenchmarkDataset
    dataset_hash: str
    catalogue_hash: str
    report: BenchmarkReport
    manifest: ReleaseManifest


def run_release_pipeline(
    *,
    release_id: str,
    dataset_path: Path | str = DEFAULT_BENCHMARK_PATH,
    catalogue_path: Path | str = DEFAULT_CATALOGUE_PATH,
    known_limitations: tuple[str, ...] = (),
    release_date: str | None = None,
    generated_at: str | None = None,
    report_relative_path: str = "",
    pytest_runner: PytestRunner | None = None,
    mandatory_test_paths: Sequence[str] = DEFAULT_MANDATORY_TEST_PATHS,
    replay_policy: DecisionPolicy | None = None,
) -> ReleaseArtifacts:
    """Run the complete release pipeline: real mandatory-acceptance
    verification, real replay-equivalence verification, the full benchmark
    (under a deterministic id_factory/clock for reproducibility), and the
    resulting report + manifest.

    Raises :class:`PueValidationError` immediately - before running the
    benchmark or writing anything - if either real verification step fails
    (Sprint 3 pre-merge correction item 1: these two conditions are release
    *blockers*, not merely reported metrics). Any other release-gate check
    that fails from the benchmark data itself (e.g. a harmful-error rate)
    still produces a normal report/manifest with ``release_gate_passed =
    False``, so the failure remains visible and debuggable rather than
    silently discarded.
    """
    acceptance_passed, acceptance_detail = verify_mandatory_acceptance(
        test_paths=mandatory_test_paths, runner=pytest_runner
    )
    if not acceptance_passed:
        raise PueValidationError(
            "release generation refused: mandatory acceptance/regression verification "
            f"failed ({acceptance_detail}); fix the failing test(s) before generating a "
            "release - this is real, executed evidence, not a configurable flag"
        )

    replay_equivalent, replay_detail = verify_replay_equivalence(
        replay_policy=replay_policy,
        id_factory=DeterministicSequentialIdFactory(prefix="release-replay-verify"),
        clock=_fixed_clock,
    )
    if not replay_equivalent:
        raise PueValidationError(
            "release generation refused: identical-version persisted replay did not report "
            f"semantic equivalence ({replay_detail}); this indicates the running code cannot "
            "reproduce its own recent Decisions and must be fixed before generating a release"
        )

    dataset = load_benchmark_dataset(dataset_path)
    dataset_hash = dataset_file_hash(dataset_path)
    catalogue_hash = catalogue_file_hash(catalogue_path)
    repository = JsonCandidateRepository.from_path(catalogue_path)

    run = run_benchmark(
        dataset,
        repository=repository,
        run_classifier=True,
        id_factory=DeterministicSequentialIdFactory(),
        clock=_fixed_clock,
    )

    report = build_benchmark_report(
        dataset,
        dataset_hash,
        run.results,
        run.failures,
        capability_version=CAPABILITY_VERSION,
        policy_version=run.context.policy_version,
        knowledge_version=run.context.knowledge_version,
        schema_version=run.context.schema_version,
        wall_time_seconds=run.wall_time_seconds,
        mandatory_acceptance_pass=acceptance_passed,
        mandatory_acceptance_detail=acceptance_detail,
        replay_equivalent=replay_equivalent,
        replay_equivalent_detail=replay_detail,
        run_differential=True,
        generated_at=generated_at,
    )

    manifest = build_release_manifest(
        release_id=release_id,
        capability_version=CAPABILITY_VERSION,
        policy_version=run.context.policy_version,
        knowledge_version=run.context.knowledge_version,
        schema_version=run.context.schema_version,
        comparison_schema_version=COMPARISON_SCHEMA_VERSION,
        benchmark_dataset_id=dataset.dataset_id,
        benchmark_dataset_version=dataset.benchmark_version,
        benchmark_dataset_hash=dataset_hash,
        catalogue_file_hash=catalogue_hash,
        policy_code_content_hash=policy_code_content_hash(),
        release_benchmark_report_path=report_relative_path,
        release_report_artifact_hash=canonical_report_artifact_hash(report),
        release_report_semantic_hash=canonical_report_semantic_hash(report),
        release_gate_passed=report.gate.passed,
        release_date=release_date or datetime.now(UTC).date().isoformat(),
        known_limitations=known_limitations,
    )

    return ReleaseArtifacts(
        dataset=dataset,
        dataset_hash=dataset_hash,
        catalogue_hash=catalogue_hash,
        report=report,
        manifest=manifest,
    )


def generate_release_artifacts(
    *,
    release_id: str,
    manifest_path: Path | str,
    report_json_path: Path | str,
    report_md_path: Path | str,
    dataset_path: Path | str = DEFAULT_BENCHMARK_PATH,
    catalogue_path: Path | str = DEFAULT_CATALOGUE_PATH,
    known_limitations: tuple[str, ...] = (),
    pytest_runner: PytestRunner | None = None,
    replay_policy: DecisionPolicy | None = None,
) -> ReleaseArtifacts:
    """Generate one complete release: refuses to write *anything* if any
    target path already exists (checked up front, before running the
    pipeline or writing any file) - a manifest-save failure must never
    leave already-overwritten report files behind (Sprint 3 pre-merge
    correction item 4).
    """
    targets = {
        "manifest_path": Path(manifest_path),
        "report_json_path": Path(report_json_path),
        "report_md_path": Path(report_md_path),
    }
    existing = {name: str(p) for name, p in targets.items() if p.exists()}
    if existing:
        raise PueValidationError(
            f"release target(s) already exist: {existing}; release artefacts are immutable "
            "and generation refuses to touch any of them before writing anything else - use "
            "a new release_id/path set for a new release"
        )

    report_relative_path = str(targets["report_json_path"])
    try:
        report_relative_path = str(targets["report_json_path"].relative_to(_REPO_ROOT)).replace(
            "\\", "/"
        )
    except ValueError:
        pass

    artifacts = run_release_pipeline(
        release_id=release_id,
        dataset_path=dataset_path,
        catalogue_path=catalogue_path,
        known_limitations=known_limitations,
        report_relative_path=report_relative_path,
        pytest_runner=pytest_runner,
        replay_policy=replay_policy,
    )

    targets["report_json_path"].parent.mkdir(parents=True, exist_ok=True)
    targets["report_json_path"].write_text(render_report_json(artifacts.report), encoding="utf-8")
    targets["report_md_path"].parent.mkdir(parents=True, exist_ok=True)
    targets["report_md_path"].write_text(render_report_markdown(artifacts.report), encoding="utf-8")
    save_release_manifest(artifacts.manifest, targets["manifest_path"])

    return artifacts


@dataclass(frozen=True, slots=True)
class VerificationReport:
    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.blocking)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "checks": [c.to_dict() for c in self.checks]}


def verify_release_reproducibility(
    manifest: ReleaseManifest,
    *,
    dataset_path: Path | str = DEFAULT_BENCHMARK_PATH,
    catalogue_path: Path | str = DEFAULT_CATALOGUE_PATH,
    committed_report_path: Path | str | None = None,
    output_dir: Path | str | None = None,
    pytest_runner: PytestRunner | None = None,
) -> VerificationReport:
    """Regenerate a release from ``dataset_path``/``catalogue_path`` (by
    default the current, current-checkout files) and verify it against a
    previously published ``manifest`` (Sprint 3 pre-merge correction item
    4; provenance/hash-splitting corrected by the Sprint 3 final
    release-integrity correction items 4/5):

    - the manifest's ``policy_code_content_hash`` (computed purely from
      file content - see
      :func:`digital_arbitrage.pue.canonical.policy_code_content_hash`)
      equals the same hash freshly computed from the current checkout -
      the authoritative, squash-merge-surviving provenance check;
    - the manifest's ``policy_code_git_commit`` equals the exact commit of
      the code actually running this verification (informational only,
      non-blocking - expected to legitimately differ once this release's
      branch is squash-merged);
    - the manifest's dataset/catalogue hashes equal freshly (canonically)
      computed hashes of the current files;
    - the manifest's ``release_report_semantic_hash`` equals the canonical
      semantic hash of a freshly regenerated report;
    - if ``committed_report_path`` is given: the manifest's
      ``release_report_artifact_hash`` equals a fresh canonical hash of the
      *exact currently-committed* report file (detects any post-publication
      tampering, including a hand-edited operational metric), and the
      freshly regenerated report's *semantic* content (see
      :func:`digital_arbitrage.pue.benchmark_report.report_semantic_dict`)
      is byte-for-byte identical to the committed report's, ignoring only
      the documented volatile fields.

    If ``output_dir`` is given, the regenerated report is written there
    (typically a fresh temporary directory) for inspection - this function
    never touches the committed release artefacts.
    """
    import json as _json

    checks: list[GateCheck] = []

    # Informational only, never blocking (Sprint 3 final release-integrity
    # correction item 4): a Git commit is *expected* to differ once this
    # release's feature branch is squash-merged into a single, different
    # commit on the base branch. The authoritative, blocking provenance
    # check is ``policy_code_content_hash_matches`` below, computed purely
    # from file content and therefore unaffected by a squash merge.
    current_commit = current_git_commit()
    checks.append(
        GateCheck(
            "policy_code_git_commit_matches_running_code",
            current_commit == manifest.policy_code_git_commit,
            f"manifest={manifest.policy_code_git_commit!r} running={current_commit!r} "
            "(informational only - expected to differ after a squash merge; see "
            "policy_code_content_hash_matches for the authoritative check)",
            blocking=False,
        )
    )

    current_content_hash = policy_code_content_hash()
    checks.append(
        GateCheck(
            "policy_code_content_hash_matches",
            current_content_hash == manifest.policy_code_content_hash,
            f"manifest={manifest.policy_code_content_hash!r} current={current_content_hash!r}",
        )
    )

    current_dataset_hash = dataset_file_hash(dataset_path)
    checks.append(
        GateCheck(
            "benchmark_dataset_hash_matches",
            current_dataset_hash == manifest.benchmark_dataset_hash,
            f"manifest={manifest.benchmark_dataset_hash!r} current={current_dataset_hash!r}",
        )
    )

    current_catalogue_hash = catalogue_file_hash(catalogue_path)
    checks.append(
        GateCheck(
            "catalogue_file_hash_matches",
            current_catalogue_hash == manifest.catalogue_file_hash,
            f"manifest={manifest.catalogue_file_hash!r} current={current_catalogue_hash!r}",
        )
    )

    regenerated = run_release_pipeline(
        release_id=manifest.release_id,
        dataset_path=dataset_path,
        catalogue_path=catalogue_path,
        known_limitations=manifest.known_limitations,
        release_date=manifest.release_date,
        report_relative_path=manifest.release_benchmark_report_path,
        pytest_runner=pytest_runner,
    )
    regenerated_semantic_hash = canonical_report_semantic_hash(regenerated.report)
    checks.append(
        GateCheck(
            "release_report_semantic_hash_matches",
            regenerated_semantic_hash == manifest.release_report_semantic_hash,
            f"manifest={manifest.release_report_semantic_hash!r} "
            f"regenerated={regenerated_semantic_hash!r}",
        )
    )
    checks.append(
        GateCheck(
            "release_gate_passed_matches",
            regenerated.report.gate.passed == manifest.release_gate_passed,
            f"manifest={manifest.release_gate_passed} regenerated={regenerated.report.gate.passed}",
        )
    )

    if committed_report_path is not None:
        committed_text = Path(committed_report_path).read_text(encoding="utf-8")
        committed_dict = _json.loads(committed_text)

        # Artifact-integrity check (Sprint 3 final release-integrity
        # correction item 5): re-hash the *exact currently-committed*
        # report file - including its (volatile-by-nature but now
        # tamper-checked) generated_at/operational_metrics fields - and
        # compare against the manifest's release_report_artifact_hash.
        # This must NEVER be compared against a freshly regenerated
        # report (real wall-clock timing varies run to run and would
        # always mismatch); it detects any post-publication edit to the
        # committed file itself, including a hand-edited operational
        # metric.
        committed_artifact_hash = canonical_json_hash(committed_dict)
        checks.append(
            GateCheck(
                "release_report_artifact_hash_matches_committed_file",
                committed_artifact_hash == manifest.release_report_artifact_hash,
                f"manifest={manifest.release_report_artifact_hash!r} "
                f"committed_file={committed_artifact_hash!r}",
            )
        )

        committed_semantic = {
            k: v for k, v in committed_dict.items() if k not in VOLATILE_REPORT_KEYS
        }
        regenerated_semantic = report_semantic_dict(regenerated.report)
        checks.append(
            GateCheck(
                "semantic_report_content_matches_committed_report",
                committed_semantic == regenerated_semantic,
                "byte-for-byte semantic (non-volatile) content comparison against "
                f"{committed_report_path}",
            )
        )

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "regenerated_report.json").write_text(
            render_report_json(regenerated.report), encoding="utf-8"
        )
        (out / "regenerated_report.md").write_text(
            render_report_markdown(regenerated.report), encoding="utf-8"
        )

    return VerificationReport(checks=tuple(checks))
