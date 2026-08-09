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


def _has_core_package(root: str) -> bool:
    # core/sync/__init__.py distinguishes the full package from the
    # cognitive scheduler's minimal core/ copy (cognition + workflow only).
    try:
        return (Path(root) / "core" / "sync" / "__init__.py").is_file()
    except OSError:
        return False


def resolve_arkaos_root() -> str:
    """Resolve ARKAOS_ROOT with the hook wrappers' validated chain.

    env ARKAOS_ROOT (unconditional operator override) → ~/.arkaos/.repo-path
    (validated) → ~/.arkaos/lib stable snapshot (validated) → .repo-path
    even without the core package (legacy VERSION readers) → ~/.arkaos →
    ARKA_OS env → ~/.claude/skills/arkaos (portable fallback).

    Mirrors arka_resolve_root() in config/hooks/_lib/arka_python.sh;
    bin/arka-py adds one extra step (its own dev checkout) between
    .repo-path and the snapshot.

    Validation matters because .repo-path points at an npx cache that
    `npm cache clean` can purge at any time.
    """
    env_root = os.environ.get("ARKAOS_ROOT", "").strip()
    if env_root:
        return env_root
    repo = repo_path()
    if repo and _has_core_package(repo):
        return repo
    lib = Path.home() / ".arkaos" / "lib"
    if _has_core_package(str(lib)):
        return str(lib)
    if repo and Path(repo).is_dir():
        return repo
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


def additional_context_payload(event_name: str, context: str) -> dict:
    """Build the additionalContext payload in the shape Claude Code accepts.

    A top-level {"additionalContext": ...} is an unrecognised key that the
    runtime silently ignores — context is ONLY delivered inside
    hookSpecificOutput with an explicit hookEventName.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": context,
        }
    }


def emit_additional_context(event_name: str, context: str) -> None:
    """Print the additionalContext payload to stdout (single construction site)."""
    print(json.dumps(additional_context_payload(event_name, context)))


# Growth cap for the degraded log. The failure mode this telemetry exists
# to expose — a venv that cannot import the gate modules — degrades on
# EVERY tool call, so the log is unbounded exactly when it matters: a
# machine left in that state writes ~264MB before anyone notices. One
# rotation to `.1` bounds the pair at twice this and costs a stat() per
# write, never a read of the log. The same constant is mirrored by the
# shell writer (arka_hook_degraded) and the Node shim (recordDegraded);
# tests/python/test_hook_output_contract.py pins the three together.
DEGRADED_LOG_MAX_BYTES = 5 * 1024 * 1024


def _rotate_degraded_log(path: Path) -> None:
    """Roll the log to `.1` once it passes the cap. Never raises.

    Swallows its own errors rather than propagating them: a log that
    cannot be rotated must still be appended to, and a cap that can
    suppress the record defeats the point of recording.
    """
    try:
        if path.stat().st_size >= DEGRADED_LOG_MAX_BYTES:
            path.replace(path.parent / (path.name + ".1"))
    except OSError:
        pass


def record_degraded(hook: str, reason: str, detail: str = "") -> None:
    """Record that a gate allowed because it could not run, not because it decided.

    Several handlers in the hook entrypoints convert a failure into "allow" —
    the right posture for governance code, since a broken import must never
    block the user's work. What was missing is the record. A gate that allows
    silently is indistinguishable from a gate that ran and found nothing, and
    that ambiguity is expensive in both directions: it hid an ArkaOS venv that
    could not ``import pydantic`` for months (every gate on that machine open,
    no signal anywhere), and it previously manufactured a phantom bug that
    cost five messages to disprove (Cross-Machine Lab, X3).

    Deliberately NOT on stderr. Claude Code surfaces hook stderr to the user
    as an error, so diagnosing here would turn a silent degradation into
    visible noise on every event. The record goes to a file; only a reader
    who wants it pays for it.

    Never raises: telemetry must not become the thing that breaks a hook.

    NOT the only writer, and deliberately not claimed as one. Three
    surfaces reach a fail-open before any Python runs, so each has its own
    implementation appending to this same file: ``arka_hook_degraded()`` in
    config/hooks/_lib/arka_python.sh (no interpreter, missing entrypoint,
    entrypoint crashed) and ``recordDegraded()`` in config/hooks/
    pre-tool-use.cjs — which is what a POSIX install actually registers, so
    its fail-opens happen before the shell chain exists. Drift between the
    three is prevented by executing all three and comparing the records
    (tests/python/test_hook_output_contract.py::TestDegradedTelemetryParity),
    not by asserting that one implementation covers every platform.

    The Windows chain is NOT covered. pre-tool-use.ps1 is a parallel
    implementation with its own embedded Python, and its six fail-open
    exits remain silent — recorded as deferred scope by the same test, not
    quietly folded into a cross-platform claim.
    """
    try:
        import time

        if not detail:
            # Called from inside an `except` block in every current caller,
            # so the live exception IS the detail. Capturing it here keeps
            # each call site to a single line and stops the handlers from
            # having to grow an `as exc` binding they otherwise never use.
            current = sys.exc_info()[1]
            if current is not None:
                detail = f"{type(current).__name__}: {current}"

        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hook": hook,
            "reason": reason,
            "detail": detail[:400],
        }, ensure_ascii=False)
        directory = Path.home() / ".arkaos" / "telemetry"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "hook-degraded.jsonl"
        _rotate_degraded_log(path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass
