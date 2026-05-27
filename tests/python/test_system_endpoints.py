"""HTTP-level tests for the system version/update endpoints (v3.72.0, #3)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        f"dashboard_api_sys_{tmp_path.name}",
        REPO_ROOT / "scripts" / "dashboard-api.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_version_reports_update_available(api):
    api._current_version = lambda: "3.72.0"
    api._npm_latest_version = lambda: "99.0.0"
    body = TestClient(api.app).get("/api/system/version").json()
    assert body["current"] == "3.72.0"
    assert body["latest"] == "99.0.0"
    assert body["update_available"] is True


def test_no_update_when_versions_equal(api):
    api._current_version = lambda: "3.72.0"
    api._npm_latest_version = lambda: "3.72.0"
    body = TestClient(api.app).get("/api/system/version").json()
    assert body["update_available"] is False


def test_no_update_when_latest_unknown(api):
    api._current_version = lambda: "3.72.0"
    api._npm_latest_version = lambda: None
    body = TestClient(api.app).get("/api/system/version").json()
    assert body["update_available"] is False
    assert body["latest"] is None


def test_update_endpoint_invokes_runner(api):
    called = {}

    def _fake_run():
        called["ran"] = True
        return {"ok": True, "output": "ArkaOS updated."}

    api._run_core_update = _fake_run
    r = TestClient(api.app).post(
        "/api/system/update", headers={"Origin": "http://localhost:3000"}
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert called.get("ran") is True


def test_update_rejects_foreign_origin(api):
    api._run_core_update = lambda: {"ok": True, "output": "should not run"}
    r = TestClient(api.app).post(
        "/api/system/update", headers={"Origin": "http://evil.example.com"}
    )
    assert r.status_code == 403
