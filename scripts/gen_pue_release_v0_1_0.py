"""Generate the pue-v0.1.0 release manifest + its bound benchmark report
(Sprint 3, brief section 11) via the reproducible release pipeline.

Refuses to write anything if any target already exists (checked before any
write - see ``release_pipeline.generate_release_artifacts``). Run from the
repository root:

    python scripts/gen_pue_release_v0_1_0.py

Regenerate only after a deliberate, reviewed release-affecting change -
review the diff carefully, and never overwrite a previously published
release manifest (this script itself refuses to, and each artefact target
must not already exist).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from digital_arbitrage.pue.release_pipeline import generate_release_artifacts  # noqa: E402
from digital_arbitrage.pue.validation import PueValidationError  # noqa: E402

RELEASES_DIR = ROOT / "data" / "pue" / "releases"
RELEASE_ID = "pue-v0.1.0"

KNOWN_LIMITATIONS = (
    "Seed catalogue (data/pue/catalogues/gpu_seed_v0.1.json) covers ~36 hand-curated "
    "products; many real GPU SKUs (e.g. RTX 40-series non-SUPER Ti variants, RX 6000-series, "
    "older generations) are catalogue gaps by design, not evaluated defects.",
    "Exact-catalogue-product identification requires a clean, dash-shaped MPN token in the "
    "title matching the catalogue's stored identifier exactly; canonical-title-only mentions "
    "correctly top out at MODEL/VARIANT identification level.",
    "Misleading-similarity non-GPU merchandise (mouse pads, t-shirts, keychains, stickers "
    "referencing a GPU model name) is not yet reliably distinguished from an actual GPU "
    "listing at the product-type level - see the downstream comparability recommendation for "
    "residual risk detail.",
    "The classifier/PUE differential and candidate-recall metrics are measured against a "
    "hand-authored benchmark, not live marketplace traffic.",
    "Evidence precision is always reported unavailable: this benchmark has only sparse "
    "negative (forbidden_evidence_types) evidence labels, never a complete allowed/expected "
    "evidence-type enumeration per case, so a genuine precision claim cannot be computed. See "
    "forbidden_evidence_violation_rate for the rate the existing labels actually support.",
    "Comparability gold labels are hand-adjudicated per case-group from real-world listing "
    "meaning (see scripts/gen_pue_benchmark_dataset.py); cases without a confident, "
    "independent real-world judgment are deliberately left unlabelled and excluded from "
    "comparability_accuracy rather than guessed.",
    "Classifier/PUE comparison is only produced for cases with an explicit search_query "
    "annotation (a buyer search-intent context, never derived from the listing's own title); "
    "cases without one are excluded from every classifier/differential metric.",
)


def main() -> int:
    manifest_path = RELEASES_DIR / f"{RELEASE_ID}.json"
    report_json_path = RELEASES_DIR / f"{RELEASE_ID}_benchmark_report.json"
    report_md_path = RELEASES_DIR / f"{RELEASE_ID}_benchmark_report.md"

    try:
        artifacts = generate_release_artifacts(
            release_id=RELEASE_ID,
            manifest_path=manifest_path,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            known_limitations=KNOWN_LIMITATIONS,
        )
    except PueValidationError as exc:
        print(f"error: {exc}")
        return 1

    print(f"release gate: {'PASS' if artifacts.report.gate.passed else 'FAIL'}")
    print(f"wrote {manifest_path}")
    print(f"wrote {report_json_path}")
    print(f"wrote {report_md_path}")
    return 0 if artifacts.report.gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
