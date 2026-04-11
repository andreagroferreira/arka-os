# Workflow State Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a workflow state tracker that records phases, detects violations, and surfaces them through hooks — the foundation for workflow enforcement.

**Architecture:** Python module `core/workflow/state.py` manages a JSON state file at `~/.arkaos/workflow-state.json`. Bash reader script enables hooks to read state cheaply. Three hooks (SessionStart, UserPromptSubmit, PostToolUse) are extended to read state and detect violations passively.

**Tech Stack:** Python (Pydantic-free, stdlib only), Bash, jq

---

## File Map

| File | Responsibility |
|------|---------------|
| `core/workflow/state.py` | Create, read, update, clear workflow state |
| `core/workflow/state_reader.sh` | Bash CLI to read state (for hooks) |
| `tests/python/test_workflow_state.py` | Python unit tests |
| `config/hooks/session-start.sh` | Show active workflow on session start |
| `config/hooks/user-prompt-submit.sh` | Inject workflow state as context tag |
| `config/hooks/post-tool-use.sh` | Detect violations after tool calls |

---

### Task 1: Python state module — init and read

**Files:**
- Create: `core/workflow/state.py`
- Create: `tests/python/test_workflow_state.py`

- [ ] **Step 1: Write failing tests for init_workflow and get_state**

Create `tests/python/test_workflow_state.py`:

```python
"""Tests for workflow state tracker."""

import json
from pathlib import Path

import pytest

from core.workflow.state import init_workflow, get_state, clear_workflow

STATE_FILE_NAME = "workflow-state.json"


@pytest.fixture(autouse=True)
def _use_tmp_state(tmp_path, monkeypatch):
    """Redirect state file to tmp_path for all tests."""
    monkeypatch.setattr(
        "core.workflow.state._state_path",
        lambda: tmp_path / STATE_FILE_NAME,
    )


class TestInitWorkflow:
    def test_creates_state_file(self, tmp_path: Path) -> None:
        """init_workflow creates the JSON state file."""
        result = init_workflow("dev/feature", "/tmp/proj", ["context", "spec", "implementation"])
        path = tmp_path / STATE_FILE_NAME
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["workflow"] == "dev/feature"
        assert data["project"] == "/tmp/proj"

    def test_phases_initialized_as_pending(self) -> None:
        """All phases start with status pending."""
        result = init_workflow("dev/feature", "/tmp/proj", ["context", "spec"])
        for phase in result["phases"].values():
            assert phase["status"] == "pending"

    def test_session_id_is_uuid(self) -> None:
        """session_id is a valid UUID4 string."""
        import uuid
        result = init_workflow("dev/fix", "/tmp/p", ["context"])
        uuid.UUID(result["session_id"], version=4)

    def test_overwrites_existing_state(self) -> None:
        """Calling init_workflow twice overwrites the first state."""
        init_workflow("dev/feature", "/tmp/a", ["context"])
        result = init_workflow("dev/fix", "/tmp/b", ["spec"])
        assert result["workflow"] == "dev/fix"
        assert result["project"] == "/tmp/b"


class TestGetState:
    def test_returns_none_when_no_file(self) -> None:
        """get_state returns None if no workflow is active."""
        assert get_state() is None

    def test_returns_state_after_init(self) -> None:
        """get_state returns the current workflow state."""
        init_workflow("dev/feature", "/tmp/proj", ["context", "spec"])
        state = get_state()
        assert state is not None
        assert state["workflow"] == "dev/feature"
        assert len(state["phases"]) == 2


class TestClearWorkflow:
    def test_removes_state_file(self, tmp_path: Path) -> None:
        """clear_workflow deletes the state file."""
        init_workflow("dev/feature", "/tmp/proj", ["context"])
        clear_workflow()
        assert not (tmp_path / STATE_FILE_NAME).exists()

    def test_clear_when_no_file_is_noop(self) -> None:
        """clear_workflow does nothing if no state file exists."""
        clear_workflow()  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/python/test_workflow_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.workflow.state'`

