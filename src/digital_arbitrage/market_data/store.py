"""SQLite persistence for the market-data collection layer.

Follows the repository convention (``persistence/storage.py``,
``pue/persistence.py``): plain :mod:`sqlite3`, no ORM, ``PRAGMA user_version``
migration protocol, all-DDL-runs-in-one-transaction initialisation.

Entity/observation rules enforced here:

* Entities dedupe on ``(provider, entity_type, provider_entity_id)`` - a
  repeated sighting updates ``last_seen_at``/``times_seen`` and never creates
  a second entity.
* Observations are append-only and dedupe on
  ``(entity_id, collection_run_id, source_kind, content_hash)`` - retrying a
  task never double-writes; the *same content seen in a later run* is a new
  row, preserving history.
* Raw payloads dedupe globally on ``payload_sha256``; each capture links a
  run/task to the deduplicated payload, so identical pages across runs cost
  one stored body while still recording that they were seen.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from .models import (
    COLLECTOR_VERSION,
    CollectionTask,
    Observation,
    ObservationState,
    ProviderEntity,
    RunStatus,
    SourceKind,
)

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id TEXT PRIMARY KEY,
    manifest_id TEXT,
    manifest_hash TEXT,
    collector_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    counters_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS collection_tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_run_id TEXT NOT NULL REFERENCES collection_runs(run_id),
    provider TEXT NOT NULL,
    query_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    page_number INTEGER NOT NULL DEFAULT 1,
    offset INTEGER NOT NULL DEFAULT 0,
    filters_json TEXT NOT NULL DEFAULT '{}',
    marketplace TEXT,
    status TEXT NOT NULL,
    http_status INTEGER,
    error_category TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    items_returned INTEGER NOT NULL DEFAULT 0,
    items_stored INTEGER NOT NULL DEFAULT 0,
    items_rejected INTEGER NOT NULL DEFAULT 0,
    reported_total INTEGER,
    has_more INTEGER,
    duration_ms INTEGER,
    retrieved_at TEXT,
    UNIQUE(collection_run_id, provider, query_id, endpoint, page_number)
);

CREATE INDEX IF NOT EXISTS idx_tasks_run ON collection_tasks(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON collection_tasks(status);

CREATE TABLE IF NOT EXISTS provider_entities (
    entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    provider_entity_id TEXT NOT NULL,
    parent_entity_id INTEGER REFERENCES provider_entities(entity_id),
    marketplace TEXT,
    canonical_url TEXT,
    title TEXT,
    seller_key TEXT,
    first_seen_run_id TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    times_seen INTEGER NOT NULL DEFAULT 0,
    latest_state TEXT NOT NULL DEFAULT 'unknown',
    UNIQUE(provider, entity_type, provider_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entities_native
    ON provider_entities(provider, entity_type, provider_entity_id);
CREATE INDEX IF NOT EXISTS idx_entities_state ON provider_entities(latest_state);

CREATE TABLE IF NOT EXISTS observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES provider_entities(entity_id),
    collection_run_id TEXT NOT NULL,
    task_id INTEGER REFERENCES collection_tasks(task_id),
    observed_at TEXT NOT NULL,
    source_event_time TEXT,
    source_kind TEXT NOT NULL,
    state TEXT NOT NULL,
    price_amount REAL,
    price_currency TEXT,
    price_kind TEXT,
    quantity_available INTEGER,
    quantity_sold_estimate INTEGER,
    condition TEXT,
    description TEXT,
    attributes_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    UNIQUE(entity_id, collection_run_id, source_kind, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_observations_entity ON observations(entity_id);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(collection_run_id);
CREATE INDEX IF NOT EXISTS idx_observations_time ON observations(observed_at);

CREATE TABLE IF NOT EXISTS raw_payloads (
    payload_id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload_sha256 TEXT NOT NULL UNIQUE,
    endpoint TEXT NOT NULL,
    http_status INTEGER,
    payload_json TEXT NOT NULL,
    redaction_version TEXT NOT NULL,
    first_retrieved_at TEXT NOT NULL,
    times_retrieved INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payload_captures (
    capture_id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_run_id TEXT NOT NULL,
    task_id INTEGER REFERENCES collection_tasks(task_id),
    payload_id INTEGER NOT NULL REFERENCES raw_payloads(payload_id),
    request_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    UNIQUE(collection_run_id, task_id, payload_id)
);

CREATE INDEX IF NOT EXISTS idx_captures_run ON payload_captures(collection_run_id);

CREATE TABLE IF NOT EXISTS entity_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES provider_entities(entity_id),
    link_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    match_method TEXT,
    match_confidence REAL,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_by TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(entity_id, link_kind, target_id)
);

CREATE TABLE IF NOT EXISTS sold_imports (
    import_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_label TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_entity_id TEXT,
    entity_id INTEGER REFERENCES provider_entities(entity_id),
    sold_price REAL,
    currency TEXT,
    sold_date TEXT,
    quantity INTEGER,
    evidence_url TEXT,
    imported_by TEXT,
    imported_at TEXT NOT NULL,
    source_file_hash TEXT,
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    raw_row_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS request_usage (
    day TEXT NOT NULL,
    provider TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, provider)
);
"""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def content_hash(
    attributes_json: str, *, state: str, price: float | None, currency: str | None
) -> str:
    """Stable hash of an observation's evidence content."""
    canonical = json.dumps(
        {
            "attributes": attributes_json,
            "state": state,
            "price": price,
            "currency": currency,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class MarketDataStore:
    """SQLite store for collection runs, entities, observations and payloads."""

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

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> MarketDataStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- runs -------------------------------------------------------------- #
    def start_run(
        self,
        run_id: str,
        *,
        manifest_id: str | None,
        manifest_hash: str | None,
        config_json: str,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO collection_runs (run_id, manifest_id, manifest_hash, "
                "collector_version, schema_version, started_at, status, config_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    manifest_id,
                    manifest_hash,
                    COLLECTOR_VERSION,
                    SCHEMA_VERSION,
                    _utc_now(),
                    RunStatus.RUNNING.value,
                    config_json,
                ),
            )

    def finish_run(self, run_id: str, *, status: str, counters: dict[str, Any]) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE collection_runs SET finished_at = ?, status = ?, "
                "counters_json = ? WHERE run_id = ?",
                (_utc_now(), status, json.dumps(counters, sort_keys=True), run_id),
            )

    # -- tasks ------------------------------------------------------------- #
    def record_task(self, run_id: str, task: CollectionTask) -> int:
        """Insert a pending task row; returns ``task_id``.

        Duplicate (run, provider, query, endpoint, page) inserts are ignored so
        retrying a task cannot create two task rows for the same page.
        """
        with self._conn:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO collection_tasks (collection_run_id, provider, "
                "query_id, query_text, endpoint, page_number, offset, filters_json, "
                "marketplace, status, retrieved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    task.provider,
                    task.query_id,
                    task.query_text,
                    task.endpoint,
                    task.page_number,
                    task.offset,
                    task.filters_json,
                    task.marketplace,
                    task.status.value,
                    _utc_now(),
                ),
            )
            del cursor
            row = self._conn.execute(
                "SELECT task_id FROM collection_tasks WHERE collection_run_id = ? "
                "AND provider = ? AND query_id = ? AND endpoint = ? AND page_number = ?",
                (run_id, task.provider, task.query_id, task.endpoint, task.page_number),
            ).fetchone()
            return int(row["task_id"])

    def finish_task(self, task_id: int, task: CollectionTask) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE collection_tasks SET status = ?, http_status = ?, "
                "error_category = ?, attempts = ?, items_returned = ?, "
                "items_stored = ?, items_rejected = ?, reported_total = ?, "
                "has_more = ?, duration_ms = ?, retrieved_at = ? WHERE task_id = ?",
                (
                    task.status.value,
                    task.http_status,
                    task.error_category,
                    task.attempts,
                    task.items_returned,
                    task.items_stored,
                    task.items_rejected,
                    task.reported_total,
                    None if task.has_more is None else int(task.has_more),
                    task.duration_ms,
                    _utc_now(),
                    task_id,
                ),
            )

    def tasks_for_run(
        self, run_id: str, *, statuses: tuple[str, ...] | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM collection_tasks WHERE collection_run_id = ?"
        params: list[Any] = [run_id]
        if statuses:
            sql += f" AND status IN ({','.join('?' * len(statuses))})"
            params.extend(statuses)
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    # -- entities ---------------------------------------------------------- #
    def upsert_entity(
        self,
        entity: ProviderEntity,
        *,
        run_id: str,
        observed_at: str,
        state: ObservationState,
    ) -> int:
        """Insert or refresh an entity; returns its stable ``entity_id``."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO provider_entities (provider, entity_type, "
                "provider_entity_id, parent_entity_id, marketplace, canonical_url, "
                "title, seller_key, first_seen_run_id, first_seen_at, last_seen_at, "
                "times_seen, latest_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?) "
                "ON CONFLICT(provider, entity_type, provider_entity_id) DO UPDATE SET "
                "parent_entity_id = COALESCE(excluded.parent_entity_id, parent_entity_id), "
                "marketplace = COALESCE(excluded.marketplace, marketplace), "
                "canonical_url = COALESCE(excluded.canonical_url, canonical_url), "
                "title = COALESCE(excluded.title, title), "
                "seller_key = COALESCE(excluded.seller_key, seller_key), "
                "last_seen_at = excluded.last_seen_at, "
                "times_seen = times_seen + 1, "
                "latest_state = excluded.latest_state",
                (
                    entity.provider,
                    entity.entity_type.value,
                    entity.provider_entity_id,
                    entity.parent_entity_id,
                    entity.marketplace,
                    entity.canonical_url,
                    entity.title,
                    entity.seller_key,
                    run_id,
                    observed_at,
                    observed_at,
                    state.value,
                ),
            )
            row = self._conn.execute(
                "SELECT entity_id FROM provider_entities WHERE provider = ? "
                "AND entity_type = ? AND provider_entity_id = ?",
                (entity.provider, entity.entity_type.value, entity.provider_entity_id),
            ).fetchone()
            return int(row["entity_id"])

    def get_entity(
        self, provider: str, entity_type: str, provider_entity_id: str
    ) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM provider_entities WHERE provider = ? AND entity_type = ? "
            "AND provider_entity_id = ?",
            (provider, entity_type, provider_entity_id),
        ).fetchone()
        return dict(row) if row else None

    def set_entity_state(self, entity_id: int, state: ObservationState) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE provider_entities SET latest_state = ? WHERE entity_id = ?",
                (state.value, entity_id),
            )

    # -- observations ------------------------------------------------------ #
    def insert_observation(self, obs: Observation) -> int | None:
        """Append an observation; ``None`` when an identical row exists.

        The unique key ``(entity_id, run, source_kind, content_hash)`` makes
        task retries idempotent while letting identical content observed in a
        *different* run persist as its own historical row.
        """
        with self._conn:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO observations (entity_id, collection_run_id, "
                "task_id, observed_at, source_event_time, source_kind, state, "
                "price_amount, price_currency, price_kind, quantity_available, "
                "quantity_sold_estimate, condition, description, attributes_json, "
                "content_hash, parser_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    obs.entity_id,
                    obs.collection_run_id,
                    obs.task_id,
                    obs.observed_at,
                    obs.source_event_time,
                    obs.source_kind.value,
                    obs.state.value,
                    obs.price_amount,
                    obs.price_currency,
                    obs.price_kind.value,
                    obs.quantity_available,
                    obs.quantity_sold_estimate,
                    obs.condition,
                    obs.description,
                    obs.attributes_json,
                    obs.content_hash,
                    obs.parser_version,
                ),
            )
            return int(cursor.lastrowid) if cursor.lastrowid else None

    def latest_observation(
        self, entity_id: int, *, source_kind: SourceKind | None = None
    ) -> dict[str, Any] | None:
        sql = (
            "SELECT * FROM observations WHERE entity_id = ? "
            + ("AND source_kind = ? " if source_kind else "")
            + "ORDER BY observed_at DESC, observation_id DESC LIMIT 1"
        )
        params: tuple[Any, ...] = (entity_id, source_kind.value) if source_kind else (entity_id,)
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def observations_for_entity(self, entity_id: int) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM observations WHERE entity_id = ? ORDER BY observed_at ASC",
            (entity_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def entities_seen_for_query(
        self, provider: str, query_text: str, *, before_run_id: str
    ) -> list[int]:
        """Entity ids whose latest sighting for ``query_text`` was state='active'
        in a run *other than* ``before_run_id``."""
        rows = self._conn.execute(
            """
            SELECT o.entity_id FROM observations o
            JOIN collection_tasks t ON o.task_id = t.task_id
            WHERE t.provider = ? AND t.query_text = ?
              AND o.state = 'active'
              AND o.collection_run_id != ?
              AND o.entity_id NOT IN (
                  SELECT o2.entity_id FROM observations o2
                  JOIN collection_tasks t2 ON o2.task_id = t2.task_id
                  WHERE t2.provider = ? AND t2.query_text = ?
                    AND o2.collection_run_id = ?
              )
            GROUP BY o.entity_id
            """,
            (provider, query_text, before_run_id, provider, query_text, before_run_id),
        ).fetchall()
        return [int(r["entity_id"]) for r in rows]

    def stale_entities(self, *, provider: str, stale_after: str) -> list[dict[str, Any]]:
        """Active entities not observed since ``stale_after`` (ISO timestamp)."""
        rows = self._conn.execute(
            "SELECT * FROM provider_entities WHERE provider = ? AND latest_state = 'active' "
            "AND last_seen_at < ?",
            (provider, stale_after),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- payloads ---------------------------------------------------------- #
    def record_payload(
        self,
        *,
        collection_run_id: str,
        task_id: int | None,
        endpoint: str,
        request_url: str,
        http_status: int,
        payload_json: str,
        payload_sha256: str,
    ) -> int:
        """Store a redacted payload (deduped on sha256) + its capture link."""
        from .models import REDACTION_VERSION

        now = _utc_now()
        with self._conn:
            self._conn.execute(
                "INSERT INTO raw_payloads (payload_sha256, endpoint, http_status, "
                "payload_json, redaction_version, first_retrieved_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(payload_sha256) DO UPDATE SET "
                "times_retrieved = times_retrieved + 1",
                (
                    payload_sha256,
                    endpoint,
                    http_status,
                    payload_json,
                    REDACTION_VERSION,
                    now,
                ),
            )
            row = self._conn.execute(
                "SELECT payload_id FROM raw_payloads WHERE payload_sha256 = ?",
                (payload_sha256,),
            ).fetchone()
            payload_id = int(row["payload_id"])
            self._conn.execute(
                "INSERT OR IGNORE INTO payload_captures (collection_run_id, task_id, "
                "payload_id, request_url, retrieved_at) VALUES (?, ?, ?, ?, ?)",
                (collection_run_id, task_id, payload_id, request_url, now),
            )
            return payload_id

    def gc_raw_payloads(self, *, older_than_days: int) -> int:
        """Delete raw payload bodies older than the retention window.

        Capture links are removed with them; observations are unaffected.
        Returns the number of deleted payload rows.
        """
        cutoff = datetime.now(UTC).timestamp() - older_than_days * 86400
        cutoff_iso = datetime.fromtimestamp(cutoff, UTC).replace(microsecond=0).isoformat()
        with self._conn:
            ids = [
                r["payload_id"]
                for r in self._conn.execute(
                    "SELECT payload_id FROM raw_payloads WHERE first_retrieved_at < ?",
                    (cutoff_iso,),
                ).fetchall()
            ]
            if not ids:
                return 0
            marks = ",".join("?" * len(ids))
            self._conn.execute(f"DELETE FROM payload_captures WHERE payload_id IN ({marks})", ids)
            self._conn.execute(f"DELETE FROM raw_payloads WHERE payload_id IN ({marks})", ids)
            return len(ids)

    # -- request usage ------------------------------------------------------ #
    def record_request(self, *, day: str, provider: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO request_usage (day, provider, requests) VALUES (?, ?, 1) "
                "ON CONFLICT(day, provider) DO UPDATE SET requests = requests + 1",
                (day, provider),
            )

    def requests_used(self, provider: str, *, day: str) -> int:
        row = self._conn.execute(
            "SELECT requests FROM request_usage WHERE day = ? AND provider = ?",
            (day, provider),
        ).fetchone()
        return int(row["requests"]) if row else 0

    # -- links --------------------------------------------------------------- #
    def upsert_link(
        self,
        *,
        entity_id: int,
        link_kind: str,
        target_id: str,
        match_method: str | None,
        match_confidence: float | None,
        status: str = "candidate",
        created_by: str | None = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO entity_links (entity_id, link_kind, target_id, "
                "match_method, match_confidence, status, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entity_id,
                    link_kind,
                    target_id,
                    match_method,
                    match_confidence,
                    status,
                    created_by,
                    _utc_now(),
                ),
            )

    # -- report queries ------------------------------------------------------ #
    def run_row(self, run_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM collection_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def observation_counts(self, run_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n, COUNT(DISTINCT entity_id) AS entities "
            "FROM observations WHERE collection_run_id = ?",
            (run_id,),
        ).fetchone()
        return {"observations": row["n"], "entities": row["entities"]}

    def field_presence(self, run_id: str, source_kind: str, provider: str) -> dict[str, Any]:
        """How often each top-level attribute key appears across one provider's
        observations of one source kind in a run (drives the missing-field
        report). Provider-scoped: each provider has a different field registry."""
        counts: dict[str, int] = {}
        total = 0
        rows = self._conn.execute(
            "SELECT o.attributes_json FROM observations o "
            "JOIN provider_entities e ON o.entity_id = e.entity_id "
            "WHERE o.collection_run_id = ? AND o.source_kind = ? AND e.provider = ? "
            "AND o.state NOT IN ('disappeared', 'inferred_outcome')",
            (run_id, source_kind, provider),
        ).fetchall()
        for row in rows:
            total += 1
            try:
                attrs = json.loads(row["attributes_json"])
            except ValueError:
                continue
            if isinstance(attrs, dict):
                for key in attrs:
                    counts[key] = counts.get(key, 0) + 1
        return {"total": total, "counts": counts}
