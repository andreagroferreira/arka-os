"""Workflow state tracker for ArkaOS governance enforcement.

Manages a JSON state file that records workflow phases, branch, and violations.
Read by hooks and skills to detect and surface governance violations.
"""

import contextlib
import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

_VALID_STATUSES = ("pending", "in_progress", "completed", "skipped")

# Gate Economy PR-9: violations must not grow without bound — the legacy
# global file reached 65KB (217 entries, 100% false positives) and was
# JSON-parsed on every UserPromptSubmit. Newest entries win.
MAX_VIOLATIONS = 100

# The pre-PR-9 GLOBAL state file: one file for every project on the
# machine, so violations from one repo leaked into every session's
# banner and the file could never legitimately clear.
_LEGACY_STATE_PATH = Path.home() / ".arkaos" / "workflow-state.json"

_SLUG_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _project_slug() -> str:
    """Stable per-project key derived from the working directory."""
    cwd = Path.cwd()
    digest = hashlib.sha256(str(cwd).encode("utf-8")).hexdigest()[:8]
    name = _SLUG_SAFE_RE.sub("-", cwd.name)[:48] or "project"
    return f"{name}-{digest}"


def _state_path() -> Path:
    """Per-project state file (Gate Economy PR-9).

    Scoped by cwd so one project's workflow phases and violations never
    leak into another's banner — the legacy global file accumulated
    cross-project violations forever.
    """
    return (
        Path.home() / ".arkaos" / "workflow-state"
        / f"{_project_slug()}.json"
    )


def _drop_legacy_state() -> None:
    """Remove the poisoned pre-PR-9 global file, once, best-effort.

    Its contents are unusable by construction: violations from every
    project interleaved, dominated by the false spec-driven entries the
    old phase check appended on every code edit.
    """
    with contextlib.suppress(OSError):
        if _LEGACY_STATE_PATH.is_file():
            _LEGACY_STATE_PATH.unlink()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read() -> dict | None:
    _drop_legacy_state()
    path = _state_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(state: dict) -> dict:
    """Atomic write: write to temp file then rename."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        dir=str(path.parent),
        suffix=".tmp",
        delete=False,
        encoding="utf-8",
    ) as fd:
        try:
            json.dump(state, fd, indent=2)
        except BaseException:
            fd.close()
            os.unlink(fd.name)
            raise
    os.replace(fd.name, str(path))
    return state


def init_workflow(workflow: str, project: str, phases: list[str]) -> dict:
    """Create a new workflow state file. Overwrites any existing state."""
    state = {
        "session_id": str(uuid.uuid4()),
        "started_at": _now_iso(),
        "workflow": workflow,
        "project": project,
        "branch": "",
        "phases": {p: {"status": "pending"} for p in phases},
        "violations": [],
    }
    return _write(state)


def get_state() -> dict | None:
    """Read current workflow state. Returns None if no active workflow."""
    return _read()


def clear_workflow() -> None:
    """Remove the state file."""
    path = _state_path()
    if path.exists():
        path.unlink()


def _require_state() -> dict:
    """Read state or raise if no active workflow."""
    state = _read()
    if state is None:
        raise RuntimeError("No active workflow")
    return state


def update_phase(phase: str, status: str, artifact: str | None = None) -> dict:
    """Update a phase status. Validates phase exists and status is valid."""
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {_VALID_STATUSES}")
    state = _require_state()
    if phase not in state["phases"]:
        raise ValueError(f"Unknown phase: {phase}. Available: {list(state['phases'])}")
    state["phases"][phase]["status"] = status
    if status in ("in_progress", "completed"):
        state["phases"][phase]["at"] = _now_iso()
    if artifact:
        state["phases"][phase]["artifact"] = artifact
    return _write(state)


def set_branch(branch: str) -> dict:
    """Record the git branch for the current workflow."""
    state = _require_state()
    state["branch"] = branch
    return _write(state)


def add_violation(
    rule: str,
    detail: str,
    tool: str | None = None,
    file: str | None = None,
    severity: str | None = None,
) -> dict:
    """Append a violation to the violations list."""
    state = _require_state()
    violation: dict = {"rule": rule, "detail": detail, "at": _now_iso()}
    if tool:
        violation["tool"] = tool
    if file:
        violation["file"] = file
    if severity:
        violation["severity"] = severity
    state["violations"].append(violation)
    # Cap the list — newest entries win (Gate Economy PR-9).
    state["violations"] = state["violations"][-MAX_VIOLATIONS:]
    return _write(state)


def update_phases(
    statuses: dict[str, str], artifacts: dict[str, str] | None = None
) -> dict:
    """Update several phases in ONE atomic write (Gate Economy PR-9).

    The gate checkpoint previously called ``update_phase`` once per
    gate — four full-file rewrites per Stop hook. Same validation as
    ``update_phase``; ``artifacts`` maps phase → artifact.
    """
    state = _require_state()
    artifacts = artifacts or {}
    for phase, status in statuses.items():
        if status not in _VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {status}. Must be one of {_VALID_STATUSES}"
            )
        if phase not in state["phases"]:
            raise ValueError(
                f"Unknown phase: {phase}. Available: {list(state['phases'])}"
            )
        state["phases"][phase]["status"] = status
        if status in ("in_progress", "completed"):
            state["phases"][phase]["at"] = _now_iso()
        artifact = artifacts.get(phase)
        if artifact:
            state["phases"][phase]["artifact"] = artifact
    return _write(state)


def is_phase_completed(phase: str) -> bool:
    """Check if a specific phase is completed."""
    state = _read()
    if state is None:
        return False
    phase_data = state["phases"].get(phase)
    if phase_data is None:
        return False
    return phase_data["status"] == "completed"