- [ ] **Step 3: Implement init_workflow, get_state, clear_workflow**

Create `core/workflow/state.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/python/test_workflow_state.py -v`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/workflow/state.py tests/python/test_workflow_state.py
git commit -m "feat(workflow): add state tracker — init, get, clear"
```

---

### Task 2: Python state module — update_phase, set_branch, add_violation, is_phase_completed

**Files:**
- Modify: `core/workflow/state.py`
- Modify: `tests/python/test_workflow_state.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/python/test_workflow_state.py`:

```python
from core.workflow.state import update_phase, set_branch, add_violation, is_phase_completed


class TestUpdatePhase:
    def test_sets_phase_status(self) -> None:
        """update_phase changes the phase status."""
        init_workflow("dev/feature", "/tmp/p", ["context", "spec"])
        result = update_phase("context", "in_progress")
        assert result["phases"]["context"]["status"] == "in_progress"
        assert "at" in result["phases"]["context"]

    def test_completed_records_timestamp(self) -> None:
        """Completing a phase records the timestamp."""
        init_workflow("dev/feature", "/tmp/p", ["spec"])
        result = update_phase("spec", "completed")
        assert result["phases"]["spec"]["status"] == "completed"
        assert result["phases"]["spec"]["at"]

    def test_stores_artifact(self) -> None:
        """update_phase can store an artifact path."""
        init_workflow("dev/feature", "/tmp/p", ["spec"])
        result = update_phase("spec", "completed", artifact="docs/spec.md")
        assert result["phases"]["spec"]["artifact"] == "docs/spec.md"

    def test_rejects_invalid_status(self) -> None:
        """update_phase raises ValueError for unknown status."""
        init_workflow("dev/feature", "/tmp/p", ["context"])
        with pytest.raises(ValueError, match="Invalid status"):
            update_phase("context", "cancelled")

    def test_rejects_unknown_phase(self) -> None:
        """update_phase raises ValueError for phase not in workflow."""
        init_workflow("dev/feature", "/tmp/p", ["context"])
        with pytest.raises(ValueError, match="Unknown phase"):
            update_phase("nonexistent", "completed")

    def test_raises_when_no_workflow(self) -> None:
        """update_phase raises RuntimeError when no workflow active."""
        with pytest.raises(RuntimeError, match="No active workflow"):
            update_phase("context", "completed")


class TestSetBranch:
    def test_sets_branch(self) -> None:
        """set_branch records the git branch."""
        init_workflow("dev/feature", "/tmp/p", ["context"])
        result = set_branch("feature/add-auth")
        assert result["branch"] == "feature/add-auth"


class TestAddViolation:
    def test_appends_violation(self) -> None:
        """add_violation appends to the violations list."""
        init_workflow("dev/feature", "/tmp/p", ["context"])
        result = add_violation("spec-driven", "Code edited without spec")
        assert len(result["violations"]) == 1
        assert result["violations"][0]["rule"] == "spec-driven"
        assert result["violations"][0]["detail"] == "Code edited without spec"
        assert "at" in result["violations"][0]

    def test_records_tool_and_file(self) -> None:
        """add_violation stores optional tool and file."""
        init_workflow("dev/feature", "/tmp/p", ["context"])
        result = add_violation("spec-driven", "Code edited", tool="Edit", file="src/a.py")
        v = result["violations"][0]
        assert v["tool"] == "Edit"
        assert v["file"] == "src/a.py"

    def test_multiple_violations_accumulate(self) -> None:
        """Multiple violations are appended, not replaced."""
        init_workflow("dev/feature", "/tmp/p", ["context"])
        add_violation("rule-a", "detail-a")
        result = add_violation("rule-b", "detail-b")
        assert len(result["violations"]) == 2


