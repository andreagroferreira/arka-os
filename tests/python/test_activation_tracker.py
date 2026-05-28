"""Tests for core.governance.activation_tracker (PR5 Squad Intelligence).

Counts how often each agent (`subagent_type`) is dispatched. Surfaces
top callers and dead agents (no activation in N days). Mirrors the
JSONL + path-safe pattern of agent_experiences.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


activation_tracker = pytest.importorskip(
    "core.governance.activation_tracker",
    reason="activation_tracker not yet implemented (TDD red phase)",
)
Activation = activation_tracker.Activation
record_activation = activation_tracker.record_activation
query_top_callers = activation_tracker.query_top_callers
query_dead_agents = activation_tracker.query_dead_agents


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        activation_tracker,
        "TELEMETRY_PATH",
        tmp_path / "telemetry" / "agent-activations.jsonl",
    )
    return tmp_path / "telemetry" / "agent-activations.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── record_activation ────────────────────────────────────────────────


def test_record_creates_jsonl_at_safe_path(tmp_store):
    record_activation("senior-dev", "sess-1")
    assert tmp_store.exists()
    line = tmp_store.read_text(encoding="utf-8").strip().splitlines()[-1]
    entry = json.loads(line)
    assert entry["subagent_type"] == "senior-dev"
    assert entry["session_id"] == "sess-1"


def test_record_appends_multiple(tmp_store):
    record_activation("senior-dev", "sess-1")
    record_activation("security-eng", "sess-1")
    record_activation("senior-dev", "sess-2")
    lines = tmp_store.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3


def test_record_rejects_unsafe_subagent_type(tmp_store):
    record_activation("../../evil", "sess-1")
    if tmp_store.exists():
        for line in tmp_store.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                assert "evil" not in entry.get("subagent_type", "")


def test_record_rejects_empty_subagent_type(tmp_store):
    record_activation("", "sess-1")
    if tmp_store.exists():
        assert tmp_store.read_text(encoding="utf-8").strip() == ""


# ─── query_top_callers ────────────────────────────────────────────────


def test_query_top_callers_returns_descending_counts(tmp_store):
    for _ in range(5):
        record_activation("senior-dev", "sess-1")
    for _ in range(3):
        record_activation("security-eng", "sess-2")
    record_activation("frontend-dev", "sess-3")
    top = query_top_callers(limit=10)
    # List of (subagent_type, count) tuples, descending
    assert top[0] == ("senior-dev", 5)
    assert top[1] == ("security-eng", 3)
    assert top[2] == ("frontend-dev", 1)


def test_query_top_callers_respects_limit(tmp_store):
    for i in range(5):
        record_activation(f"agent-{i}", "sess-1")
    assert len(query_top_callers(limit=3)) == 3


def test_query_top_callers_since_filter(tmp_store):
    """Old activations excluded when `since` cutoff is set."""
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=10)).isoformat()
    # Write a raw old line directly
    tmp_store.parent.mkdir(parents=True, exist_ok=True)
    tmp_store.write_text(
        json.dumps({
            "ts": old_ts,
            "subagent_type": "old-agent",
            "session_id": "sess-old",
        }) + "\n",
        encoding="utf-8",
    )
    record_activation("recent-agent", "sess-now")
    top = query_top_callers(limit=10, since=now - timedelta(days=1))
    types = {t for t, _ in top}
    assert "recent-agent" in types
    assert "old-agent" not in types


def test_query_top_callers_empty_store(tmp_store):
    assert query_top_callers() == []


# ─── query_dead_agents ────────────────────────────────────────────────


def test_dead_agent_no_activations_in_window(tmp_store):
    """Agents with last activation older than `since_days` are flagged."""
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=45)).isoformat()
    tmp_store.parent.mkdir(parents=True, exist_ok=True)
    tmp_store.write_text(
        json.dumps({
            "ts": old_ts,
            "subagent_type": "dormant-agent",
            "session_id": "sess-old",
        }) + "\n",
        encoding="utf-8",
    )
    record_activation("active-agent", "sess-now")
    dead = query_dead_agents(since_days=30)
    types = [agent for agent, _ in dead]
    assert "dormant-agent" in types
    assert "active-agent" not in types


def test_dead_agents_include_last_seen_timestamp(tmp_store):
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=60)).isoformat()
    tmp_store.parent.mkdir(parents=True, exist_ok=True)
    tmp_store.write_text(
        json.dumps({
            "ts": old_ts,
            "subagent_type": "ancient",
            "session_id": "sess-archaeology",
        }) + "\n",
        encoding="utf-8",
    )
    dead = query_dead_agents(since_days=30)
    assert dead
    agent, last_seen = dead[0]
    assert agent == "ancient"
    assert last_seen == old_ts


def test_dead_agents_empty_when_all_recent(tmp_store):
    record_activation("active-agent", "sess-1")
    assert query_dead_agents(since_days=30) == []


# ─── Activation dataclass ─────────────────────────────────────────────


def test_activation_dataclass_fields():
    a = Activation(
        ts="2026-05-28T00:00:00+00:00",
        subagent_type="senior-dev",
        session_id="sess-1",
    )
    assert a.ts.startswith("2026")
    assert a.subagent_type == "senior-dev"
    assert a.session_id == "sess-1"
