"""Tests for core/workflow/flow_enforcer.py."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.workflow import flow_enforcer, marker_cache
from core.workflow.flow_enforcer import (
    Decision,
    evaluate,
    mark_flow_required,
    clear_flow_required,
    _extract_text,
    _load_last_assistant_messages,
    _scan_markers,
)


# ─── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Isolate CONFIG_PATH / BYPASS_AUDIT / TELEMETRY / FLOW_REQUIRED_DIR."""
    home = tmp_path / "home"
    home.mkdir()
    tmp_flow_required = tmp_path / "wf-required"
    tmp_marker_cache = tmp_path / "marker-cache"
    monkeypatch.setattr(flow_enforcer, "CONFIG_PATH", home / "config.json")
    monkeypatch.setattr(flow_enforcer, "BYPASS_AUDIT_PATH", home / "audit" / "bypass.log")
    monkeypatch.setattr(flow_enforcer, "TELEMETRY_PATH", home / "telemetry" / "enforcement.jsonl")
    monkeypatch.setattr(flow_enforcer, "FLOW_REQUIRED_DIR", tmp_flow_required)
    monkeypatch.setattr(marker_cache, "MARKER_CACHE_DIR", tmp_marker_cache)
    return home


def _write_config(home: Path, hard_enforcement: bool) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text(
        json.dumps({"hooks": {"hardEnforcement": hard_enforcement}}),
        encoding="utf-8",
    )


def _write_transcript(path: Path, assistant_messages: list[str]) -> Path:
    lines = [{"role": "user", "content": "implement a feature"}]
    for msg in assistant_messages:
        lines.append({"role": "assistant", "content": msg})
    path.write_text(
        "\n".join(json.dumps(line) for line in lines),
        encoding="utf-8",
    )
    return path


# ─── Core gate behavior ────────────────────────────────────────────────


def test_non_gated_tool_always_allows(tmp_config):
    _write_config(tmp_config, True)
    d = evaluate("Read", "/nonexistent", "session-1", "/tmp")
    assert d.allow is True
    assert d.reason == "tool-not-gated"


def test_bash_is_never_gated(tmp_config):
    """Bash must never be blocked — prevents deadlock."""
    _write_config(tmp_config, True)
    d = evaluate("Bash", "/nonexistent", "session-1", "/tmp")
    assert d.allow is True
    assert d.reason == "tool-not-gated"


def test_feature_flag_off_allows_all(tmp_config, tmp_path):
    # No config.json written → flag is off by default
    d = evaluate("Write", "/nonexistent", "session-1", "/tmp")
    assert d.allow is True
    assert d.reason == "feature-flag-off"


def test_feature_flag_explicit_false_allows_all(tmp_config):
    _write_config(tmp_config, False)
    d = evaluate("Write", "/nonexistent", "session-1", "/tmp")
    assert d.allow is True
    assert d.reason == "feature-flag-off"


def test_classifier_no_match_allows(tmp_config):
    _write_config(tmp_config, True)
    # flow NOT marked required → classifier did not match → allow
    d = evaluate("Write", "/nonexistent", "session-no-match", "/tmp")
    assert d.allow is True
    assert d.reason == "classifier-did-not-match"


# ─── Marker detection paths ────────────────────────────────────────────


def test_write_without_marker_denies(tmp_config, tmp_path):
    _write_config(tmp_config, True)
    mark_flow_required("session-2")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["Just writing without any flow marker."],
    )
    d = evaluate("Write", str(transcript), "session-2", "/tmp")
    assert d.allow is False
    assert d.reason == f"no-flow-marker-in-last-{flow_enforcer.ASSISTANT_WINDOW}-assistant-messages"
    assert d.marker_found is None


def test_routing_marker_allows(tmp_config, tmp_path):
    _write_config(tmp_config, True)
    mark_flow_required("session-3")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:routing] dev -> Paulo\nFollowing the 13-phase flow."],
    )
    d = evaluate("Write", str(transcript), "session-3", "/tmp")
    assert d.allow is True
    assert d.marker_found == "routing"


def test_trivial_marker_allows(tmp_config, tmp_path):
    _write_config(tmp_config, True)
    mark_flow_required("session-4")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:trivial] rename variable — single-line edit"],
    )
    d = evaluate("Write", str(transcript), "session-4", "/tmp")
    assert d.allow is True
    assert d.marker_found == "trivial"


def test_phase_marker_allows(tmp_config, tmp_path):
    _write_config(tmp_config, True)
    mark_flow_required("session-5")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:phase:11] Running per-todo loop now."],
    )
    d = evaluate("Write", str(transcript), "session-5", "/tmp")
    assert d.allow is True
    assert d.marker_found == "phase"
    assert d.phase_observed == "[arka:phase:11]"


