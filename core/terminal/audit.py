"""Metadata-only audit log for terminal sessions.

PR99a v3.67.0 — writes start/end events as JSONL to
``~/.arkaos/terminal-audit.jsonl``. Deliberately captures NO input or
output payload — only session lifecycle metadata — because terminal
input frequently carries secrets (PATs, tokens, passwords) and
operators paste them in.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()


def _audit_path() -> Path:
    base = Path(os.environ.get("ARKAOS_HOME", Path.home() / ".arkaos"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "terminal-audit.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(event: dict) -> None:
    path = _audit_path()
    line = json.dumps(event, ensure_ascii=False)
    with _LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def log_start(session_id: str, shell: str, cwd: str) -> None:
    """Record that a PTY session has been created."""
    _write({
        "event": "start",
        "session_id": session_id,
        "shell": shell,
        "cwd": cwd,
        "ts": _now_iso(),
    })


def log_end(session_id: str, exit_code: int | None, reason: str = "closed") -> None:
    """Record that a PTY session has terminated."""
    _write({
        "event": "end",
        "session_id": session_id,
        "exit_code": exit_code,
        "reason": reason,
        "ts": _now_iso(),
    })
