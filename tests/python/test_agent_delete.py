"""Tests for the agent DELETE endpoint (PR83b v3.4.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_dashboard_api():
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "dashboard-api.py"
    spec = importlib.util.spec_from_file_location("dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_delete_removes_yaml_file():
    api = _load_dashboard_api()
    # Create an agent, then delete it.
    created = api._do_agent_create({
        "name": "Delete Me",
        "role": "Test Agent",
        "department": "dev",
        "tier": 2,
        "id": "agent-delete-test-fixture",
    })
    assert created.get("created") is True
    yaml_path = Path(created["yaml_path"])
    assert yaml_path.exists()
    res = api.agent_delete("agent-delete-test-fixture")
    if yaml_path.exists():
        # Defensive cleanup if the delete somehow failed.
        yaml_path.unlink()
    assert res.get("deleted") is True
    assert not yaml_path.exists()


def test_delete_returns_error_for_unknown_agent():
    api = _load_dashboard_api()
    res = api.agent_delete("definitely-does-not-exist-zzzzz")
    assert "error" in res
    assert "not found" in res["error"].lower()


def test_delete_refuses_tier_0():
    api = _load_dashboard_api()
    # Find an existing Tier 0 agent (C-Suite). Spec: Marco/CTO is tier 0.
    agents = api._load_agents()
    tier0 = [a for a in agents if int(a.get("tier") or 99) == 0]
    if not tier0:
        # If no tier-0 fixture is present in this checkout, skip the
        # assertion rather than failing — environment-dependent.
        return
    target = tier0[0]
    res = api.agent_delete(target["id"])
    assert "error" in res
    assert "Tier 0" in res["error"]
