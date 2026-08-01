"""Canonical JSON serialization and cross-platform-stable hashing (Sprint 3
pre-merge correction).

Hashing raw file bytes (``hashlib.sha256(path.read_bytes())``) is affected
by CRLF/LF line-ending conversion (e.g. Git's ``core.autocrlf`` on Windows)
and by incidental whitespace/key-order differences between two JSON files
that encode the exact same content. Every release artifact hash in this
package must instead be computed over a **canonical JSON serialization** of
the *parsed* content - sorted keys, no insignificant whitespace, ``\\n``
newlines only (irrelevant here since there are none) - so the hash is
stable across operating systems, editors, and git checkout configurations,
and changes if and only if the actual content changes.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from .validation import PueValidationError

#: Source and policy/knowledge-data files (repo-root-relative) whose
#: content materially determines a Decision - the basis of
#: :func:`policy_code_content_hash`, a release-provenance identity that
#: survives a squash merge (unlike a Git commit hash, which necessarily
#: changes when a feature branch's commits are squashed into a single
#: merge commit on the base branch - Sprint 3 final release-integrity
#: correction item 4). Deliberately excludes the benchmark/report/release
#: machinery itself (``benchmark*.py``, ``release*.py``, ``comparison.py``)
#: - this hash identifies the *reasoning* code and knowledge/policy data a
#: Decision was produced under, not the harness that measured it.
DEFAULT_POLICY_CODE_PATHS: tuple[str, ...] = (
    "src/digital_arbitrage/pue/admission.py",
    "src/digital_arbitrage/pue/claims.py",
    "src/digital_arbitrage/pue/decisions.py",
    "src/digital_arbitrage/pue/enums.py",
    "src/digital_arbitrage/pue/evaluation.py",
    "src/digital_arbitrage/pue/evidence.py",
    "src/digital_arbitrage/pue/hypotheses.py",
    "src/digital_arbitrage/pue/models.py",
    "src/digital_arbitrage/pue/orchestration.py",
    "src/digital_arbitrage/pue/policies.py",
    "src/digital_arbitrage/pue/retrieval.py",
    "src/digital_arbitrage/pue/validation.py",
    "data/pue/knowledge/gpu_terms_v0.1.json",
)


def canonical_json_bytes(obj: object) -> bytes:
    """Deterministic, whitespace-free, key-sorted UTF-8 JSON encoding.

    Two Python objects that are ``==`` (dict key order does not matter for
    dict equality) always produce identical bytes; this is the basis for
    every content hash in this module.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_json_hash(obj: object) -> str:
    """SHA-256 hex digest of ``obj``'s canonical JSON encoding."""
    return hashlib.sha256(canonical_json_bytes(obj)).hexdigest()


def canonical_file_hash(path: Path | str) -> str:
    """SHA-256 hex digest of the *parsed and re-canonicalized* content of
    the JSON file at ``path`` - stable across CRLF/LF, whitespace, and key
    ordering; sensitive only to actual content changes.

    Raises :class:`PueValidationError` if the file cannot be read or is not
    valid JSON (never a bare ``OSError``/``json.JSONDecodeError``).
    """
    resolved = Path(path)
    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        raise PueValidationError(f"could not read {resolved} for canonical hashing: {exc}") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PueValidationError(
            f"{resolved} is not valid JSON, cannot canonically hash: {exc}"
        ) from exc
    return canonical_json_hash(parsed)


def policy_code_content_hash(
    paths: Sequence[str] = DEFAULT_POLICY_CODE_PATHS, *, repo_root: Path | None = None
) -> str:
    """Deterministic SHA-256 over the content of every file in ``paths``
    (repo-root-relative, hashed in sorted order regardless of the order
    given) - a release-provenance identity computed purely from file
    *content*, so it survives a squash merge (a Git commit hash does not:
    it necessarily changes when a feature branch's commits are squashed
    into a single merge commit on the base branch).

    Each file contributes its repo-relative path and raw bytes to a single
    running digest, so both a content change *and* a path rename/removal
    change the result. A missing file contributes a fixed sentinel rather
    than raising or being silently skipped - its absence must still change
    (and therefore be caught by) the resulting hash.
    """
    root = repo_root or Path(__file__).resolve().parents[3]
    hasher = hashlib.sha256()
    for rel in sorted(paths):
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        try:
            content = (root / rel).read_bytes()
        except OSError:
            content = b"<missing>"
        hasher.update(content)
        hasher.update(b"\0")
    return hasher.hexdigest()
