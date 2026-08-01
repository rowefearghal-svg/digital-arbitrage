"""Regenerate a published PUE release from the current checkout and verify
it against the committed manifest (Sprint 3 pre-merge correction item 4).

Run from the repository root:

    python scripts/verify_pue_release.py data/pue/releases/pue-v0.1.0.json

Verifies:

- the manifest's ``policy_code_git_commit`` equals the exact commit of the
  code actually running this verification;
- the manifest's dataset/catalogue hashes equal freshly (canonically)
  computed hashes of the current checkout's files;
- the manifest's ``release_report_hash`` equals the canonical hash of a
  freshly regenerated report;
- the regenerated report's semantic content is byte-for-byte identical to
  the committed report's (ignoring only documented volatile fields).

Regenerates into a fresh temporary directory - never touches the committed
release artefacts.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from digital_arbitrage.pue.release import load_release_manifest  # noqa: E402
from digital_arbitrage.pue.release_pipeline import verify_release_reproducibility  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_path", help="Path to the published release manifest JSON.")
    args = parser.parse_args()

    manifest = load_release_manifest(args.manifest_path)
    committed_report_path = Path(manifest.release_benchmark_report_path)
    if not committed_report_path.is_absolute():
        committed_report_path = ROOT / committed_report_path

    with tempfile.TemporaryDirectory() as tmp:
        result = verify_release_reproducibility(
            manifest,
            committed_report_path=committed_report_path if committed_report_path.exists() else None,
            output_dir=tmp,
        )
        for check in result.checks:
            print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
        print(f"regenerated artefacts written to: {tmp}")

    print(f"verification: {'PASS' if result.passed else 'FAIL'}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
