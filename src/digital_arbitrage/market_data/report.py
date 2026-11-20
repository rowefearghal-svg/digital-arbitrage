"""Completeness / acquisition report for a collection run.

Answers, per run and per (provider, query, endpoint): how much was requested,
fetched, stored and rejected; which expected fields were missing and *why*;
where coverage is a sample rather than the whole market; what went wrong; and
how much request budget was consumed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from .expected_fields import EXPECTED_FIELDS
from .models import SourceKind, TaskStatus
from .store import MarketDataStore


def _source_kind_for_endpoint(provider: str, endpoint: str) -> str | None:
    if endpoint in ("item_summary/search", "catalog/search"):
        return SourceKind.SEARCH.value
    if endpoint == "item/detail":
        return SourceKind.DETAIL.value
    if endpoint == "market-data":
        return SourceKind.MARKET_DATA.value
    if endpoint == "variants":
        return SourceKind.VARIANTS.value
    return None


def build_report(
    store: MarketDataStore, run_id: str, *, stale_after_hours: int = 48
) -> dict[str, Any]:
    """Assemble the completeness report for ``run_id``."""
    run = store.run_row(run_id) or {}
    tasks = store.tasks_for_run(run_id)

    # --- per (provider, query, endpoint) roll-up ---------------------------
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for task in tasks:
        key = (task["provider"], task["query_id"], task["endpoint"])
        bucket = groups.setdefault(
            key,
            {
                "provider": task["provider"],
                "query_id": task["query_id"],
                "endpoint": endpoint_label(task["endpoint"]),
                "pages": 0,
                "tasks_done": 0,
                "tasks_failed": 0,
                "items_returned": 0,
                "items_stored": 0,
                "items_rejected": 0,
                "reported_total": None,
                "last_has_more": None,
                "errors": [],
            },
        )
        bucket["pages"] += 1
        bucket["tasks_done"] += int(task["status"] == TaskStatus.DONE.value)
        bucket["tasks_failed"] += int(task["status"] == TaskStatus.FAILED.value)
        bucket["items_returned"] += task["items_returned"]
        bucket["items_stored"] += task["items_stored"]
        bucket["items_rejected"] += task["items_rejected"]
        if task["reported_total"] is not None:
            bucket["reported_total"] = task["reported_total"]
        bucket["last_has_more"] = task["has_more"]
        if task["error_category"]:
            bucket["errors"].append(
                {
                    "page": task["page_number"],
                    "error": task["error_category"],
                    "http_status": task["http_status"],
                }
            )

    # --- per (provider, query) coverage -------------------------------------
    coverage: dict[tuple[str, str], dict[str, Any]] = {}
    for (provider, query_id, endpoint), bucket in groups.items():
        if endpoint not in ("item_summary/search", "catalog/search"):
            continue
        cov = coverage.setdefault(
            (provider, query_id),
            {
                "provider": provider,
                "query_id": query_id,
                "query_text": "",
                "reported_total": None,
                "items_fetched": 0,
                "items_stored": 0,
                "pages_fetched": 0,
                "coverage": "COMPLETE",
            },
        )
        cov["reported_total"] = bucket["reported_total"]
        cov["items_fetched"] += bucket["items_returned"]
        cov["items_stored"] += bucket["items_stored"]
        cov["pages_fetched"] += bucket["pages"]
        if bucket["tasks_failed"]:
            cov["coverage"] = "FAILED"
        elif bucket["last_has_more"]:
            cov["coverage"] = "SAMPLE"  # provider still had more; caps stopped us
    for task in tasks:
        cov_key = (task["provider"], task["query_id"])
        if cov_key in coverage:
            coverage[cov_key]["query_text"] = task["query_text"]

    # --- missing fields ------------------------------------------------------
    missing_fields: dict[str, Any] = {}
    counts_cache: dict[tuple[str, str], dict[str, Any]] = {}
    for provider, endpoints in EXPECTED_FIELDS.items():
        for source_kind, fields in endpoints.items():
            presence = counts_cache.get((provider, source_kind))
            if presence is None:
                presence = store.field_presence(run_id, source_kind, provider)
                counts_cache[(provider, source_kind)] = presence
            total = presence["total"]
            if total == 0:
                continue
            counts: dict[str, int] = presence["counts"]
            entry: dict[str, Any] = {}
            for field_name, classification in fields.items():
                n = counts.get(field_name, 0)
                if classification == "not_in_api":
                    entry[field_name] = {"status": "not_in_api"}
                elif classification == "restricted":
                    entry[field_name] = {
                        "status": "restricted" if n == 0 else "returned",
                        "rate": round(n / total, 3),
                    }
                elif n < total:
                    entry[field_name] = {
                        "status": "missing",
                        "classification": classification,
                        "rate": round(n / total, 3),
                    }
                else:
                    entry[field_name] = {"status": "returned", "rate": 1.0}
            missing_fields.setdefault(provider, {})[source_kind] = {
                "records": total,
                "fields": entry,
            }

    # --- errors ---------------------------------------------------------------
    errors = [
        {
            "provider": t["provider"],
            "query_id": t["query_id"],
            "endpoint": t["endpoint"],
            "page": t["page_number"],
            "error": t["error_category"],
            "http_status": t["http_status"],
            "attempts": t["attempts"],
        }
        for t in tasks
        if t["status"] == TaskStatus.FAILED.value
    ]

    # --- enrichment coverage ---------------------------------------------------
    enrichment = {
        "detail": _endpoint_counts(tasks, "item/detail"),
        "market_data": _endpoint_counts(tasks, "market-data"),
        "variants": _endpoint_counts(tasks, "variants"),
    }

    # --- request usage ----------------------------------------------------------
    day = (run.get("started_at") or datetime.now(UTC).isoformat())[:10]
    requests_used = {
        provider: store.requests_used(provider, day=day)
        for provider in {t["provider"] for t in tasks} or {"ebay_browse", "stockx"}
    }

    # --- staleness --------------------------------------------------------------
    stale_cutoff = (
        (datetime.now(UTC) - timedelta(hours=stale_after_hours)).replace(microsecond=0).isoformat()
    )
    stale = {
        provider: len(store.stale_entities(provider=provider, stale_after=stale_cutoff))
        for provider in {t["provider"] for t in tasks}
    }

    # --- raw payloads -------------------------------------------------------------
    payloads = store._conn.execute(  # noqa: SLF001 - internal report query
        "SELECT COUNT(*) AS captures, COUNT(DISTINCT payload_id) AS bodies "
        "FROM payload_captures WHERE collection_run_id = ?",
        (run_id,),
    ).fetchone()

    return {
        "run": run,
        "counters": json.loads(run.get("counters_json") or "{}"),
        "groups": list(groups.values()),
        "coverage": list(coverage.values()),
        "missing_fields": missing_fields,
        "enrichment": enrichment,
        "errors": errors,
        "requests_used_today": requests_used,
        "stale_entities": stale,
        "raw_payloads": {
            "captures": payloads["captures"] if payloads else 0,
            "distinct_bodies": payloads["bodies"] if payloads else 0,
        },
        "states": _state_counts(store, run_id),
    }


def _endpoint_counts(tasks: list[dict[str, Any]], endpoint: str) -> dict[str, int]:
    selected = [t for t in tasks if t["endpoint"] == endpoint]
    return {
        "attempted": len(selected),
        "done": sum(1 for t in selected if t["status"] == TaskStatus.DONE.value),
        "failed": sum(1 for t in selected if t["status"] == TaskStatus.FAILED.value),
        "items_stored": sum(t["items_stored"] for t in selected),
    }


def _state_counts(store: MarketDataStore, run_id: str) -> dict[str, int]:
    rows = store._conn.execute(  # noqa: SLF001
        "SELECT state, COUNT(*) AS n FROM observations WHERE collection_run_id = ? "
        "GROUP BY state",
        (run_id,),
    ).fetchall()
    return {r["state"]: r["n"] for r in rows}


def endpoint_label(endpoint: str) -> str:
    return endpoint


def render_markdown(report: dict[str, Any]) -> str:
    """Human-readable rendering of :func:`build_report` output."""
    run = report.get("run") or {}
    counters = report.get("counters") or {}
    lines = [
        f"# Collection report {run.get('run_id', '?')}",
        "",
        f"- manifest: {run.get('manifest_id')} | status: {run.get('status')} "
        f"| started: {run.get('started_at')}",
        f"- fetched {counters.get('fetched', 0)} | stored "
        f"{counters.get('stored', 0)} | rejected {counters.get('rejected', 0)} "
        f"| reported market total {counters.get('reported_market_total')}",
        f"- entities {counters.get('entities', 0)} | observations "
        f"{counters.get('observations', 0)}",
        f"- requests used today: {json.dumps(report.get('requests_used_today', {}))}",
        "",
        "## Coverage",
        "",
        "| provider | query | coverage | reported_total | fetched | stored | pages |",
        "|---|---|---|---|---|---|---|",
    ]
    for cov in report.get("coverage", []):
        lines.append(
            f"| {cov['provider']} | {cov['query_id']} | {cov['coverage']} "
            f"| {cov['reported_total']} | {cov['items_fetched']} "
            f"| {cov['items_stored']} | {cov['pages_fetched']} |"
        )
    lines += ["", "## Missing / restricted / unavailable fields", ""]
    for provider, kinds in (report.get("missing_fields") or {}).items():
        for kind, detail in kinds.items():
            lines.append(f"### {provider} / {kind} ({detail['records']} records)")
            for fname, info in detail["fields"].items():
                if info["status"] != "returned":
                    lines.append(
                        f"- `{fname}`: {info['status']}"
                        + (f" ({info.get('classification')})" if info.get("classification") else "")
                        + (f" rate={info['rate']}" if "rate" in info else "")
                    )
            lines.append("")
    if report.get("errors"):
        lines += ["## Errors", ""]
        for err in report["errors"]:
            lines.append(
                f"- {err['provider']}/{err['query_id']}/{err['endpoint']} "
                f"page {err['page']}: {err['error']} (http {err['http_status']}, "
                f"{err['attempts']} attempts)"
            )
        lines.append("")
    enrich = report.get("enrichment", {})
    lines += [
        "## Enrichment",
        "",
        f"- detail: {enrich.get('detail')}",
        f"- market_data: {enrich.get('market_data')}",
        f"- variants: {enrich.get('variants')}",
        "",
        "## Observation states",
        "",
        json.dumps(report.get("states", {})),
    ]
    return "\n".join(lines)
