"""Lightweight SQLite persistence for scan history.

Saves each :class:`PipelineResult` as a run plus its ranked opportunity
snapshots, and reads them back for review. Standard-library ``sqlite3`` only -
no external dependencies, network calls, or ORM (ADR-013).

Quick start::

    from digital_arbitrage.persistence import ResultStore

    with ResultStore("history.db") as store:
        run_id = store.save_run(result)
        for run in store.list_runs():
            print(run.run_id, run.query, run.total_opportunities)
"""

from __future__ import annotations

from .models import StoredOpportunity, StoredRun
from .storage import SCHEMA_VERSION, ResultStore

__all__ = [
    "SCHEMA_VERSION",
    "ResultStore",
    "StoredOpportunity",
    "StoredRun",
]
