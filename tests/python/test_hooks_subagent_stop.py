"""Tests for core.hooks.subagent_stop (F2-4)."""

from __future__ import annotations

import json
from pathlib import Path

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
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return str(path)


def _telemetry(tmp_path):
    p = tmp_path / ".arkaos" / "telemetry" / "subagent-stop.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    # Deliverable-shaped ("fixed") AND a phantom claim ("I committed") with
    # NO tool call in the turn -> flagged + nudged via additionalContext.
    transcript = _transcript(
        tmp_path, "I committed the change and fixed the bug.", with_tool=False
    )
    assert main({"session_id": "s1", "subagent_type": "paulo",
                 "transcript_path": transcript}) == 0
    # The nudge reaches the model via stdout additionalContext — Claude
    # Code discards hook stderr at exit 0, so stderr would be inert.
    out = json.loads(capsys.readouterr().out)
    nudge = out["hookSpecificOutput"]["additionalContext"]
    assert "[arka:subagent-qa]" in nudge
    assert "Quality Gate" in nudge
    rows = _telemetry(tmp_path)
    assert rows[0]["phantom"] == "phantom-action"
    assert rows[0]["deliverable"] is True


def test_no_nudge_when_not_deliverable(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(subagent_stop, "_persist_output", lambda *a: None)
    transcript = _transcript(tmp_path, "Here is a summary of the options.", with_tool=False)
    main({"session_id": "s1", "subagent_type": "analyst",
          "transcript_path": transcript})
    # No deliverable => no stdout nudge (but the telemetry row is still
    # written, which is the durable record).
    assert capsys.readouterr().out.strip() == ""
    assert len(_telemetry(tmp_path)) == 1


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


def test_invalid_utf8_transcript_never_raises(tmp_path):
    """QG B1: a hook that promises 'never blocks' must survive an
    invalid-UTF-8 transcript (read_text would raise UnicodeDecodeError)."""
    bad = tmp_path / "bad.jsonl"
    bad.write_bytes(b'{"type":"assistant","content":"\xff\xfe bad bytes"}')
    assert main({"session_id": "s1", "transcript_path": str(bad)}) == 0


def test_null_byte_transcript_path_never_raises(tmp_path):
    """QG B1: a null-byte path from stdin JSON raises ValueError in
    read_text — must be swallowed, exit 0."""
    assert main({"session_id": "s1", "transcript_path": "/x\x00y.jsonl"}) == 0


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


# ─── reviewer channel (PR-B1) ────────────────────────────────────────────


def _scoped_transcript(tmp_path, main_text, sidechain_text):
    """Main-scope turn holding the in-flight Task call + the subagent's reply.

    Mirrors what Claude Code writes: at SubagentStop the LAST record in
    the transcript is the parent's turn (whose content serialises as
    ``<tool_use:Agent>``), and the reviewer's actual words carry
    ``isSidechain: true``.
    """
    lines = [
        {"type": "user", "message": {"role": "user", "content": "review it"}},
        {"type": "assistant", "isSidechain": True,
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": sidechain_text}]}},
        {"type": "assistant", "isSidechain": False,
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "name": "Agent", "input": {}}]}},
        {"type": "assistant", "isSidechain": False,
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": main_text}]}},
    ]
    path = tmp_path / "scoped.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return str(path)


VERDICT_TEXT = (
    "Technical review complete.\n\n```arka-qgverdict\n"
    + json.dumps({
        "verdict": "REJECTED",
        "evidence_report": {"overall": "fail", "checks_ran": ["lint"],
                            "checks_failed": ["lint"], "checks_skipped": []},
        "blockers": [{"check": "lint", "detail": "ruff exit 1",
                      "file": "a.py", "verdict": "CONFIRMED"}],
        "reviewer": "tech-director-francisca",
    })
    + "\n```\n"
)


def test_reads_the_subagent_scope_not_the_parent_turn(tmp_path):
    """Regression: every persisted reviewer output on disk was the 16-byte
    string '<tool_use:Agent>' — the parent's in-flight turn, read from
    the wrong transcript scope. The reviewer's words never survived."""
    transcript = _scoped_transcript(tmp_path, "parent narration", VERDICT_TEXT)
    raw = Path(transcript).read_text(encoding="utf-8")
    text = subagent_stop._final_assistant_text(transcript, raw)
    assert "<tool_use:" not in text, "read the parent's tool call, not the reviewer"
    assert "arka-qgverdict" in text


def test_reviewer_verdict_reaches_the_orchestrator_with_artifact(tmp_path, capsys):
    transcript = _scoped_transcript(tmp_path, "parent narration", VERDICT_TEXT)
    assert main({"session_id": "qg-1", "subagent_type": "francisca-tech",
                 "transcript_path": transcript}) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SubagentStop"
    assert "[arka:qg:reviewer-verdict] francisca-tech REJECTED" in context
    assert "blockers=1" in context
    assert "VERBATIM" in context

    artifact = tmp_path / ".arkaos" / "quality-gate" / "qg-1" / "francisca-tech-1.json"
    assert artifact.is_file(), "the verdict must be on disk before the aggregator sees it"
    record = json.loads(artifact.read_text(encoding="utf-8"))
    assert record["verdict"]["verdict"] == "REJECTED"
    assert record["raw_output"] == VERDICT_TEXT
    assert record["source"] == "subagent-stop"


def test_non_reviewer_subagent_gets_no_verdict_channel(tmp_path, capsys):
    transcript = _scoped_transcript(tmp_path, "parent", "Implemented the queue.")
    assert main({"session_id": "qg-2", "subagent_type": "frontend-dev",
                 "transcript_path": transcript}) == 0
    out = capsys.readouterr().out
    assert "[arka:qg:reviewer-verdict]" not in out
    assert not (tmp_path / ".arkaos" / "quality-gate" / "qg-2").exists()


def test_unparsed_verdict_still_points_at_the_artifact(tmp_path, capsys):
    broken = "Review done.\n\n```arka-qgverdict\n{bad json,,}\n```\n"
    transcript = _scoped_transcript(tmp_path, "parent", broken)
    assert main({"session_id": "qg-3", "subagent_type": "eduardo-copy",
                 "transcript_path": transcript}) == 0
    context = json.loads(
        capsys.readouterr().out.strip().splitlines()[0]
    )["hookSpecificOutput"]["additionalContext"]
    assert "verdict-unparsed" in context
    assert "artifact=" in context
