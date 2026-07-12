"""Session semantic memory store (F1-A2 — memory/learning reform).

Per-turn transcript memory at ``~/.arkaos/session-memory.db``: every
turn is summarised, sanitized, optionally embedded (multi-backend, see
core/knowledge/embedding_backends.py) and stored. Retrieval happens in
two honest modes, labeled exactly like core/knowledge/vector_store.py:

- ``semantic``          — cosine over stored embeddings, computed OFF
                          the hot path (the detached turn_capture worker
                          precomputes neighbours into a session cache)
- ``keyword-degraded``  — live LIKE query, ``score`` is None

No vec0 dependency by design: the read path NEVER embeds, and the
worker's brute-force cosine over the bounded scan window (most recent
rows with embeddings) runs off-turn, so an extension adds failure modes
without buying latency where it matters. Embeddings are only compared
within the same backend+model+dims — cosine across vector spaces is a
meaningless number dressed as similarity, so mismatched rows are skipped.

The store is born self-healing (core/shared/sqlite_recovery.py).
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field

DB_ENV = "ARKA_SESSION_MEMORY_DB"
_SEMANTIC_SCAN_CAP = 2000  # most-recent embedded rows the worker scans
_DEFAULT_RETENTION_DAYS = 90
_DEFAULT_MAX_ROWS = 20_000


class TurnRecord(BaseModel):
    """One captured turn — embeddings always declare their provenance."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    ts: str = ""
    session_id: str = ""
    project_name: str = ""
    cwd: str = ""
    summary: str = ""
    tools_used: list[str] = Field(default_factory=list)
    file_paths: list[str] = Field(default_factory=list)
    importance: float = 0.5
    embedding: list[float] | None = None
    embedding_backend: str = "none"
    embedding_model: str = ""
    dims: int = 0


def default_db_path() -> Path:
    env = os.environ.get(DB_ENV, "").strip()
    if env:
        return Path(env)
    return Path.home() / ".arkaos" / "session-memory.db"


_TAG_TOKEN_RE = re.compile(r"\[([^\]]*)\]")


def neutralize_summary(text: str) -> str:
    """Read-side neutralization before any context injection (OWASP LLM01):
    collapse whitespace so a stored summary cannot forge a new line, and
    defuse ``[tag]`` tokens into ``(tag)`` so it cannot impersonate
    ``[SESSION-MEMORY]``/``[arka:*]`` markers. Write-time sanitization
    only redacts client identifiers — it does not neutralize payloads."""
    collapsed = " ".join(str(text).split())
    return _TAG_TOKEN_RE.sub(r"(\1)", collapsed)


