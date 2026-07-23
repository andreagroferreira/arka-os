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
            {"type": "tool_use", "name": "mcp__megacorp-db__query",
             "input": {}},
        ]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text",
             "text": "Implemented the megacorp payment retry queue and fixed the error."},
        ]}},
    ]
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in lines), encoding="utf-8")
    return path


@pytest.fixture
def redaction_config(tmp_path, monkeypatch):
    """A REAL redaction config — the pipeline under test is the real one.

    _DEFAULT_CONFIG_PATH is an import-time constant (Path.home() frozen
    before this fixture's HOME override), so it is pointed explicitly at
    the isolated config.
    """
    from core.governance import leak_scanner

    cfg_dir = tmp_path / ".arkaos"
    cfg_dir.mkdir(exist_ok=True)
    cfg = cfg_dir / "redaction-clients.json"
    cfg.write_text(json.dumps({"clients": ["megacorp"]}), encoding="utf-8")
    monkeypatch.setattr(leak_scanner, "_DEFAULT_CONFIG_PATH", cfg)


@pytest.fixture
def fake_embed(monkeypatch):
    monkeypatch.setattr(
        turn_capture, "embed",
        lambda text: EmbeddingResult(vector=[1.0, 0.0], backend="fastembed",
                                     model="test-model", dims=2),
    )


def test_capture_full_pipeline_with_real_sanitizer(tmp_path, redaction_config,
                                                   fake_embed):
    """QG blocker B1/B2 regression: NO stubs on the sanitize path — a real
    redaction config, the real _sanitized_summary, a persisted str row."""
    transcript = _write_transcript(tmp_path)
    assert turn_capture.capture_turn("sess-1", str(transcript), "/repo/myproj") == 0
    store = SessionMemoryStore()
    records = store.recent()
    assert len(records) == 1
    record = records[0]
    assert isinstance(record.summary, str)
    assert "payment retry queue" in record.summary
    assert "megacorp" not in record.summary  # redacted, not passed through
    assert "[CLIENT-1]" in record.summary
    assert record.project_name == "myproj"
    assert "Write" in record.tools_used
    assert not any("megacorp" in t for t in record.tools_used)  # B4
    assert "/repo/core/api.py" in record.file_paths
    assert record.embedding_backend == "fastembed"
    assert record.importance > 0.5  # error keyword + Write tool
    cache = tmp_path / ".arkaos" / "context-cache" / "session-memory-sess-1.json"
    assert cache.exists()
    payload = json.loads(cache.read_text(encoding="utf-8"))
    assert payload["retrieval"] == "semantic"
    assert payload["version"] == 1
    assert payload["session_id"] == "sess-1"
    assert payload["dims"] == 2
    # Unique-tmp discipline: no stray tmp files left behind (B3).
    assert not list((tmp_path / ".arkaos" / "context-cache").glob("*.tmp"))


def test_cache_ranks_cross_session_neighbours(tmp_path, redaction_config,
                                              fake_embed):
    store = SessionMemoryStore()
    from core.memory.semantic_store import TurnRecord

    store.save(TurnRecord(id="prev", ts="2026-07-10T00:00:00+00:00",
                          session_id="old-sess", project_name="myproj",
                          summary="previous payment work", embedding=[1.0, 0.0],
                          embedding_backend="fastembed",
                          embedding_model="test-model", dims=2))
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-2", str(transcript), "/repo/myproj")
    payload = json.loads(
        (tmp_path / ".arkaos" / "context-cache" / "session-memory-sess-2.json")
        .read_text(encoding="utf-8")
    )
    assert len(payload["items"]) == 1
    assert payload["items"][0]["summary"] == "previous payment work"
    assert payload["items"][0]["retrieval"] == "semantic"


def test_sanitizer_missing_refuses_text(tmp_path, monkeypatch, fake_embed):
    """No redaction config -> the REAL refusal branch fires: summary and
    paths refused; mcp tool server segments stripped. The import-time
    _DEFAULT_CONFIG_PATH is pinned to an absent file for determinism
    (the operator's real machine HAS a config)."""
    from core.governance import leak_scanner

    monkeypatch.setattr(
        leak_scanner, "_DEFAULT_CONFIG_PATH",
        tmp_path / ".arkaos" / "redaction-clients.json",  # does not exist
    )
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-3", str(transcript), "/repo/myproj")
    record = SessionMemoryStore().recent()[0]
    assert record.summary == ""
    assert record.file_paths == []
    assert "Write" in record.tools_used  # generic names carry no client text
    assert "mcp__query" in record.tools_used  # server segment stripped (B4)
    assert not any("megacorp" in t for t in record.tools_used)


