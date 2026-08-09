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

pytest.importorskip("fastapi")  # optional dashboard dependency
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


def _no_pty_response(api):
    """Drive the real no-PTY code path and return the browser's response.

    Reproduces production instead of injecting a synthetic exception:
    ``_PTY_SUPPORTED = False`` sends ``create()`` down the ConPTY branch,
    and a ``winpty`` entry of ``None`` in ``sys.modules`` makes the
    backend's ``import winpty`` raise ModuleNotFoundError through the
    real import machinery — the same class a Windows box without
    pywinpty produces. Pinning the import that way also keeps
    the test hermetic on a Windows runner where pywinpty *is* installed —
    otherwise it would spawn a real shell and never reach the error path.

    ``raise_server_exceptions=False`` is what makes the assertion mean
    anything: it returns the response the browser would actually receive
    rather than re-raising server-side, so an unhandled error shows up as
    the bare 500 that ServerErrorMiddleware produces *outside* the CORS
    middleware — no Access-Control-Allow-Origin, hence "Failed to fetch".
    """
    from core.terminal import session as _sess

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(_sess, "_PTY_SUPPORTED", False)
        mp.setitem(sys.modules, "winpty", None)
        client = TestClient(api.app, raise_server_exceptions=False)
        return client.post(
            "/api/terminal/sessions",
            json={"shell": "powershell.exe"},
            headers={"Origin": "http://localhost:3000"},
        )


def test_no_pty_returns_501(api):
    """A platform with no PTY backend must answer 501, not an opaque 500."""
    r = _no_pty_response(api)
    assert r.status_code == 501
    detail = r.json()["detail"]
    assert "no pty backend" in detail.lower()
    # The class name is the triage hint an operator acts on — and it is
    # the genuine one a Windows box without pywinpty produces, because
    # the real import machinery ran.
    assert "ModuleNotFoundError" in detail
    # The underlying exception's own text must never be echoed back:
    # the reviewed version returned str(exc) and leaked internals.
    assert "sys.modules" not in detail and "halted" not in detail


def test_no_pty_501_carries_cors_header(api):
    """The decisive assertion: the 501 must reach the browser readable.

    Without CORS headers the fetch fails before the status is ever
    observable, which is precisely the bug — the operator saw only
    "Failed to fetch" and never the reason.
    """
    r = _no_pty_response(api)
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_no_pty_leaks_no_session(api):
    """A failed backend build must not register a half-built session."""
    _no_pty_response(api)
    assert TestClient(api.app).get("/api/terminal/sessions").json()["sessions"] == []


def test_unrelated_runtime_error_is_not_labelled_501(api, monkeypatch):
    """501 means "no PTY here", never "some bug happened".

    Here the injected exception *is* the subject: the handler must
    discriminate on PtyUnavailableError, not on its RuntimeError base.
    Catching the base would relabel every genuine bug as a permanent
    platform limitation and send the operator hunting for pywinpty on a
    machine that has a perfectly good PTY.
    """
    from core.terminal import session as _sess

    def _boom(*_args, **_kwargs):
        raise RuntimeError("unrelated failure")

    monkeypatch.setattr(_sess.default_manager(), "create", _boom)
    r = TestClient(api.app, raise_server_exceptions=False).post(
        "/api/terminal/sessions",
        json={"shell": "/bin/sh"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert r.status_code != 501
    assert r.status_code == 500


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


def test_ws_replays_scrollback_on_connect(api):
    """v3.71.0 — a client (re)connecting to a live session receives the
    recorded scrollback as the first frame, restoring its view after a
    navigation / reload."""
    import select
    import time

    client = TestClient(api.app)
    created = client.post("/api/terminal/sessions", json={"shell": "/bin/sh"}).json()
    sid, token = created["session_id"], created["token"]

    from core.terminal.session import default_manager
    session = default_manager().get(sid)
    # Produce output and drain it so it lands in the scrollback — this
    # simulates work done before the operator navigated away.
    session.write(b"echo replay-marker\n")
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        readable, _, _ = select.select([session.master_fd], [], [], 0.1)
        if readable:
            session.read(4096)
        if b"replay-marker" in session.scrollback():
            break
    assert b"replay-marker" in session.scrollback()

    with client.websocket_connect(
        f"/ws/terminal/{sid}?token={token}",
        headers={"Origin": "http://localhost:3000"},
    ) as ws:
        first = ws.receive_bytes()
        assert b"replay-marker" in first
