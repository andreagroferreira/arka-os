"""Lexical retrieval (FTS5) and its fusion into the KB context layer.

The load-bearing property under test is not ranking quality — it is that
every failure mode leaves the vector path untouched. A knowledge base
without a lexical index, a stale index, a SQLite build without FTS5 and a
corrupt sidecar must all behave exactly like the layer did before this
module existed.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.knowledge import lexical
from core.knowledge.lexical_fusion import fuse

requires_fts5 = pytest.mark.skipif(
    not lexical.fts5_available(),
    reason="this SQLite build has no FTS5; the layer degrades by design",
)


def _knowledge_db(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    db_path = tmp_path / "knowledge.db"
    con = sqlite3.connect(db_path)
    con.execute("create table chunks (source text, text text, metadata text)")
    con.executemany("insert into chunks (source, text) values (?, ?)", rows)
    con.commit()
    con.close()
    return db_path


ROWS = [
    ("/vault/memoria.md", "memoria e recuperacao de notas no vault"),
    ("/vault/deploy.md", "continuous deployment pipeline and rollback"),
    ("/vault/rede.md", "configuracao de rede e certificados"),
]


# ── portability ──────────────────────────────────────────────────────────

def test_fts5_probe_never_raises():
    assert lexical.fts5_available() in (True, False)


def test_build_reports_failure_instead_of_raising(tmp_path):
    built, message = lexical.build(tmp_path / "does-not-exist.db")
    assert built is False
    assert message


@requires_fts5
def test_paths_with_percent_and_spaces(tmp_path):
    """A raw f-string URI decodes '%' as an escape and breaks here."""
    awkward = tmp_path / "pasta com % e espacos"
    awkward.mkdir()
    db_path = _knowledge_db(awkward, ROWS)
    assert lexical.build(db_path)[0] is True
    assert lexical.search(db_path, "memoria recuperacao")


# ── retrieval behaviour ──────────────────────────────────────────────────

@requires_fts5
def test_diacritics_fold_both_ways(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    unaccented = lexical.search(db_path, "memoria recuperacao")
    accented = lexical.search(db_path, "memória e recuperação")
    assert unaccented == accented
    assert unaccented


@requires_fts5
def test_stopwords_do_not_drag_in_everything(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    # 'como' and 'para' appear nowhere; a query made only of stopwords
    # must match nothing rather than OR-matching the whole corpus.
    assert lexical.search(db_path, "como e que para com isso") == []


@requires_fts5
def test_search_returns_sources_in_rank_order(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    hits = lexical.search(db_path, "deployment rollback pipeline")
    assert hits and hits[0] == "/vault/deploy.md"


# ── staleness ────────────────────────────────────────────────────────────

def test_missing_index_is_stale_and_searches_empty(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    assert lexical.is_stale(db_path) is True
    assert lexical.search(db_path, "memoria") == []


@requires_fts5
def test_index_older_than_corpus_is_ignored(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    assert lexical.search(db_path, "memoria recuperacao")
    os.utime(db_path, None)  # corpus moves on, index does not
    assert lexical.is_stale(db_path) is True
    assert lexical.search(db_path, "memoria recuperacao") == []


@requires_fts5
def test_failed_build_leaves_no_partial_index(tmp_path):
    db_path = tmp_path / "knowledge.db"
    con = sqlite3.connect(db_path)
    con.execute("create table not_chunks (x text)")  # no chunks table
    con.commit()
    con.close()
    built, _ = lexical.build(db_path)
    assert built is False
    assert not lexical.index_path(db_path).exists()


# ── fusion ───────────────────────────────────────────────────────────────

class _Store:
    def __init__(self, db_path):
        self._db_path = str(db_path)


def _note(path: str, score: float = 0.9) -> dict:
    return {"title": Path(path).stem, "path": path, "excerpt": "",
            "relates": [], "score": score, "inferred": False}


def _builder(hit: dict) -> dict:
    return _note(hit["source"], hit.get("score", 0.0))


def test_fusion_passes_through_without_an_index(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    notes = [_note("/vault/rede.md")]
    assert fuse(_Store(db_path), "memoria", notes, 5, _builder) == notes


def test_fusion_passes_through_when_disabled(tmp_path, monkeypatch):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    monkeypatch.setenv("ARKA_KB_LEXICAL", "0")
    notes = [_note("/vault/rede.md")]
    assert fuse(_Store(db_path), "memoria recuperacao", notes, 5, _builder) == notes


@requires_fts5
def test_fusion_adds_a_note_the_vector_path_missed(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    notes = [_note("/vault/rede.md")]
    fused = fuse(_Store(db_path), "memoria recuperacao", notes, 5, _builder)
    paths = [n["path"] for n in fused]
    assert "/vault/memoria.md" in paths
    assert "/vault/rede.md" in paths, "fusion must never drop a vector note"


@requires_fts5
def test_fusion_never_returns_fewer_notes_than_it_received(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.build(db_path)
    notes = [_note(f"/vault/only-vector-{i}.md") for i in range(4)]
    fused = fuse(_Store(db_path), "memoria recuperacao", notes, 5, _builder)
    assert len(fused) >= len(notes)


def test_fusion_survives_a_corrupt_sidecar(tmp_path):
    db_path = _knowledge_db(tmp_path, ROWS)
    lexical.index_path(db_path).write_bytes(b"not a database at all")
    notes = [_note("/vault/rede.md")]
    assert fuse(_Store(db_path), "memoria", notes, 5, _builder) == notes


def test_rrf_rewards_agreement_across_signals():
    a = ["x", "top-of-a", "shared"]
    b = ["y", "top-of-b", "shared"]
    ranked = lexical.rrf([a, b], top_k=3)
    assert ranked[0] == "shared", (
        "a note both retrievers rank mid should beat one that only a "
        "single retriever ranks first"
    )
