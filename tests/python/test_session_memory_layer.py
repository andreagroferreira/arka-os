"""Tests for core.synapse.session_memory_layer (F1-A3)."""

from __future__ import annotations

import json

import pytest

from core.memory.semantic_store import SessionMemoryStore, TurnRecord
from core.synapse.layers import PromptContext
from core.synapse.session_memory_layer import SessionMemoryLayer


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARKA_SESSION_MEMORY_DB", str(tmp_path / "sm.db"))
    monkeypatch.delenv("ARKA_BYPASS_L95", raising=False)
    # _CONFIG_PATH is an import-time constant — pin it to isolated HOME.
    from core.synapse import session_memory_layer as sml

    monkeypatch.setattr(sml, "_CONFIG_PATH", tmp_path / ".arkaos" / "config.json")
    return tmp_path


def _write_cache(tmp_path, session_id: str, items: list[dict], version: int = 1):
    cache_dir = tmp_path / ".arkaos" / "context-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"session-memory-{session_id}.json").write_text(
        json.dumps({"version": version, "session_id": session_id,
                    "retrieval": "semantic", "items": items})
    )


def _ctx(prompt="payment retry design", session_id="sess-1", project=""):
    return PromptContext(user_input=prompt, project_name=project,
                         extra={"session_id": session_id})


def test_inert_when_store_and_cache_absent():
    result = SessionMemoryLayer().compute(_ctx())
    assert result.content == ""
    assert result.tokens_est == 0


def test_cache_items_injected_with_asof_label(tmp_path):
    _write_cache(tmp_path, "sess-1", [
        {"summary": "built the retry queue", "project_name": "proj",
         "ts": "2026-07-10T00:00:00+00:00", "score": 0.91, "retrieval": "semantic"},
    ])
    result = SessionMemoryLayer().compute(_ctx())
    assert result.tag == "[session-memory:1]"
    assert "semantic 0.91 asof-last-turn" in result.content
    assert "built the retry queue" in result.content


def test_live_keyword_hits_labeled_honestly(tmp_path):
    store = SessionMemoryStore()
    store.save(TurnRecord(id="t1", ts="2026-07-10T00:00:00+00:00",
                          session_id="old", project_name="proj",
                          summary="payment retry queue implementation"))
    result = SessionMemoryLayer().compute(_ctx(project="proj"))
    assert "keyword — NOT semantic similarity" in result.content
    assert "payment retry queue" in result.content


def test_cache_and_keyword_deduplicated(tmp_path):
    _write_cache(tmp_path, "sess-1", [
        {"summary": "payment retry queue implementation", "project_name": "proj",
         "ts": "2026-07-10T00:00:00+00:00", "score": 0.9, "retrieval": "semantic"},
    ])
    store = SessionMemoryStore()
    store.save(TurnRecord(id="t1", ts="2026-07-10T00:00:00+00:00",
                          session_id="old", project_name="proj",
                          summary="payment retry queue implementation"))
    result = SessionMemoryLayer().compute(_ctx(project="proj"))
    assert result.content.count("payment retry queue implementation") == 1


def test_unknown_cache_version_ignored(tmp_path):
    _write_cache(tmp_path, "sess-1", [
        {"summary": "future format", "score": 0.9, "retrieval": "semantic"},
    ], version=99)
    result = SessionMemoryLayer().compute(_ctx())
    assert result.content == ""


def test_env_bypass_disables_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_L95", "1")
    _write_cache(tmp_path, "sess-1", [
        {"summary": "anything", "score": 0.9, "retrieval": "semantic"},
    ])
    result = SessionMemoryLayer().compute(_ctx())
    assert result.content == ""


def test_config_flag_disables_layer(tmp_path):
    cfg = tmp_path / ".arkaos" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"synapse": {"l95SessionMemory": False}}))
    _write_cache(tmp_path, "sess-1", [
        {"summary": "anything", "score": 0.9, "retrieval": "semantic"},
    ])
    result = SessionMemoryLayer().compute(_ctx())
    assert result.content == ""


def test_empty_prompt_is_inert(tmp_path):
    _write_cache(tmp_path, "sess-1", [
        {"summary": "anything", "score": 0.9, "retrieval": "semantic"},
    ])
    result = SessionMemoryLayer().compute(_ctx(prompt=""))
    assert result.content == ""


def test_item_cap_and_token_budget(tmp_path):
    _write_cache(tmp_path, "sess-1", [
        {"summary": f"cached item {i} " + "x" * 300, "project_name": "proj",
         "ts": "2026-07-10T00:00:00+00:00", "score": 0.9, "retrieval": "semantic"}
        for i in range(10)
    ])
    result = SessionMemoryLayer().compute(_ctx())
    assert result.content.count("\n") <= 4  # max 5 items
    assert result.tokens_est < 250


def test_registered_in_default_engine():
    from core.synapse.engine import create_default_engine

    engine = create_default_engine()
    ids = [layer.id for layer in engine._layers]
    assert "L9.5" in ids