class TestIsPhaseCompleted:
    def test_returns_true_when_completed(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        update_phase("context", "completed")
        assert is_phase_completed("context") is True

    def test_returns_false_when_pending(self) -> None:
        init_workflow("dev/feature", "/tmp/p", ["context"])
        assert is_phase_completed("context") is False

    def test_returns_false_when_no_workflow(self) -> None:
        assert is_phase_completed("context") is False
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `python -m pytest tests/python/test_workflow_state.py -v`
Expected: 13 new tests FAIL with `ImportError`

- [ ] **Step 3: Implement update_phase, set_branch, add_violation, is_phase_completed**

Append to `core/workflow/state.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `python -m pytest tests/python/test_workflow_state.py -v`
Expected: all 21 tests PASS

- [ ] **Step 5: Run full suite for regressions**

Run: `python -m pytest tests/ --tb=short -q`
Expected: 2002+ passed

- [ ] **Step 6: Commit**

```bash
git add core/workflow/state.py tests/python/test_workflow_state.py
git commit -m "feat(workflow): add update_phase, set_branch, add_violation, is_phase_completed"
```

---

### Task 3: Bash state reader

**Files:**
- Create: `core/workflow/state_reader.sh`

- [ ] **Step 1: Create the bash reader script**

Create `core/workflow/state_reader.sh`:

```bash
#!/usr/bin/env bash
# ============================================================================
# ArkaOS — Workflow State Reader (for hooks)
# Reads ~/.arkaos/workflow-state.json and outputs requested fields.
# Dependencies: jq (required), python3 (fallback)
# ============================================================================

STATE_FILE="$HOME/.arkaos/workflow-state.json"

if [ ! -f "$STATE_FILE" ]; then
  case "${1:-}" in
    active) exit 1 ;;
    summary) exit 1 ;;
    violations) echo "0"; exit 0 ;;
    phase) echo "none"; exit 0 ;;
    check) exit 1 ;;
    *) echo "No active workflow"; exit 1 ;;
  esac
fi

CMD="${1:-summary}"
ARG="${2:-}"

case "$CMD" in
  active)
    # Exit 0 if workflow active, 1 if not
    exit 0
    ;;

  phase)
    # Output phase status
    if [ -z "$ARG" ]; then
      echo "Usage: state-reader.sh phase <name>" >&2
      exit 1
    fi
    STATUS=$(jq -r ".phases.\"$ARG\".status // \"unknown\"" "$STATE_FILE" 2>/dev/null)
    echo "$STATUS"
    ;;

  check)
    # Exit 0 if phase completed, 1 if not
    if [ -z "$ARG" ]; then
      echo "Usage: state-reader.sh check <name>" >&2
      exit 1
    fi
    STATUS=$(jq -r ".phases.\"$ARG\".status // \"pending\"" "$STATE_FILE" 2>/dev/null)
    [ "$STATUS" = "completed" ] && exit 0 || exit 1
    ;;

  violations)
    # Output violation count
    COUNT=$(jq '.violations | length' "$STATE_FILE" 2>/dev/null || echo "0")
    echo "$COUNT"
    ;;

  summary)
    # Output: workflow|current_phase|progress|branch|violations
    WORKFLOW=$(jq -r '.workflow // ""' "$STATE_FILE" 2>/dev/null)
    BRANCH=$(jq -r '.branch // ""' "$STATE_FILE" 2>/dev/null)
    VIOLATIONS=$(jq '.violations | length' "$STATE_FILE" 2>/dev/null || echo "0")
    TOTAL=$(jq '.phases | length' "$STATE_FILE" 2>/dev/null || echo "0")
    COMPLETED=$(jq '[.phases[] | select(.status == "completed")] | length' "$STATE_FILE" 2>/dev/null || echo "0")
    # Find current phase (first non-completed, non-skipped)
    CURRENT=$(jq -r '[.phases | to_entries[] | select(.value.status == "in_progress")] | .[0].key // "none"' "$STATE_FILE" 2>/dev/null)
    [ "$CURRENT" = "null" ] && CURRENT="none"
    echo "${WORKFLOW}|${CURRENT}|${COMPLETED}/${TOTAL}|${BRANCH}|${VIOLATIONS}"
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: state-reader.sh {active|phase|check|violations|summary} [arg]" >&2
    exit 1
    ;;
