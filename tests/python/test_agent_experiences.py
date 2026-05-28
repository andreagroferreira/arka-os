"""Tests for core.governance.agent_experiences (PR3 Squad Intelligence).

Append-only Experience store backing the QG-feedback-loop persistence.
Storage: ~/.arkaos/agents/<agent_id>/experiences.jsonl. Tests use tmp
paths via monkeypatch so the real operator vault is never touched.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


agent_experiences = pytest.importorskip(
    "core.governance.agent_experiences",
    reason="agent_experiences not yet implemented (TDD red phase)",
)
Experience = agent_experiences.Experience
record_experience = agent_experiences.record_experience
query_experiences = agent_experiences.query_experiences


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    """Isolate AGENTS_ROOT to tmp_path so no real vault is touched."""
    monkeypatch.setattr(agent_experiences, "AGENTS_ROOT", tmp_path / "agents")
    return tmp_path / "agents"


def _make_experience(
    *,
    ts: datetime | None = None,
    agent_id: str = "tech-lead-paulo",
    session_id: str = "sess-1",
    context: str = "PR1 implementation",
    verdict: str = "REJECTED",
    blockers: list[str] | None = None,
    patterns: list[str] | None = None,
    fix_applied: str | None = None,
    references: list[str] | None = None,
    tags: list[str] | None = None,
) -> Experience:
    return Experience(
        ts=(ts or datetime.now(timezone.utc)).isoformat(),
        agent_id=agent_id,
        session_id=session_id,
        context=context,
        verdict=verdict,
        blockers=blockers if blockers is not None else ["B1: evaluate() 31 lines"],
        patterns=patterns if patterns is not None else ["function-length-violation"],
        fix_applied=fix_applied,
        references=references if references is not None else [],
        tags=tags if tags is not None else [],
    )


# ─── Storage roundtrip ─────────────────────────────────────────────────


def test_record_and_query_roundtrip(tmp_store):
    exp = _make_experience()
    record_experience(exp)
    results = query_experiences("tech-lead-paulo")
    assert len(results) == 1
    assert results[0].agent_id == "tech-lead-paulo"
    assert results[0].verdict == "REJECTED"
    assert "B1" in results[0].blockers[0]


def test_record_creates_jsonl_at_safe_path(tmp_store):
    exp = _make_experience()
    record_experience(exp)
    expected = tmp_store / "tech-lead-paulo" / "experiences.jsonl"
    assert expected.exists()
    line = expected.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert json.loads(line)["agent_id"] == "tech-lead-paulo"


def test_query_missing_agent_returns_empty(tmp_store):
    assert query_experiences("no-such-agent") == []


def test_query_returns_recent_first(tmp_store):
    now = datetime.now(timezone.utc)
    old = _make_experience(ts=now - timedelta(hours=2), context="old")
    new = _make_experience(ts=now, context="new")
    record_experience(old)
    record_experience(new)
    results = query_experiences("tech-lead-paulo")
    assert results[0].context == "new"
    assert results[1].context == "old"


# ─── Filters ────────────────────────────────────────────────────────────


def test_query_limit(tmp_store):
    for i in range(10):
        record_experience(_make_experience(context=f"pr{i}"))
    results = query_experiences("tech-lead-paulo", limit=3)
    assert len(results) == 3


def test_query_since(tmp_store):
    now = datetime.now(timezone.utc)
    old = _make_experience(ts=now - timedelta(days=2), context="old")
    fresh = _make_experience(ts=now, context="fresh")
    record_experience(old)
    record_experience(fresh)
    results = query_experiences("tech-lead-paulo", since=now - timedelta(hours=1))
    assert len(results) == 1
    assert results[0].context == "fresh"


def test_query_tag_filter(tmp_store):
    a = _make_experience(context="a", tags=["function-length"])
    b = _make_experience(context="b", tags=["security"])
    c = _make_experience(context="c", tags=["function-length", "docs"])
    record_experience(a)
    record_experience(b)
    record_experience(c)
    results = query_experiences("tech-lead-paulo", tag="function-length")
    contexts = sorted(r.context for r in results)
    assert contexts == ["a", "c"]


# ─── Robustness ────────────────────────────────────────────────────────


def test_malformed_jsonl_line_skipped(tmp_store):
    record_experience(_make_experience())
    # Corrupt the file by appending garbage
    path = tmp_store / "tech-lead-paulo" / "experiences.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ not valid json\n")
    record_experience(_make_experience(context="after-corruption"))
    results = query_experiences("tech-lead-paulo")
    contexts = sorted(r.context for r in results)
    # Both valid records returned; corrupt line silently skipped
    assert "after-corruption" in contexts


def test_blank_lines_skipped(tmp_store):
    record_experience(_make_experience())
    path = tmp_store / "tech-lead-paulo" / "experiences.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n\n")
    results = query_experiences("tech-lead-paulo")
    assert len(results) == 1


# ─── Path-traversal safety ─────────────────────────────────────────────


def test_record_rejects_unsafe_agent_id(tmp_store):
    exp = _make_experience(agent_id="../../evil")
    # Should silently skip (no exception), nothing written to evil path
    record_experience(exp)
    assert not (tmp_store.parent / "evil").exists()
    # Reading back the malicious agent_id should also return empty
    assert query_experiences("../../evil") == []


def test_record_rejects_empty_agent_id(tmp_store):
    exp = _make_experience(agent_id="")
    record_experience(exp)
    # No file should be created at all
    assert list(tmp_store.glob("*/experiences.jsonl")) == []


def test_query_rejects_unsafe_agent_id(tmp_store):
    # Even if an unsafe agent_id was somehow written, query rejects it
    assert query_experiences("../escape") == []


# ─── Experience dataclass shape ────────────────────────────────────────


def test_experience_dataclass_fields():
    exp = _make_experience()
    # Required fields
    assert hasattr(exp, "ts")
    assert hasattr(exp, "agent_id")
    assert hasattr(exp, "session_id")
    assert hasattr(exp, "context")
    assert hasattr(exp, "verdict")
    assert hasattr(exp, "blockers")
    assert hasattr(exp, "patterns")
    assert hasattr(exp, "fix_applied")
    assert hasattr(exp, "references")
    assert hasattr(exp, "tags")


def test_experience_serializes_to_dict():
    exp = _make_experience(
        references=["https://github.com/x/y/pull/204"],
        tags=["solid-clean-code", "function-length"],
    )
    d = agent_experiences.experience_to_dict(exp)
    assert d["agent_id"] == "tech-lead-paulo"
    assert d["tags"] == ["solid-clean-code", "function-length"]
    assert isinstance(d["references"], list)
