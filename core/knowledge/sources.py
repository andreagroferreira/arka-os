"""Source registry for the knowledge base.

Stores rich per-source metadata (title, duration, media path, transcript,
thumbnail, status) in a dedicated ``sources`` table living inside the same
``knowledge.db`` as the vector store. This module is purely additive: it
never touches the ``chunks`` table owned by :class:`VectorStore`.
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    type TEXT DEFAULT '',
    title TEXT DEFAULT '',
    duration INTEGER DEFAULT 0,
    language TEXT DEFAULT '',
    thumbnail_path TEXT DEFAULT '',
    media_path TEXT DEFAULT '',
    transcript TEXT DEFAULT '',
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error TEXT DEFAULT '',
    created_at REAL DEFAULT (unixepoch('now')),
    updated_at REAL DEFAULT (unixepoch('now'))
)
"""

_COLUMNS = (
    "id", "source", "type", "title", "duration", "language",
    "thumbnail_path", "media_path", "transcript", "chunk_count",
    "status", "error", "created_at", "updated_at",
)


def source_id(source: str) -> str:
    """Return a stable id for a source string: ``src-`` + sha1[:12]."""
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()
    return f"src-{digest[:12]}"


class SourceRegistry:
    """SQLite-backed registry of knowledge sources and their metadata."""

    def __init__(self, db_path: str | Path = "") -> None:
        """Open (or create) the sources table in the knowledge database."""
        self._db_path = str(db_path) if db_path else self._default_path()
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    @staticmethod
    def _default_path() -> str:
        home = Path.home() / ".arkaos"
        home.mkdir(parents=True, exist_ok=True)
        return str(home / "knowledge.db")

    def upsert(
        self,
        source: str,
        *,
        type: str = "",
        title: str = "",
        duration: int = 0,
        language: str = "",
        thumbnail_path: str = "",
        media_path: str = "",
        transcript: str = "",
        chunk_count: int = 0,
        status: str = "ready",
        error: str = "",
    ) -> str:
        """Insert or replace a source row by id; return its stable id."""
        sid = source_id(source)
        params = (
            sid, source, type, title, duration, language, thumbnail_path,
            media_path, transcript, chunk_count, status, error, sid,
        )
        with self._lock:
            self._conn.execute(self._upsert_sql(), params)
            self._conn.commit()
        return sid

    @staticmethod
    def _upsert_sql() -> str:
        """SQL that preserves created_at on update via a COALESCE subquery."""
        return (
            "INSERT OR REPLACE INTO sources "
            "(id, source, type, title, duration, language, thumbnail_path, "
            "media_path, transcript, chunk_count, status, error, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, COALESCE((SELECT created_at FROM sources WHERE id = ?), "
            "unixepoch('now')), unixepoch('now'))"
        )

    def get(self, source_id_: str) -> Optional[dict]:
        """Return the full row for a source id as a dict, or None."""
        row = self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id_,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_by_source(self, source: str) -> Optional[dict]:
        """Return the row matching a raw source string, or None."""
        return self.get(source_id(source))

    def list(self) -> list[dict]:
        """Return all source rows, newest updated first."""
        rows = self._conn.execute(
            "SELECT * FROM sources ORDER BY updated_at DESC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, source_id_: str) -> bool:
        """Delete a source row; return True if a row was removed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM sources WHERE id = ?", (source_id_,)
            )
            self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_dict(row: tuple) -> dict:
        """Map a SELECT * tuple to a column-keyed dict."""
        return dict(zip(_COLUMNS, row))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
