"""PTY session + manager for the dashboard terminal.

PR99a v3.67.0 — spawns a forked shell on a pseudo-terminal, exposes
bidirectional read/write/resize over a file descriptor, and offers a
manager that caps concurrent sessions and reaps dead/idle ones.

Design notes
------------
* ``pty.fork`` is used (not ``pty.openpty`` + ``Popen``) because we want
  the child to be a session leader with a controlling tty — that is what
  makes the shell behave interactively (job control, signals, prompts,
  ANSI rendering).
* The master fd is set non-blocking so the asyncio loop in the
  dashboard-api can ``add_reader`` it and pump bytes to the WebSocket
  without a thread pool.
* The manager keeps sessions in a dict keyed by url-safe id; nothing
  here imports FastAPI so the unit tests can run without spinning up an
  HTTP app.
"""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import secrets
import signal
import struct
import termios
import time
from typing import Any, Optional

from core.terminal import audit


class SessionCapacityError(RuntimeError):
    """Raised when ``create()`` is called past the configured cap."""


def _default_shell() -> str:
    return os.environ.get("SHELL") or "/bin/zsh"


def _default_cwd() -> str:
    return os.path.expanduser("~")


# v3.71.0 — in-memory scrollback so a reconnecting client (after the
# operator navigates away or reloads the dashboard) can replay recent
# output and find its session as it left it. Bounded, RAM-only, cleared
# on close, never written to disk and never sent to the audit log.
DEFAULT_SCROLLBACK_BYTES = 512 * 1024


