"""SQLite persistence for scan runs and their opportunity snapshots.

``ResultStore`` writes a :class:`PipelineResult` into two tables - ``runs``
(one row per scan) and ``opportunities`` (one row per ranked item) - and reads
them back as :class:`StoredRun` / :class:`StoredOpportunity` models. It uses only
the standard-library :mod:`sqlite3`; there are no external dependencies, network
calls, or ORM. The schema is deliberately small and additive, with
``PRAGMA user_version`` tracking it for future migrations.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from ..pipeline.models import PipelineResult
from .models import StoredOpportunity, StoredRun

#: Current on-disk schema version (bumped when the schema changes).
SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL,
    config_summary TEXT NOT NULL,
    total_listings_scanned INTEGER NOT NULL,
    total_groups INTEGER NOT NULL,
    total_opportunities INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    provider TEXT NOT NULL,
    currency TEXT NOT NULL,
    asking_price REAL,
    estimated_market_price REAL,
    roi_percentage REAL,
    net_profit REAL,
    confidence_score REAL NOT NULL,
    risk_score REAL NOT NULL,
    recommendation_score REAL NOT NULL,
    recommendation TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opportunities_run ON opportunities(run_id);
"""


def _utc_now() -> str:
    """Current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ResultStore:
    """Store and retrieve scan runs in a SQLite database.

    Usable as a context manager::

        with ResultStore("history.db") as store:
            run_id = store.save_run(result)
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            parent = Path(self.path).parent
            if parent and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    # -- lifecycle --------------------------------------------------------- #
    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def __enter__(self) -> ResultStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- writes ------------------------------------------------------------ #
    def save_run(
        self,
        result: PipelineResult,
        *,
        config_summary: str = "defaults",
        created_at: str | None = None,
    ) -> int:
        """Persist a :class:`PipelineResult` and return its new run id."""
        timestamp = created_at if created_at is not None else _utc_now()
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO runs (query, created_at, config_summary, "
                "total_listings_scanned, total_groups, total_opportunities) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    result.query,
                    timestamp,
                    config_summary,
                    result.total_listings_scanned,
                    result.total_groups,
                    len(result.items),
                ),
            )
            run_id = int(cursor.lastrowid or 0)
            self._conn.executemany(
                "INSERT INTO opportunities (run_id, rank, title, provider, currency, "
                "asking_price, estimated_market_price, roi_percentage, net_profit, "
                "confidence_score, risk_score, recommendation_score, recommendation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        rank,
                        item.title,
                        item.provider,
                        item.opportunity.currency,
                        item.opportunity.asking_price,
                        item.opportunity.estimated_market_price,
                        item.roi_percentage,
                        item.net_profit,
                        item.confidence_score,
                        item.risk_score,
                        item.score,
                        item.recommendation.value,
                    )
                    for rank, item in enumerate(result.items, start=1)
                ],
            )
        return run_id

    # -- reads ------------------------------------------------------------- #
    def list_runs(self, *, limit: int | None = None) -> list[StoredRun]:
        """Return stored runs, newest first (optionally capped by ``limit``)."""
        sql = "SELECT * FROM runs ORDER BY id DESC"
        params: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: int) -> StoredRun | None:
        """Return a single run summary, or ``None`` if it does not exist."""
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row) if row is not None else None

    def list_opportunities(self, run_id: int) -> list[StoredOpportunity]:
        """Return the opportunity snapshots for a run, in stored rank order."""
        rows = self._conn.execute(
            "SELECT * FROM opportunities WHERE run_id = ? ORDER BY rank ASC",
            (run_id,),
        ).fetchall()
        return [self._row_to_opportunity(row) for row in rows]

    # -- mapping ----------------------------------------------------------- #
    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> StoredRun:
        return StoredRun(
            run_id=row["id"],
            query=row["query"],
            created_at=row["created_at"],
            config_summary=row["config_summary"],
            total_listings_scanned=row["total_listings_scanned"],
            total_groups=row["total_groups"],
            total_opportunities=row["total_opportunities"],
        )

    @staticmethod
    def _row_to_opportunity(row: sqlite3.Row) -> StoredOpportunity:
        return StoredOpportunity(
            id=row["id"],
            run_id=row["run_id"],
            rank=row["rank"],
            title=row["title"],
            provider=row["provider"],
            currency=row["currency"],
            asking_price=row["asking_price"],
            estimated_market_price=row["estimated_market_price"],
            roi_percentage=row["roi_percentage"],
            net_profit=row["net_profit"],
            confidence_score=row["confidence_score"],
            risk_score=row["risk_score"],
            recommendation_score=row["recommendation_score"],
            recommendation=row["recommendation"],
        )