esac
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x core/workflow/state_reader.sh
bash -n core/workflow/state_reader.sh && echo "SYNTAX OK"
```

- [ ] **Step 3: Integration test with Python state module**

```bash
# Create a test workflow
python3 -c "
import sys; sys.path.insert(0, '.')
from core.workflow.state import init_workflow, update_phase
init_workflow('dev/feature', '/tmp/test', ['context', 'spec', 'implementation', 'quality_gate'])
update_phase('context', 'completed')
update_phase('spec', 'in_progress')
"

# Test reader
echo "active:" && bash core/workflow/state_reader.sh active && echo "YES" || echo "NO"
echo "phase spec:" && bash core/workflow/state_reader.sh phase spec
echo "check context:" && bash core/workflow/state_reader.sh check context && echo "COMPLETED" || echo "NOT DONE"
echo "check spec:" && bash core/workflow/state_reader.sh check spec && echo "COMPLETED" || echo "NOT DONE"
echo "violations:" && bash core/workflow/state_reader.sh violations
echo "summary:" && bash core/workflow/state_reader.sh summary

# Cleanup
python3 -c "import sys; sys.path.insert(0, '.'); from core.workflow.state import clear_workflow; clear_workflow()"
```

Expected output:
```
active:
YES
phase spec:
in_progress
check context:
COMPLETED
check spec:
NOT DONE
violations:
0
summary:
dev/feature|spec|1/4||0
```

- [ ] **Step 4: Commit**

```bash
git add core/workflow/state_reader.sh
git commit -m "feat(workflow): add bash state reader for hook integration"
```

---

### Task 4: Hook integration — SessionStart

**Files:**
- Modify: `config/hooks/session-start.sh:41-53`

- [ ] **Step 1: Add workflow status to SessionStart greeting**

In `config/hooks/session-start.sh`, find the line that builds `MSG+="ArkaOS v${VERSION}..."` (around line 52). BEFORE that line, add:

```bash
# ─── Active Workflow ──────────────────────────────────────────────────
STATE_READER="$REPO/core/workflow/state_reader.sh"
if [ -f "$STATE_READER" ] && bash "$STATE_READER" active 2>/dev/null; then
  WF_SUMMARY=$(bash "$STATE_READER" summary 2>/dev/null)
  WF_NAME=$(echo "$WF_SUMMARY" | cut -d'|' -f1)
  WF_PHASE=$(echo "$WF_SUMMARY" | cut -d'|' -f2)
  WF_PROGRESS=$(echo "$WF_SUMMARY" | cut -d'|' -f3)
  WF_BRANCH=$(echo "$WF_SUMMARY" | cut -d'|' -f4)
  WF_VIOLATIONS=$(echo "$WF_SUMMARY" | cut -d'|' -f5)
  MSG+="\\nWorkflow: ${WF_NAME} (${WF_PROGRESS})"
  [ -n "$WF_BRANCH" ] && MSG+=" branch:${WF_BRANCH}"
  [ "$WF_VIOLATIONS" != "0" ] && MSG+=" VIOLATIONS:${WF_VIOLATIONS}"
  MSG+="\\n"
