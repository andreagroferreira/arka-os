"""Tests for core.memory.turn_capture (F1-A2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.knowledge.embedding_backends import EmbeddingResult
from core.memory import turn_capture
from core.memory.semantic_store import SessionMemoryStore


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARKA_SESSION_MEMORY_DB", str(tmp_path / "sm.db"))
    monkeypatch.delenv("ARKA_SESSION_MEMORY", raising=False)
    return tmp_path


def _write_transcript(tmp_path: Path) -> Path:
    lines = [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Write",
             "input": {"file_path": "/repo/core/api.py"}},
        ]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text",
             "text": "Implemented the payment retry queue and fixed the error."},
        ]}},
    ]
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in lines))
    return path


@pytest.fixture
def sanitizer_ok(monkeypatch):
    monkeypatch.setattr(turn_capture, "_sanitized_summary",
                        lambda text: (text[:600], True))


@pytest.fixture
def fake_embed(monkeypatch):
    monkeypatch.setattr(
        turn_capture, "embed",
        lambda text: EmbeddingResult(vector=[1.0, 0.0], backend="fastembed",
                                     model="test-model", dims=2),
    )


def test_capture_full_pipeline(tmp_path, sanitizer_ok, fake_embed):
    transcript = _write_transcript(tmp_path)
    assert turn_capture.capture_turn("sess-1", str(transcript), "/repo/myproj") == 0
    store = SessionMemoryStore()
    records = store.recent()
    assert len(records) == 1
    record = records[0]
    assert "payment retry queue" in record.summary
    assert record.project_name == "myproj"
    assert "Write" in record.tools_used
    assert "/repo/core/api.py" in record.file_paths
    assert record.embedding_backend == "fastembed"
    assert record.importance > 0.5  # error keyword + Write tool
    cache = tmp_path / ".arkaos" / "context-cache" / "session-memory-sess-1.json"
    assert cache.exists()
    payload = json.loads(cache.read_text())
    assert payload["retrieval"] == "semantic"


def test_cache_ranks_cross_session_neighbours(tmp_path, sanitizer_ok, fake_embed):
    store = SessionMemoryStore()
    from core.memory.semantic_store import TurnRecord

    store.save(TurnRecord(id="prev", ts="2026-07-10T00:00:00+00:00",
                          session_id="old-sess", project_name="myproj",
                          summary="previous payment work", embedding=[1.0, 0.0],
                          embedding_backend="fastembed", dims=2))
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-2", str(transcript), "/repo/myproj")
    payload = json.loads(
        (tmp_path / ".arkaos" / "context-cache" / "session-memory-sess-2.json")
        .read_text()
    )
    assert len(payload["items"]) == 1
    assert payload["items"][0]["summary"] == "previous payment work"
    assert payload["items"][0]["retrieval"] == "semantic"


def test_sanitizer_missing_refuses_text(tmp_path, monkeypatch, fake_embed):
    """No sanitizer config -> summary AND paths are refused (metadata only)."""
    monkeypatch.setattr(turn_capture, "_sanitized_summary", lambda t: ("", False))
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-3", str(transcript), "/repo/myproj")
    record = SessionMemoryStore().recent()[0]
    assert record.summary == ""
    assert record.file_paths == []
    assert record.tools_used == ["Write"]  # tool names carry no client text


def test_degraded_embedding_labeled(tmp_path, sanitizer_ok, monkeypatch):
    monkeypatch.setattr(turn_capture, "embed", lambda text: EmbeddingResult())
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-4", str(transcript), "/repo/myproj")
    record = SessionMemoryStore().recent()[0]
    assert record.embedding is None
    assert record.embedding_backend == "none"
    payload = json.loads(
        (tmp_path / ".arkaos" / "context-cache" / "session-memory-sess-4.json")
        .read_text()
    )
    assert payload["retrieval"] == "keyword-degraded"
    assert payload["items"] == []


def test_kill_switch_disables_capture(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_SESSION_MEMORY", "0")
    transcript = _write_transcript(tmp_path)
    assert turn_capture.capture_turn("sess-5", str(transcript), "") == 0
    assert not (tmp_path / "sm.db").exists()


def test_config_flag_disables_capture(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(
        json.dumps({"memory": {"sessionMemory": False}})
    )
    transcript = _write_transcript(tmp_path)
    assert turn_capture.capture_turn("sess-6", str(transcript), "") == 0
    assert not (tmp_path / "sm.db").exists()


def test_importance_heuristic():
    assert turn_capture._importance("all good", []) == 0.5
    assert turn_capture._importance("an error occurred", []) == pytest.approx(0.7)
    assert turn_capture._importance("verdict APPROVED", ["Write"]) == pytest.approx(0.75)
    assert turn_capture._importance("error verdict failed", ["Edit"]) == pytest.approx(0.95)


def test_cli_usage_and_missing_transcript(tmp_path):
    assert turn_capture.main([]) == 2
    assert turn_capture.main(["s", str(tmp_path / "missing.jsonl")]) == 0
