"""Tests for core.synapse.agent_experiences_layer (PR3 Squad Intelligence)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.governance import agent_experiences
from core.governance.agent_experiences import Experience, record_experience
from core.synapse.agent_experiences_layer import (
    AgentExperiencesLayer,
    _extract_dispatch_target,
    format_experiences,
)
from core.synapse.layers import PromptContext


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_experiences, "AGENTS_ROOT", tmp_path / "agents")
    return tmp_path / "agents"


def _exp(agent_id: str, **kwargs) -> Experience:
    base = dict(
        ts=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        session_id="sess-1",
        context="PR1 implementation",
        verdict="REJECTED",
        blockers=["B1: evaluate() 31 lines"],
        patterns=["function-length-violation"],
        fix_applied=None,
        references=[],
        tags=[],
    )
    base.update(kwargs)
    return Experience(**base)


# ─── Dispatch target extraction ────────────────────────────────────────


def test_extract_target_from_dispatch_marker():
    text = "Lorem ipsum\n[arka:dispatch] paulo -> frontend-dev\nmore"
    assert _extract_dispatch_target(text) == "frontend-dev"


def test_extract_target_case_insensitive():
    assert _extract_dispatch_target("[ARKA:DISPATCH] paulo -> Senior-Dev") == "senior-dev"


def test_extract_target_returns_last_when_multiple():
    text = "[arka:dispatch] paulo -> frontend-dev\nmid\n[arka:dispatch] paulo -> security-eng"
    assert _extract_dispatch_target(text) == "security-eng"


def test_extract_target_returns_none_when_absent():
    assert _extract_dispatch_target("nothing here") is None
    assert _extract_dispatch_target("") is None


def test_extract_target_handles_routing_does_not_trigger():
    # [arka:routing] should NOT be matched by the dispatch regex
    text = "[arka:routing] dev -> Paulo\nnothing dispatched"
    assert _extract_dispatch_target(text) is None


# ─── Layer compute path ────────────────────────────────────────────────


def test_layer_returns_empty_when_no_dispatch(tmp_store):
    layer = AgentExperiencesLayer()
    result = layer.compute(PromptContext(user_input="no dispatch here"))
    assert result.content == ""
    assert result.tokens_est == 0


def test_layer_returns_empty_when_target_has_no_experiences(tmp_store):
    layer = AgentExperiencesLayer()
    result = layer.compute(
        PromptContext(user_input="[arka:dispatch] paulo -> frontend-dev")
    )
    assert result.content == ""
    assert "frontend-dev" in result.tag
    assert "none" in result.tag


def test_layer_injects_recent_experiences(tmp_store):
    record_experience(_exp("frontend-dev", context="PR0 attempt"))
    record_experience(_exp("frontend-dev", context="PR1 attempt", patterns=["naming"]))
    layer = AgentExperiencesLayer(limit=5)
    result = layer.compute(
        PromptContext(user_input="[arka:dispatch] paulo -> frontend-dev")
    )
    assert "Past lessons for frontend-dev" in result.content
    assert "PR0 attempt" in result.content
    assert "PR1 attempt" in result.content
    assert "naming" in result.content
    assert "count:2" in result.tag


def test_layer_respects_limit(tmp_store):
    for i in range(10):
        record_experience(_exp("frontend-dev", context=f"pr{i}"))
    layer = AgentExperiencesLayer(limit=3)
    result = layer.compute(
        PromptContext(user_input="[arka:dispatch] paulo -> frontend-dev")
    )
    assert "count:3" in result.tag


# ─── Format ────────────────────────────────────────────────────────────


def test_format_includes_blockers_and_patterns():
    exps = [
        _exp(
            "frontend-dev",
            context="PR1",
            blockers=["B1: evaluate() 31 lines", "B2: glob 37 lines"],
            patterns=["function-length-violation", "governance-gap"],
            fix_applied="extracted helper",
            references=["https://example.com/pr/204"],
        )
    ]
    out = format_experiences("frontend-dev", exps)
    assert "PR1" in out
    assert "function-length-violation" in out
    assert "governance-gap" in out
    assert "B1: evaluate() 31 lines" in out
    assert "B2: glob 37 lines" in out
    assert "extracted helper" in out
    assert "https://example.com/pr/204" in out
    assert "Apply these lessons proactively" in out


def test_format_truncates_blockers_at_three():
    exps = [
        _exp(
            "frontend-dev",
            blockers=[f"B{i}: issue" for i in range(10)],
        )
    ]
    out = format_experiences("frontend-dev", exps)
    assert "B0:" in out
    assert "B1:" in out
    assert "B2:" in out
    # B3+ should NOT appear
    assert "B3:" not in out


def test_layer_priority_and_id():
    layer = AgentExperiencesLayer()
    assert layer.id == "L2.6"
    assert layer.name == "AgentExperiences"
    assert layer.cache_ttl == 30
    assert layer.priority == 25
