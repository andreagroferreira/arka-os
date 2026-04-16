#!/usr/bin/env bash
# ============================================================================
# ARKA OS — PostToolUse Hook (Gotchas Memory)
# Detects errors from tool output and tracks recurring patterns
# Timeout: 5s | Output: JSON to stdout
# ============================================================================

input=$(cat)

# ─── Performance Timing ──────────────────────────────────────────────────
_HOOK_START=$(date +%s 2>/dev/null)
_HOOK_START_NS=$(date +%s%N 2>/dev/null || echo "0")
_hook_ms() {
  local end_ns=$(date +%s%N 2>/dev/null || echo "0")
  if [ "$_HOOK_START_NS" != "0" ] && [ "$end_ns" != "0" ] && [ ${#end_ns} -gt 10 ]; then
    echo $(( (end_ns - _HOOK_START_NS) / 1000000 ))
  else
    echo $(( ($(date +%s) - _HOOK_START) * 1000 ))
  fi
}

# Extract fields
TOOL_NAME=$(echo "$input" | jq -r '.tool_name // ""' 2>/dev/null)
TOOL_OUTPUT=$(echo "$input" | jq -r '.tool_output // ""' 2>/dev/null)
EXIT_CODE=$(echo "$input" | jq -r '.exit_code // "0"' 2>/dev/null)
CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)

# Only process if there was an error
if [ "$EXIT_CODE" = "0" ] || [ -z "$EXIT_CODE" ]; then
  # Also check for error patterns in output even with exit code 0
  if ! echo "$TOOL_OUTPUT" | grep -qiE '(error:|fatal:|exception:|failed|ENOENT|EACCES|EPERM|panic:)'; then
    echo '{}'
    exit 0
  fi
fi

# ─── Extract Error Pattern ────────────────────────────────────────────────
# Get first meaningful error line (skip blank lines, timestamps)
ERROR_LINE=$(echo "$TOOL_OUTPUT" | grep -iE '(error|fatal|exception|failed|ENOENT|EACCES|EPERM|panic|cannot|not found|permission denied)' | head -1)

if [ -z "$ERROR_LINE" ]; then
  # Fallback: first non-empty line of output for non-zero exit
  ERROR_LINE=$(echo "$TOOL_OUTPUT" | head -5 | tail -1)
fi

[ -z "$ERROR_LINE" ] && { echo '{}'; exit 0; }

# Normalize: remove timestamps, hashes, paths with unique segments, line numbers
PATTERN=$(echo "$ERROR_LINE" | \
  sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}[^ ]*/TIMESTAMP/g' | \
  sed -E 's/[0-9a-f]{7,40}/HASH/g' | \
  sed -E 's/line [0-9]+/line N/g' | \
  sed -E 's/:[0-9]+:/:N:/g' | \
  head -c 200)

[ -z "$PATTERN" ] && { echo '{}'; exit 0; }

# ─── Categorize ──────────────────────────────────────────────────────────
CATEGORY="general"
if echo "$ERROR_LINE" | grep -qiE '(artisan|eloquent|laravel|blade|migration|composer|php )'; then
  CATEGORY="laravel"
elif echo "$ERROR_LINE" | grep -qiE '(npm|node|vue|react|nuxt|next|vite|webpack|typescript|tsx|jsx)'; then
  CATEGORY="frontend"
elif echo "$ERROR_LINE" | grep -qiE '(git |merge|rebase|checkout|branch|commit|push|pull)'; then
  CATEGORY="git"
elif echo "$ERROR_LINE" | grep -qiE '(sql|postgres|mysql|database|migration|table|column|constraint)'; then
  CATEGORY="database"
elif echo "$ERROR_LINE" | grep -qiE '(permission|denied|EACCES|EPERM|chmod|chown|sudo)'; then
  CATEGORY="permissions"
elif echo "$ERROR_LINE" | grep -qiE '(test|assert|expect|jest|phpunit|bats|coverage)'; then
  CATEGORY="testing"
fi

# ─── Match Fix Suggestion ────────────────────────────────────────────────
SUGGESTION=""
FIXES_FILE="${ARKA_OS:-$HOME/.claude/skills/arka}/config/gotchas-fixes.json"
# Also check repo path
if [ ! -f "$FIXES_FILE" ]; then
  REPO_PATH=$(cat "${ARKA_OS:-$HOME/.claude/skills/arka}/.repo-path" 2>/dev/null || echo "")
  [ -n "$REPO_PATH" ] && FIXES_FILE="$REPO_PATH/config/gotchas-fixes.json"
fi
if [ -f "$FIXES_FILE" ] && command -v jq &>/dev/null; then
  SUGGESTION=$(jq -r --arg err "$ERROR_LINE" '
    .fixes[] | select(.pattern_match as $p | $err | test($p; "i")) | .suggestion
  ' "$FIXES_FILE" 2>/dev/null | head -1)
fi

# ─── Detect Active Project ───────────────────────────────────────────────
PROJECT=""
if [ -n "$CWD" ]; then
  # Try to extract project name from CWD
  REPO_PATH=$(cat "${ARKA_OS:-$HOME/.claude/skills/arka}/.repo-path" 2>/dev/null || echo "")
  if [ -n "$REPO_PATH" ] && [ -d "$REPO_PATH/projects" ]; then
    for proj_dir in "$REPO_PATH/projects"/*/; do
      [ -f "$proj_dir/.project-path" ] || continue
      PROJ_PATH=$(cat "$proj_dir/.project-path" 2>/dev/null)
      if [ -n "$PROJ_PATH" ] && [[ "$CWD" == "$PROJ_PATH"* ]]; then
        PROJECT=$(basename "$proj_dir")
        break
      fi
    done
  fi
  # Fallback: use directory name
  [ -z "$PROJECT" ] && PROJECT=$(basename "$CWD")
fi

# ─── Store in gotchas.json ────────────────────────────────────────────────
GOTCHAS_FILE="$HOME/.arkaos/gotchas.json"
mkdir -p "$HOME/.arkaos"

# Use flock for concurrent safety (fallback if flock not available on macOS)
LOCK_FILE="$HOME/.arkaos/gotchas.lock"
if command -v flock &>/dev/null; then
  LOCK_CMD="flock -w 3 200"
else
  LOCK_CMD="true"
fi
(
  eval "$LOCK_CMD" || { echo '{}'; exit 0; }

  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Initialize if missing or invalid
  if [ ! -f "$GOTCHAS_FILE" ] || ! jq empty "$GOTCHAS_FILE" 2>/dev/null; then
    echo '[]' > "$GOTCHAS_FILE"
  fi

  # Check if pattern already exists
  EXISTING_IDX=$(jq -r --arg pat "$PATTERN" \
    'to_entries[] | select(.value.pattern == $pat) | .key' \
    "$GOTCHAS_FILE" 2>/dev/null | head -1)

  if [ -n "$EXISTING_IDX" ] && [ "$EXISTING_IDX" -ge 0 ] 2>/dev/null; then
    # Increment count, update last_seen, add project if new, add suggestion if missing
    jq --argjson idx "$EXISTING_IDX" \
       --arg now "$NOW" \
       --arg proj "$PROJECT" \
       --arg sug "$SUGGESTION" \
       '.[$idx].count += 1 |
        .[$idx].last_seen = $now |
        (if $proj != "" and ($proj | IN(.[$idx].projects[]?) | not) then .[$idx].projects += [$proj] else . end) |
        (if $sug != "" and ((.[$idx].suggestion // "") == "") then .[$idx].suggestion = $sug else . end)' \
       "$GOTCHAS_FILE" > "$GOTCHAS_FILE.tmp" 2>/dev/null && mv "$GOTCHAS_FILE.tmp" "$GOTCHAS_FILE"
  else
    # Add new entry
    jq --arg pat "$PATTERN" \
       --arg full "$ERROR_LINE" \
       --arg cat "$CATEGORY" \
       --arg tool "$TOOL_NAME" \
       --arg now "$NOW" \
       --arg proj "$PROJECT" \
       --arg sug "$SUGGESTION" \
       '. += [{
         "pattern": $pat,
         "full_pattern": ($full | .[0:500]),
         "category": $cat,
         "tool": $tool,
         "count": 1,
         "first_seen": $now,
         "last_seen": $now,
         "projects": (if $proj != "" then [$proj] else [] end),
         "suggestion": (if $sug != "" then $sug else null end)
       }]' \
       "$GOTCHAS_FILE" > "$GOTCHAS_FILE.tmp" 2>/dev/null && mv "$GOTCHAS_FILE.tmp" "$GOTCHAS_FILE"
  fi

  # Keep top 100 sorted by count
  jq 'sort_by(-.count) | .[0:100]' "$GOTCHAS_FILE" > "$GOTCHAS_FILE.tmp" 2>/dev/null && \
    mv "$GOTCHAS_FILE.tmp" "$GOTCHAS_FILE"

) 200>"$LOCK_FILE"

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
    if echo "$TOOL_OUTPUT" | grep -qE '^\[(master|main)' 2>/dev/null; then
      CMD_TEXT=$(echo "$input" | jq -r '.command // ""' 2>/dev/null)
      if echo "$CMD_TEXT" | grep -qE 'git commit'; then
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
          PYTHONPATH="$ARKAOS_ROOT" _V_TOOL="$TOOL_NAME" _V_FILE="$FILE_PATH" $ARKAOS_PY -c "
import os; from core.workflow.state import add_violation
add_violation('spec-driven', 'Code edited without completed spec', os.environ['_V_TOOL'], os.environ['_V_FILE'])
" 2>/dev/null
        VIOLATION_MSG="VIOLATION [spec-driven]: Code edited without completed spec ($FILE_PATH). Complete the spec phase first."
      fi
    fi
  fi

  # Rule 3: Sequential — implementation before planning
  if [ -z "$VIOLATION_MSG" ] && { [ "$TOOL_NAME" = "Write" ] || [ "$TOOL_NAME" = "Edit" ]; }; then
    FILE_PATH=$(echo "$input" | jq -r '.file_path // ""' 2>/dev/null)
    if echo "$FILE_PATH" | grep -qE '\.(py|js|ts|vue|php|jsx|tsx)$'; then
      IMPL_STATUS=$(bash "$STATE_READER" phase implementation 2>/dev/null)
      if [ "$IMPL_STATUS" = "pending" ]; then
        [ -n "$ARKAOS_PY" ] && [ -n "$ARKAOS_ROOT" ] && \
          PYTHONPATH="$ARKAOS_ROOT" _V_TOOL="$TOOL_NAME" _V_FILE="$FILE_PATH" $ARKAOS_PY -c "
import os; from core.workflow.state import add_violation
add_violation('sequential-validation', 'Code written before implementation phase started', os.environ['_V_TOOL'], os.environ['_V_FILE'])
" 2>/dev/null
        VIOLATION_MSG="VIOLATION [sequential-validation]: Implementation started before planning completed ($FILE_PATH)."
      fi
    fi
  fi
fi

# ─── ArkaOS Enforcement Engine (All 14 Rules) ─────────────────────────────────
# Uses core/workflow/enforcer.py to check ALL 14 NON-NEGOTIABLE rules
# BLOCK violations halt operation; ESCALATE violations alert Tier 0
# Gotchas auto-recovery is ALWAYS active (SIM per Sprint 3 decision)

if [ -z "${ARKAOS_PY:-}" ]; then
  [ -f "$HOME/.arkaos/venv/bin/python3" ] && ARKAOS_PY="$HOME/.arkaos/venv/bin/python3"
  [ -z "${ARKAOS_PY:-}" ] && [ -f "$HOME/.arkaos/.venv/bin/python3" ] && ARKAOS_PY="$HOME/.arkaos/.venv/bin/python3"
  [ -z "${ARKAOS_PY:-}" ] && ARKAOS_PY=$(command -v python3 2>/dev/null)
fi
[ -z "${ARKAOS_ROOT:-}" ] && ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null)

if [ -n "$ARKAOS_PY" ] && [ -n "$ARKAOS_ROOT" ] && [ -f "$ARKAOS_ROOT/core/workflow/enforcer.py" ]; then
  ENFORCER_OUTPUT=$(PYTHONPATH="$ARKAOS_ROOT" $ARKAOS_PY -c "
import json, sys
from core.workflow.enforcer import enforce_tool
from core.workflow.state import add_violation

input_data = json.loads(sys.stdin.read())
tool_name = input_data.get('tool_name', '')
command = input_data.get('command', '')
file_path = input_data.get('file_path', '')
user_input = input_data.get('user_input', '')

extra = {}
if tool_name == 'Bash':
    import subprocess
    try:
        branch = subprocess.check_output(['git', 'branch', '--show-current'], text=True, stderr=subprocess.DEVNULL).strip()
        extra['git_branch'] = branch
    except:
        extra['git_branch'] = ''

result = enforce_tool(
    tool_name=tool_name,
    command=command,
    file_path=file_path,
    user_input=user_input,
    **extra
)

if result.violations:
    for v in result.violations:
        try:
            add_violation(v.rule_id, v.message, v.tool, v.file_path, v.severity)
        except:
            pass

    print(json.dumps({
        'violations': [v.to_dict() for v in result.violations],
        'blocked': result.blocked,
        'escalated': result.escalated,
        'messages': result.messages
    }))
else:
    print(json.dumps({'violations': [], 'blocked': False, 'escalated': False, 'messages': []}))
" <<< "$input" 2>/dev/null)

  if [ -n "$ENFORCER_OUTPUT" ] && echo "$ENFORCER_OUTPUT" | jq -e '.violations | length > 0' &>/dev/null; then
    ENFORCER_BLOCKED=$(echo "$ENFORCER_OUTPUT" | jq -r '.blocked')
    ENFORCER_MESSAGES=$(echo "$ENFORCER_OUTPUT" | jq -r '.messages | join("|")')

    for msg in $(echo "$ENFORCER_MESSAGES" | tr '|' '\n'); do
      [ -n "$msg" ] && VIOLATION_MSG="${VIOLATION_MSG}${VIOLATION_MSG:+$'\n'}${msg}"
    done

    if [ "$ENFORCER_BLOCKED" = "true" ]; then
      VIOLATION_MSG="🔴 BLOCK: ${VIOLATION_MSG}"
    fi
  fi
fi

# --- Forge Violation Detection ---
_FORGE_ACTIVE="$HOME/.arkaos/plans/active.yaml"

# Ensure ARKAOS_PY and ARKAOS_ROOT are set (may not be set if no active workflow)
if [ -z "${ARKAOS_PY:-}" ]; then
  [ -f "$HOME/.arkaos/venv/bin/python3" ] && ARKAOS_PY="$HOME/.arkaos/venv/bin/python3"
  [ -z "${ARKAOS_PY:-}" ] && [ -f "$HOME/.arkaos/.venv/bin/python3" ] && ARKAOS_PY="$HOME/.arkaos/.venv/bin/python3"
  [ -z "${ARKAOS_PY:-}" ] && ARKAOS_PY=$(command -v python3 2>/dev/null)
fi
[ -z "${ARKAOS_ROOT:-}" ] && ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null)

if [ -z "$VIOLATION_MSG" ] && [ -f "$_FORGE_ACTIVE" ] && [ -n "$ARKAOS_PY" ] && [ -n "$ARKAOS_ROOT" ]; then
  _FORGE_ID=$(cat "$_FORGE_ACTIVE" 2>/dev/null)
  _FORGE_FILE="$HOME/.arkaos/plans/${_FORGE_ID}.yaml"

  if [ -f "$_FORGE_FILE" ]; then
    if [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ]; then
      _EDITED_FILE="${tool_input_file_path:-}"
      # Fallback: extract file_path from input JSON
      [ -z "$_EDITED_FILE" ] && _EDITED_FILE=$(echo "$input" | jq -r '.file_path // ""' 2>/dev/null)
      if [ -n "$_EDITED_FILE" ]; then
        _FORGE_VIOLATION=$(FORGE_FILE="$_FORGE_FILE" EDITED_FILE="$_EDITED_FILE" PYTHONPATH="$ARKAOS_ROOT" $ARKAOS_PY -c "
import yaml, sys, os
plan = yaml.safe_load(open(os.environ['FORGE_FILE']))
if plan.get('status', '') != 'executing':
    sys.exit(0)
phases = plan.get('plan_phases', [])
all_deliverables = []
for p in phases:
    all_deliverables.extend(p.get('deliverables', []))
edited = os.environ['EDITED_FILE']
match = any(d in edited or edited.endswith(d) for d in all_deliverables)
if not match and all_deliverables:
    print('forge-scope-creep')
" 2>/dev/null)
        if [ "$_FORGE_VIOLATION" = "forge-scope-creep" ]; then
          VIOLATION_MSG="⚠ Forge scope-creep: editing ${_EDITED_FILE} which is outside forge plan deliverables."
        fi
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