fi
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n config/hooks/session-start.sh && echo "SYNTAX OK"
```

- [ ] **Step 3: Commit**

```bash
git add config/hooks/session-start.sh
git commit -m "feat(hooks): show active workflow in SessionStart greeting"
```

---

### Task 5: Hook integration — UserPromptSubmit

**Files:**
- Modify: `config/hooks/user-prompt-submit.sh:133`

- [ ] **Step 1: Inject workflow state into context**

In `config/hooks/user-prompt-submit.sh`, find the line `python_result="$L0 $L4 $L7"` (the bash fallback around line 133). BEFORE that line, add:

```bash
  # L8: Workflow state
  L8=""
  STATE_READER="$ARKAOS_ROOT/core/workflow/state_reader.sh"
  if [ -f "$STATE_READER" ] && bash "$STATE_READER" active 2>/dev/null; then
    WF_SUMMARY=$(bash "$STATE_READER" summary 2>/dev/null)
    WF_NAME=$(echo "$WF_SUMMARY" | cut -d'|' -f1)
    WF_PHASE=$(echo "$WF_SUMMARY" | cut -d'|' -f2)
    WF_BRANCH=$(echo "$WF_SUMMARY" | cut -d'|' -f4)
    WF_VIOLATIONS=$(echo "$WF_SUMMARY" | cut -d'|' -f5)
    L8="[workflow:${WF_NAME}] [phase:${WF_PHASE}] [branch:${WF_BRANCH}] [violations:${WF_VIOLATIONS}]"
    if [ "$WF_VIOLATIONS" != "0" ]; then
      L8="WARNING: ${WF_VIOLATIONS} workflow violation(s) detected. $L8"
    fi
  fi
```

Then update the assembly line to include L8:

```bash
  python_result="$L0 $L4 $L7 $L8"
```

- [ ] **Step 2: Also inject L8 when Python synapse bridge is used**

Find the output line (around line 137): `echo "{\"additionalContext\": \"${_ARKA_GREETING:-}${_SYNC_NOTICE:-}$python_result\"}"`. The L8 should be appended to `python_result` in both the python and bash paths. After line 101 (where `python_result` is set from bridge output), add:

```bash
    # Append workflow state even when Python bridge is used
    STATE_READER="$ARKAOS_ROOT/core/workflow/state_reader.sh"
    if [ -f "$STATE_READER" ] && bash "$STATE_READER" active 2>/dev/null; then
      WF_SUMMARY=$(bash "$STATE_READER" summary 2>/dev/null)
      WF_NAME=$(echo "$WF_SUMMARY" | cut -d'|' -f1)
      WF_PHASE=$(echo "$WF_SUMMARY" | cut -d'|' -f2)
      WF_BRANCH=$(echo "$WF_SUMMARY" | cut -d'|' -f4)
      WF_VIOLATIONS=$(echo "$WF_SUMMARY" | cut -d'|' -f5)
      WF_TAG="[workflow:${WF_NAME}] [phase:${WF_PHASE}] [branch:${WF_BRANCH}] [violations:${WF_VIOLATIONS}]"
      [ "$WF_VIOLATIONS" != "0" ] && WF_TAG="WARNING: ${WF_VIOLATIONS} workflow violation(s). $WF_TAG"
      python_result="${python_result} ${WF_TAG}"
    fi
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n config/hooks/user-prompt-submit.sh && echo "SYNTAX OK"
```

- [ ] **Step 4: Commit**

```bash
git add config/hooks/user-prompt-submit.sh
git commit -m "feat(hooks): inject workflow state into UserPromptSubmit context"
```

---

### Task 6: Hook integration — PostToolUse violation detection

**Files:**
- Modify: `config/hooks/post-tool-use.sh`

- [ ] **Step 1: Add violation detection before the final echo**

In `config/hooks/post-tool-use.sh`, find the final line `echo '{}'` (line 188). REPLACE the last section (from the metrics log onwards, around line 173-188) with:

```bash
# ─── Workflow Violation Detection ────────────────────────────────────────
VIOLATION_MSG=""
STATE_READER=""
[ -f "$HOME/.arkaos/.repo-path" ] && STATE_READER="$(cat "$HOME/.arkaos/.repo-path")/core/workflow/state_reader.sh"

