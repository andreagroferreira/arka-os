#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — PreToolUse Hook (Flow Enforcement Gate)
#
# Blocks Write/Edit/MultiEdit when the 4-gate evidence flow is required
# for the session AND the assistant has not emitted a flow marker
# (`[arka:routing]`, `[arka:trivial]`, `[arka:gate:`, or the legacy
# `[arka:phase:`) in its recent transcript messages.
#
# Delegates the decision to core/workflow/flow_enforcer.py (single source
# of truth, pytest-covered). This shell script is a thin wrapper — anti
# pattern `duplicated-security-logic` compliance.
#
# Timeout: 10s.
# Allow semantics: no stdout, exit 0.
# Deny semantics: hookSpecificOutput.permissionDecision=deny JSON on stdout,
# `[ARKA:ENFORCEMENT] ...` on stderr, exit 2.
# ============================================================================

input=$(cat)

# ─── Extract fields (docs: session_id, transcript_path, cwd, tool_name)
TOOL_NAME=""
TRANSCRIPT_PATH=""
SESSION_ID=""
CWD=""
if command -v jq &>/dev/null; then
  TOOL_NAME=$(echo "$input" | jq -r '.tool_name // ""' 2>/dev/null)
  TRANSCRIPT_PATH=$(echo "$input" | jq -r '.transcript_path // ""' 2>/dev/null)
  SESSION_ID=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)
  CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)
fi

# ─── Resolve ARKAOS_ROOT (same rules as user-prompt-submit.sh) ──────────
if [ -z "${ARKAOS_ROOT:-}" ]; then
  if [ -f "$HOME/.arkaos/.repo-path" ]; then
    ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path")
  elif [ -d "$HOME/.arkaos" ]; then
    ARKAOS_ROOT="$HOME/.arkaos"
  else
    ARKAOS_ROOT="${ARKA_OS:-$HOME/.claude/skills/arkaos}"
  fi
fi

# ─── Degrade gracefully if Python is unavailable ────────────────────────
if ! command -v python3 &>/dev/null; then
  exit 0
fi

# ─── KB-first gate (Task #6, independent from flow_enforcer) ────────────
# Runs BEFORE the flow-marker gate so that external research tools are
# always KB-checked regardless of whether the tool is Write/Edit/MultiEdit.
# Extract the user query (if present) to feed the nudge generator.
QUERY_HINT=""
if command -v jq &>/dev/null; then
  QUERY_HINT=$(echo "$input" | jq -r '.tool_input.query // .tool_input.prompt // .tool_input.url // ""' 2>/dev/null | head -c 500)
fi

if [ -f "$ARKAOS_ROOT/core/workflow/research_gate.py" ]; then
  KB_DECISION_JSON=$(TOOL_NAME="$TOOL_NAME" \
                     SESSION_ID="$SESSION_ID" \
                     QUERY_HINT="$QUERY_HINT" \
                     ARKAOS_ROOT="$ARKAOS_ROOT" \
                     python3 - <<'PY' 2>/dev/null
import json
import os
import sys

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
try:
    from core.workflow.research_gate import evaluate_research_gate, record_telemetry
except Exception:
    print(json.dumps({"allow": True, "nudge": False, "reason": "kb-gate-import-failed"}))
    sys.exit(0)

decision = evaluate_research_gate(
    tool_name=os.environ.get("TOOL_NAME", ""),
    session_id=os.environ.get("SESSION_ID", ""),
    query=os.environ.get("QUERY_HINT", ""),
)
try:
    record_telemetry(
        session_id=os.environ.get("SESSION_ID", ""),
        tool=os.environ.get("TOOL_NAME", ""),
        decision=decision,
    )
except Exception:
    pass
print(json.dumps({
    "allow": decision.allow,
    "nudge": decision.nudge,
    "reason": decision.reason,
    "stderr_msg": decision.to_stderr_message(),
}))
PY
)

  if [ -n "$KB_DECISION_JSON" ]; then
    KB_ALLOW=$(echo "$KB_DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('allow', True))" 2>/dev/null)
    KB_NUDGE=$(echo "$KB_DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('nudge', False))" 2>/dev/null)
    KB_STDERR=$(echo "$KB_DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('stderr_msg',''))" 2>/dev/null)

    if [ "$KB_ALLOW" != "True" ] && [ "$KB_ALLOW" != "true" ]; then
      echo "$KB_STDERR" >&2
      STDERR_MSG="$KB_STDERR" python3 - <<'PY'