def _cosine(a: list[float], b: list[float]) -> float:
    # Callers guarantee equal dims (backend+model+dims guard upstream).
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class SessionMemoryStore:
    """SQLite-backed turn memory; connections opened per operation."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        from core.shared.sqlite_recovery import open_with_recovery
        open_with_recovery(self._db_path, self._init_db)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        # closing() closes the connection; the inner `conn` context
        # commits the transaction — sqlite3's context manager alone
        # commits but never closes (leaks in long-lived consumers).
        with closing(self._conn()) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    ts TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    project_name TEXT NOT NULL DEFAULT '',
                    cwd TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    tools_used TEXT NOT NULL DEFAULT '[]',
                    file_paths TEXT NOT NULL DEFAULT '[]',
                    importance REAL NOT NULL DEFAULT 0.5,
                    embedding TEXT,
                    embedding_backend TEXT NOT NULL DEFAULT 'none',
                    embedding_model TEXT NOT NULL DEFAULT '',
                    dims INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_project_ts "
                "ON turns (project_name, ts DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_turns_session ON turns (session_id)"
            )

    def save(self, record: TurnRecord) -> None:
        row = record.model_dump()
        row["tools_used"] = json.dumps(record.tools_used)
        row["file_paths"] = json.dumps(record.file_paths)
        row["embedding"] = (
            json.dumps(record.embedding) if record.embedding is not None else None
        )
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO turns (id, ts, session_id, project_name,"
                " cwd, summary, tools_used, file_paths, importance, embedding,"
                " embedding_backend, embedding_model, dims)"
                " VALUES (:id, :ts, :session_id, :project_name, :cwd, :summary,"
                " :tools_used, :file_paths, :importance, :embedding,"
                " :embedding_backend, :embedding_model, :dims)",
                row,
            )

    def _row_to_record(self, row: sqlite3.Row) -> TurnRecord:
        data = dict(row)
        data["tools_used"] = json.loads(data.get("tools_used") or "[]")
        data["file_paths"] = json.loads(data.get("file_paths") or "[]")
        raw_emb = data.get("embedding")
        data["embedding"] = json.loads(raw_emb) if raw_emb else None
        return TurnRecord(**data)

    def recent(
        self,
        project_name: str | None = None,
        limit: int = 20,
        exclude_session: str | None = None,
    ) -> list[TurnRecord]:
        """Most recent turns, importance-weighted recency order."""
        where, params = self._scope(project_name, exclude_session)
        with closing(self._conn()) as conn:
            rows = conn.execute(
                f"SELECT * FROM turns {where} ORDER BY ts DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
        records = [self._row_to_record(r) for r in rows]
        return sorted(records, key=lambda r: (r.importance, r.ts), reverse=True)

    def _scope(
        self, project_name: str | None, exclude_session: str | None
    ) -> tuple[str, list]:
        clauses, params = [], []
        if project_name:
            clauses.append("project_name = ?")
            params.append(project_name)
        if exclude_session:
            clauses.append("session_id != ?")
            params.append(exclude_session)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def keyword_search(
        self, query: str, project_name: str | None = None, top_k: int = 3
    ) -> list[dict]:
        """Live substring match — labeled, never presented as semantic."""
        words = [w for w in query.lower().split() if len(w) > 2][:5]
        if not words:
            return []
        where, params = self._scope(project_name, None)
        like = " OR ".join(["lower(summary) LIKE ?"] * len(words))
        where = f"{where} AND ({like})" if where else f"WHERE {like}"
        with closing(self._conn()) as conn:
            rows = conn.execute(
                f"SELECT * FROM turns {where} ORDER BY ts DESC LIMIT ?",
                params + [f"%{w}%" for w in words] + [top_k],
            ).fetchall()
        return [
            {**self._row_to_record(r).model_dump(exclude={"embedding"}),
             "score": None, "retrieval": "keyword-degraded"}
            for r in rows
        ]

    def semantic_neighbors(
        self,
        vector: list[float],
        project_name: str | None = None,
        top_k: int = 3,
        exclude_session: str | None = None,
        backend: str = "",
        model: str = "",
    ) -> list[dict]:
        """Brute-force cosine over the bounded scan window (off-turn only).

        Rows are SKIPPED unless backend, model AND dims all match the
        query vector's provenance — cosine across different embedding
        spaces yields a meaningless number dressed as similarity, the
        exact silent lie the honesty labels exist to prevent.
        """
        where, params = self._scope(project_name, exclude_session)
        prefix = f"{where} AND" if where else "WHERE"
        with closing(self._conn()) as conn:
            rows = conn.execute(
                f"SELECT * FROM turns {prefix} embedding IS NOT NULL"
                " ORDER BY ts DESC LIMIT ?",
                [*params, _SEMANTIC_SCAN_CAP],
            ).fetchall()
        scored = []
        for row in rows:
            record = self._row_to_record(row)
            if not record.embedding or record.dims != len(vector):
                continue
            if record.embedding_backend != backend or record.embedding_model != model:
                continue
            score = _cosine(vector, record.embedding)
            scored.append(
                {**record.model_dump(exclude={"embedding"}),
                 "score": score, "retrieval": "semantic"}
            )
        scored.sort(key=lambda d: d["score"], reverse=True)
        return scored[:top_k]

    def backfill_candidates(self, limit: int = 10) -> list[TurnRecord]:
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT * FROM turns WHERE embedding IS NULL AND summary != ''"
                " ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_embedding(
        self, turn_id: str, vector: list[float], backend: str, model: str
    ) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "UPDATE turns SET embedding = ?, embedding_backend = ?,"
                " embedding_model = ?, dims = ? WHERE id = ?",
                (json.dumps(vector), backend, model, len(vector), turn_id),
            )

    def prune(
        self,
        retention_days: int = _DEFAULT_RETENTION_DAYS,
        max_rows: int = _DEFAULT_MAX_ROWS,
    ) -> int:
        cutoff = (
            datetime.now(UTC) - timedelta(days=retention_days)
        ).isoformat()
        with closing(self._conn()) as conn, conn:
            removed = conn.execute(
                "DELETE FROM turns WHERE ts < ?", (cutoff,)
            ).rowcount
            removed += conn.execute(
                "DELETE FROM turns WHERE id NOT IN"
                " (SELECT id FROM turns ORDER BY ts DESC LIMIT ?)",
                (max_rows,),
            ).rowcount
        return removed

    def vacuum(self) -> None:
        """Nightly-maintenance compaction (never on a hook hot path)."""
        with closing(self._conn()) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")

    def stats(self) -> dict:
        with closing(self._conn()) as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM turns").fetchone()["c"]
            backends = dict(
                conn.execute(
                    "SELECT embedding_backend, COUNT(*) FROM turns"
                    " GROUP BY embedding_backend"
                ).fetchall()
            )
        return {"total_turns": total, "by_embedding_backend": backends}
