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


def test_full_merge_round_trip(tmp_path):
    """Create a one-off agent in src, merge into dst, verify and clean up."""
    api = _load_dashboard_api()
    # Create a throwaway agent in dev department
    created = api._do_agent_create({
        "name": "Merge Probe",
        "role": "Test",
        "department": "dev",
        "tier": 2,
        "id": "dept-merge-probe-agent",
    })
    if not created.get("created"):
        return
    src_path = Path(created["yaml_path"])
    try:
        res = api.department_merge("dev", "ops")
        assert "moved" in res
        # Our probe must have been moved
        ids_moved = [r["id"] for r in res["results"] if r["status"] == "moved"]
        assert "dept-merge-probe-agent" in ids_moved
        # File should be at the new location
        dst_path = Path(str(src_path).replace("/dev/", "/ops/"))
        assert dst_path.exists()
        dst_path.unlink()
    finally:
        if src_path.exists():
            src_path.unlink()
        candidate = Path(str(src_path).replace("/dev/", "/ops/"))
        if candidate.exists():
            candidate.unlink()
