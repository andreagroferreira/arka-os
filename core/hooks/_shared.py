"""Shared stdlib-only helpers for the consolidated hook entrypoints.

MUST stay importable on a bare python3 (no PyYAML, no third-party deps) —
see the package docstring for the degradation contract.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Mirror of core.shared.safe_session_id (kept local so this module never
# depends on package-level imports that may drag in heavier modules).
SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def safe_session_id(session_id: str) -> str | None:
    """Allowlist check for untrusted session ids (CWE-22 mitigation)."""
    if not session_id or not SAFE_SESSION_ID_RE.match(session_id):
        return None
    return session_id


def read_stdin_json() -> tuple[dict, str]:
    """Read stdin once. Returns (parsed_dict, raw_text)."""
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}, ""
    try:
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, raw


def get_str(data: dict, *keys: str) -> str:
    """Walk nested keys; return str value or "" (mirrors `jq -r '// ""'`)."""
    cur: object = data
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    if cur is None:
        return ""
    return str(cur)


def resolve_arkaos_root() -> str:
    """Resolve ARKAOS_ROOT with the same precedence as the bash hooks.

    env ARKAOS_ROOT → ~/.arkaos/.repo-path → ~/.arkaos → ARKA_OS env →
    ~/.claude/skills/arkaos (portable fallback).
    """
    env_root = os.environ.get("ARKAOS_ROOT", "").strip()
    if env_root:
        return env_root
    repo_file = Path.home() / ".arkaos" / ".repo-path"
    if repo_file.is_file():
        try:
            return repo_file.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    if (Path.home() / ".arkaos").is_dir():
        return str(Path.home() / ".arkaos")
    return os.environ.get(
        "ARKA_OS", str(Path.home() / ".claude" / "skills" / "arkaos")
    )


def repo_path() -> str:
    """Contents of ~/.arkaos/.repo-path, or ""."""
    repo_file = Path.home() / ".arkaos" / ".repo-path"
    try:
        return repo_file.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def venv_python() -> str | None:
    """Path to the ArkaOS venv python, mirroring the old ARKAOS_PY lookup."""
    for candidate in (
        Path.home() / ".arkaos" / "venv" / "bin" / "python3",
        Path.home() / ".arkaos" / ".venv" / "bin" / "python3",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def ensure_root_on_path(root: str) -> None:
    """sys.path.insert(0, root) — same effect as the old heredocs."""
    if root and root not in sys.path:
        sys.path.insert(0, root)


def emit_deny_json(reason: str) -> None:
    """Print the PreToolUse permissionDecision=deny payload to stdout."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
