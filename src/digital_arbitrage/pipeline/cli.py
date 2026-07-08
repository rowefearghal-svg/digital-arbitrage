"""Command-line interface for the arbitrage pipeline.

Exposes three commands, all built from :class:`ArbitragePipeline` results with no
scraping or external calls (mock providers only):

* ``arb scan "<query>"`` - run the pipeline with filtering, sorting, and multiple
  output formats (``table``, ``json``, ``csv``, ``markdown``); ``--save`` also
  persists the run to a SQLite history database.
* ``arb history`` - list previously saved scan runs.
* ``arb show <run_id>`` - view the opportunities stored for a previous run.
* ``arb compare <old_run_id> <new_run_id>`` - diff two saved runs.
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
from pathlib import Path

from ..comparison import OpportunityDelta, RunComparison, compare_runs
from ..opportunity import Recommendation
from ..persistence import ResultStore, StoredOpportunity, StoredRun
from ..product_scanner import ScannerConfig
from .config_file import load_pipeline_config
from .models import PipelineItemResult, PipelineResult
from .pipeline import ArbitragePipeline, PipelineConfig, recommendation_rank

#: Default location for the scan-history database (override with --db).
DEFAULT_DB_PATH = Path.home() / ".digital_arbitrage" / "history.db"

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
# history / show renderers
# --------------------------------------------------------------------------- #
def _fixed_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    grid = [list(headers), *[list(row) for row in rows]]
    widths = [max(len(row[col]) for row in grid) for col in range(len(headers))]
    lines = ["  ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) for row in grid]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(lines)


_RUN_COLUMNS: tuple[tuple[str, str], ...] = (
    ("run_id", "RUN"),
    ("created_at", "CREATED"),
    ("query", "QUERY"),
    ("total_listings_scanned", "SCANNED"),
    ("total_groups", "GROUPS"),
    ("total_opportunities", "OPPS"),
    ("config_summary", "CONFIG"),
)

_SHOW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("rank", "RANK"),
    ("recommendation", "RECOMMENDATION"),
    ("recommendation_score", "SCORE"),
    ("title", "TITLE"),
    ("provider", "PROVIDER"),
    ("asking_price", "ASKING"),
    ("estimated_market_price", "MARKET"),
    ("net_profit", "NET"),
    ("roi_percentage", "ROI%"),
    ("confidence_score", "CONF"),
    ("risk_score", "RISK"),
)


def render_runs(runs: Sequence[StoredRun], fmt: str) -> str:
    if fmt == "json":
        return json.dumps([run.to_dict() for run in runs], indent=2)
    if not runs:
        return "(no saved runs)"
    rows = [[_cell(run.to_dict()[key]) for key, _ in _RUN_COLUMNS] for run in runs]
    return _fixed_table([label for _, label in _RUN_COLUMNS], rows)


def render_stored_run(run: StoredRun, opportunities: Sequence[StoredOpportunity], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(
            {"run": run.to_dict(), "opportunities": [o.to_dict() for o in opportunities]},
            indent=2,
        )
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        keys = [key for key, _ in _SHOW_COLUMNS]
        writer.writerow(keys)
        for opp in opportunities:
            data = opp.to_dict()
            writer.writerow([data[key] for key in keys])
        return buffer.getvalue().rstrip("\n")

    header = (
        f"run {run.run_id}: {run.query!r} @ {run.created_at}\n"
        f"scanned {run.total_listings_scanned} listings -> {run.total_groups} groups, "
        f"{run.total_opportunities} opportunities ({run.config_summary})"
    )
    if not opportunities:
        return header + "\n(no opportunities)"
    rows = [[_cell(opp.to_dict()[key]) for key, _ in _SHOW_COLUMNS] for opp in opportunities]
    table = _fixed_table([label for _, label in _SHOW_COLUMNS], rows)
    return header + "\n\n" + table


# --------------------------------------------------------------------------- #
# compare renderer
# --------------------------------------------------------------------------- #
# Metric columns shown as new-minus-old deltas in the compare output.
_COMPARE_METRICS: tuple[tuple[str, str], ...] = (
    ("recommendation_score", "SCORE"),
    ("roi_percentage", "ROI%"),
    ("net_profit", "NET"),
    ("confidence_score", "CONF"),
    ("risk_score", "RISK"),
)


def _delta_cell(delta: OpportunityDelta, metric: str) -> str:
    md = delta.metric(metric)
    if md is None or md.delta == 0:
        return "="
    return f"{md.delta:+.2f}"


def _compare_header(comparison: RunComparison) -> list[str]:
    old, new = comparison.old_run, comparison.new_run
    counts = comparison.counts_by_category()
    return [
        f"compare run {old.run_id} ({old.created_at}) -> run {new.run_id} ({new.created_at})",
        f"old query: {old.query!r} | new query: {new.query!r}",
        "counts: " + ", ".join(f"{k}={v}" for k, v in counts.items()),
        "metric columns show new-minus-old delta ('=' means no change)",
    ]


def render_comparison_table(comparison: RunComparison) -> str:
    header = "\n".join(_compare_header(comparison))
    if not comparison.deltas:
        return header + "\n(no opportunities in either run)"
    headers = ["CATEGORY", "PROVIDER", "TITLE", *[label for _, label in _COMPARE_METRICS]]
    rows = [
        [
            delta.category.value,
            delta.provider,
            delta.title,
            *[_delta_cell(delta, metric) for metric, _ in _COMPARE_METRICS],
        ]
        for delta in comparison.deltas
    ]
    return header + "\n\n" + _fixed_table(headers, rows)


def render_comparison_json(comparison: RunComparison) -> str:
    return json.dumps(comparison.to_dict(), indent=2)


def render_comparison_csv(comparison: RunComparison) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    metric_cols = [
        f"{metric}_{suffix}" for metric, _ in _COMPARE_METRICS for suffix in ("old", "new", "delta")
    ]
    writer.writerow(["category", "key", "provider", "title", "reason", *metric_cols])
    for delta in comparison.deltas:
        values: list[object] = [
            delta.category.value,
            delta.key,
            delta.provider,
            delta.title,
            delta.reason,
        ]
        for metric, _ in _COMPARE_METRICS:
            md = delta.metric(metric)
            values.extend((None, None, None) if md is None else (md.old, md.new, md.delta))
        writer.writerow(values)
    return buffer.getvalue().rstrip("\n")


def render_comparison_markdown(comparison: RunComparison) -> str:
    old, new = comparison.old_run, comparison.new_run
    labels = ["CATEGORY", "PROVIDER", "TITLE", *[label for _, label in _COMPARE_METRICS]]
    lines = [
        f"# Comparison: run {old.run_id} -> run {new.run_id}",
        "",
        *[f"- {line}" for line in _compare_header(comparison)[1:]],
        "",
    ]
    if not comparison.deltas:
        lines.append("_No opportunities in either run._")
        return "\n".join(lines)
    lines.append("| " + " | ".join(labels) + " |")
    lines.append("| " + " | ".join("---" for _ in labels) + " |")
    for delta in comparison.deltas:
        cells = [
            delta.category.value,
            delta.provider,
            delta.title,
            *[_delta_cell(delta, metric) for metric, _ in _COMPARE_METRICS],
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


_COMPARE_RENDERERS: dict[str, Callable[[RunComparison], str]] = {
    "table": render_comparison_table,
    "json": render_comparison_json,
    "csv": render_comparison_csv,
    "markdown": render_comparison_markdown,
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
        "-p",
        "--provider",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Provider to scan (repeatable); overrides the configured provider "
            "list. Live providers (e.g. ebay_browse) read credentials from the "
            "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET environment variables."
        ),
    )
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
    scan.add_argument(
        "--save",
        action="store_true",
        help="Persist the full scan result to the history database.",
    )
    scan.add_argument(
        "--db",
        default=None,
        help=f"History database path (default: {DEFAULT_DB_PATH}).",
    )
    scan.add_argument("--debug", action="store_true", help="Show a full traceback on error.")

    history = subparsers.add_parser("history", help="List previously saved scan runs.")
    history.add_argument(
        "-f", "--format", choices=("table", "json"), default="table", help="Output format."
    )
    history.add_argument(
        "-l", "--limit", type=int, default=None, help="Show only the N newest runs."
    )
    history.add_argument(
        "--db", default=None, help=f"History database path (default: {DEFAULT_DB_PATH})."
    )
    history.add_argument("--debug", action="store_true", help="Show a full traceback on error.")

    show = subparsers.add_parser("show", help="Show opportunities from a saved run.")
    show.add_argument("run_id", type=int, help="Run id (see `arb history`).")
    show.add_argument(
        "-f",
        "--format",
        choices=("table", "json", "csv"),
        default="table",
        help="Output format.",
    )
    show.add_argument(
        "--db", default=None, help=f"History database path (default: {DEFAULT_DB_PATH})."
    )
    show.add_argument("--debug", action="store_true", help="Show a full traceback on error.")

    compare = subparsers.add_parser("compare", help="Diff two saved runs.")
    compare.add_argument("old_run_id", type=int, help="Older run id.")
    compare.add_argument("new_run_id", type=int, help="Newer run id.")
    compare.add_argument(
        "-f",
        "--format",
        choices=tuple(_COMPARE_RENDERERS),
        default="table",
        help="Output format.",
    )
    compare.add_argument(
        "--db", default=None, help=f"History database path (default: {DEFAULT_DB_PATH})."
    )
    compare.add_argument("--debug", action="store_true", help="Show a full traceback on error.")
    return parser


def _config_summary(args: argparse.Namespace) -> str:
    parts = [f"config={args.config}" if args.config else "config=defaults"]
    if args.limit is not None:
        parts.append(f"limit={args.limit}")
    if args.provider:
        parts.append(f"providers={'+'.join(args.provider)}")
    return ", ".join(parts)


def _apply_provider_override(config: PipelineConfig, providers: list[str]) -> PipelineConfig:
    """Override the scanner's provider list with the CLI ``--provider`` values.

    Other scanner settings (and any ``[providers.<name>]`` live config) are
    preserved; only the set of providers to query is replaced.
    """
    base = config.scanner_config or ScannerConfig()
    return replace(config, scanner_config=replace(base, providers=list(providers)))


def _run_scan(args: argparse.Namespace) -> int:
    config = load_pipeline_config(args.config) if args.config else PipelineConfig()
    if args.limit is not None:
        config = replace(config, scan_limit=args.limit)
    if args.provider:
        config = _apply_provider_override(config, args.provider)

    result = ArbitragePipeline(config).analyze(args.query)
    items = _sort_items(_filter_items(result.items, args), args.sort)
    print(_RENDERERS[args.format](result, items))

    if args.save:
        db_path = args.db if args.db is not None else DEFAULT_DB_PATH
        with ResultStore(db_path) as store:
            run_id = store.save_run(result, config_summary=_config_summary(args))
        print(f"saved run {run_id} to {db_path}", file=sys.stderr)
    return 0


def _run_history(args: argparse.Namespace) -> int:
    db_path = args.db if args.db is not None else DEFAULT_DB_PATH
    with ResultStore(db_path) as store:
        runs = store.list_runs(limit=args.limit)
    print(render_runs(runs, args.format))
    return 0


def _run_show(args: argparse.Namespace) -> int:
    db_path = args.db if args.db is not None else DEFAULT_DB_PATH
    with ResultStore(db_path) as store:
        run = store.get_run(args.run_id)
        if run is None:
            print(f"error: run {args.run_id} not found", file=sys.stderr)
            return 1
        opportunities = store.list_opportunities(args.run_id)
    print(render_stored_run(run, opportunities, args.format))
    return 0


def _run_compare(args: argparse.Namespace) -> int:
    db_path = args.db if args.db is not None else DEFAULT_DB_PATH
    with ResultStore(db_path) as store:
        old_run = store.get_run(args.old_run_id)
        new_run = store.get_run(args.new_run_id)
        for run_id, run in ((args.old_run_id, old_run), (args.new_run_id, new_run)):
            if run is None:
                print(f"error: run {run_id} not found", file=sys.stderr)
                return 1
        assert old_run is not None and new_run is not None
        old_opps = store.list_opportunities(args.old_run_id)
        new_opps = store.list_opportunities(args.new_run_id)
    comparison = compare_runs(old_run, old_opps, new_run, new_opps)
    print(_COMPARE_RENDERERS[args.format](comparison))
    return 0


_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "scan": _run_scan,
    "history": _run_history,
    "show": _run_show,
    "compare": _run_compare,
}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = _COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    try:
        return handler(args)
    except Exception as error:  # noqa: BLE001 - top-level CLI boundary
        if args.debug:
            traceback.print_exc()
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
