"""Tests for the turn-scoped Obsidian query marker in core.synapse.kb_cache.

Covers:
- record_obsidian_query atomic write
- Concurrent writers do not lose records
- Safe session id allowlist (path traversal defense)
- invalidate_obsidian_query idempotency
- Integration with the existing KBSessionCache is unchanged
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from core.synapse import kb_cache


@pytest.fixture(autouse=True)
def _isolate_marker_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "kb-query"))
    yield


def test_record_obsidian_query_writes_marker(tmp_path, monkeypatch):
    target = tmp_path / "markers"
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(target))
    kb_cache.record_obsidian_query("session-abc", "first query", hit_count=3)
    record = kb_cache.read_obsidian_query("session-abc")
    assert record is not None
    assert record["last_hit_count"] == 3
    assert record["queries"][0]["query"] == "first query"
    assert (target / "session-abc.json").exists()


def test_record_obsidian_query_appends_multiple(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    kb_cache.record_obsidian_query("sess", "q1", 1)
    kb_cache.record_obsidian_query("sess", "q2", 2)
    record = kb_cache.read_obsidian_query("sess")
    assert len(record["queries"]) == 2
    assert record["queries"][0]["query"] == "q1"
    assert record["queries"][1]["query"] == "q2"
    assert record["last_hit_count"] == 2


def test_record_obsidian_query_atomic_concurrent(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    # 16 concurrent writers — final file must be valid JSON, not truncated.
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            kb_cache.record_obsidian_query("sess-conc", f"q{i}", i)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    record = kb_cache.read_obsidian_query("sess-conc")
    assert record is not None
    # File is valid JSON (else read_obsidian_query would have returned None).
    assert isinstance(record["queries"], list)
    assert record["last_query_ts"] > 0


def test_record_obsidian_query_safe_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    # Path traversal attempts must be silently rejected.
    for bad in ("../evil", "a/b", "\x00null", "a" * 200, "", None):
        kb_cache.record_obsidian_query(bad, "q", 1)  # type: ignore[arg-type]
        assert kb_cache.read_obsidian_query(bad) is None  # type: ignore[arg-type]


def test_read_obsidian_query_returns_none_when_absent():
    assert kb_cache.read_obsidian_query("never-written") is None


def test_invalidate_obsidian_query_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    kb_cache.record_obsidian_query("sess-X", "q", 1)
    assert kb_cache.read_obsidian_query("sess-X") is not None
    kb_cache.invalidate_obsidian_query("sess-X")
    assert kb_cache.read_obsidian_query("sess-X") is None
    # Second call is a no-op, must not raise.
    kb_cache.invalidate_obsidian_query("sess-X")


def test_kb_query_marker_invalidated_on_new_turn(tmp_path, monkeypatch):
    """Semantic test: UserPromptSubmit invalidation wipes the marker."""
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    kb_cache.record_obsidian_query("sess-turn", "q", 5)
    assert kb_cache.obsidian_queried_this_turn("sess-turn") is True
    # Simulate UserPromptSubmit hook callback.
    kb_cache.invalidate_obsidian_query("sess-turn")
    assert kb_cache.obsidian_queried_this_turn("sess-turn") is False


def test_obsidian_queried_this_turn_defaults_false():
    assert kb_cache.obsidian_queried_this_turn("unseen") is False


def test_record_obsidian_query_caps_queries_per_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    for i in range(100):
        kb_cache.record_obsidian_query("cap", f"q{i}", 1)
    record = kb_cache.read_obsidian_query("cap")
    assert record is not None
    # Internal cap is 32; verify we never accumulate unbounded state.
    assert len(record["queries"]) <= 32


def test_record_obsidian_query_truncates_long_query(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    huge = "x" * 5000
    kb_cache.record_obsidian_query("trunc", huge, 1)
    record = kb_cache.read_obsidian_query("trunc")
    assert record is not None
    stored = record["queries"][0]["query"]
    assert len(stored) <= 512


def test_record_obsidian_query_non_int_hit_count(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "m"))
    kb_cache.record_obsidian_query("bad-hit", "q", hit_count="nope")  # type: ignore[arg-type]
    record = kb_cache.read_obsidian_query("bad-hit")
    assert record is not None
    assert record["last_hit_count"] == 0


def test_read_obsidian_query_malformed_file(tmp_path, monkeypatch):
    target = tmp_path / "m"
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(target))
    target.mkdir(parents=True, exist_ok=True)
    (target / "corrupt.json").write_text("{not json")
    assert kb_cache.read_obsidian_query("corrupt") is None


def test_existing_session_cache_unaffected(tmp_path):
    """Regression: the new marker APIs must not touch KBSessionCache files."""
    cache = kb_cache.KBSessionCache(
        session_id="regression", cache_dir=str(tmp_path / "session-cache")
    )
    cache.store("what is kb architecture", [{"text": "KB body", "source": "a.md"}])
    # Query marker write must not interfere with the session cache file.
    kb_cache.record_obsidian_query("regression", "what is kb", 1)
    assert cache.retrieve(query="what is kb architecture")
