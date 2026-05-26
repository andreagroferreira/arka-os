"""Tests for the agent YAML update endpoint (PR95b v3.52.0)."""

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


def test_rejects_non_object_body():
    api = _load_dashboard_api()
    res = api.agent_update_yaml("some-id", "not a dict")
    assert "error" in res


def test_rejects_empty_content():
    api = _load_dashboard_api()
    res = api.agent_update_yaml("some-id", {"content": ""})
    assert "error" in res
    assert "required" in res["error"]


def test_rejects_unknown_agent():
    api = _load_dashboard_api()
    res = api.agent_update_yaml(
        "definitely-not-real-agent-zzzz",
        {"content": "id: x\n"},
    )
    assert "error" in res
    assert "not found" in res["error"].lower()


def test_rejects_invalid_yaml():
    """When YAML parses but root is not a dict, refuse."""
    api = _load_dashboard_api()
    # Create a throwaway agent so we have something to point at.
    created = api._do_agent_create({
        "name": "Probe",
        "role": "Tester",
        "department": "dev",
        "tier": 2,
        "id": "agent-yaml-update-probe",
    })
    if not created.get("created"):
        return
    yaml_path = Path(created["yaml_path"])
    try:
        res = api.agent_update_yaml(
            "agent-yaml-update-probe",
            {"content": "- not\n- a\n- mapping\n"},
        )
        assert "error" in res
        assert "mapping" in res["error"]
    finally:
        if yaml_path.exists():
            yaml_path.unlink()


def test_rejects_id_mismatch():
    api = _load_dashboard_api()
    created = api._do_agent_create({
        "name": "Probe2",
        "role": "Tester",
        "department": "dev",
        "tier": 2,
        "id": "agent-yaml-mismatch-probe",
    })
    if not created.get("created"):
        return
    yaml_path = Path(created["yaml_path"])
    try:
        res = api.agent_update_yaml(
            "agent-yaml-mismatch-probe",
            {"content": "id: different-id\nname: X\n"},
        )
        assert "error" in res
        assert "match" in res["error"]
    finally:
        if yaml_path.exists():
            yaml_path.unlink()


def test_refuses_tier_zero():
    api = _load_dashboard_api()
    agents = api._load_agents()
    tier0 = [a for a in agents if int(a.get("tier") or 99) == 0]
    if not tier0:
        return
    target = tier0[0]
    res = api.agent_update_yaml(target["id"], {"content": "id: " + target["id"] + "\n"})
    assert "error" in res
    assert "Tier 0" in res["error"]


def test_round_trip_update_preserves_content():
    api = _load_dashboard_api()
    created = api._do_agent_create({
        "name": "Round Trip",
        "role": "Tester",
        "department": "dev",
        "tier": 2,
        "id": "agent-yaml-roundtrip-probe",
    })
    if not created.get("created"):
        return
    yaml_path = Path(created["yaml_path"])
    try:
        original = yaml_path.read_text(encoding="utf-8")
        res = api.agent_update_yaml(
            "agent-yaml-roundtrip-probe", {"content": original},
        )
        assert res.get("updated") is True
        assert yaml_path.read_text(encoding="utf-8") == original
    finally:
        if yaml_path.exists():
            yaml_path.unlink()
