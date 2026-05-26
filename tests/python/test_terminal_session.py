"""Tests for core.terminal.session.

PR99a v3.67.0 — covers PTY creation, write/read round-trip, kill,
cap enforcement, dead-reap and idle-reap.

These tests fork real PTYs but only inside ``/bin/sh -c`` invocations
that exit immediately, so no zombie shells leak into CI.
"""

from __future__ import annotations

import os
import select
import time

import pytest

from core.terminal.session import (
    SessionCapacityError,
    TerminalSession,
    TerminalSessionManager,
)


def _read_until(session: TerminalSession, needle: bytes, timeout_s: float = 3.0) -> bytes:
    """Pump the PTY until ``needle`` shows up or timeout expires."""
    deadline = time.monotonic() + timeout_s
    buf = b""
    while time.monotonic() < deadline:
        if session.master_fd < 0:
            break
        readable, _, _ = select.select([session.master_fd], [], [], 0.1)
        if not readable:
            continue
        chunk = session.read(4096)
        if chunk:
            buf += chunk
            if needle in buf:
                return buf
    return buf


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    monkeypatch.delenv("ARKAOS_TERMINAL_MAX_SESSIONS", raising=False)
    monkeypatch.delenv("ARKAOS_TERMINAL_IDLE_S", raising=False)
    mgr = TerminalSessionManager(max_sessions=3, idle_timeout_s=60)
    yield mgr
    mgr.shutdown()


def test_create_session_spawns_real_pty(manager):
    session = manager.create(shell="/bin/sh")
    try:
        assert session.pid > 0
        assert session.master_fd > 0
        assert session.is_alive()
    finally:
        session.kill()


def test_session_round_trip_echo(manager):
    session = manager.create(shell="/bin/sh")
    try:
        session.write(b"echo arkaos-marker; exit\n")
        out = _read_until(session, b"arkaos-marker")
        assert b"arkaos-marker" in out
    finally:
        session.kill()


def test_kill_terminates_child(manager):
    session = manager.create(shell="/bin/sh")
    pid = session.pid
    session.kill()
    time.sleep(0.05)
    assert not session.is_alive()
    with pytest.raises(OSError):
        os.kill(pid, 0)


def test_cap_enforced(manager):
    sessions = [manager.create(shell="/bin/sh") for _ in range(3)]
    try:
        with pytest.raises(SessionCapacityError):
            manager.create(shell="/bin/sh")
    finally:
        for s in sessions:
            s.kill()


def test_reap_dead_returns_count(manager):
    a = manager.create(shell="/bin/sh")
    b = manager.create(shell="/bin/sh")
    a.kill()
    time.sleep(0.05)
    reaped = manager.reap_dead()
    assert reaped == 1
    assert manager.count() == 1
    b.kill()


def test_reap_idle_kills_long_idle_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    mgr = TerminalSessionManager(max_sessions=2, idle_timeout_s=0)
    s = mgr.create(shell="/bin/sh")
    time.sleep(0.05)
    reaped = mgr.reap_idle()
    assert reaped == 1
    assert mgr.count() == 0
    s.kill()
    mgr.shutdown()


def test_resize_does_not_crash(manager):
    session = manager.create(shell="/bin/sh", cols=80, rows=24)
    try:
        session.resize(200, 50)
        session.resize(10, 5)
    finally:
        session.kill()


def test_to_dict_shape(manager):
    session = manager.create(shell="/bin/sh")
    try:
        d = session.to_dict()
        assert set(d.keys()) >= {
            "session_id", "shell", "cwd", "title", "created_at",
            "idle_seconds", "alive", "exit_code",
        }
        assert d["alive"] is True
    finally:
        session.kill()


def test_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    monkeypatch.setenv("ARKAOS_TERMINAL_MAX_SESSIONS", "1")
    mgr = TerminalSessionManager()
    assert mgr.max_sessions == 1
    s = mgr.create(shell="/bin/sh")
    try:
        with pytest.raises(SessionCapacityError):
            mgr.create(shell="/bin/sh")
    finally:
        s.kill()
    mgr.shutdown()