if [ -n "$STATE_READER" ] && [ -f "$STATE_READER" ] && bash "$STATE_READER" active 2>/dev/null; then
  ARKAOS_PY=""
  [ -f "$HOME/.arkaos/venv/bin/python3" ] && ARKAOS_PY="$HOME/.arkaos/venv/bin/python3"
  [ -z "$ARKAOS_PY" ] && [ -f "$HOME/.arkaos/.venv/bin/python3" ] && ARKAOS_PY="$HOME/.arkaos/.venv/bin/python3"
  [ -z "$ARKAOS_PY" ] && ARKAOS_PY=$(command -v python3 2>/dev/null)
  ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null)

  # Rule 1: Branch isolation — commit on master while workflow active
  if [ "$TOOL_NAME" = "Bash" ]; then
    if echo "$TOOL_OUTPUT" | grep -q "^\[master\|^\[main" 2>/dev/null; then
      if echo "$input" | jq -r '.command // ""' 2>/dev/null | grep -qE 'git commit'; then
        [ -n "$ARKAOS_PY" ] && [ -n "$ARKAOS_ROOT" ] && \
          PYTHONPATH="$ARKAOS_ROOT" $ARKAOS_PY -c "
from core.workflow.state import add_violation
add_violation('branch-isolation', 'Commit on master/main while workflow active', 'Bash')
" 2>/dev/null
        VIOLATION_MSG="VIOLATION [branch-isolation]: Commit on master while workflow active. Use a feature branch."
      fi
    fi
  fi

  # Rule 2: Spec-driven — code edited without completed spec
  if [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; then
    FILE_PATH=$(echo "$input" | jq -r '.file_path // ""' 2>/dev/null)
    if echo "$FILE_PATH" | grep -qE '\.(py|js|ts|vue|php|jsx|tsx)$'; then
      if ! bash "$STATE_READER" check spec 2>/dev/null; then
        [ -n "$ARKAOS_PY" ] && [ -n "$ARKAOS_ROOT" ] && \
          PYTHONPATH="$ARKAOS_ROOT" $ARKAOS_PY -c "
from core.workflow.state import add_violation
add_violation('spec-driven', 'Code edited without completed spec', '$TOOL_NAME', '$FILE_PATH')
" 2>/dev/null
        VIOLATION_MSG="VIOLATION [spec-driven]: Code edited without completed spec ($FILE_PATH). Complete the spec phase first."
      fi
    fi
  fi

  # Rule 3: Sequential — implementation before planning
  if [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; then
    FILE_PATH=$(echo "$input" | jq -r '.file_path // ""' 2>/dev/null)
    if echo "$FILE_PATH" | grep -qE '\.(py|js|ts|vue|php|jsx|tsx)$'; then
      IMPL_STATUS=$(bash "$STATE_READER" phase implementation 2>/dev/null)
      if [ "$IMPL_STATUS" = "pending" ]; then
        [ -n "$ARKAOS_PY" ] && [ -n "$ARKAOS_ROOT" ] && \
          PYTHONPATH="$ARKAOS_ROOT" $ARKAOS_PY -c "
from core.workflow.state import add_violation
add_violation('sequential-validation', 'Code written before implementation phase started', '$TOOL_NAME', '$FILE_PATH')
" 2>/dev/null
        [ -z "$VIOLATION_MSG" ] && VIOLATION_MSG="VIOLATION [sequential-validation]: Implementation started before planning completed ($FILE_PATH)."
      fi
    fi
  fi
fi

# ─── Log Metrics ─────────────────────────────────────────────────────────
_DURATION_MS=$(_hook_ms)
METRICS_FILE="$HOME/.arkaos/hook-metrics.json"
METRICS_LOCK="$HOME/.arkaos/hook-metrics.lock"
mkdir -p "$HOME/.arkaos"
(
  if command -v flock &>/dev/null; then flock -w 2 200; else true; fi
  [ ! -f "$METRICS_FILE" ] && echo '[]' > "$METRICS_FILE"
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq --argjson dur "$_DURATION_MS" --arg ts "$NOW" --arg hook "post-tool-use" \
    '. += [{"hook": $hook, "duration_ms": $dur, "timestamp": $ts}] | .[-500:]' \
    "$METRICS_FILE" > "$METRICS_FILE.tmp" 2>/dev/null && mv "$METRICS_FILE.tmp" "$METRICS_FILE"
) 200>"$METRICS_LOCK" 2>/dev/null

# Output violation as context if detected, otherwise empty
if [ -n "$VIOLATION_MSG" ]; then
  echo "{\"additionalContext\": \"$VIOLATION_MSG\"}"
else
  echo '{}'
fi
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n config/hooks/post-tool-use.sh && echo "SYNTAX OK"
```

- [ ] **Step 3: Commit**

```bash
git add config/hooks/post-tool-use.sh
git commit -m "feat(hooks): detect workflow violations in PostToolUse"
```

---

### Task 7: Full validation and deploy

**Files:**
- Modify: `core/workflow/__init__.py` (add state exports)

- [ ] **Step 1: Update workflow __init__.py to export state module**

Add to `core/workflow/__init__.py`:

```python
from core.workflow.state import (
    init_workflow as init_workflow_state,
    get_state as get_workflow_state,
    update_phase,
    set_branch,
    add_violation,
    is_phase_completed,
    clear_workflow,
)
```

And add them to `__all__`.

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest tests/ --tb=short -q
```
Expected: 2002+ passed (21 new from state tracker)

- [ ] **Step 3: Integration test — full workflow lifecycle**

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from core.workflow.state import *

# Start workflow
s = init_workflow('dev/feature', '/tmp/test', ['context', 'spec', 'planning', 'implementation', 'quality_gate', 'documentation'])
print(f'Started: {s[\"workflow\"]} with {len(s[\"phases\"])} phases')

# Progress through phases
set_branch('feature/test-auth')
update_phase('context', 'completed')
update_phase('spec', 'completed', artifact='docs/spec.md')
update_phase('planning', 'completed')
update_phase('implementation', 'in_progress')

# Simulate a violation
add_violation('branch-isolation', 'Commit on master', tool='Bash')

# Check state
s = get_state()
print(f'Phase implementation: {s[\"phases\"][\"implementation\"][\"status\"]}')
print(f'Violations: {len(s[\"violations\"])}')
print(f'Spec completed: {is_phase_completed(\"spec\")}')
print(f'QG completed: {is_phase_completed(\"quality_gate\")}')

# Reader test
import subprocess
reader = 'core/workflow/state_reader.sh'
print(f'Summary: {subprocess.run([\"bash\", reader, \"summary\"], capture_output=True, text=True).stdout.strip()}')

# Cleanup
clear_workflow()
print('Cleared')
"
```

Expected:
```
Started: dev/feature with 6 phases
Phase implementation: in_progress
Violations: 1
Spec completed: True
QG completed: False
Summary: dev/feature|implementation|3/6|feature/test-auth|1
Cleared
```

- [ ] **Step 4: Verify all hooks have valid syntax**

```bash
bash -n config/hooks/session-start.sh && echo "session-start OK"
bash -n config/hooks/user-prompt-submit.sh && echo "user-prompt-submit OK"
bash -n config/hooks/post-tool-use.sh && echo "post-tool-use OK"
```

- [ ] **Step 5: Deploy updated hooks locally**

```bash
cp config/hooks/session-start.sh ~/.arkaos/config/hooks/ 2>/dev/null
cp config/hooks/user-prompt-submit.sh ~/.arkaos/config/hooks/ 2>/dev/null
cp config/hooks/post-tool-use.sh ~/.arkaos/config/hooks/ 2>/dev/null
echo "Hooks deployed"
```

- [ ] **Step 6: Commit docs and plan**

```bash
git add docs/superpowers/specs/2026-04-11-workflow-state-tracker-design.md
git add docs/superpowers/plans/2026-04-11-workflow-state-tracker.md
git commit -m "docs: add workflow state tracker spec and plan"
```
