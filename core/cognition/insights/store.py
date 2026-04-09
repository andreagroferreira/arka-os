"""SQLite CRUD store for actionable insights.

Persists ActionableInsight instances with support for status-based retrieval,
project filtering, presentation lifecycle, and dismissal analytics.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.cognition.memory.schemas import ActionableInsight


class InsightStore:
    """SQLite-backed store for actionable insights."""

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
                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    trigger_source TEXT NOT NULL,
                    date_generated TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    context TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    presented_at TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_insights_project ON insights (project)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_insights_status ON insights (status)"
            )

    def _row_to_insight(self, row: sqlite3.Row) -> ActionableInsight:
        data = dict(row)
        # Map trigger_source back to trigger (SQL keyword workaround)
        data["trigger"] = data.pop("trigger_source")
        # Parse datetime fields
        data["date_generated"] = datetime.fromisoformat(data["date_generated"])
        if data["presented_at"] is not None:
            data["presented_at"] = datetime.fromisoformat(data["presented_at"])
        return ActionableInsight(**data)

    def save(self, insight: ActionableInsight) -> None:
        """Insert or replace an ActionableInsight record."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO insights
                    (id, project, trigger_source, date_generated, category,
                     severity, title, description, recommendation, context,
                     status, presented_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    insight.id,
                    insight.project,
                    insight.trigger,
                    insight.date_generated.isoformat(),
                    insight.category,
                    insight.severity,
                    insight.title,
                    insight.description,
                    insight.recommendation,
                    insight.context,
                    insight.status,
                    insight.presented_at.isoformat() if insight.presented_at else None,
                ),
            )

    def get_pending(self, project: str) -> list[ActionableInsight]:
        """Return pending insights for a specific project."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM insights
                WHERE project = ? AND status = 'pending'
                ORDER BY date_generated ASC
                """,
                (project,),
            ).fetchall()
        return [self._row_to_insight(r) for r in rows]

    def get_all_pending(self) -> list[ActionableInsight]:
        """Return all pending insights across all projects."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM insights WHERE status = 'pending' ORDER BY date_generated ASC"
            ).fetchall()
        return [self._row_to_insight(r) for r in rows]

    def get_by_project(self, project: str) -> list[ActionableInsight]:
        """Return all insights for a project regardless of status."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM insights WHERE project = ? ORDER BY date_generated ASC",
                (project,),
            ).fetchall()
        return [self._row_to_insight(r) for r in rows]

    def update_status(self, insight_id: str, status: str) -> None:
        """Update the status of a single insight."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE insights SET status = ? WHERE id = ?",
                (status, insight_id),
            )

    def mark_presented(self, ids: list[str]) -> None:
        """Mark insights as presented and record the timestamp."""
        if not ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        placeholders = ",".join("?" * len(ids))
        with self._conn() as conn:
            conn.execute(
                f"UPDATE insights SET status = 'presented', presented_at = ? WHERE id IN ({placeholders})",
                [now, *ids],
            )

    def dismissed_counts(self, project: str) -> dict[str, int]:
        """Return count of dismissed insights grouped by category for a project."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT category, COUNT(*) as cnt FROM insights
                WHERE project = ? AND status = 'dismissed'
                GROUP BY category
                """,
                (project,),
            ).fetchall()
        return {r["category"]: r["cnt"] for r in rows}

    def close(self) -> None:
        """No-op — connections are opened per-operation."""
