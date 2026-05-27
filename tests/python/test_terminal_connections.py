"""Tests for the single-writer-per-session connection registry (v3.71.1).

Guards against two concurrent WebSockets fighting over one PTY master fd.
"""

from __future__ import annotations

from core.terminal.connections import ConnectionRegistry


def test_first_acquire_returns_none():
    reg = ConnectionRegistry()
    assert reg.acquire("s1", "connA") is None
    assert reg.is_active("s1", "connA")


def test_second_acquire_supersedes_and_returns_previous():
    reg = ConnectionRegistry()
    reg.acquire("s1", "connA")
    old = reg.acquire("s1", "connB")
    assert old == "connA"
    assert reg.is_active("s1", "connB")
    assert not reg.is_active("s1", "connA")


def test_release_by_active_removes():
    reg = ConnectionRegistry()
    reg.acquire("s1", "connA")
    assert reg.release("s1", "connA") is True
    assert not reg.is_active("s1", "connA")


def test_release_by_superseded_is_noop():
    """A superseded connection's late teardown must not evict its
    replacement — the core race this registry exists to prevent."""
    reg = ConnectionRegistry()
    reg.acquire("s1", "connA")
    reg.acquire("s1", "connB")
    assert reg.release("s1", "connA") is False
    assert reg.is_active("s1", "connB")


def test_sessions_are_independent():
    reg = ConnectionRegistry()
    reg.acquire("s1", "connA")
    reg.acquire("s2", "connB")
    assert reg.is_active("s1", "connA")
    assert reg.is_active("s2", "connB")
    assert reg.release("s1", "connA") is True
    assert reg.is_active("s2", "connB")
