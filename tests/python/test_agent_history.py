"""Tests for the agent history endpoint (PR88d v3.26.0)."""

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


def test_unknown_agent_returns_empty_events():
    api = _load_dashboard_api()
    res = api.agent_history("nonexistent-agent-zzzzz")
    assert res == {"events": []}


def test_returns_payload_shape_for_existing_agent():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return  # Environment-dependent
    res = api.agent_history(agents[0]["id"], limit=5)
    assert "events" in res
    assert isinstance(res["events"], list)


def test_limit_caps_events():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_history(agents[0]["id"], limit=2)
    assert len(res["events"]) <= 2


def test_event_shape():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_history(agents[0]["id"], limit=10)
    for e in res["events"]:
        assert "kind" in e
        assert "summary" in e
        # ts may be null for malformed entries — but for git-commit events
        # we expect an iso string
        if e["kind"] == "git-commit":
            assert e.get("ts")
            assert e.get("ref")


def test_events_sorted_desc_by_ts():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_history(agents[0]["id"], limit=20)
    timestamps = [e["ts"] for e in res["events"] if e.get("ts")]
    if len(timestamps) >= 2:
        assert timestamps == sorted(timestamps, reverse=True)


def test_trash_ts_helper_returns_iso():
    api = _load_dashboard_api()
    ts = 1735689600  # 2025-01-01 UTC
    iso = api._trash_ts_to_iso(ts)
    assert iso is not None
    assert iso.startswith("20")


def test_trash_ts_helper_handles_none():
    api = _load_dashboard_api()
    assert api._trash_ts_to_iso(None) is None
