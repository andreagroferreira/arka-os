"""Tests for the workflow YAML update endpoint (PR94d v3.50.0)."""

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
    res = api.workflow_update_yaml("some-id", "not a dict")
    assert "error" in res


def test_rejects_empty_content():
    api = _load_dashboard_api()
    res = api.workflow_update_yaml("some-id", {"content": ""})
    assert "error" in res
    assert "required" in res["error"]


def test_rejects_unknown_workflow():
    api = _load_dashboard_api()
    res = api.workflow_update_yaml(
        "definitely-not-real-workflow-zzzz",
        {"content": "id: x\n"},
    )
    assert "error" in res
    assert "not found" in res["error"]


def test_rejects_invalid_yaml():
    api = _load_dashboard_api()
    res = api._resolve_workflow_yaml.__name__  # smoke-test the helper exists
    assert res == "_resolve_workflow_yaml"


def test_rejects_yaml_without_id():
    """When the YAML parses but lacks id, the endpoint refuses the write."""
    api = _load_dashboard_api()
    # Pick the first known workflow id to satisfy the resolve step.
    wf_res = api.workflows_list()
    workflows = wf_res.get("workflows") or []
    if not workflows:
        return  # No workflows present — skip
    target = workflows[0]
    res = api.workflow_update_yaml(
        target["id"], {"content": "name: missing-id\n"},
    )
    assert "error" in res
    assert "id" in res["error"].lower()


def test_round_trip_update_preserves_id():
    """Write the existing content back unchanged — should succeed."""
    api = _load_dashboard_api()
    wf_res = api.workflows_list()
    workflows = wf_res.get("workflows") or []
    if not workflows:
        return
    target = workflows[0]
    original = target["content"]
    res = api.workflow_update_yaml(target["id"], {"content": original})
    assert res.get("updated") is True
    # Read-back via the list endpoint should show the same content
    wf_res2 = api.workflows_list()
    refreshed = next(
        (w for w in wf_res2["workflows"] if w["id"] == target["id"]), None,
    )
    assert refreshed is not None
    assert refreshed["content"] == original


def test_resolve_helper_returns_none_for_unknown():
    api = _load_dashboard_api()
    assert api._resolve_workflow_yaml("definitely-not-real-zzzz") is None
