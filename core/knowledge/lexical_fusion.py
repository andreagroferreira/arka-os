"""Fuse the lexical ranking into the KB layer's vector ranking.

Kept out of `layers_kb.py` on purpose: the patch that installs this into
production is then a three-line call plus an import, which survives an
upstream refactor of the surrounding method far better than a fifty-line
inline edit would.

Everything here is fail-open. If the lexical index is missing, stale,
unreadable, or the SQLite build has no FTS5, `fuse` returns the vector
notes untouched and the layer behaves exactly as it did before.

Disable at runtime with ARKA_KB_LEXICAL=0.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def enabled() -> bool:
    return os.environ.get("ARKA_KB_LEXICAL", "1").strip().lower() not in (
        "0", "false", "no", "off")


def _db_path(store) -> str:
    return str(getattr(store, "_db_path", "") or "")


def _chunk_for(db_path: str, source: str) -> tuple[str, dict]:
    """Best-effort (text, metadata) for a source the vector search missed."""
    try:
        con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro",
                              uri=True)
        row = con.execute(
            "select text, metadata from chunks where source = ? limit 1",
            (source,)).fetchone()
        con.close()
    except Exception:                                   # noqa: BLE001
        return "", {}
    if not row:
        return "", {}
    metadata = {}
    if row[1]:
        try:
            import json
            parsed = json.loads(row[1])
            metadata = parsed if isinstance(parsed, dict) else {}
        except Exception:                               # noqa: BLE001
            metadata = {}
    return row[0] or "", metadata


def fuse(store, prompt: str, notes: list[dict], max_notes: int,
         note_builder) -> list[dict]:
    """Vector notes reordered by RRF against the lexical ranking.

    `notes` are the entries the layer already built from its vector hits.
    Sources the lexical index found and the vector search did not are
    appended as new entries with score 0.0 — they are real matches on a
    different signal, not weak semantic ones, and scoring them on a
    similarity scale they never competed on would be a lie.
    """
    if not enabled():
        return notes
    try:
        from core.knowledge import lexical
    except Exception:                                   # noqa: BLE001
        return notes

    db_path = _db_path(store)
    if not db_path or not Path(db_path).is_file():
        return notes

    try:
        lexical_sources = lexical.search(db_path, prompt, top_k=max_notes * 4)
    except Exception:                                   # noqa: BLE001
        return notes
    if not lexical_sources:
        return notes

    by_source: dict[str, dict] = {}
    vector_ranking: list[str] = []
    for note in notes:
        source = str(note.get("path") or "")
        if source and source not in by_source:
            by_source[source] = note
            vector_ranking.append(source)

    try:
        fused = lexical.rrf([vector_ranking, lexical_sources],
                            top_k=max_notes * 2)
    except Exception:                                   # noqa: BLE001
        return notes

    out: list[dict] = []
    for source in fused:
        note = by_source.get(source)
        if note is None:
            text, metadata = _chunk_for(db_path, source)
            if not text:
                continue
            hit = {"source": source, "text": text, "metadata": metadata,
                   "score": 0.0, "heading": Path(source).stem}
            try:
                note = note_builder(hit)
            except Exception:                           # noqa: BLE001
                continue
        out.append(note)
    # Never return fewer notes than the vector path alone would have: the
    # lexical signal is here to add reach, and a bug in it must not be
    # able to subtract from what already worked.
    return out if len(out) >= len(notes) else notes
