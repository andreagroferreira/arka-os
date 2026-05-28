"""Vector store — SQLite-vec backed semantic search.

Stores document chunks with embeddings for fast similarity search.
Graceful degradation: works without sqlite-vec (brute-force fallback).
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from core.knowledge.embedder import embed, embed_batch, EMBEDDING_DIMS


_VEC_UNAVAILABLE_REASON: str = ""  # set by _load_vec on failure


def _load_vec(db: sqlite3.Connection) -> bool:
    """Try to load sqlite-vec extension.

    PR73 v2.91.0 — failure reason is now captured in a module-level
    string so the dashboard / /api/knowledge/stats can surface why
    vector search is unavailable instead of just "Unavailable".
    Common reasons:
      - sqlite-vec not installed (pip install sqlite-vec)
      - Python sqlite3 built without enable_load_extension (rare on
        homebrew Python; common on system Python on some distros)
    """
    global _VEC_UNAVAILABLE_REASON
    try:
        db.enable_load_extension(True)
    except AttributeError:
        _VEC_UNAVAILABLE_REASON = (
            "Python sqlite3 was built without extension loading support. "
            "On macOS, reinstall via Homebrew Python: brew install python."
        )
        return False
    except sqlite3.OperationalError as exc:
        _VEC_UNAVAILABLE_REASON = f"sqlite3 refused extension loading: {exc}"
        return False
    try:
        import sqlite_vec  # noqa: PLC0415
    except ImportError:
        _VEC_UNAVAILABLE_REASON = (
            "sqlite-vec package missing. Install with: "
            "pip install sqlite-vec"
        )
        return False
    try:
        sqlite_vec.load(db)
        _VEC_UNAVAILABLE_REASON = ""
        return True
    except Exception as exc:  # noqa: BLE001
        _VEC_UNAVAILABLE_REASON = f"sqlite_vec.load failed: {exc}"
        return False


def vec_unavailable_reason() -> str:
    """Public accessor for the last vec-load failure reason."""
    return _VEC_UNAVAILABLE_REASON


class VectorStore:
    """SQLite-vec backed vector store for knowledge retrieval.

    PR73 v2.91.0 — connection is opened with ``check_same_thread=False``
    so background ingest workers (knowledge_ingest, knowledge_ingest_bulk
    in scripts/dashboard-api.py) can reuse a long-lived FastAPI-scoped
    store instance without hitting ``sqlite3.ProgrammingError: SQLite
    objects created in a thread can only be used in that same thread``.
    Concurrent writes are serialised via ``_write_lock``; SQLite's WAL
    journal_mode lets readers continue while a writer holds the lock.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        import threading
        self._db_path = str(db_path)
        # check_same_thread=False — see class docstring.
        self._db = sqlite3.connect(self._db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        # WAL gives concurrent readers + a single writer at the engine
        # level. The Python lock below serialises our application-level
        # writes per VectorStore instance.
        try:
            self._db.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            # in-memory DBs don't support WAL — harmless.
            pass
        self._write_lock = threading.Lock()
        self._vec_available = _load_vec(self._db)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                heading TEXT DEFAULT '',
                source TEXT DEFAULT '',
                file_hash TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                created_at REAL DEFAULT (unixepoch('now')),
                embedding BLOB
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);
            CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(file_hash);
        """)
        self._migrate_vss_to_vec()
        if self._vec_available:
            try:
                self._db.execute(
                    f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{EMBEDDING_DIMS}])"
                )
            except Exception:
                self._vec_available = False
        self._db.commit()

    def _migrate_vss_to_vec(self) -> None:
        """Drop legacy sqlite-vss tables if present.

        The vss_chunks virtual table used a different schema and query
        syntax that is incompatible with sqlite-vec. Dropping it forces a
        clean re-index on the next /arka index invocation. The chunks
        table (with raw embeddings) is preserved — only the virtual table
        index is removed.
        """
        try:
            tables = [
                r[0]
                for r in self._db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'vss_%'"
                ).fetchall()
            ]
            if tables:
                for t in tables:
                    self._db.execute(f"DROP TABLE IF EXISTS {t}")
                self._db.commit()
        except Exception:
            pass

    def index_chunks(
        self,
        texts: list[str],
        headings: list[str] | None = None,
        source: str = "",
        file_hash: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Index multiple text chunks with embeddings.

        Returns number of chunks indexed.
        """
        if not texts:
            return 0

        embeddings = embed_batch(texts)
        meta_json = json.dumps(metadata or {})
        count = 0

        # PR73 v2.91.0 — serialise writes from background ingest threads.
        # check_same_thread=False on the connection lets the threads use
        # `self._db`; the lock ensures only one writer at a time so
        # cursor lastrowid stays consistent.
        with self._write_lock:
            for i, text in enumerate(texts):
                heading = headings[i] if headings and i < len(headings) else ""
                emb_blob = None

                if embeddings and i < len(embeddings):
                    emb_blob = _vec_to_blob(embeddings[i])

                cursor = self._db.execute(
                    "INSERT INTO chunks (text, heading, source, file_hash, metadata, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                    (text, heading, source, file_hash, meta_json, emb_blob),
                )

                if self._vec_available and emb_blob:
                    self._db.execute(
                        "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                        (cursor.lastrowid, emb_blob),
                    )
                count += 1

            self._db.commit()
        return count

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for similar chunks.

        Returns list of dicts with: text, heading, source, score, metadata.
        """
        # Check if store has any data
        total = self._db.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()["cnt"]
        if total == 0:
            return []

        query_emb = embed(query)

        if query_emb and self._vec_available:
            try:
                return self._vec_search(query_emb, top_k)
            except Exception:
                return self._keyword_search(query, top_k)

        # Fallback: keyword search
        return self._keyword_search(query, top_k)

    def _vec_search(self, query_emb: list[float], top_k: int) -> list[dict]:
        """Vector similarity search via sqlite-vec."""
        query_blob = _vec_to_blob(query_emb)
        rows = self._db.execute("""
            SELECT c.text, c.heading, c.source, c.metadata, v.distance
            FROM vec_chunks v
            JOIN chunks c ON c.id = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
        """, (query_blob, top_k)).fetchall()

        return [
            {
                "text": r["text"],
                "heading": r["heading"],
                "source": r["source"],
                "score": 1.0 / (1.0 + r["distance"]),  # Convert distance to similarity
                "metadata": json.loads(r["metadata"]),
            }
            for r in rows
        ]

    def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        """Fallback keyword search when VSS unavailable."""
        words = query.lower().split()
        if not words:
            return []

        conditions = " OR ".join(["lower(text) LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words[:5]]  # Max 5 keywords

        rows = self._db.execute(
            f"SELECT text, heading, source, metadata FROM chunks WHERE {conditions} LIMIT ?",
            params + [top_k],
        ).fetchall()

        return [
            {
                "text": r["text"],
                "heading": r["heading"],
                "source": r["source"],
                "score": 0.5,  # No real score for keyword search
                "metadata": json.loads(r["metadata"]),
            }
            for r in rows
        ]

    def is_file_indexed(self, source: str, file_hash: str) -> bool:
        """Check if a file (identified by source path + content hash) is indexed.

        The source path is part of the key so identical content in two
        different locations (e.g. two npx cache directories) each get
        indexed — a hash-only check would skip every subsequent cache
        and leave the new location un-searchable.
        """
        row = self._db.execute(
            "SELECT COUNT(*) as cnt FROM chunks WHERE source = ? AND file_hash = ?",
            (source, file_hash),
        ).fetchone()
        return row["cnt"] > 0

    def remove_file(self, source: str) -> int:
        """Remove all chunks from a source file."""
        with self._write_lock:
            if self._vec_available:
                rows = self._db.execute("SELECT id FROM chunks WHERE source = ?", (source,)).fetchall()
                for r in rows:
                    self._db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (r["id"],))
            deleted = self._db.execute("DELETE FROM chunks WHERE source = ?", (source,)).rowcount
            self._db.commit()
            return deleted

    def get_stats(self) -> dict:
        """Get store statistics."""
        total = self._db.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()["cnt"]
        sources = self._db.execute("SELECT COUNT(DISTINCT source) as cnt FROM chunks").fetchone()["cnt"]
        return {
            "total_chunks": total,
            "total_files": sources,
            "vec_available": self._vec_available,
            "db_path": self._db_path,
        }

    def list_sources(self) -> list[dict]:
        """PR88c v3.25.0 — distinct sources with chunk counts.

        Returns rows sorted by chunk count desc so the noisiest
        sources surface first.
        """
        rows = self._db.execute(
            "SELECT source, COUNT(*) AS chunks FROM chunks "
            "WHERE source IS NOT NULL AND source != '' "
            "GROUP BY source ORDER BY chunks DESC"
        ).fetchall()
        return [{"source": r["source"], "chunks": int(r["chunks"])} for r in rows]

    def clear(self) -> None:
        """Remove all data."""
        if self._vec_available:
            self._db.execute("DELETE FROM vec_chunks")
        self._db.execute("DELETE FROM chunks")
        self._db.commit()

    def close(self) -> None:
        """Close database connection."""
        self._db.close()


def _vec_to_blob(vec: list[float]) -> bytes:
    """Convert float vector to bytes for SQLite storage."""
    import struct
    return struct.pack(f"{len(vec)}f", *vec)
