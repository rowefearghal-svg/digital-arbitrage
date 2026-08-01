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
from pathlib import Path

from .validation import PueValidationError


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
