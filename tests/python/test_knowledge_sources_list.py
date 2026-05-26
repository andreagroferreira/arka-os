"""Tests for VectorStore.list_sources + /api/knowledge/sources (PR88c)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path):
    from core.knowledge.vector_store import VectorStore
    db = tmp_path / "kb.db"
    return VectorStore(db)


def _insert_chunk(store, source: str, text: str = "x") -> None:
    """Insert directly via SQL to skip the embedding pipeline (fastembed
    is heavy and not needed for list_sources testing)."""
    with store._write_lock:
        store._db.execute(
            "INSERT INTO chunks (text, heading, source, file_hash, metadata, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (text, "", source, "", "{}", None),
        )
        store._db.commit()


def test_list_sources_empty(store):
    assert store.list_sources() == []


def test_list_sources_returns_distinct_with_counts(store):
    _insert_chunk(store, "https://example.com/a")
    _insert_chunk(store, "https://example.com/a")
    _insert_chunk(store, "https://example.com/b")
    rows = store.list_sources()
    assert len(rows) == 2
    by_source = {r["source"]: r["chunks"] for r in rows}
    assert by_source["https://example.com/a"] == 2
    assert by_source["https://example.com/b"] == 1


def test_list_sources_sorted_desc_by_chunks(store):
    _insert_chunk(store, "https://small")
    for _ in range(3):
        _insert_chunk(store, "https://big")
    rows = store.list_sources()
    assert rows[0]["source"] == "https://big"
    assert rows[1]["source"] == "https://small"


def test_list_sources_skips_blank_source(store):
    _insert_chunk(store, "")
    _insert_chunk(store, "https://example.com")
    rows = store.list_sources()
    assert len(rows) == 1
    assert rows[0]["source"] == "https://example.com"


def _load_dashboard_api():
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "dashboard-api.py"
    spec = importlib.util.spec_from_file_location("dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_endpoint_returns_payload_shape():
    api = _load_dashboard_api()
    res = api.knowledge_list_sources()
    assert "sources" in res
    assert "total" in res
    assert isinstance(res["sources"], list)
    assert isinstance(res["total"], int)
