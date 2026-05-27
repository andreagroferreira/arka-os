"""Single active WebSocket connection per terminal session (v3.71.1).

asyncio allows only one reader per fd, so two concurrent WebSockets on the
same session would fight over the PTY master fd and the scrollback replay
could duplicate output. This registry enforces "latest wins": a new
connection supersedes the previous one (which the endpoint then closes),
and release is guarded so a superseded connection's teardown cannot evict
its replacement.

Pure bookkeeping — no FastAPI import, so it's unit-testable standalone.
"""

from __future__ import annotations

from typing import Any, Optional


class ConnectionRegistry:
    """Tracks the one live connection per session id."""

    def __init__(self) -> None:
        self._active: dict[str, Any] = {}

    def acquire(self, session_id: str, conn: Any) -> Optional[Any]:
        """Make ``conn`` the active connection for ``session_id``.

        Returns the connection it superseded (for the caller to close), or
        ``None`` when there was none / it was already active.
        """
        old = self._active.get(session_id)
        self._active[session_id] = conn
        return old if old is not conn else None

    def release(self, session_id: str, conn: Any) -> bool:
        """Drop ``conn`` iff it is still the active connection.

        Returns whether it was — the caller should only tear down shared
        resources (the fd reader) when this is ``True``.
        """
        if self._active.get(session_id) is conn:
            del self._active[session_id]
            return True
        return False

    def is_active(self, session_id: str, conn: Any) -> bool:
        return self._active.get(session_id) is conn
