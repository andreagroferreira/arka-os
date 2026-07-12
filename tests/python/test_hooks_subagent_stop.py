"""Tests for core.hooks.subagent_stop (F2-4)."""

from __future__ import annotations

import json

import pytest

from core.hooks import subagent_stop
from core.hooks.subagent_stop import main


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ARKA_SUBAGENT_QA", raising=False)
    # Pin the telemetry path into the isolated HOME.
    monkeypatch.setattr(
        subagent_stop, "_TELEMETRY",
        tmp_path / ".arkaos" / "telemetry" / "subagent-stop.jsonl",
    )
    return tmp_path


def _transcript(tmp_path, text, with_tool=False):
    # A real user message delimits the subagent's turn (phantom check
    # counts tool_use blocks AFTER the last real user message).
    lines = [{"type": "user", "message": {"role": "user", "content": "do the task"}}]
    if with_tool:
        lines.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Write", "input": {"file_path": "/x.py"}},
        ]}})
    lines.append({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text},
    ]}})
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines))
    return str(path)


def _telemetry(tmp_path):
    p = tmp_path / ".arkaos" / "telemetry" / "subagent-stop.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def test_persists_output_and_records_qa(tmp_path, monkeypatch):
    monkeypatch.setattr(subagent_stop, "_persist_output",
                        lambda *a: monkeypatch.setattr(
                            test_persists_output_and_records_qa, "_ran", True,
                            raising=False))
    transcript = _transcript(tmp_path, "Implemented the retry queue.", with_tool=True)
    assert main({"session_id": "s1", "subagent_type": "paulo",
                 "transcript_path": transcript}) == 0
    rows = _telemetry(tmp_path)
    assert len(rows) == 1
    assert rows[0]["agent_id"] == "paulo"
    assert rows[0]["mode"] == "warn"
    assert rows[0]["phantom"] == "pass"  # a Write tool_use is present


def test_phantom_action_flagged_and_nudged(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(subagent_stop, "_persist_output", lambda *a: None)
    # Deliverable-shaped ("implemented") AND a phantom claim ("I committed")
    # with NO tool call in the turn -> flagged + nudged.
    transcript = _transcript(
        tmp_path, "I committed the change and fixed the bug.", with_tool=False
    )
    assert main({"session_id": "s1", "subagent_type": "paulo",
                 "transcript_path": transcript}) == 0
    err = capsys.readouterr().err
    assert "[arka:subagent-qa]" in err
    assert "Quality Gate" in err
    rows = _telemetry(tmp_path)
    assert rows[0]["phantom"] == "phantom-action"
    assert rows[0]["deliverable"] is True


def test_no_nudge_when_not_deliverable(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(subagent_stop, "_persist_output", lambda *a: None)
    transcript = _transcript(tmp_path, "Here is a summary of the options.", with_tool=False)
    main({"session_id": "s1", "subagent_type": "analyst",
          "transcript_path": transcript})
    assert "[arka:subagent-qa]" not in capsys.readouterr().err


def test_qa_off_is_inert(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_SUBAGENT_QA", "off")
    transcript = _transcript(tmp_path, "Implemented X.", with_tool=False)
    assert main({"session_id": "s1", "transcript_path": transcript}) == 0
    assert _telemetry(tmp_path) == []


def test_unsafe_session_id_bails(tmp_path):
    assert main({"session_id": "../evil", "transcript_path": "x"}) == 0
    assert _telemetry(tmp_path) == []


def test_empty_transcript_no_record(tmp_path):
    assert main({"session_id": "s1", "transcript_path": ""}) == 0
    assert _telemetry(tmp_path) == []


def test_persist_sanitizes(tmp_path, monkeypatch):
    """The real persist path: sanitizer-missing => output omitted, but the
    AgentOutput row is still written (metadata-only, recipes precedent)."""
    from core.governance import leak_scanner

    monkeypatch.setattr(
        leak_scanner, "_DEFAULT_CONFIG_PATH",
        tmp_path / ".arkaos" / "redaction-clients.json",  # absent
    )
    transcript = _transcript(tmp_path, "did work", with_tool=True)
    main({"session_id": "s2", "subagent_type": "paulo",
          "transcript_path": transcript})
    from core.memory.session_store import SessionStore

    outputs = SessionStore("s2").load_agent_outputs("paulo")
    assert len(outputs) == 1
    assert outputs[0].output == ""  # refused text, metadata row kept
    assert outputs[0].phase_id == "subagent-stop"
