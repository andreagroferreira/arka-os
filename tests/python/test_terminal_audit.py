"""Tests for core.terminal.audit."""

from __future__ import annotations

import json

from core.terminal import audit


def test_log_start_appends_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    audit.log_start("sid-1", "/bin/zsh", "/Users/me")
    path = tmp_path / "terminal-audit.jsonl"
    assert path.exists()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "start"
    assert event["session_id"] == "sid-1"
    assert event["shell"] == "/bin/zsh"
    assert event["cwd"] == "/Users/me"
    assert "ts" in event


def test_log_end_appends_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    audit.log_end("sid-2", exit_code=0, reason="closed")
    path = tmp_path / "terminal-audit.jsonl"
    event = json.loads(path.read_text(encoding="utf-8").strip())
    assert event["event"] == "end"
    assert event["session_id"] == "sid-2"
    assert event["exit_code"] == 0
    assert event["reason"] == "closed"


def test_multiple_events_append(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    audit.log_start("a", "/bin/sh", "/tmp")
    audit.log_end("a", 0)
    audit.log_start("b", "/bin/sh", "/tmp")
    path = tmp_path / "terminal-audit.jsonl"
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    events = [json.loads(line) for line in lines]
    assert [e["event"] for e in events] == ["start", "end", "start"]


def test_audit_never_includes_payload(tmp_path, monkeypatch):
    """Defence-in-depth: the audit module exposes no input-capture API."""
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    audit.log_start("sid-x", "/bin/zsh", "/tmp")
    audit.log_end("sid-x", 0)
    path = tmp_path / "terminal-audit.jsonl"
    body = path.read_text(encoding="utf-8")
    for forbidden in ("password", "stdin", "input", "keystroke"):
        assert forbidden not in body.lower()


def test_token_module_is_constant_per_process(tmp_path, monkeypatch):
    from core.terminal import token
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    a = token.current_token()
    b = token.current_token()
    assert a == b
    assert token.verify(a)
    assert not token.verify("not-the-token")
    assert not token.verify("")


def test_token_rotate_changes_value():
    from core.terminal import token
    original = token.current_token()
    new = token.rotate()
    try:
        assert new != original
        assert token.verify(new)
        assert not token.verify(original)
    finally:
        token._TOKEN = original  # restore for other tests
