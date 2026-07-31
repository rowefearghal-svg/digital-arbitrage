"""Generate the pue-0.1.0 release manifest + its bound benchmark report
(Sprint 3, brief section 11). Run from the repository root:

    python scripts/gen_pue_release_v0_1_0.py

Regenerate only after a deliberate, reviewed release-affecting change -
review the diff carefully, and never overwrite a previously published
release manifest (this script itself refuses to, via
``save_release_manifest``).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from digital_arbitrage.pue.benchmark import (  # noqa: E402
    DEFAULT_BENCHMARK_PATH,
    dataset_file_hash,
    load_benchmark_dataset,
)
from digital_arbitrage.pue.benchmark_report import (  # noqa: E402
    build_benchmark_report,
    render_report_json,
    render_report_markdown,
)
from digital_arbitrage.pue.benchmark_runner import run_benchmark  # noqa: E402
from digital_arbitrage.pue.catalogue import DEFAULT_CATALOGUE_PATH  # noqa: E402
from digital_arbitrage.pue.comparison import COMPARISON_SCHEMA_VERSION  # noqa: E402
from digital_arbitrage.pue.release import (  # noqa: E402
    build_release_manifest,
    save_release_manifest,
)
from digital_arbitrage.pue.version import CAPABILITY_VERSION  # noqa: E402

RELEASES_DIR = ROOT / "data" / "pue" / "releases"


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    dataset = load_benchmark_dataset(DEFAULT_BENCHMARK_PATH)
    dataset_hash = dataset_file_hash(DEFAULT_BENCHMARK_PATH)
    run = run_benchmark(dataset, run_classifier=True)

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
        mandatory_acceptance_pass=True,
        replay_equivalent=True,
        run_differential=True,
        generated_at=datetime.now(UTC).isoformat(),
    )

    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    report_json_path = RELEASES_DIR / "pue_v0.1.0_benchmark_report.json"
    report_md_path = RELEASES_DIR / "pue_v0.1.0_benchmark_report.md"
    report_json_path.write_text(render_report_json(report), encoding="utf-8")
    report_md_path.write_text(render_report_markdown(report), encoding="utf-8")

    manifest = build_release_manifest(
        release_id="pue-v0.1.0",
        capability_version=CAPABILITY_VERSION,
        policy_version=run.context.policy_version,
        knowledge_version=run.context.knowledge_version,
        schema_version=run.context.schema_version,
        comparison_schema_version=COMPARISON_SCHEMA_VERSION,
        benchmark_dataset_id=dataset.dataset_id,
        benchmark_dataset_version=dataset.benchmark_version,
        benchmark_dataset_hash=dataset_hash,
        catalogue_file_hash=_sha256_file(Path(DEFAULT_CATALOGUE_PATH)),
        release_benchmark_report_path=str(report_json_path.relative_to(ROOT)).replace("\\", "/"),
        release_gate_passed=report.gate.passed,
        release_date=datetime.now(UTC).date().isoformat(),
        known_limitations=(
            "Seed catalogue (data/pue/catalogues/gpu_seed_v0.1.json) covers ~36 hand-curated "
            "products; many real GPU SKUs (e.g. RTX 40-series non-SUPER Ti variants, RX 6000-"
            "series, older generations) are catalogue gaps by design, not evaluated defects.",
            "Exact-catalogue-product identification requires a clean, dash-shaped MPN token "
            "in the title matching the catalogue's stored identifier exactly; canonical-title-"
            "only mentions correctly top out at MODEL/VARIANT identification level.",
            "Misleading-similarity non-GPU merchandise (mouse pads, t-shirts, keychains, "
            "stickers referencing a GPU model name) is not yet reliably distinguished from an "
            "actual GPU listing at the product-type level - see the downstream comparability "
            "recommendation for residual risk detail.",
            "The classifier/PUE differential and candidate-recall metrics are measured "
            "against a 118-case hand-authored benchmark, not live marketplace traffic.",
        ),
    )
    manifest_path = RELEASES_DIR / "pue_v0.1.0.json"
    save_release_manifest(manifest, manifest_path)

    print(f"release gate: {'PASS' if report.gate.passed else 'FAIL'}")
    print(f"wrote {manifest_path}")
    print(f"wrote {report_json_path}")
    print(f"wrote {report_md_path}")
    return 0 if report.gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
