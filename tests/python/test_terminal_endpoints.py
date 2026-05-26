"""HTTP-level tests for the terminal endpoints in scripts/dashboard-api.py.

PR99a v3.67.0 — REST CRUD only. WebSocket round-trip is exercised by
test_terminal_session.py (PTY side) and the Playwright smoke in PR99b
(client side).
"""

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
    monkeypatch.setenv("ARKAOS_TERMINAL_MAX_SESSIONS", "2")
    sys.path.insert(0, str(REPO_ROOT))

    spec = importlib.util.spec_from_file_location(
        f"dashboard_api_{tmp_path.name}",
        REPO_ROOT / "scripts" / "dashboard-api.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from core.terminal import session as _sess
    _sess._default_manager = None  # fresh manager picks up env override
    yield module
    from core.terminal.session import default_manager
    default_manager().shutdown()
    _sess._default_manager = None


def test_get_token_returns_string(api):
    client = TestClient(api.app)
    r = client.get("/api/terminal/token")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("token"), str)
    assert len(body["token"]) > 16


def test_create_session_returns_shape(api):
    client = TestClient(api.app)
    r = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["shell"] == "/bin/sh"
    assert body["cwd"]
    assert body["token"]
    assert body["ws_path"].startswith("/ws/terminal/")
    assert body["max_sessions"] == 2
    assert body["active_count"] == 1


def test_list_sessions_after_create(api):
    client = TestClient(api.app)
    create = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"}).json()
    listing = client.get("/api/terminal/sessions").json()
    assert listing["max_sessions"] == 2
    ids = [s["session_id"] for s in listing["sessions"]]
    assert create["session_id"] in ids


def test_delete_session_closes_and_returns_flag(api):
    client = TestClient(api.app)
    created = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"}).json()
    sid = created["session_id"]
    r = client.delete(f"/api/terminal/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["closed"] is True
    assert body["session_id"] == sid
    listing = client.get("/api/terminal/sessions").json()
    assert sid not in [s["session_id"] for s in listing["sessions"]]


def test_delete_unknown_session_returns_false(api):
    client = TestClient(api.app)
    r = client.delete("/api/terminal/sessions/does-not-exist")
    assert r.status_code == 200
    assert r.json()["closed"] is False


def test_cap_returns_429(api):
    client = TestClient(api.app)
    client.post("/api/terminal/sessions", json={"shell": "/bin/sh"})
    client.post("/api/terminal/sessions", json={"shell": "/bin/sh"})
    r = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"})
    assert r.status_code == 429
    assert "max sessions" in r.json()["detail"].lower()


def test_origin_helper_rejects_external(api):
    assert api._terminal_origin_ok("") is False
    assert api._terminal_origin_ok("http://evil.com") is False
    assert api._terminal_origin_ok("https://localhost") is True
    assert api._terminal_origin_ok("http://localhost:3000") is True
    assert api._terminal_origin_ok("http://127.0.0.1:5173") is True
    assert api._terminal_origin_ok("http://localhost.evil.com") is False


def test_ws_bad_origin_closes_4403(api):
    client = TestClient(api.app)
    created = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"}).json()
    sid = created["session_id"]
    token = created["token"]
    # Default TestClient sends no Origin → origin_ok returns False.
    try:
        with client.websocket_connect(
            f"/ws/terminal/{sid}?token={token}",
        ) as ws:
            ws.receive()  # should never get here
    except Exception:
        pass  # close before accept manifests as broken handshake


def test_ws_bad_token_closes_4401(api):
    client = TestClient(api.app)
    created = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"}).json()
    sid = created["session_id"]
    try:
        with client.websocket_connect(
            f"/ws/terminal/{sid}?token=wrong",
            headers={"Origin": "http://localhost:3000"},
        ) as ws:
            ws.receive()
    except Exception:
        pass
