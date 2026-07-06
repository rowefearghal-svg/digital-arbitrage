"""Command-line interface for the arbitrage pipeline.

Exposes ``arb scan "<query>"`` with filtering, sorting, and multiple output
formats (``table``, ``json``, ``csv``, ``markdown``). Output is built from
:class:`ArbitragePipeline` results; no scraping or external calls (mock
providers only).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import traceback
from collections.abc import Callable, Sequence
from dataclasses import replace

from ..opportunity import Recommendation
from .config_file import load_pipeline_config
from .models import PipelineItemResult, PipelineResult
from .pipeline import ArbitragePipeline, PipelineConfig, recommendation_rank

# Columns shown in the fixed-width table and markdown output.
_COLUMNS: tuple[tuple[str, str], ...] = (
    ("recommendation", "RECOMMENDATION"),
    ("recommendation_score", "SCORE"),
    ("title", "TITLE"),
    ("provider", "PROVIDER"),
    ("asking_price", "ASKING"),
    ("estimated_market_price", "MARKET"),
    ("net_profit", "NET"),
    ("roi_percentage", "ROI%"),
    ("confidence_score", "CONF"),
)

# Full column set for CSV export (one row per opportunity).
_CSV_COLUMNS: tuple[str, ...] = (
    "recommendation",
    "recommendation_score",
    "title",
    "provider",
    "currency",
    "asking_price",
    "estimated_market_price",
    "gross_profit",
    "net_profit",
    "roi_percentage",
    "margin_percentage",
    "confidence_score",
    "risk_score",
    "comparable_count",
    "group_size",
    "reasons",
)

_SORTS: dict[str, Callable[[PipelineItemResult], tuple[float, str]]] = {
    "score": lambda i: (-i.score, i.group.canonical.listing_id),
    "roi": lambda i: (-_or_ninf(i.roi_percentage), i.group.canonical.listing_id),
    "net_profit": lambda i: (-_or_ninf(i.net_profit), i.group.canonical.listing_id),
    "confidence": lambda i: (-i.confidence_score, i.group.canonical.listing_id),
}


def _or_ninf(value: float | None) -> float:
    return value if value is not None else float("-inf")


def _cell(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


# --------------------------------------------------------------------------- #
# filtering + sorting
# --------------------------------------------------------------------------- #
def _filter_items(
    items: Sequence[PipelineItemResult], args: argparse.Namespace
) -> list[PipelineItemResult]:
    selected = list(items)
    if args.actionable_only:
        selected = [i for i in selected if i.opportunity.is_actionable]
    if args.min_recommendation is not None:
        floor = recommendation_rank(Recommendation(args.min_recommendation))
        selected = [i for i in selected if recommendation_rank(i.recommendation) >= floor]
    if args.min_roi is not None:
        selected = [
            i for i in selected if i.roi_percentage is not None and i.roi_percentage >= args.min_roi
        ]
    if args.min_net_profit is not None:
        selected = [
            i for i in selected if i.net_profit is not None and i.net_profit >= args.min_net_profit
        ]
    return selected


def _sort_items(items: Sequence[PipelineItemResult], sort: str | None) -> list[PipelineItemResult]:
    if sort is None or sort == "recommendation":
        # Already ranked by (recommendation, roi, confidence) in the pipeline.
        return list(items)
    return sorted(items, key=_SORTS[sort])


# --------------------------------------------------------------------------- #
# renderers
# --------------------------------------------------------------------------- #
def _header_lines(result: PipelineResult, shown: int) -> list[str]:
    return [
        f"query: {result.query!r}",
        f"scanned {result.total_listings_scanned} listings -> {result.total_groups} groups",
        f"showing {shown} of {len(result.items)} opportunities",
        "counts: " + ", ".join(f"{k}={v}" for k, v in result.counts_by_recommendation().items()),
    ]


def render_table(result: PipelineResult, items: Sequence[PipelineItemResult]) -> str:
    header = "\n".join(_header_lines(result, len(items)))
    if not items:
        return header + "\n(no opportunities)"

    rows = [[label for _, label in _COLUMNS]]
    for item in items:
        data = item.to_dict()
        rows.append([_cell(data[key]) for key, _ in _COLUMNS])

    widths = [max(len(row[col]) for row in rows) for col in range(len(_COLUMNS))]
    lines = ["  ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) for row in rows]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return header + "\n\n" + "\n".join(lines)


def render_json(result: PipelineResult, items: Sequence[PipelineItemResult]) -> str:
    payload = result.to_dict()
    payload["items"] = [item.to_dict() for item in items]
    payload["shown"] = len(items)
    return json.dumps(payload, indent=2)


def render_csv(result: PipelineResult, items: Sequence[PipelineItemResult]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    for item in items:
        data = item.to_dict()
        row = [";".join(data["reasons"]) if key == "reasons" else data[key] for key in _CSV_COLUMNS]
        writer.writerow(row)
    return buffer.getvalue().rstrip("\n")


def render_markdown(result: PipelineResult, items: Sequence[PipelineItemResult]) -> str:
    labels = [label for _, label in _COLUMNS]
    lines = [
        f"# Opportunities for {result.query!r}",
        "",
        f"- Scanned **{result.total_listings_scanned}** listings into "
        f"**{result.total_groups}** groups",
        f"- Showing **{len(items)}** of **{len(result.items)}** opportunities",
        "",
    ]
    if not items:
        lines.append("_No opportunities._")
        return "\n".join(lines)

    lines.append("| " + " | ".join(labels) + " |")
    lines.append("| " + " | ".join("---" for _ in labels) + " |")
    for item in items:
        data = item.to_dict()
        lines.append("| " + " | ".join(_cell(data[key]) for key, _ in _COLUMNS) + " |")
    return "\n".join(lines)


_RENDERERS: dict[str, Callable[[PipelineResult, Sequence[PipelineItemResult]], str]] = {
    "table": render_table,
    "json": render_json,
    "csv": render_csv,
    "markdown": render_markdown,
}


# --------------------------------------------------------------------------- #
# argument parsing + dispatch
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arb", description="Digital arbitrage analysis pipeline (mock providers)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan providers and score opportunities.")
    scan.add_argument("query", help="Product search query, e.g. 'rtx 4090'.")
    scan.add_argument(
        "-f",
        "--format",
        choices=tuple(_RENDERERS),
        default="table",
        help="Output format.",
    )
    scan.add_argument(
        "-s",
        "--sort",
        choices=("recommendation", "score", "roi", "net_profit", "confidence"),
        default="recommendation",
        help="Sort order (default: recommendation).",
    )
    scan.add_argument("-l", "--limit", type=int, default=None, help="Max results per provider.")
    scan.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to a TOML config file (see configs/default.toml).",
    )
    scan.add_argument(
        "--actionable-only",
        action="store_true",
        help="Only show BUY / STRONG_BUY opportunities.",
    )
    scan.add_argument(
        "--min-recommendation",
        choices=tuple(rec.value for rec in Recommendation),
        default=None,
        help="Only show opportunities at or above this recommendation.",
    )
    scan.add_argument(
        "--min-roi", type=float, default=None, help="Minimum ROI percentage (e.g. 15)."
    )
    scan.add_argument("--min-net-profit", type=float, default=None, help="Minimum net profit.")
    scan.add_argument("--debug", action="store_true", help="Show a full traceback on error.")
    return parser


def _run_scan(args: argparse.Namespace) -> int:
    config = load_pipeline_config(args.config) if args.config else PipelineConfig()
    if args.limit is not None:
        config = replace(config, scan_limit=args.limit)

    result = ArbitragePipeline(config).analyze(args.query)
    items = _sort_items(_filter_items(result.items, args), args.sort)
    print(_RENDERERS[args.format](result, items))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "scan":
        parser.print_help()
        return 1
    try:
        return _run_scan(args)
    except Exception as error:  # noqa: BLE001 - top-level CLI boundary
        if args.debug:
            traceback.print_exc()
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