def test_degraded_embedding_labeled(tmp_path, redaction_config, monkeypatch):
    monkeypatch.setattr(turn_capture, "embed", lambda text: EmbeddingResult())
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-4", str(transcript), "/repo/myproj")
    record = SessionMemoryStore().recent()[0]
    assert record.embedding is None
    assert record.embedding_backend == "none"
    payload = json.loads(
        (tmp_path / ".arkaos" / "context-cache" / "session-memory-sess-4.json")
        .read_text(encoding="utf-8")
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
        json.dumps({"memory": {"sessionMemory": False}}), encoding="utf-8"
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


# ─── Cross-runtime capture (opencode transcript-free path) ────────────


def test_capture_turn_tags_claude_runtime(tmp_path, redaction_config, fake_embed):
    transcript = _write_transcript(tmp_path)
    turn_capture.capture_turn("sess-cl", str(transcript), "/repo/myproj")
    record = SessionMemoryStore().recent()[0]
    assert record.runtime == "claude"


def test_capture_text_turn_tags_opencode_runtime(tmp_path, redaction_config,
                                                 fake_embed):
    assert turn_capture.capture_text_turn(
        "sess-oc", "Implemented the megacorp retry queue from opencode.",
        "/repo/myproj", "opencode",
    ) == 0
    record = SessionMemoryStore().recent()[0]
    assert record.runtime == "opencode"
    assert record.project_name == "myproj"
    assert "retry queue" in record.summary
    assert "megacorp" not in record.summary  # same sanitizer pipeline
    assert record.embedding_backend == "fastembed"


def test_capture_text_turn_empty_text_noop(tmp_path):
    assert turn_capture.capture_text_turn("sess-oc", "   ", "/repo/myproj") == 0
    assert not (tmp_path / "sm.db").exists()


def test_capture_text_turn_respects_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_SESSION_MEMORY", "0")
    assert turn_capture.capture_text_turn("s", "real text", "/repo/p") == 0
    assert not (tmp_path / "sm.db").exists()


def test_cli_capture_text_reads_stdin(tmp_path, redaction_config, fake_embed,
                                      monkeypatch):
    monkeypatch.setattr(
        "sys.stdin", type("S", (), {"read": lambda s: "did the thing from stdin"})()
    )
    assert turn_capture.main(
        ["capture-text", "sess-cli", "/repo/myproj", "opencode"]
    ) == 0
    record = SessionMemoryStore().recent()[0]
    assert record.runtime == "opencode"
    assert record.summary == "did the thing from stdin"


def test_cli_capture_text_usage_error():
    assert turn_capture.main(["capture-text", "only-two"]) == 2


# ─── F1-A4: nightly maintenance mode ──────────────────────────────────


def test_maintenance_backfills_prunes_and_vacuums(tmp_path, monkeypatch):
    from core.memory.semantic_store import TurnRecord

    store = SessionMemoryStore()
    store.save(TurnRecord(id="old", ts="2020-01-01T00:00:00+00:00",
                          session_id="s", summary="ancient row"))
    store.save(TurnRecord(id="pending", ts="2026-07-11T00:00:00+00:00",
                          session_id="s", summary="needs embedding"))
    monkeypatch.setattr(
        turn_capture, "embed",
        lambda text: EmbeddingResult(vector=[1.0], backend="fastembed",
                                     model="m", dims=1),
    )
    assert turn_capture.run_maintenance() == 0
    records = {r.id: r for r in SessionMemoryStore().recent(limit=50)}
    assert "old" not in records  # pruned (>90d)
    assert records["pending"].embedding_backend == "fastembed"  # backfilled


def test_maintenance_stops_on_degraded_backend(tmp_path, monkeypatch):
    """A dead embedding backend must never spin the batch loop."""
    from core.memory.semantic_store import TurnRecord

    store = SessionMemoryStore()
    store.save(TurnRecord(id="pending", ts="2026-07-11T00:00:00+00:00",
                          session_id="s", summary="needs embedding"))
    calls = []
    monkeypatch.setattr(
        turn_capture, "embed",
        lambda text: calls.append(1) or EmbeddingResult(),
    )
    assert turn_capture.run_maintenance() == 0
    assert len(calls) == 1  # bailed on first degraded result


def test_maintenance_respects_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_SESSION_MEMORY", "0")
    assert turn_capture.run_maintenance() == 0
    assert not (tmp_path / "sm.db").exists()


def test_maintenance_cli_entry(tmp_path):
    assert turn_capture.main(["maintenance"]) == 0
