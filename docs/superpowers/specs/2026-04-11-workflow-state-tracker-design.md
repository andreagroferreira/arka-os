# Workflow State Tracker — Design Spec (SP1)

**Date:** 2026-04-11
**Status:** Approved
**Scope:** Foundation state tracking system for workflow enforcement
**Part of:** WS3 Workflow Enforcement (SP1 of 3)

## Problem

ArkaOS governance (14 NON-NEGOTIABLE rules, Quality Gate, phase gates) is designed but not enforced. The AI receives rules via context injection but can ignore them. There is no mechanism to track which workflow phases have been completed, detect violations, or surface them visibly.

## Solution

A JSON state file per workflow session that tracks phases, branch, and violations. Python module for writing, bash helper for reading from hooks. Three existing hooks (SessionStart, UserPromptSubmit, PostToolUse) extended to read state and detect violations passively.

## State File

**Location:** `~/.arkaos/workflow-state.json`

**Schema:**
```json
{
  "session_id": "uuid4",
  "started_at": "ISO8601",
  "workflow": "dev/feature",
  "project": "/path/to/project",
  "branch": "feature/description",
  "phases": {
    "context": { "status": "completed", "at": "ISO8601" },
    "spec": { "status": "completed", "at": "ISO8601", "artifact": "docs/specs/file.md" },
    "planning": { "status": "in_progress", "at": "ISO8601" },
    "implementation": { "status": "pending" },
    "quality_gate": { "status": "pending" },
    "documentation": { "status": "pending" }
  },
  "violations": [
    {
      "rule": "spec-driven",
      "detail": "Code edited without completed spec",
      "at": "ISO8601",
      "tool": "Edit",
      "file": "src/auth.py"
    }
  ]
}
```

**Phase statuses:** `pending` | `in_progress` | `completed` | `skipped`

**Lifecycle:**
- Created when a workflow starts (e.g., `/dev feature`, `/dev fix`)
- Updated as phases progress
- Cleared when workflow completes (QG approved + committed) or user starts a new workflow
- Only one active workflow at a time per machine

## Python Module

**File:** `core/workflow/state.py`

### Functions

```python
def init_workflow(workflow: str, project: str, phases: list[str]) -> dict:
    """Create a new workflow state file. Overwrites any existing state."""

def get_state() -> dict | None:
    """Read current workflow state. Returns None if no active workflow."""

def update_phase(phase: str, status: str, artifact: str | None = None) -> dict:
    """Update a phase status. Validates phase exists and status is valid."""

def add_violation(rule: str, detail: str, tool: str | None = None, file: str | None = None) -> dict:
    """Append a violation to the violations list."""

def set_branch(branch: str) -> dict:
    """Record the git branch for the current workflow."""

def clear_workflow() -> None:
    """Remove the state file (workflow completed or abandoned)."""

def is_phase_completed(phase: str) -> bool:
    """Check if a specific phase is completed."""
```

**State file path:** `Path.home() / ".arkaos" / "workflow-state.json"`

**Validation:**
- `update_phase` rejects invalid statuses
- `update_phase` rejects phase names not in the current workflow
- `init_workflow` generates a UUID4 session_id and ISO8601 timestamp
- All writes are atomic (write to temp file, then rename)

## Bash Reader

**File:** `core/workflow/state-reader.sh`

**Usage:**
```bash
# Read phase status
bash state-reader.sh phase <name>
# Output: "pending" | "in_progress" | "completed" | "skipped"
# Exit: 0

# Check if phase is completed
bash state-reader.sh check <name>
# Exit: 0 if completed, 1 if not

# Get violation count
bash state-reader.sh violations
# Output: "3"
# Exit: 0

# Get current workflow summary (one line)
bash state-reader.sh summary
# Output: "dev/feature|implementation|3/6|feature/add-auth|0"
# (workflow|current_phase|progress|branch|violations)
# Exit: 0 if active, 1 if no workflow

# Check if any workflow is active
bash state-reader.sh active
# Exit: 0 if active, 1 if not
```

**Dependencies:** `jq` (already required by other hooks) with `python3 -c` fallback.

## Hook Integration

### SessionStart

If workflow state exists, append to greeting:
```
Workflow active: dev/feature (my-project)
  Branch: feature/add-auth
  Phase: implementation (3/6)
  Violations: 0
```

### UserPromptSubmit

Inject state as context tag in `additionalContext`:
```
[workflow:dev/feature] [phase:implementation] [branch:feature/add-auth] [violations:0]
```

If violations > 0, prepend warning:
```
WARNING: 2 workflow violations detected. Run /dev status for details.
```

### PostToolUse

After each tool call, check 3 rules:

**Rule 1: Branch isolation**
- Trigger: tool is `Bash`, command matches `git commit`, current git branch is `master` or `main`, and a workflow is active
- Action: `add_violation("branch-isolation", "Commit on master while workflow active")`

**Rule 2: Spec-driven**
- Trigger: tool is `Write` or `Edit`, file extension is code (`.py`, `.js`, `.ts`, `.vue`, `.php`, `.jsx`, `.tsx`), and phase `spec` is not `completed`
- Action: `add_violation("spec-driven", "Code edited without completed spec", tool, file)`

**Rule 3: Sequential phases**
- Trigger: tool is `Write` or `Edit` on code files, and phase `implementation` status is `pending` (meaning planning isn't done)
- Action: `add_violation("sequential-validation", "Implementation started before planning completed", tool, file)`

**Violation output:** Each violation is written to the state file AND output as `additionalContext` warning in the hook response:
```json
{"additionalContext": "VIOLATION [spec-driven]: Code edited without completed spec (src/auth.py). Complete the spec phase before writing code."}
```

## Testing

**Python tests** (`tests/python/test_workflow_state.py`):
- `test_init_workflow` — creates file with correct schema
- `test_update_phase` — transitions states correctly
- `test_update_phase_rejects_invalid_status` — ValueError on bad status
- `test_update_phase_rejects_unknown_phase` — ValueError on missing phase
- `test_add_violation` — appends to violations list
- `test_set_branch` — updates branch field
- `test_clear_workflow` — removes file
- `test_is_phase_completed` — returns correct bool
- `test_get_state_returns_none_when_no_file` — handles missing file
- `test_atomic_write` — file is valid JSON even after error

**Bash tests** (manual verification):
- `state-reader.sh phase spec` returns correct status
- `state-reader.sh check spec` exits 0/1 correctly
- `state-reader.sh violations` returns count
- `state-reader.sh summary` returns pipe-separated string
- `state-reader.sh active` exits 0/1 correctly

## What This Does NOT Include

- Skills calling the state tracker automatically (SP3)
- UserPromptSubmit blocking prompts with exit 2 (SP2)
- Quality Gate enforcement (SP3)
- Violation reports or dashboards (future)
- PowerShell reader equivalent (add when Windows hooks need it)

SP1 delivers the foundation: state file, read/write functions, and passive violation detection in hooks.
