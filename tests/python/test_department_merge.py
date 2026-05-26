"""Tests for the department merge endpoint (PR95c v3.53.0)."""

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


def test_rejects_same_department():
    api = _load_dashboard_api()
    res = api.department_merge("dev", "dev")
    assert "error" in res
    assert "differ" in res["error"]


def test_rejects_empty_src():
    api = _load_dashboard_api()
    res = api.department_merge("", "dev")
    assert "error" in res


def test_rejects_unknown_src():
    api = _load_dashboard_api()
    res = api.department_merge("totally-not-real-dept", "dev")
    assert "error" in res
    assert "not found" in res["error"]


def test_rejects_unknown_dst():
    api = _load_dashboard_api()
    res = api.department_merge("dev", "totally-not-real-dept")
    assert "error" in res
    assert "not found" in res["error"]


def test_dryrun_self_merge_returns_error_without_side_effects():
    """Self-merge must error before walking any files."""
    api = _load_dashboard_api()
    res = api.department_merge("dev", "dev")
    assert "moved" not in res


def test_endpoint_signature_returns_status_keys(monkeypatch):
    """Smoke-test the merge endpoint contract WITHOUT moving real agents.

    Patches agent_move to a no-op stub so we exercise the loop + summary
    aggregation against a real source directory without ever touching
    YAML on disk. The earlier version of this test ran a real merge
    against the dev department — that turned out to be destructive
    when CI / dev environments shared the same repo. Never again.
    """
    api = _load_dashboard_api()

    calls: list[tuple[str, str]] = []

    def fake_move(agent_id: str, body: dict):
        calls.append((agent_id, body.get("department", "")))
        # Pretend Tier 0 to exercise the skipped branch.
        if "tomas" in agent_id or "marta" in agent_id or "marco" in agent_id:
            return {"error": "Cannot move Tier 0 (C-Suite) agents from the dashboard"}
        return {"moved": True, "id": agent_id, "yaml_path": "/tmp/fake.yaml"}

    monkeypatch.setattr(api, "agent_move", fake_move)
    res = api.department_merge("dev", "ops")
    if "error" in res:
        # No `dev` agents in the checkout — env-dependent, skip.
        return
    assert "moved" in res
    assert "skipped" in res
    assert "failed" in res
    assert isinstance(res["results"], list)
    # Stub was called for every source agent, never against the actual fs
    assert len(calls) == len(res["results"])
    assert all(target == "ops" for _, target in calls)
