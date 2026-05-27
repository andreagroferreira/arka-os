"""ArkaOS terminal — PTY session manager + audit log.

PR99a v3.67.0 — replaces the v3.51.0 allowlist runner with a real
multi-session PTY that lets the operator run claude, codex, anything,
streamed bidirectionally over a WebSocket and rendered in xterm.js.

Security: localhost-only binding (inherits from dashboard-api), origin
pinning + per-process bearer token, idle-kill 30 min, hard cap on
concurrent sessions, metadata-only audit log (no input capture).
"""

from core.terminal.session import (
    TerminalSession,
    TerminalSessionManager,
    SessionCapacityError,
)
from core.terminal.audit import log_end, log_start
from core.terminal.token import current_token
from core.terminal.connections import ConnectionRegistry

__all__ = [
    "TerminalSession",
    "TerminalSessionManager",
    "SessionCapacityError",
    "log_start",
    "log_end",
    "current_token",
    "ConnectionRegistry",
]
