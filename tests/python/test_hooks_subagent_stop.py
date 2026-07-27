"""Tests for core.hooks.subagent_stop (F2-4)."""

from __future__ import annotations

import json
import os
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
    # The nudge is QUEUED, not emitted: SubagentStop context wakes the
    # subagent it describes (65 measured re-entries before this change).
    assert capsys.readouterr().out.strip() == ""
    from core.governance.reviewer_ledger import notices_context

    nudge = notices_context("s1")
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
#
# Payload shape verified against Claude Code 2.1.220: SubagentStop sends
# `last_assistant_message` (the subagent's own final text) and
# `agent_transcript_path` (<session>/subagents/agent-<id>.jsonl). The
# parent transcript at `transcript_path` holds ONLY main-scope records —
# reading its tail returns the orchestrator's turn, which is how three
# identical-hash artifacts were once filed under three reviewer names.


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


def _parent_transcript(tmp_path, orchestrator_text):
    """The parent file CC passes as transcript_path: main scope only."""
    lines = [
        {"type": "user", "message": {"role": "user", "content": "review it"}},
        {"type": "assistant", "isSidechain": False,
         "message": {"role": "assistant", "content": [
             {"type": "tool_use", "name": "Agent", "input": {}}]}},
        {"type": "assistant", "isSidechain": False,
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": orchestrator_text}]}},
    ]
    path = tmp_path / "parent.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return str(path)


def _agent_transcript(tmp_path, agent_id, text):
    """The subagent's own file, as written under <session>/subagents/."""
    subdir = tmp_path / "parent" / "subagents"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"agent-{agent_id}.jsonl"
    path.write_text(json.dumps(
        {"type": "assistant", "isSidechain": True,
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": text}]}}
    ), encoding="utf-8")
    return str(path)


def test_last_assistant_message_is_preferred(tmp_path):
    """The payload carries the reviewer's text — no transcript parsing."""
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    text, source = subagent_stop._subagent_text(
        {"last_assistant_message": VERDICT_TEXT, "transcript_path": parent},
        parent, Path(parent).read_text(encoding="utf-8"),
    )
    assert text == VERDICT_TEXT
    assert source == "payload"


def test_falls_back_to_the_agent_transcript_never_the_parent(tmp_path):
    """Regression: reading the parent returned '<tool_use:Agent>' or the
    orchestrator's own words, which were then filed under the reviewer's
    name with a hash. The subagent's file is the only valid source."""
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    agent = _agent_transcript(tmp_path, "abc123", VERDICT_TEXT)
    text, source = subagent_stop._subagent_text(
        {"agent_transcript_path": agent, "transcript_path": parent},
        parent, Path(parent).read_text(encoding="utf-8"),
    )
    assert "arka-qgverdict" in text
    assert "orchestrator status update" not in text
    assert "<tool_use:" not in text
    assert source == "agent-transcript"


def test_no_subagent_source_is_never_attributable(tmp_path):
    """Fail closed: with only the parent transcript, attribution cannot
    be proven, so the ledger must not write. Missing a verdict beats
    fabricating one."""
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    # Keyed on where the text CAME FROM, not on which field was present:
    # an unreadable agent_transcript_path falls through to the parent, and
    # gating on the field alone signed the orchestrator's words.
    assert subagent_stop._attributable("parent", "orchestrator words") is False
    assert subagent_stop._attributable("payload", "reviewer words") is True
    assert subagent_stop._attributable("agent-transcript", "reviewer words") is True
    # A tool-call placeholder is not a verdict.
    assert subagent_stop._attributable("payload", "<tool_use:Write>") is False
    assert subagent_stop._attributable("agent-transcript", "  ") is False

    # End-to-end: a payload naming a path that does not resolve must not
    # produce a record, even though the FIELD is present.
    missing = str(tmp_path / "does-not-exist.jsonl")
    _, source = subagent_stop._subagent_text(
        {"agent_transcript_path": missing, "transcript_path": parent},
        parent, Path(parent).read_text(encoding="utf-8"),
    )
    assert source == "parent", "an unreadable agent transcript must not be trusted"


def test_unattributable_run_writes_no_artifact(tmp_path, capsys):
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    assert main({"session_id": "qg-noattr", "subagent_type": "francisca-tech",
                 "transcript_path": parent}) == 0
    assert not (tmp_path / ".arkaos" / "quality-gate" / "qg-noattr").exists()
    assert "[arka:qg:reviewer-verdict]" not in capsys.readouterr().out


def test_reviewer_verdict_reaches_the_orchestrator_with_artifact(tmp_path, capsys):
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    assert main({"session_id": "qg-1", "subagent_type": "francisca-tech",
                 "transcript_path": parent,
                 "last_assistant_message": VERDICT_TEXT}) == 0
    assert capsys.readouterr().out.strip() == "", (
        "SubagentStop context is delivered to the SUBAGENT — emitting here "
        "wakes the agent that just stopped instead of the orchestrator"
    )
    from core.governance.reviewer_ledger import notices_context

    context = notices_context("qg-1")
    assert "[arka:qg:reviewer-verdict] francisca-tech REJECTED" in context
    assert "blockers=1" in context
    assert "quote the verdict verbatim" in context

    records = list(
        (tmp_path / ".arkaos" / "quality-gate" / "qg-1").glob("francisca-tech-*.json")
    )
    assert len(records) == 1, "the verdict must be on disk before the aggregator sees it"
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["verdict"]["verdict"] == "REJECTED"
    assert record["raw_output"] == VERDICT_TEXT
    assert record["source"] == "subagent-stop"


def test_two_reviewers_get_distinct_records(tmp_path):
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    for reviewer in ("francisca-tech", "eduardo-copy"):
        main({"session_id": "qg-two", "subagent_type": reviewer,
              "transcript_path": parent,
              "last_assistant_message": f"{reviewer} says:\n{VERDICT_TEXT}"})
    files = sorted((tmp_path / ".arkaos" / "quality-gate" / "qg-two").glob("*.json"))
    assert len(files) == 2
    digests = {json.loads(f.read_text())["raw_sha256"] for f in files}
    assert len(digests) == 2, "distinct reviewers must not share a hash"


def test_agent_type_is_used_when_subagent_type_is_absent(tmp_path):
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    main({"session_id": "qg-atype", "agent_type": "eduardo-copy",
          "transcript_path": parent, "last_assistant_message": VERDICT_TEXT})
    files = list((tmp_path / ".arkaos" / "quality-gate" / "qg-atype").glob("*.json"))
    assert [f.name.split("-1-")[0] for f in files] == ["eduardo-copy"]


def test_non_reviewer_subagent_gets_no_verdict_channel(tmp_path, capsys):
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    assert main({"session_id": "qg-2", "subagent_type": "frontend-dev",
                 "transcript_path": parent,
                 "last_assistant_message": "Implemented the queue."}) == 0
    out = capsys.readouterr().out
    assert "[arka:qg:reviewer-verdict]" not in out
    assert not (tmp_path / ".arkaos" / "quality-gate" / "qg-2").exists()


def test_unparsed_verdict_still_points_at_the_artifact(tmp_path, capsys):
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    broken = "Review done.\n\n```arka-qgverdict\n{bad json,,}\n```\n"
    assert main({"session_id": "qg-3", "subagent_type": "eduardo-copy",
                 "transcript_path": parent,
                 "last_assistant_message": broken}) == 0
    assert capsys.readouterr().out.strip() == ""
    from core.governance.reviewer_ledger import notices_context

    context = notices_context("qg-3")
    assert "verdict-unparsed" in context
    assert "artifact=" in context


# ─── PostToolUse task-result extraction (PR-B1) ──────────────────────────
#
# The payload key is `tool_response` — `tool_output` does not exist in the
# 2.1.220 binary. An ASYNC Task returns {agentId, status, isAsync} with no
# output at PostToolUse time; capturing from it would file a status blob
# as a reviewer's verdict.


def test_async_task_yields_no_capturable_text():
    """An async dispatch has no reviewer output yet, and the text it does
    carry is harness metadata ("Async agent launched successfully…").
    Capturing it would file that blob under the reviewer's name."""
    from core.hooks.post_tool_use import _task_result_text

    observed = {
        "agentId": "a1", "status": "running", "isAsync": True,
        "canReadOutputFile": True, "outputFile": "/tmp/a1.output",
        "description": "QG review", "prompt": "review it",
        "resolvedModel": "opus",
    }
    assert _task_result_text({"tool_response": observed}) == ""
    # Same dispatch, with the harness text the model is shown attached.
    assert _task_result_text({"tool_response": dict(observed, content=[
        {"type": "text", "text": "Async agent launched successfully. (…)"},
    ])}) == ""


def test_sync_task_text_is_extracted():
    from core.hooks.post_tool_use import _task_result_text

    assert _task_result_text({"tool_response": {
        "content": [{"type": "text", "text": VERDICT_TEXT}],
    }}) == VERDICT_TEXT
    assert _task_result_text({"tool_response": {"content": "plain"}}) == "plain"
    assert _task_result_text({"tool_response": "bare string"}) == "bare string"


def test_missing_or_odd_payload_is_empty():
    from core.hooks.post_tool_use import _task_result_text

    assert _task_result_text({}) == ""
    assert _task_result_text({"tool_response": None}) == ""
    assert _task_result_text({"tool_response": {"success": True}}) == ""
    # The legacy key the hook used to read does not exist in the runtime.
    assert _task_result_text({"tool_output": "ignored"}) == ""


def test_agent_transcript_equal_to_parent_is_refused(tmp_path):
    """The round-1 fabrication root cause: when the payload names the
    PARENT file as the agent transcript, reading it returns the
    orchestrator's words. Removing the `!=` guard survived every test
    until this one (found by an independent mutation set)."""
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    text, source = subagent_stop._subagent_text(
        {"agent_transcript_path": parent, "transcript_path": parent},
        parent, Path(parent).read_text(encoding="utf-8"),
    )
    assert source == "parent", "the parent file is never a subagent source"
    assert subagent_stop._attributable(source, text) is False

    # End to end: no artifact, whatever the payload claims.
    assert main({"session_id": "qg-selfpath", "subagent_type": "francisca-tech",
                 "transcript_path": parent,
                 "agent_transcript_path": parent}) == 0
    assert not (tmp_path / ".arkaos" / "quality-gate" / "qg-selfpath").exists()


def test_placeholder_match_is_anchored(tmp_path):
    """`fullmatch`, not `search`: a legitimate verdict that MENTIONS a
    tool-call placeholder must still be captured."""
    body = VERDICT_TEXT.replace(
        "Technical review complete.",
        "Technical review complete. The persisted output was <tool_use:Agent>.",
    )
    assert subagent_stop._attributable("payload", body) is True
    assert subagent_stop._attributable("payload", "<tool_use:Agent>") is False
    assert subagent_stop._attributable("payload", "<tool_use:A><tool_use:B>") is False


def test_symlinked_agent_transcript_to_parent_is_refused(tmp_path):
    """A string compare is bypassed by a symlink pointing back at the
    parent — the round-1 fabrication path with one extra hop."""
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    link = tmp_path / "looks-like-an-agent-file.jsonl"
    link.symlink_to(parent)
    text, source = subagent_stop._subagent_text(
        {"agent_transcript_path": str(link), "transcript_path": parent},
        parent, Path(parent).read_text(encoding="utf-8"),
    )
    assert source == "parent"
    assert subagent_stop._attributable(source, text) is False


def test_post_tool_use_writer_reaches_the_ledger(tmp_path, monkeypatch):
    """Integration cover for the PostToolUse writer: _task_result_text was
    unit-tested, its wiring was not (0% coverage on the call site)."""
    from core.hooks import post_tool_use

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    post_tool_use._record_reviewer_output(
        "francisca-tech",
        {"tool_response": {"content": [{"type": "text", "text": VERDICT_TEXT}]}},
        "ptu-live",
    )
    records = list((tmp_path / ".arkaos" / "quality-gate" / "ptu-live").glob("*.json"))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["source"] == "post-tool-use"
    assert record["raw_output"] == VERDICT_TEXT
    assert record["verdict"]["verdict"] == "REJECTED"


def test_post_tool_use_writer_skips_async_and_non_reviewers(tmp_path, monkeypatch):
    from core.hooks import post_tool_use

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    post_tool_use._record_reviewer_output(
        "francisca-tech",
        {"tool_response": {"agentId": "a1", "isAsync": True,
                           "content": [{"type": "text", "text": "Async agent launched"}]}},
        "ptu-async",
    )
    post_tool_use._record_reviewer_output(
        "frontend-dev",
        {"tool_response": {"content": [{"type": "text", "text": VERDICT_TEXT}]}},
        "ptu-nonreviewer",
    )
    root = tmp_path / ".arkaos" / "quality-gate"
    assert not (root / "ptu-async").exists()
    assert not (root / "ptu-nonreviewer").exists()


def test_null_text_block_does_not_lose_the_rest(tmp_path, monkeypatch):
    """A null text block raised TypeError and aborted main() mid-turn.

    Asserted at the extraction level: _record_reviewer_output swallows
    exceptions, so calling it proves nothing on its own.
    """
    from core.hooks.post_tool_use import _task_result_text

    assert _task_result_text({"tool_response": {"content": [
        {"type": "text", "text": None},
        {"type": "text", "text": "the real verdict"},
    ]}}) == "the real verdict"

    from core.hooks import post_tool_use

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    post_tool_use._record_reviewer_output(
        "francisca-tech",
        {"tool_response": {"content": [{"type": "text", "text": None}]}},
        "ptu-null",
    )


def test_post_tool_use_main_drives_the_writer(tmp_path, monkeypatch, capsys):
    """The production call site had no cover: deleting it from main()
    left the whole suite green (independent mutation, round 4)."""
    from core.hooks import post_tool_use

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert post_tool_use.main({
        "tool_name": "Task",
        "session_id": "ptu-main",
        "cwd": "/tmp",
        "transcript_path": "",
        "tool_input": {"subagent_type": "francisca-tech"},
        "tool_response": {"content": [{"type": "text", "text": VERDICT_TEXT}]},
    }) == 0
    capsys.readouterr()
    records = list((tmp_path / ".arkaos" / "quality-gate" / "ptu-main").glob("*.json"))
    assert len(records) == 1, "main() must drive the ledger writer"
    assert json.loads(records[0].read_text())["source"] == "post-tool-use"


def test_hardlinked_agent_transcript_is_refused(tmp_path):
    """Comparing resolved NAMES is bypassed by a hardlink (and, on a
    case-insensitive filesystem, by a case variant): both read the
    parent transcript and would sign it with a reviewer's name."""
    parent = _parent_transcript(tmp_path, "orchestrator status update")
    hard = tmp_path / "agent-looks-real.jsonl"
    os.link(parent, hard)
    assert Path(hard).resolve() != Path(parent).resolve(), (
        "fixture must exercise inode identity, not name identity"
    )
    text, source = subagent_stop._subagent_text(
        {"agent_transcript_path": str(hard), "transcript_path": parent},
        parent, Path(parent).read_text(encoding="utf-8"),
    )
    assert source == "parent", "inode identity must win over the name"
    assert subagent_stop._attributable(source, text) is False


# ─── CQO id widening (PR-B1) ─────────────────────────────────────────────


def test_cqo_experience_persistence_fires_on_the_dispatched_id(
    tmp_path, monkeypatch
):
    """Dispatches carry the agent-file name (marta-cqo), not the bare
    role, so `== "cqo"` skipped the experience-persistence MUST rule on
    ~90% of CQO dispatches. The widening shipped with no test: reverting
    it left the whole suite green."""
    from core.hooks import post_tool_use

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    seen: list[str] = []
    monkeypatch.setattr(
        post_tool_use, "_record_cqo_rejected",
        lambda _out, _prompt, _sid: seen.append("recorded"),
    )
    monkeypatch.setattr(post_tool_use, "_record_pattern_stub", lambda *a: None)

    for dispatched in ("cqo", "marta-cqo", "cqo-marta"):
        seen.clear()
        post_tool_use.main({
            "tool_name": "Task",
            "session_id": f"cqo-{dispatched}",
            "cwd": "/tmp",
            "transcript_path": "",
            "tool_input": {
                "subagent_type": dispatched,
                "prompt": "[arka:reviewing francisca-tech]",
            },
            "tool_response": {"content": [
                {"type": "text", "text": "Quality Gate Verdict: REJECTED"},
            ]},
        })
        assert seen == ["recorded"], (
            f"experience persistence must fire for dispatch id {dispatched!r}"
        )

    seen.clear()
    post_tool_use.main({
        "tool_name": "Task", "session_id": "cqo-other", "cwd": "/tmp",
        "transcript_path": "",
        "tool_input": {"subagent_type": "frontend-dev", "prompt": "x"},
        "tool_response": {"content": [{"type": "text", "text": "done"}]},
    })
    assert seen == [], "and must not fire for a non-CQO dispatch"
