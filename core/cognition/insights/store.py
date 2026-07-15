"""SQLite CRUD store for actionable insights.

Persists ActionableInsight instances with support for status-based retrieval,
project filtering, presentation lifecycle, and dismissal analytics.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from core.cognition.memory.schemas import (
    INSTINCT_CONFIDENCE_MAX,
    INSTINCT_CONFIDENCE_MIN,
    ActionableInsight,
)


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

    # Instinct columns added after the original 12-column schema. An
    # operator's existing DB has the old shape, so these are ALTER-added
    # with defaults rather than baked into CREATE TABLE — a fresh install
    # gets them from CREATE, an upgrade gets them from _migrate.
    #
    # Each entry carries the FULL, literal ALTER statement — never an
    # f-string built from parts. SQLite cannot parameterise a DDL
    # identifier, so the only safe construction is a constant statement,
    # and a constant statement is also the only one a scanner can trust:
    # there is no interpolation site to become an injection the day these
    # names turn dynamic.
    _INSTINCT_COLUMNS = (
        ("confidence",
         "ALTER TABLE insights ADD COLUMN confidence REAL NOT NULL DEFAULT 0.5"),
        ("scope",
         "ALTER TABLE insights ADD COLUMN scope TEXT NOT NULL DEFAULT 'project'"),
        ("evidence_count",
         "ALTER TABLE insights ADD COLUMN evidence_count "
         "INTEGER NOT NULL DEFAULT 1"),
    )

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
                    presented_at TEXT,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    scope TEXT NOT NULL DEFAULT 'project',
                    evidence_count INTEGER NOT NULL DEFAULT 1
                )
            """)
            self._migrate(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_insights_project ON insights (project)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_insights_status ON insights (status)"
            )

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Add instinct columns to a pre-existing table. Idempotent."""
        existing = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(insights)").fetchall()
        }
        for name, alter_stmt in self._INSTINCT_COLUMNS:
            if name not in existing:
                conn.execute(alter_stmt)

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
                     status, presented_at, confidence, scope, evidence_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    insight.confidence,
                    insight.scope,
                    insight.evidence_count,
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
        now = datetime.now(UTC).isoformat()
        placeholders = ",".join("?" * len(ids))
        with self._conn() as conn:
            conn.execute(
                "UPDATE insights SET status = 'presented', presented_at = ? "
                f"WHERE id IN ({placeholders})",
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

    def reinforce(self, insight_id: str, step: float = 0.1) -> None:
        """Corroboration: raise confidence (clamped) and count evidence.

        The clamp lives in ``ActionableInsight``; the SQL bounds mirror it
        so a direct UPDATE cannot push a value past the band either.
        """
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE insights
                SET confidence = MIN(?, confidence + ?),
                    evidence_count = evidence_count + 1
                WHERE id = ?
                """,
                (INSTINCT_CONFIDENCE_MAX, step, insight_id),
            )

    def weaken(self, insight_id: str, step: float = 0.2) -> None:
        """Contradiction: lower confidence (clamped to the band floor).

        A correction cuts harder than a corroboration lifts — the default
        step is larger — because one contradiction outweighs several
        passive confirmations.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE insights SET confidence = MAX(?, confidence - ?) WHERE id = ?",
                (INSTINCT_CONFIDENCE_MIN, step, insight_id),
            )

    def promotable(
        self, min_projects: int = 2, min_confidence: float = 0.8
    ) -> list[str]:
        """Titles seen as project-scoped across >= min_projects distinct
        projects with mean confidence >= min_confidence.

        The signal B7 (``/arka promote``) consumes: a pattern that has
        proven itself in more than one project has earned global scope.
        Grouped by title because that is the instinct's stable identity
        across projects (the id is per-occurrence).
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT title FROM insights
                WHERE scope = 'project'
                GROUP BY title
                HAVING COUNT(DISTINCT project) >= ?
                   AND AVG(confidence) >= ?
                """,
                (min_projects, min_confidence),
            ).fetchall()
        return [r["title"] for r in rows]

    def promote_to_global(self, title: str) -> int:
        """Flip every project-scoped insight with this title to global.
        Returns the number of rows promoted."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE insights SET scope = 'global' WHERE title = ? AND scope = 'project'",
                (title,),
            )
            return cur.rowcount

    def close(self) -> None:
        """No-op — connections are opened per-operation."""
