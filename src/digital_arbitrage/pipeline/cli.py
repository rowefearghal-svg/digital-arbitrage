"""Command-line interface for the arbitrage pipeline.

Exposes ``arb scan "<query>"`` with ``--format table|json``. Output is built
from :class:`ArbitragePipeline` results; no scraping or external calls (mock
providers only).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace

from .config_file import ConfigError, load_pipeline_config
from .models import PipelineResult
from .pipeline import ArbitragePipeline, PipelineConfig

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("recommendation", "RECOMMENDATION"),
    ("title", "TITLE"),
    ("provider", "PROVIDER"),
    ("asking_price", "ASKING"),
    ("estimated_market_price", "MARKET"),
    ("net_profit", "NET"),
    ("roi_percentage", "ROI%"),
    ("confidence_score", "CONF"),
)


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_table(result: PipelineResult) -> str:
    """Render a result as a fixed-width text table."""
    header = "\n".join(
        [
            f"query: {result.query!r}",
            f"scanned {result.total_listings_scanned} listings -> {result.total_groups} groups",
            "counts: "
            + ", ".join(f"{k}={v}" for k, v in result.counts_by_recommendation().items()),
        ]
    )
    if not result.items:
        return header + "\n(no opportunities)"

    rows = [[label for _, label in _COLUMNS]]
    for item in result.items:
        data = item.to_dict()
        rows.append([_cell(data[key]) for key, _ in _COLUMNS])

    widths = [max(len(row[col]) for row in rows) for col in range(len(_COLUMNS))]
    lines = ["  ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) for row in rows]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return header + "\n\n" + "\n".join(lines)


def render_json(result: PipelineResult) -> str:
    """Render a result as pretty-printed JSON."""
    return json.dumps(result.to_dict(), indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arb", description="Digital arbitrage analysis pipeline (mock providers)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan providers and score opportunities.")
    scan.add_argument("query", help="Product search query, e.g. 'rtx 4090'.")
    scan.add_argument(
        "-f", "--format", choices=("table", "json"), default="table", help="Output format."
    )
    scan.add_argument("-l", "--limit", type=int, default=None, help="Max results per provider.")
    scan.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to a TOML config file (see configs/default.toml).",
    )
    return parser


def _run_scan(args: argparse.Namespace) -> int:
    try:
        config = load_pipeline_config(args.config) if args.config else PipelineConfig()
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.limit is not None:
        config = replace(config, scan_limit=args.limit)

    try:
        result = ArbitragePipeline(config).analyze(args.query)
    except Exception as error:  # noqa: BLE001 - surface any failure cleanly to the CLI user
        print(f"error: {error}", file=sys.stderr)
        return 1

    output = render_json(result) if args.format == "json" else render_table(result)
    print(output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return _run_scan(args)
    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
