"""SQLite CRUD store for raw session captures.

Persists RawCapture instances with support for date-based retrieval,
project filtering, processing lifecycle, and archival.
"""

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from core.cognition.memory.schemas import RawCapture


class CaptureStore:
    """SQLite-backed store for raw session captures."""

    def __init__(self, db_path: str) -> None:
        """Connect to SQLite database and initialize tables."""
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS captures (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    project_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT NOT NULL DEFAULT '{}',
                    processed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_captures_timestamp ON captures (timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_captures_project_name ON captures (project_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_captures_processed ON captures (processed)"
            )

    def _row_to_capture(self, row: sqlite3.Row) -> RawCapture:
        data = dict(row)
        data["context"] = json.loads(data["context"])
        # Remove store-only fields before passing to Pydantic
        data.pop("processed", None)
        data.pop("archived", None)
        return RawCapture(**data)

    def save(self, capture: RawCapture) -> None:
        """Insert or replace a RawCapture record."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO captures
                    (id, timestamp, session_id, project_path, project_name,
                     category, content, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    capture.id,
                    capture.timestamp.isoformat(),
                    capture.session_id,
                    capture.project_path,
                    capture.project_name,
                    capture.category,
                    capture.content,
                    json.dumps(capture.context),
                ),
            )

    def get_by_date(self, target_date: date) -> list[RawCapture]:
        """Return all non-archived captures whose timestamp falls on target_date (UTC)."""
        start = datetime(target_date.year, target_date.month, target_date.day,
                         0, 0, 0, tzinfo=timezone.utc)
        end = datetime(target_date.year, target_date.month, target_date.day,
                       23, 59, 59, 999999, tzinfo=timezone.utc)
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM captures
                WHERE timestamp >= ? AND timestamp <= ?
                  AND archived = 0
                ORDER BY timestamp ASC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    def get_by_project(self, project_name: str) -> list[RawCapture]:
        """Return all captures for a given project name."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM captures WHERE project_name = ? ORDER BY timestamp ASC",
                (project_name,),
            ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    def get_unprocessed(self) -> list[RawCapture]:
        """Return all captures not yet processed."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM captures WHERE processed = 0 ORDER BY timestamp ASC"
            ).fetchall()
        return [self._row_to_capture(r) for r in rows]

    def mark_processed(self, ids: list[str]) -> None:
        """Mark the given capture IDs as processed."""
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with self._conn() as conn:
            conn.execute(
                f"UPDATE captures SET processed = 1 WHERE id IN ({placeholders})",
                ids,
            )

    def archive_processed(self) -> int:
        """Archive all processed captures. Returns count of archived records."""
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE captures SET archived = 1 WHERE processed = 1 AND archived = 0"
            )
            return result.rowcount

    def stats(self) -> dict:
        """Return store statistics: total, unprocessed, and per-category counts."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
            unprocessed = conn.execute(
                "SELECT COUNT(*) FROM captures WHERE processed = 0"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM captures GROUP BY category"
            ).fetchall()
            by_category = {r["category"]: r["cnt"] for r in rows}
        return {
            "total": total,
            "unprocessed": unprocessed,
            "by_category": by_category,
        }

    def close(self) -> None:
        """No-op — connections are opened per-operation."""
