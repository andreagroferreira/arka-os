"""Vector store — SQLite-vec backed semantic search.

Stores document chunks with embeddings for fast similarity search.
Graceful degradation: works without sqlite-vec (keyword fallback) — but
HONESTLY (PR-3 v4.1): degraded results carry ``retrieval:
"keyword-degraded"`` and ``score: None`` instead of a fake similarity
score, and the first degraded search per process emits a visible
stderr warning explaining why semantic search is unavailable.
"""

import json
import logging
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Optional

from core.knowledge.embedder import embed, embed_batch, embedding_dims

logger = logging.getLogger(__name__)

_VEC_UNAVAILABLE_REASON: str = ""  # set by _load_vec on failure
_DEGRADED_WARNED: bool = False  # one-time per-process degradation warning
_VEC_DIMS_RE = re.compile(r"float\[(\d+)\]")


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


def _parse_vec_dims(create_sql: str | None) -> Optional[int]:
    """Extract the float[N] dimension from a vec0 CREATE statement."""
    if not create_sql:
        return None
    match = _VEC_DIMS_RE.search(create_sql)
    return int(match.group(1)) if match else None


def _warn_degraded_once(reason: str) -> None:
    """Emit the one-time visible degradation warning (stderr + log)."""
    global _DEGRADED_WARNED
    if _DEGRADED_WARNED:
        return
    _DEGRADED_WARNED = True
    msg = (
        f"[arka:kb-degraded] semantic search unavailable ({reason}) — "
        "results are keyword matches, NOT similarity-ranked. "
        "Fix: pip install fastembed sqlite-vec (or: npx arkaos doctor)."
    )
    try:
        sys.stderr.write(msg + "\n")
    except OSError:
        pass
    logger.warning(msg)


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
        self._vec_dims = embedding_dims()  # derived from the active model
        if self._vec_available:
            try:
                stored = self._stored_vec_dims()
                if stored is not None and stored != self._vec_dims:
                    # An existing index was built with a different model
                    # dimension. NEVER corrupt it — keep the stored dim
                    # and let dimension guards route mismatched vectors
                    # to the degraded path until the user re-indexes.
                    logger.warning(
                        "vec_chunks dimension %d differs from configured "
                        "embed model dimension %d — keeping the stored "
                        "index. Re-index (/arka index) to switch models.",
                        stored, self._vec_dims,
                    )
                    self._vec_dims = stored
                else:
                    self._db.execute(
                        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{self._vec_dims}])"
                    )
            except Exception:
                self._vec_available = False
        self._db.commit()

    def _stored_vec_dims(self) -> Optional[int]:
        """Dimension of an existing vec_chunks table, if any."""
        try:
            row = self._db.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'vec_chunks'"
            ).fetchone()
        except sqlite3.Error:
            return None
        return _parse_vec_dims(row["sql"] if row else None)

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

                # Dimension guard: a vector produced by a differently-sized
                # model must never be inserted into the vec0 table (it
                # would poison distance queries). The raw embedding is
                # still stored on the chunk row for a later re-index.
                if (
                    self._vec_available
                    and emb_blob
                    and len(embeddings[i]) == self._vec_dims
                ):
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
            if len(query_emb) != self._vec_dims:
                return self._keyword_search(
                    query, top_k,
                    reason="embed model dimension differs from the stored "
                           "index — re-index to switch models",
                )
            try:
                return self._vec_search(query_emb, top_k)
            except Exception:
                return self._keyword_search(query, top_k, reason="vector query failed")

        # Fallback: keyword search — labeled, never presented as semantic.
        return self._keyword_search(query, top_k, reason=self._degradation_reason(query_emb))

    def _degradation_reason(self, query_emb: Optional[list[float]]) -> str:
        if query_emb is None:
            return "fastembed missing or embedding failed"
        return vec_unavailable_reason() or "sqlite-vec unavailable"

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
                "retrieval": "semantic",
                "metadata": json.loads(r["metadata"]),
            }
            for r in rows
        ]

    def _keyword_search(self, query: str, top_k: int, reason: str = "") -> list[dict]:
        """Fallback keyword search when semantic retrieval is unavailable.

        HONESTY CONTRACT (PR-3 v4.1): these results are substring matches,
        not similarity-ranked. ``score`` is None (there is no similarity)
        and ``retrieval`` is ``"keyword-degraded"`` so every consumer can
        label them. The previous behaviour — a hardcoded fake ``0.5``
        score — silently impersonated semantic search.
        """
        words = query.lower().split()[:5]  # Max 5 keywords
        if not words:
            return []

        _warn_degraded_once(reason or "semantic retrieval unavailable")

        # Placeholders and params MUST come from the same capped list —
        # previously a 6+ word query produced more `?` than bindings.
        conditions = " OR ".join(["lower(text) LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]

        rows = self._db.execute(
            f"SELECT text, heading, source, metadata FROM chunks WHERE {conditions} LIMIT ?",
            params + [top_k],
        ).fetchall()

        return [
            {
                "text": r["text"],
                "heading": r["heading"],
                "source": r["source"],
                "score": None,  # keyword match — NO similarity score exists
                "retrieval": "keyword-degraded",
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
        from core.knowledge.embedder import is_available as _embedder_available

        total = self._db.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()["cnt"]
        sources = self._db.execute("SELECT COUNT(DISTINCT source) as cnt FROM chunks").fetchone()["cnt"]
        semantic = self._vec_available and _embedder_available()
        return {
            "total_chunks": total,
            "total_files": sources,
            "vec_available": self._vec_available,
            "retrieval_mode": "semantic" if semantic else "keyword-degraded",
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

    def distinct_sources(self) -> list[str]:
        """Return the distinct non-empty source strings, noisiest first.

        Read-only reverse-lookup helper: the dashboard only has a
        sha1-based source_id and must recover the raw source string to
        serve chunks-only (pre-registry) sources. Reuses the same SELECT
        shape as :meth:`list_sources`.
        """
        rows = self._db.execute(
            "SELECT source, COUNT(*) AS chunks FROM chunks "
            "WHERE source IS NOT NULL AND source != '' "
            "GROUP BY source ORDER BY chunks DESC"
        ).fetchall()
        return [r["source"] for r in rows]

    def chunks_for_source(self, source: str) -> list[dict]:
        """Return all chunks for a source as text/heading/metadata dicts.

        Ordered by ``id`` ASC (insertion / ingest order) so callers that
        re-join the text — e.g. :meth:`transcript_for_source` — read the
        chunks back in their original sequence.
        """
        rows = self._db.execute(
            "SELECT text, heading, metadata FROM chunks "
            "WHERE source = ? ORDER BY id",
            (source,),
        ).fetchall()
        return [
            {
                "text": r["text"],
                "heading": r["heading"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            }
            for r in rows
        ]

    def transcript_for_source(self, source: str) -> str:
        """Reconstruct a source's transcript from its indexed chunks.

        Read-only. Joins the chunk texts (in ingest order, via
        :meth:`chunks_for_source`) via :func:`~core.knowledge.chunker.stitch_chunks`,
        which dedupes the token-overlap window the chunker keeps between
        consecutive chunks so the seams don't repeat ~50 tokens of text.
        Returns "" when the source has no chunks. Used to surface a transcript
        for legacy sources ingested before the SourceRegistry, which have
        chunks but no stored transcript.
        """
        from core.knowledge.chunker import stitch_chunks

        chunks = self.chunks_for_source(source)
        return stitch_chunks([c["text"] for c in chunks])

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