import json, os
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": os.environ.get("STDERR_MSG", ""),
}}))
PY
      exit 2
    fi

    # Nudge path: emit advisory to stderr, continue to flow-marker gate.
    if [ "$KB_NUDGE" = "True" ] || [ "$KB_NUDGE" = "true" ]; then
      [ -n "$KB_STDERR" ] && echo "$KB_STDERR" >&2
    fi
  fi
fi

# ─── Specialist-dispatch gate (between KB-gate and flow-gate) ──────────
# Blocks Tier-1 leads from writing to specialist-owned files without
# dispatching first. Only fires for file-mutation tools. Independent
# feature flag (`hooks.specialistEnforcement`) — fails open if the
# Python module is absent or raises.
if [ -f "$ARKAOS_ROOT/core/workflow/specialist_enforcer.py" ]; then
  case "$TOOL_NAME" in
    Write|Edit|MultiEdit|NotebookEdit)
      TOOL_INPUT_JSON_SP="{}"
      if command -v jq &>/dev/null; then
        TOOL_INPUT_JSON_SP=$(echo "$input" | jq -c '.tool_input // {}' 2>/dev/null)
      fi
      SP_DECISION_JSON=$(TOOL_NAME="$TOOL_NAME" \
                         TRANSCRIPT_PATH="$TRANSCRIPT_PATH" \
                         SESSION_ID="$SESSION_ID" \
                         CWD="$CWD" \
                         TOOL_INPUT_JSON="$TOOL_INPUT_JSON_SP" \
                         ARKAOS_ROOT="$ARKAOS_ROOT" \
                         python3 - <<'PY' 2>/dev/null
import json
import os
import sys

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
try:
    from core.workflow.specialist_enforcer import evaluate, record_telemetry
except Exception:
    print(json.dumps({"allow": True, "reason": "specialist-import-failed"}))
    sys.exit(0)

try:
    tool_input = json.loads(os.environ.get("TOOL_INPUT_JSON", "{}"))
except json.JSONDecodeError:
    tool_input = {}

decision = evaluate(
    tool_name=os.environ.get("TOOL_NAME", ""),
    transcript_path=os.environ.get("TRANSCRIPT_PATH", ""),
    session_id=os.environ.get("SESSION_ID", ""),
    cwd=os.environ.get("CWD", ""),
    tool_input=tool_input,
)
try:
    record_telemetry(
        session_id=os.environ.get("SESSION_ID", ""),
        tool=os.environ.get("TOOL_NAME", ""),
        decision=decision,
        cwd=os.environ.get("CWD", ""),
        target_file=str(tool_input.get("file_path", "")),
        model_requested=str(tool_input.get("model", "")),
    )
except Exception:
    pass
print(json.dumps({
    "allow": decision.allow,
    "reason": decision.reason,
    "stderr_msg": decision.to_stderr_message(),
}))
PY
)

      if [ -n "$SP_DECISION_JSON" ]; then
        SP_ALLOW=$(echo "$SP_DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('allow', True))" 2>/dev/null)
        if [ "$SP_ALLOW" != "True" ] && [ "$SP_ALLOW" != "true" ]; then
          SP_STDERR=$(echo "$SP_DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('stderr_msg',''))" 2>/dev/null)
          echo "$SP_STDERR" >&2
          STDERR_MSG="$SP_STDERR" python3 - <<'PY'
