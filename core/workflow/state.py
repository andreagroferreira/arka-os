"""Workflow state tracker for ArkaOS governance enforcement.

Manages a JSON state file that records workflow phases, branch, and violations.
Read by hooks and skills to detect and surface governance violations.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

_VALID_STATUSES = ("pending", "in_progress", "completed", "skipped")


def _state_path() -> Path:
    return Path.home() / ".arkaos" / "workflow-state.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> dict | None:
    path = _state_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write(state: dict) -> dict:
    """Atomic write: write to temp file then rename."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = NamedTemporaryFile(
        mode="w", dir=str(path.parent), suffix=".tmp", delete=False, encoding="utf-8",
    )
    try:
        json.dump(state, fd, indent=2)
        fd.close()
        os.replace(fd.name, str(path))
    except BaseException:
        fd.close()
        os.unlink(fd.name)
        raise
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
    rule: str, detail: str, tool: str | None = None, file: str | None = None,
) -> dict:
    """Append a violation to the violations list."""
    state = _require_state()
    violation: dict = {"rule": rule, "detail": detail, "at": _now_iso()}
    if tool:
        violation["tool"] = tool
    if file:
        violation["file"] = file
    state["violations"].append(violation)
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