class TerminalSession:
    """A single forked PTY + the bookkeeping needed to drive it.

    Public attributes are read-only from the outside; mutate state via
    the methods so the manager can keep its invariants.
    """

    def __init__(
        self,
        session_id: str,
        shell: str,
        cwd: str,
        cols: int = 120,
        rows: int = 32,
        scrollback_bytes: int = DEFAULT_SCROLLBACK_BYTES,
    ) -> None:
        self.session_id = session_id
        self.shell = shell
        self.cwd = cwd
        self.created_at = time.time()
        self.last_activity = time.monotonic()
        self.exit_code: Optional[int] = None
        self.title: str = ""
        self.scrollback_max = max(0, int(scrollback_bytes))
        self._scrollback = bytearray()
        self._closed = False
        self.pid, self.master_fd = pty.fork()
        if self.pid == 0:
            self._child_exec(shell, cwd)
        os.set_blocking(self.master_fd, False)
        self.resize(cols, rows)

    @staticmethod
    def _child_exec(shell: str, cwd: str) -> None:
        try:
            os.chdir(cwd)
        except OSError:
            pass
        env = os.environ.copy()
        env["TERM"] = env.get("TERM", "xterm-256color")
        env["COLORTERM"] = env.get("COLORTERM", "truecolor")
        try:
            os.execvpe(shell, [shell, "-l"], env)
        except OSError:
            os._exit(127)

    def read(self, max_bytes: int = 4096) -> bytes:
        """Non-blocking read. Returns ``b""`` when there is nothing yet."""
        if self._closed or self.master_fd < 0:
            return b""
        try:
            data = os.read(self.master_fd, max_bytes)
        except BlockingIOError:
            return b""
        except OSError as exc:
            if exc.errno in (errno.EIO, errno.EBADF):
                self._closed = True
                return b""
            raise
        if data:
            self.last_activity = time.monotonic()
            self._record(data)
        return data

    def _record(self, data: bytes) -> None:
        """Append output to the bounded scrollback, evicting the oldest."""
        if self.scrollback_max <= 0:
            return
        self._scrollback += data
        if len(self._scrollback) > self.scrollback_max:
            del self._scrollback[: -self.scrollback_max]

    def scrollback(self) -> bytes:
        """Snapshot of recent output, for replay on (re)connect."""
        return bytes(self._scrollback)

    def write(self, data: bytes) -> int:
        if self._closed or self.master_fd < 0 or not data:
            return 0
        try:
            n = os.write(self.master_fd, data)
        except OSError:
            self._closed = True
            return 0
        self.last_activity = time.monotonic()
        return n

    def resize(self, cols: int, rows: int) -> None:
        if self._closed or self.master_fd < 0:
            return
        cols = max(1, int(cols))
        rows = max(1, int(rows))
        try:
            fcntl.ioctl(
                self.master_fd,
                termios.TIOCSWINSZ,
                struct.pack("HHHH", rows, cols, 0, 0),
            )
        except OSError:
            pass

    def is_alive(self) -> bool:
        if self._closed:
            return False
        try:
            wpid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            self._closed = True
            return False
        except OSError:
            return False
        if wpid == 0:
            return True
        self.exit_code = os.waitstatus_to_exitcode(status)
        self._closed = True
        return False

    def kill(self, sig: int = signal.SIGTERM) -> None:
        if self._closed:
            return
        try:
            os.kill(self.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        for _ in range(10):
            if not self.is_alive():
                break
            time.sleep(0.05)
        if self.is_alive():
            try:
                os.kill(self.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self._close_fd()

    def _close_fd(self) -> None:
        if self.master_fd >= 0:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = -1
        self._scrollback.clear()
        self._closed = True

    def to_dict(self) -> dict[str, Any]:
        idle_s = max(0.0, time.monotonic() - self.last_activity)
        return {
            "session_id": self.session_id,
            "shell": self.shell,
            "cwd": self.cwd,
            "title": self.title or self.session_id,
            "created_at": self.created_at,
            "idle_seconds": round(idle_s, 1),
            "alive": self.is_alive(),
            "exit_code": self.exit_code,
        }


class TerminalSessionManager:
    """Owns the dict of live sessions and enforces caps + idle-kill."""

    DEFAULT_MAX = 8
    DEFAULT_IDLE_S = 1800  # 30 minutes

    def __init__(
        self,
        max_sessions: Optional[int] = None,
        idle_timeout_s: Optional[int] = None,
    ) -> None:
        max_default = self.DEFAULT_MAX if max_sessions is None else max_sessions
        idle_default = self.DEFAULT_IDLE_S if idle_timeout_s is None else idle_timeout_s
        self.max_sessions = int(
            os.environ.get("ARKAOS_TERMINAL_MAX_SESSIONS", max_default)
        )
        self.idle_timeout_s = int(
            os.environ.get("ARKAOS_TERMINAL_IDLE_S", idle_default)
        )
        self.scrollback_bytes = int(
            os.environ.get("ARKAOS_TERMINAL_SCROLLBACK_BYTES", DEFAULT_SCROLLBACK_BYTES)
        )
        self._sessions: dict[str, TerminalSession] = {}

    def create(
        self,
        shell: Optional[str] = None,
        cwd: Optional[str] = None,
        cols: int = 120,
        rows: int = 32,
    ) -> TerminalSession:
        self.reap_dead()
        if len(self._sessions) >= self.max_sessions:
            raise SessionCapacityError(
                f"max sessions ({self.max_sessions}) reached"
            )
        sid = secrets.token_urlsafe(8)
        chosen_shell = shell or _default_shell()
        chosen_cwd = cwd or _default_cwd()
        session = TerminalSession(
            session_id=sid,
            shell=chosen_shell,
            cwd=chosen_cwd,
            cols=cols,
            rows=rows,
            scrollback_bytes=self.scrollback_bytes,
        )
        self._sessions[sid] = session
        audit.log_start(sid, chosen_shell, chosen_cwd)
        return session

    def get(self, session_id: str) -> Optional[TerminalSession]:
        return self._sessions.get(session_id)

    def list_all(self) -> list[dict]:
        self.reap_dead()
        return [s.to_dict() for s in self._sessions.values()]

    def count(self) -> int:
        return len(self._sessions)

    def close(self, session_id: str, reason: str = "closed") -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.kill()
        audit.log_end(session_id, session.exit_code, reason=reason)
        return True

    def reap_dead(self) -> int:
        dead = [sid for sid, s in self._sessions.items() if not s.is_alive()]
        for sid in dead:
            session = self._sessions.pop(sid)
            session._close_fd()
            audit.log_end(sid, session.exit_code, reason="exited")
        return len(dead)

    def reap_idle(self) -> int:
        now = time.monotonic()
        timeout = self.idle_timeout_s
        idle = [
            sid for sid, s in self._sessions.items()
            if now - s.last_activity > timeout
        ]
        for sid in idle:
            self.close(sid, reason="idle-timeout")
        return len(idle)

    def shutdown(self) -> None:
        for sid in list(self._sessions.keys()):
            self.close(sid, reason="shutdown")


_default_manager: Optional[TerminalSessionManager] = None


def default_manager() -> TerminalSessionManager:
    """Lazy global manager — one per process."""
    global _default_manager
    if _default_manager is None:
        _default_manager = TerminalSessionManager()
    return _default_manager
