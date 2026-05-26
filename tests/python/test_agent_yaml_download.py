"""Tests for the agent YAML download endpoint (PR89d v3.30.0)."""

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


def test_unknown_agent_returns_error_dict():
    api = _load_dashboard_api()
    res = api.agent_download_yaml("nonexistent-zzzzz")
    # When agent missing, returns plain dict instead of Response
    assert isinstance(res, dict)
    assert "error" in res


def test_returns_response_for_existing_agent():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return  # Environment-dependent
    res = api.agent_download_yaml(agents[0]["id"])
    # FastAPI Response — has body + headers
    assert hasattr(res, "body")
    assert res.media_type == "application/x-yaml"
    assert "attachment" in res.headers.get("content-disposition", "")


def test_content_disposition_includes_filename():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    target = agents[0]
    res = api.agent_download_yaml(target["id"])
    if isinstance(res, dict):
        return
    assert ".yaml" in res.headers["content-disposition"]


def test_body_contains_yaml_keys():
    api = _load_dashboard_api()
    agents = api._load_agents()
    if not agents:
        return
    res = api.agent_download_yaml(agents[0]["id"])
    if isinstance(res, dict):
        return
    body = res.body.decode("utf-8") if isinstance(res.body, bytes) else res.body
    # Every agent YAML should start with `id:` and have `name:`
    assert "id:" in body
    assert "name:" in body
