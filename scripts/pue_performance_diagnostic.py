"""Run the full-scale PUE performance/memory diagnostic (Sprint 3, brief
section 13). Excludes provider acquisition and persistence entirely -
title-only, in-process, deterministic synthetic listings.

Usage (from the repository root):

    python scripts/pue_performance_diagnostic.py --count 10000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from digital_arbitrage.pue.performance import (  # noqa: E402
    render_diagnostic_text,
    run_performance_diagnostic,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--count", type=int, default=10_000, help="Number of synthetic listings to process."
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON instead of text."
    )
    args = parser.parse_args()

    result = run_performance_diagnostic(args.count)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(render_diagnostic_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