def test_marker_in_any_of_last_three_messages(tmp_config, tmp_path):
    """Marker in message N-2 is still valid if N-1 and N lack it."""
    _write_config(tmp_config, True)
    mark_flow_required("session-6")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        [
            "[arka:routing] dev -> Paulo",
            "Now running tests.",
            "All tests green.",
        ],
    )
    d = evaluate("Write", str(transcript), "session-6", "/tmp")
    assert d.allow is True
    assert d.marker_found == "routing"


def test_marker_older_than_window_denies(tmp_config, tmp_path):
    """Marker beyond the configured window is stale → deny."""
    _write_config(tmp_config, True)
    mark_flow_required("session-7")
    filler = [f"Step {i}." for i in range(flow_enforcer.ASSISTANT_WINDOW + 1)]
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:routing] dev -> Paulo", *filler],
    )
    d = evaluate("Write", str(transcript), "session-7", "/tmp")
    assert d.allow is False


# ─── Bypass path ───────────────────────────────────────────────────────


def test_env_bypass_allows_and_audits(tmp_config, tmp_path, monkeypatch):
    _write_config(tmp_config, True)
    mark_flow_required("session-bypass")
    transcript = _write_transcript(tmp_path / "t.jsonl", ["no marker"])
    monkeypatch.setenv("ARKA_BYPASS_FLOW", "1")
    monkeypatch.setenv("ARKA_BYPASS_REASON", "installer-update")
    d = evaluate("Write", str(transcript), "session-bypass", "/tmp")
    assert d.allow is True
    assert d.bypass_used is True
    assert d.reason == "env-bypass"
    # Audit log was written
    audit = flow_enforcer.BYPASS_AUDIT_PATH
    assert audit.exists()
    entry = json.loads(audit.read_text().strip().splitlines()[-1])
    assert entry["tool"] == "Write"
    assert entry["reason"] == "installer-update"


# ─── Transcript parsing edge cases ─────────────────────────────────────


def test_extract_text_handles_string():
    assert _extract_text("hello") == "hello"


def test_extract_text_handles_list_of_dicts():
    content = [{"type": "text", "text": "hello"}, {"type": "tool_use", "name": "Read"}]
    assert "hello" in _extract_text(content)
    assert "<tool_use:Read>" in _extract_text(content)


def test_extract_text_empty():
    assert _extract_text(None) == ""
    assert _extract_text({}) == ""


def test_load_last_assistant_messages_handles_malformed_lines(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        '{"role":"user","content":"q"}\n'
        "this is not json\n"
        '{"role":"assistant","content":"ok"}\n'
        "\n"
        '{"role":"assistant","content":"last"}\n',
        encoding="utf-8",
    )
    msgs = _load_last_assistant_messages(str(path), 3)
    assert msgs == ["ok", "last"]


def test_load_last_assistant_messages_handles_nested_message_shape(tmp_path):
    """Some runtimes wrap the message in a `message` envelope."""
    path = tmp_path / "t.jsonl"
    path.write_text(
        '{"message":{"role":"user","content":"q"}}\n'
        '{"message":{"role":"assistant","content":"nested"}}\n',
        encoding="utf-8",
    )
    msgs = _load_last_assistant_messages(str(path), 3)
    assert msgs == ["nested"]


def test_load_last_assistant_messages_missing_file_returns_empty():
    assert _load_last_assistant_messages("/does/not/exist", 3) == []


def test_scan_markers_prefers_phase_for_observation():
    marker, phase = _scan_markers(["plain text", "[arka:phase:7] reviewing"])
    assert marker == "phase"
    assert phase == "[arka:phase:7]"


# ─── Spoofing-resistance note (partial defense) ────────────────────────


def test_forged_routing_text_still_allows(tmp_config, tmp_path):
    """Document the known limitation: regex-only check cannot stop forged tags.
    PostToolUse cross-check against Task dispatch (out of scope here) is the
    complementary defense per the ADR.
    """
    _write_config(tmp_config, True)
    mark_flow_required("session-forge")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:routing] dev -> Paulo (but I did none of the flow)"],
    )
    d = evaluate("Write", str(transcript), "session-forge", "/tmp")
    assert d.allow is True  # regex permits; semantic defense lives elsewhere


# ─── Decision.to_stderr_message ────────────────────────────────────────


def test_stderr_message_on_allow_is_empty():
    d = Decision(allow=True, reason="ok")
    assert d.to_stderr_message() == ""


def test_stderr_message_on_deny_contains_guidance():
    d = Decision(allow=False, reason="no-flow-marker-in-last-3-assistant-messages")
    msg = d.to_stderr_message()
    assert "[ARKA:ENFORCEMENT]" in msg
    assert "[arka:routing]" in msg
    assert "[arka:trivial]" in msg


# ─── Session marker helpers ────────────────────────────────────────────


def test_mark_and_clear_flow_required(tmp_config):
    mark_flow_required("session-mark")
    assert flow_enforcer._flow_required_for_session("session-mark") is True
    clear_flow_required("session-mark")
    assert flow_enforcer._flow_required_for_session("session-mark") is False


