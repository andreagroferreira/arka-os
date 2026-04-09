"""VectorWriter — stores KnowledgeEntry objects in SQLite with optional embeddings.

Graceful degradation: if fastembed is not installed, falls back to text-based
keyword matching for search.
"""

import json
import math
import sqlite3
import struct
from typing import Optional

from core.cognition.memory.schemas import KnowledgeEntry

# Optional embedder — imported lazily to survive missing fastembed
try:
    from core.knowledge import embedder as _embedder
except ImportError:
    _embedder = None  # type: ignore[assignment]


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id              TEXT PRIMARY KEY,
    entry_id        TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    category        TEXT NOT NULL,
    tags            TEXT NOT NULL,
    stacks          TEXT NOT NULL,
    content         TEXT NOT NULL,
    source_project  TEXT NOT NULL,
    applicable_to   TEXT NOT NULL,
    confidence      REAL NOT NULL,
    times_used      INTEGER NOT NULL,
    embedding       BLOB,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
)
"""

_CREATE_IDX_ENTRY_ID = "CREATE INDEX IF NOT EXISTS idx_entry_id ON knowledge_entries (entry_id)"
_CREATE_IDX_CATEGORY = "CREATE INDEX IF NOT EXISTS idx_category ON knowledge_entries (category)"
_CREATE_IDX_APPLICABLE = "CREATE INDEX IF NOT EXISTS idx_applicable_to ON knowledge_entries (applicable_to)"

_UPSERT = """
INSERT INTO knowledge_entries
    (id, entry_id, title, category, tags, stacks, content, source_project,
     applicable_to, confidence, times_used, embedding, created_at, updated_at)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(entry_id) DO UPDATE SET
    title          = excluded.title,
    category       = excluded.category,
    tags           = excluded.tags,
    stacks         = excluded.stacks,
    content        = excluded.content,
    source_project = excluded.source_project,
    applicable_to  = excluded.applicable_to,
    confidence     = excluded.confidence,
    times_used     = excluded.times_used,
    embedding      = excluded.embedding,
    updated_at     = excluded.updated_at
"""


def _pack_embedding(floats: list[float]) -> bytes:
    """Pack a list of floats into a compact binary blob."""
    return struct.pack(f"{len(floats)}f", *floats)


def _unpack_embedding(blob: bytes) -> list[float]:
    """Unpack a binary blob back into a list of floats."""
    count = len(blob) // struct.calcsize("f")
    return list(struct.unpack(f"{count}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _text_score(query: str, row: dict) -> int:
    """Count keyword matches in title, tags, and content."""
    terms = query.lower().split()
    haystack = " ".join([
        row["title"],
        " ".join(json.loads(row["tags"])),
        row["content"],
    ]).lower()
    return sum(1 for term in terms if term in haystack)


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to the public result dict."""
    return {
        "entry_id": row["entry_id"],
        "title": row["title"],
        "category": row["category"],
        "tags": json.loads(row["tags"]),
        "stacks": json.loads(row["stacks"]),
        "content": row["content"],
        "source_project": row["source_project"],
        "applicable_to": row["applicable_to"],
        "confidence": row["confidence"],
        "times_used": row["times_used"],
    }


class VectorWriter:
    """Writes KnowledgeEntry objects to SQLite, optionally with embeddings."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._bootstrap()

    # --- Setup ---

    def _bootstrap(self) -> None:
        cur = self._conn.cursor()
        cur.execute(_CREATE_TABLE)
        cur.execute(_CREATE_IDX_ENTRY_ID)
        cur.execute(_CREATE_IDX_CATEGORY)
        cur.execute(_CREATE_IDX_APPLICABLE)
        self._conn.commit()

    # --- Public API ---

    def write(self, entry: KnowledgeEntry) -> bool:
        """UPSERT a KnowledgeEntry. Returns True on success."""
        embedding_blob: Optional[bytes] = None
        vector = self._embed(entry)
        if vector is not None:
            embedding_blob = _pack_embedding(vector)

        self._conn.execute(
            _UPSERT,
            (
                entry.id,
                entry.id,              # entry_id mirrors id (stable natural key)
                entry.title,
                entry.category,
                json.dumps(entry.tags),
                json.dumps(entry.stacks),
                entry.content,
                entry.source_project,
                entry.applicable_to,
                entry.confidence,
                entry.times_used,
                embedding_blob,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
            ),
        )
        self._conn.commit()
        return True

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search entries. Semantic when embeddings available, text fallback otherwise."""
        rows = self._conn.execute(
            "SELECT * FROM knowledge_entries"
        ).fetchall()

        if not rows:
            return []

        use_semantic = self._can_embed() and any(r["embedding"] is not None for r in rows)

        if use_semantic:
            return self._semantic_search(query, rows, top_k)
        return self._text_search(query, rows, top_k)

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # --- Internal helpers ---

    def _embed(self, entry: KnowledgeEntry) -> Optional[list[float]]:
        """Try to embed the entry's title + content. Returns None on failure."""
        if not self._can_embed():
            return None
        text = f"{entry.title}\n{entry.content}"
        return _embedder.embed(text)  # type: ignore[union-attr]

    def _can_embed(self) -> bool:
        return _embedder is not None and _embedder.is_available()

    def _semantic_search(
        self, query: str, rows: list[sqlite3.Row], top_k: int
    ) -> list[dict]:
        query_vec = _embedder.embed(query)  # type: ignore[union-attr]
        if query_vec is None:
            return self._text_search(query, rows, top_k)

        scored = []
        for row in rows:
            if row["embedding"] is None:
                continue
            entry_vec = _unpack_embedding(row["embedding"])
            score = _cosine_similarity(query_vec, entry_vec)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [_row_to_dict(r) for _, r in scored[:top_k]]

    def _text_search(
        self, query: str, rows: list[sqlite3.Row], top_k: int
    ) -> list[dict]:
        scored = []
        for row in rows:
            score = _text_score(query, dict(row))
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [_row_to_dict(r) for _, r in scored[:top_k]]
