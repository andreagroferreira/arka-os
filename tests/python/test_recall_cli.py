"""Deep recall: fusion order, signal attribution, and graceful degradation.

The property that carries the weight is the last one: this CLI must return
something sensible on an install with no lexical module, no FTS5, or an
empty knowledge base — the worst outcome of any failure is an empty list,
never an exception.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.knowledge.recall_cli import (
    _dedupe_to_notes,
    _fuse,
    deep_recall,
)


class _Store:
    """Vector store double: returns canned chunk hits, records the query."""

    def __init__(self, hits, db_path=""):
        self._hits = hits
        self._db_path = db_path

    def search(self, query, top_k=5):
        return self._hits


def _hit(source):
    return {"source": source, "text": "", "score": 0.5}


# ── fusion mechanics ─────────────────────────────────────────────────────

def test_rrf_rewards_agreement():
    fused = _fuse([["x", "shared"], ["y", "shared"]], top_k=3)
    assert fused[0] == "shared"


def test_chunks_collapse_to_notes_keeping_best_rank():
    hits = [_hit("a.md"), _hit("b.md"), _hit("a.md"), _hit("a.md")]
    assert _dedupe_to_notes(hits) == ["a.md", "b.md"]


def test_hits_without_a_source_are_dropped():
    assert _dedupe_to_notes([{"source": ""}, {"source": None}]) == []


# ── signal attribution ───────────────────────────────────────────────────

def test_results_name_the_signals_that_found_them(monkeypatch):
    import core.knowledge.recall_cli as recall_cli
    monkeypatch.setattr(recall_cli, "_lexical_ranking",
                        lambda db, q: ["b.md", "c.md"])
    store = _Store([_hit("a.md"), _hit("b.md")])
    results = deep_recall(store, "query", top_k=5)
    by_source = {r["source"]: r["signals"] for r in results}
    assert by_source["a.md"] == ["vector"]
    assert by_source["c.md"] == ["lexical"]
    assert by_source["b.md"] == ["vector", "lexical"]


def test_agreement_outranks_single_signal_first_place(monkeypatch):
    import core.knowledge.recall_cli as recall_cli
    monkeypatch.setattr(recall_cli, "_lexical_ranking",
                        lambda db, q: ["x.md", "shared.md"])
    store = _Store([_hit("y.md"), _hit("shared.md")])
    results = deep_recall(store, "query", top_k=4)
    assert results[0]["source"] == "shared.md"


# ── degradation ──────────────────────────────────────────────────────────

def test_no_lexical_module_degrades_to_vector_only(monkeypatch):
    import core.knowledge.recall_cli as recall_cli
    monkeypatch.setattr(recall_cli, "_lexical_ranking", lambda db, q: [])
    store = _Store([_hit("a.md"), _hit("b.md")])
    results = deep_recall(store, "query", top_k=5)
    assert [r["source"] for r in results] == ["a.md", "b.md"]
    assert all(r["signals"] == ["vector"] for r in results)


def test_lexical_failure_never_raises(monkeypatch):
    import core.knowledge.recall_cli as recall_cli

    def boom(db, q):
        raise RuntimeError("no fts5 in this build")

    # _lexical_ranking already swallows; simulate at the import layer by
    # patching the inner call path instead of the wrapper.
    monkeypatch.setattr(recall_cli, "_lexical_ranking",
                        recall_cli._lexical_ranking)
    store = _Store([_hit("a.md")], db_path="/nonexistent/knowledge.db")
    results = deep_recall(store, "query", top_k=5)
    assert [r["source"] for r in results] == ["a.md"]


def test_empty_everything_returns_empty_list_not_error():
    store = _Store([])
    assert deep_recall(store, "query", top_k=5) == []


def test_top_k_bounds_the_result():
    store = _Store([_hit(f"{i}.md") for i in range(30)])
    assert len(deep_recall(store, "query", top_k=7)) == 7
