"""Tests for mcps/arka-tools/server.py (F2-3).

The FastMCP decorators wrap plain functions — tests import the module
with the repo pinned and call the underlying logic directly, with
stores isolated to tmp HOME. The honesty contract is the core subject:
absent stores => {"available": false, "reason": ...}, never fabricated.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def tools(tmp_path, monkeypatch):
    """Import a fresh server module with isolated HOME + pinned repo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARKA_OS", str(REPO_ROOT))
    monkeypatch.setenv("ARKA_SESSION_MEMORY_DB", str(tmp_path / "sm.db"))
    monkeypatch.delenv("ARKA_TOOLS_WRITE", raising=False)
    monkeypatch.setenv(
        "ARKA_ROUTING_SCORES_PATH", str(tmp_path / "routing-scores.json")
    )
    spec = importlib.util.spec_from_file_location(
        "arka_tools_server_under_test",
        REPO_ROOT / "mcps" / "arka-tools" / "server.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("arka_tools_server_under_test", None)


def _fn(tools, name):
    """Unwrap the FastMCP tool back to the plain function."""
    attr = getattr(tools, name)
    return getattr(attr, "fn", attr)


# ─── honesty contract: absent stores are honest, never fabricated ─────


def test_kb_search_absent_store_is_honest(tools):
    result = _fn(tools, "kb_search")("payment retry")
    assert result["available"] is False
    assert "knowledge.db not found" in result["reason"]
    assert "results" not in result  # nothing invented


def test_session_memory_requires_project_scope(tools):
    result = _fn(tools, "session_memory_search")("query", "")
    assert result["available"] is False
    assert "never searches globally" in result["reason"]


def test_routing_scores_absent_is_honest(tools):
    result = _fn(tools, "routing_scores")()
    assert result["available"] is False
    assert "rebuild" in result["reason"]


# ─── write gating (v1 read-first) ──────────────────────────────────────


@pytest.mark.parametrize("tool_name,args", [
    ("workflow_update_phase", ("spec", "completed")),
    ("qg_submit", ("t", "d", "code", "paulo")),
    ("qg_verdict", ("id-1", "marta", "APPROVED")),
])
def test_write_tools_disabled_by_default(tools, tool_name, args):
    result = _fn(tools, tool_name)(*args)
    assert result["available"] is False
    assert "ARKA_TOOLS_WRITE=1" in result["reason"]


def test_write_tools_enabled_by_env(tools, monkeypatch):
    monkeypatch.setenv("ARKA_TOOLS_WRITE", "1")
    result = _fn(tools, "workflow_update_phase")("spec", "not-a-status")
    assert result["available"] is False
    assert "Invalid status" in result["reason"]  # reached the real API


# ─── read tools against real (isolated) stores ─────────────────────────


def test_workflow_get_none_active(tools):
    result = _fn(tools, "workflow_get")()
    assert result == {"available": True, "active": False}


def test_qg_flow_end_to_end(tools, monkeypatch):
    monkeypatch.setenv("ARKA_TOOLS_WRITE", "1")
    submitted = _fn(tools, "qg_submit")(
        "Feature X", "does X", "code", "paulo"
    )
    assert submitted["available"] is True
    sid = submitted["submission"]["submission_id"]
    pending = _fn(tools, "qg_pending")()
    assert pending["count"] >= 1
    verdict = _fn(tools, "qg_verdict")(sid, "marta-cqo", "APPROVED", "ok")
    assert verdict == {"available": True, "recorded": True}
    status = _fn(tools, "qg_status")(sid)
    assert status["available"] is True


def test_qg_status_unknown_id(tools):
    result = _fn(tools, "qg_status")("nope-123")
    assert result["available"] is False


def test_session_memory_scoped_search(tools):
    from core.memory.semantic_store import SessionMemoryStore, TurnRecord

    store = SessionMemoryStore()
    store.save(TurnRecord(id="t1", ts="2026-07-11T00:00:00+00:00",
                          session_id="s", project_name="projX",
                          summary="payment retry queue built"))
    store.save(TurnRecord(id="t2", ts="2026-07-11T00:00:00+00:00",
                          session_id="s", project_name="clientY",
                          summary="payment secret gateway"))
    result = _fn(tools, "session_memory_search")("payment", "projX")
    assert result["available"] is True
    assert result["count"] == 1
    assert result["results"][0]["retrieval"] == "keyword-degraded"  # honest label
    assert "clientY" not in json.dumps(result)  # scope holds


def test_routing_scores_roundtrip(tools):
    from core.governance.routing_feedback import (
        RoutingScore,
        RoutingScores,
        _atomic_write,
        scores_path,
    )

    _atomic_write(scores_path(), RoutingScores(
        computed_at="2026-07-12T00:00:00+00:00",
        scores=[RoutingScore(department="dev", approvals=3, samples=5)],
    ))
    result = _fn(tools, "routing_scores")()
    assert result["available"] is True
    assert result["scores"][0]["department"] == "dev"


def test_forge_plan_none_active(tools):
    result = _fn(tools, "forge_plan")()
    assert result == {"available": True, "active": False}


def test_recipes_search_empty(tools):
    result = _fn(tools, "recipes_search")("payment", "laravel")
    assert result["available"] is True
    assert result["recipes"] == []
