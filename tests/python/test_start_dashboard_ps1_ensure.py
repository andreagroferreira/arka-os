"""The Windows dashboard launcher must honour the `ensure` contract.

``scripts/start-dashboard.sh`` has had `ensure` since v4.1.2 (covered by
``tests/dashboard.bats``): when the recorded API and UI ports are both
healthy, exit 0 and leave the running dashboard alone. The PowerShell port
never parsed its arguments at all, so every SessionStart -- which invokes it
with `ensure` (``core/hooks/session_start.py``) -- killed a healthy
dashboard, started a replacement out of whatever checkout the session was
in, and opened a browser tab. Issue #541.

These tests RUN the script. A substring search for "ensure" in the source
would pass against a comment; the drift guard for ``stop.ps1`` documents
exactly that failure mode, proven by mutation. Here the fall-through cases
are the mutation guard: they use a USERPROFILE with no venv, so any path
that does not early-exit provably reaches the venv guard and says so.

Windows-only by construction (the script reads %USERPROFILE% and
%ComSpec%), so this file runs on the cross-platform CI leg and skips
elsewhere rather than pretending to cover the platform it cannot execute.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "start-dashboard.ps1"

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="start-dashboard.ps1 is the Windows launcher"
)

_RESPONSE = (
    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
    b"Content-Length: 11\r\nConnection: close\r\n\r\n"
    b'{"ok":true}'
)


class StubEndpoint:
    """Always-200 loopback listener standing in for a healthy dashboard.

    Raw sockets rather than http.server: the latter's server_bind() calls
    socket.getfqdn(), which blocks long enough on Windows that the listener
    never appears while the process stays alive.
    """

    def __init__(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self.port: int = self._srv.getsockname()[1]
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(2)
                    conn.recv(4096)
                    conn.sendall(_RESPONSE)
                except OSError:
                    pass

    def close(self) -> None:
        self._stop = True
        self._srv.close()


def _run(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("no PowerShell on PATH")
    env = {
        **os.environ,
        "USERPROFILE": str(home),
        # Never let a test open the operator's browser, whatever path it takes.
        "ARKAOS_NO_BROWSER": "1",
    }
    return subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(SCRIPT), *args],
        capture_output=True, text=True, env=env, timeout=180,
    )


def _write_ports(home: Path, api_port: int, ui_port: int) -> Path:
    ports = home / ".arkaos" / "dashboard.ports"
    ports.parent.mkdir(parents=True, exist_ok=True)
    ports.write_text(f"API_PORT={api_port}\nUI_PORT={ui_port}\n", encoding="ascii")
    return ports


@pytest.fixture()
def healthy(tmp_path: Path):
    api, ui = StubEndpoint(), StubEndpoint()
    ports = _write_ports(tmp_path, api.port, ui.port)
    try:
        yield tmp_path, ports
    finally:
        api.close()
        ui.close()


def test_ensure_exits_zero_and_leaves_a_healthy_dashboard_alone(healthy) -> None:
    home, ports = healthy
    out = _run(home, "ensure")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "already running" in out.stdout
    # The full-start path deletes the ports file before rewriting it; an
    # intact file is the evidence that path was never entered.
    assert ports.is_file()


def test_ensure_falls_through_when_the_recorded_ports_are_dead(tmp_path: Path) -> None:
    dead = StubEndpoint()
    port = dead.port
    dead.close()  # nothing is listening on `port` any more
    _write_ports(tmp_path, port, port)
    out = _run(tmp_path, "ensure")
    assert "already running" not in out.stdout
    assert "venv unavailable" in out.stdout
    assert out.returncode == 1


def test_ensure_falls_through_when_no_ports_file_exists(tmp_path: Path) -> None:
    (tmp_path / ".arkaos").mkdir(parents=True, exist_ok=True)
    out = _run(tmp_path, "ensure")
    assert "already running" not in out.stdout
    assert "venv unavailable" in out.stdout
    assert out.returncode == 1


def test_without_ensure_a_healthy_dashboard_is_still_restarted(healthy) -> None:
    """`ensure` must be opt-in: a bare invocation keeps restarting.

    This is the mutation guard in the other direction -- making the
    fast-path unconditional would silently break `npx arkaos dashboard
    restart`, and every other test here would still pass.
    """
    home, _ = healthy
    out = _run(home)
    assert "already running" not in out.stdout
    assert "venv unavailable" in out.stdout