import json, os
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": os.environ.get("STDERR_MSG", ""),
}}))
PY
          exit 2
        fi
      fi
      ;;
  esac
fi

# ─── Fast allow: not a flow-gated tool ──────────────────────────────────
# PR11 v2.33.0 expanded the gated set to include all EFFECT tools.
# Bash is special — handled per-command by the Python enforcer via
# bash_is_effect(). Skip fast-path for Bash so the enforcer can classify.
case "$TOOL_NAME" in
  Write|Edit|MultiEdit|NotebookEdit|Task|Skill|Bash) ;;
  *) exit 0 ;;
esac

if [ ! -f "$ARKAOS_ROOT/core/workflow/flow_enforcer.py" ]; then
  exit 0
fi

# ─── Extract tool_input (needed for Bash command classification) ───────
TOOL_INPUT_JSON="{}"
if command -v jq &>/dev/null; then
  TOOL_INPUT_JSON=$(echo "$input" | jq -c '.tool_input // {}' 2>/dev/null)
fi

# ─── Delegate to Python enforcer ────────────────────────────────────────
DECISION_JSON=$(TOOL_NAME="$TOOL_NAME" \
                TRANSCRIPT_PATH="$TRANSCRIPT_PATH" \
                SESSION_ID="$SESSION_ID" \
                CWD="$CWD" \
                TOOL_INPUT_JSON="$TOOL_INPUT_JSON" \
                ARKAOS_ROOT="$ARKAOS_ROOT" \
                python3 - <<'PY' 2>/dev/null
import json
import os
import sys

sys.path.insert(0, os.environ["ARKAOS_ROOT"])
try:
    from core.workflow.flow_enforcer import evaluate, record_telemetry
except Exception:
    print(json.dumps({"allow": True, "reason": "enforcer-import-failed"}))
    sys.exit(0)

try:
    tool_input = json.loads(os.environ.get("TOOL_INPUT_JSON", "{}"))
except json.JSONDecodeError:
    tool_input = {}

decision = evaluate(
    tool_name=os.environ.get("TOOL_NAME", ""),
    transcript_path=os.environ.get("TRANSCRIPT_PATH", ""),
    session_id=os.environ.get("SESSION_ID", ""),
    cwd=os.environ.get("CWD", ""),
    tool_input=tool_input,
)
try:
    record_telemetry(
        session_id=os.environ.get("SESSION_ID", ""),
        tool=os.environ.get("TOOL_NAME", ""),
        decision=decision,
        cwd=os.environ.get("CWD", ""),
    )
except Exception:
    pass
print(json.dumps({
    "allow": decision.allow,
    "reason": decision.reason,
    "stderr_msg": decision.to_stderr_message(),
}))
PY
)

if [ -z "$DECISION_JSON" ]; then
  exit 0
fi

ALLOW=$(echo "$DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('allow', True))" 2>/dev/null)

if [ "$ALLOW" = "True" ] || [ "$ALLOW" = "true" ]; then
  exit 0
fi

# ─── Deny path: structured hookSpecificOutput + stderr fallback ─────────
REASON=$(echo "$DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('reason',''))" 2>/dev/null)
STDERR_MSG=$(echo "$DECISION_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('stderr_msg',''))" 2>/dev/null)

# Emit stderr (visible to the model per Claude Code hook spec) ─────────
echo "$STDERR_MSG" >&2

# Emit structured deny JSON (preferred path when runtime understands it).
# STDERR_MSG is passed via env var and read inside a single-quoted heredoc
# so no shell interpolation occurs inside the Python source — this closes
# the command-injection surface flagged by Francisca's tech review.
STDERR_MSG="$STDERR_MSG" python3 - <<'PY'
import json
import os

out = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": os.environ.get("STDERR_MSG", ""),
    }
}
print(json.dumps(out))
PY

exit 2