def test_mark_with_empty_session_is_noop(tmp_config):
    mark_flow_required("")
    # No file created; directory may or may not exist
    d = evaluate("Write", "/nowhere", "", "/tmp")
    # feature flag still off because _write_config wasn't called
    assert d.allow is True


# ─── Security: path traversal guards ───────────────────────────────────


@pytest.mark.parametrize(
    "hostile_id",
    [
        "../etc/passwd",
        "../../home/victim/.ssh/authorized_keys",
        "foo/bar",
        "foo\\bar",
        "with space",
        "with\nnewline",
        "x" * 129,  # too long
        "",
    ],
)
def test_session_id_with_unsafe_chars_rejected(tmp_config, hostile_id):
    """mark_flow_required must reject any id outside [A-Za-z0-9._-]{1,128}."""
    mark_flow_required(hostile_id)
    # FLOW_REQUIRED_DIR should contain no file at all (marker never written)
    if flow_enforcer.FLOW_REQUIRED_DIR.exists():
        assert list(flow_enforcer.FLOW_REQUIRED_DIR.iterdir()) == []
    # _flow_required_for_session returns False for the same hostile id
    assert flow_enforcer._flow_required_for_session(hostile_id) is False


def test_session_id_safe_chars_accepted(tmp_config):
    for safe_id in ["abc123", "session-1", "a.b_c-d", "A" * 128]:
        mark_flow_required(safe_id)
        assert flow_enforcer._flow_required_for_session(safe_id) is True
        clear_flow_required(safe_id)


# ─── Concurrent append integrity ───────────────────────────────────────


# ─── Security: bash classifier path-traversal guard ───────────────────


def test_bash_classifier_rejects_unsafe_session_ids(tmp_path, monkeypatch):
    """arka_wf_mark_required in the shared bash lib must also reject any
    session_id outside [A-Za-z0-9._-]{1,128} — mirroring the Python guard.
    Covers the case where user-prompt-submit.sh is the caller (the Python
    layer is not in the path).
    """
    import subprocess

    repo_root = Path(__file__).resolve().parents[2]
    lib = repo_root / "config" / "hooks" / "_lib" / "workflow-classifier.sh"
    fake_dir = tmp_path / "wf-required"

    for hostile in ["../PWNED", "foo/bar", "foo\\bar", "with space", "x" * 200, ""]:
        subprocess.run(
            ["bash", str(lib), "mark", hostile],
            env={**os.environ, "ARKA_WF_REQUIRED_DIR": str(fake_dir)},
            check=False,
            capture_output=True,
        )
    # Either the dir was never created, or it exists but contains no files
    if fake_dir.exists():
        assert list(fake_dir.iterdir()) == []

    # Sanity: a safe id *is* accepted
    subprocess.run(
        ["bash", str(lib), "mark", "safe-id-1"],
        env={**os.environ, "ARKA_WF_REQUIRED_DIR": str(fake_dir)},
        check=True,
        capture_output=True,
    )
    assert (fake_dir / "safe-id-1").exists()


# ─── v2 window widening + cache integration sanity ────────────────────


def test_assistant_window_is_six_after_v2():
    """v2 widens the fallback scan from 3 → 6 messages."""
    assert flow_enforcer.ASSISTANT_WINDOW == 6


def test_deny_reason_reflects_current_window(tmp_config, tmp_path):
    _write_config(tmp_config, True)
    mark_flow_required("session-v2-deny")
    transcript = _write_transcript(tmp_path / "t.jsonl", ["no marker here"])
    d = evaluate("Write", str(transcript), "session-v2-deny", "/tmp")
    assert d.allow is False
    assert f"last-{flow_enforcer.ASSISTANT_WINDOW}" in d.reason


def test_cache_hit_does_not_break_transcript_fallback(tmp_config, tmp_path):
    """If cache is empty, evaluate() must still honour transcript markers."""
    _write_config(tmp_config, True)
    mark_flow_required("session-fallback")
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        ["[arka:routing] dev -> Paulo"],
    )
    d = evaluate("Write", str(transcript), "session-fallback", "/tmp")
    assert d.allow is True
    assert d.marker_found == "routing"
    assert not d.reason.startswith("marker-cache-hit")


def test_telemetry_append_remains_valid_jsonl_under_concurrency(tmp_config):
    """Each line of the telemetry log must parse as JSON, even under heavy
    concurrent writes. Uses threads as a proxy — full multi-process fuzz is
    out of scope for unit tests but the flock guard covers that case too.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _write(i: int) -> None:
        flow_enforcer.record_telemetry(
            session_id=f"s{i}",
            tool="Write",
            decision=Decision(allow=True, reason="concurrent-test"),
            cwd="/tmp",
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(_write, range(200)))

    lines = flow_enforcer.TELEMETRY_PATH.read_text().splitlines()
    assert len(lines) == 200
    for line in lines:
        record = json.loads(line)  # must not raise
        assert record["tool"] == "Write"
