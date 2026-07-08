"""Windows PTY session backend (ConPTY via pywinpty).

The POSIX backend in ``session.py`` builds on ``pty.fork`` + fcntl /
termios, none of which exist on Windows. This module provides the same
``TerminalSession`` surface on top of pywinpty's ConPTY wrapper, so the
dashboard terminal works on Windows. ``TerminalSessionManager.create``
selects it when ``os.name == "nt"``.

IO model
--------
pywinpty's ``read`` is blocking and there is no pollable fd, so the POSIX
approach (``loop.add_reader(master_fd)``) does not apply. Instead each
session owns one daemon reader thread that drains the pty for the
session's whole lifetime: it always appends to the bounded scrollback
(so a client reconnecting after navigating away replays what it missed)
and, when a WebSocket is attached, forwards each chunk to that single
``listener``. Decoupling the reader from the connection avoids two
readers racing on the same pty across a reload/supersede.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from core.terminal import audit

DEFAULT_SCROLLBACK_BYTES = 512 * 1024


class WindowsTerminalSession:
    """A ConPTY-backed shell + the bookkeeping the manager relies on.

    Mirrors the public surface of ``session.TerminalSession``:
    ``read``/``write``/``resize``/``scrollback``/``is_alive``/``kill``/
    ``to_dict`` plus the ``session_id``/``shell``/``cwd``/``exit_code``
    attributes. ``master_fd`` is always ``-1`` — the dashboard WebSocket
    handler uses that to pick the thread-listener pump instead of
    ``add_reader``.
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
        import winpty  # lazy: the dependency is only needed on Windows

        self.session_id = session_id
        self.shell = shell
        self.cwd = cwd
        self.created_at = time.time()
        self.last_activity = time.monotonic()
        self.exit_code: Optional[int] = None
        self.title = ""
        self.scrollback_max = max(0, int(scrollback_bytes))
        self._scrollback = bytearray()
        self._closed = False
        self.master_fd = -1  # no pollable fd on Windows

        # ConPTY dimensions are (rows, cols).
        self._proc = winpty.PtyProcess.spawn(
            shell,
            cwd=cwd,
            dimensions=(max(1, int(rows)), max(1, int(cols))),
        )
        self.pid = self._proc.pid

        self._listener: Optional[Callable[[bytes], None]] = None
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # -- reader thread ------------------------------------------------------
    def _read_loop(self) -> None:
        """Drain the pty for the session lifetime; feed scrollback + listener."""
        while not self._closed:
            try:
                chunk = self._proc.read(8192)
            except EOFError:
                break
            except OSError:
                break
            if not chunk:
                if not self._proc_alive():
                    break
                continue
            raw = chunk.encode("utf-8", "replace") if isinstance(chunk, str) else bytes(chunk)
            self.last_activity = time.monotonic()
            # Record + capture the listener under the lock so attach() can
            # snapshot scrollback and start receiving with no gap and no dup.
            with self._lock:
                self._record(raw)
                listener = self._listener
            if listener is not None:
                try:
                    listener(raw)
                except Exception:
                    pass
        self._closed = True

    def attach(self, listener: Callable[[bytes], None]) -> bytes:
        """Atomically snapshot scrollback and register the live output sink.

        Returns the scrollback to replay. Any chunk recorded after this
        snapshot is delivered to ``listener`` (no gap, no duplicate).
        """
        with self._lock:
            snapshot = bytes(self._scrollback)
            self._listener = listener
            return snapshot

    def set_listener(self, listener: Optional[Callable[[bytes], None]]) -> None:
        """Register (or clear with ``None``) the live output sink."""
        with self._lock:
            self._listener = listener

    def _proc_alive(self) -> bool:
        try:
            return self._proc.isalive()
        except OSError:
            return False

    # -- output -------------------------------------------------------------
    def read(self, max_bytes: int = 4096) -> bytes:
        """Compatibility shim: a session-owned thread does the real reading.

        The POSIX backend is polled via ``read``; on Windows reading happens
        in ``_read_loop``, so direct callers get an empty read.
        """
        return b""

    def _record(self, data: bytes) -> None:
        if self.scrollback_max <= 0:
            return
        self._scrollback += data
        if len(self._scrollback) > self.scrollback_max:
            del self._scrollback[: -self.scrollback_max]

    def scrollback(self) -> bytes:
        return bytes(self._scrollback)

    # -- input / control ----------------------------------------------------
    def write(self, data: bytes) -> int:
        if self._closed or not data:
            return 0
        text = (
            data.decode("utf-8", "replace")
            if isinstance(data, (bytes, bytearray))
            else str(data)
        )
        try:
            self._proc.write(text)
        except (OSError, EOFError):
            self._closed = True
            return 0
        self.last_activity = time.monotonic()
        return len(data)

    def resize(self, cols: int, rows: int) -> None:
        if self._closed:
            return
        try:
            self._proc.setwinsize(max(1, int(rows)), max(1, int(cols)))
        except OSError:
            pass

    def is_alive(self) -> bool:
        if self._closed:
            return False
        if not self._proc_alive():
            self.exit_code = getattr(self._proc, "exitstatus", None)
            self._closed = True
            return False
        return True

    def kill(self, sig: Optional[int] = None) -> None:
        self._closed = True
        self._listener = None
        try:
            self._proc.terminate(force=True)
        except Exception:
            pass

    def _close_fd(self) -> None:
        self._listener = None
        if not self._closed:
            try:
                self._proc.terminate(force=True)
            except Exception:
                pass
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
