#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — UserPromptSubmit Hook (Synapse v2 Bridge)
# Calls Python Synapse engine for 8-layer context injection
# Timeout: 10s | Output: JSON to stdout | Target: <100ms
# ============================================================================

input=$(cat)

# ─── Performance Timing ──────────────────────────────────────────────────
_HOOK_START_NS=$(date +%s%N 2>/dev/null || echo "0")
_hook_ms() {
  local end_ns=$(date +%s%N 2>/dev/null || echo "0")
  if [ "$_HOOK_START_NS" != "0" ] && [ "$end_ns" != "0" ] && [ ${#end_ns} -gt 10 ]; then
    echo $(( (end_ns - _HOOK_START_NS) / 1000000 ))
  else
    echo "0"
  fi
}

# ─── Paths ───────────────────────────────────────────────────────────────
# Resolve ARKAOS_ROOT: env var → .repo-path → npm package → fallback
if [ -n "${ARKAOS_ROOT:-}" ]; then
  : # already set
elif [ -f "$HOME/.arkaos/.repo-path" ]; then
  ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path")
elif [ -d "$HOME/.arkaos" ]; then
  ARKAOS_ROOT="$HOME/.arkaos"
else
  ARKAOS_ROOT="${ARKA_OS:-$HOME/.claude/skills/arkaos}"
fi
export ARKAOS_ROOT

CACHE_DIR="/tmp/arkaos-context-cache"
CACHE_TTL=300  # Constitution cache: 5 minutes

mkdir -p "$CACHE_DIR" 2>/dev/null

# ─── Extract user input from hook JSON ───────────────────────────────────
user_input=""
if command -v jq &>/dev/null; then
  user_input=$(echo "$input" | jq -r '.userInput // .message // ""' 2>/dev/null)
fi
# Fallback: try to get the raw text
if [ -z "$user_input" ]; then
  user_input=$(echo "$input" | head -c 2000)
fi

# ─── Try Python Synapse bridge first ────────────────────────────────────
python_result=""
BRIDGE_SCRIPT="${ARKAOS_ROOT}/scripts/synapse-bridge.py"

if command -v python3 &>/dev/null && [ -f "$BRIDGE_SCRIPT" ]; then
  bridge_output=$(echo "{\"user_input\":$(echo "$user_input" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '""')}" \
    | ARKAOS_ROOT="$ARKAOS_ROOT" python3 "$BRIDGE_SCRIPT" --root "$ARKAOS_ROOT" 2>/dev/null)

  if [ -n "$bridge_output" ]; then
    python_result=$(echo "$bridge_output" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('context_string',''))" 2>/dev/null)
  fi
fi

# ─── Fallback: Bash-only context (if Python unavailable) ────────────────
if [ -z "$python_result" ]; then
  # L0: Constitution (cached)
  L0=""
  L0_CACHE="$CACHE_DIR/l0-constitution"
  if [ -f "$L0_CACHE" ] && [ $(($(date +%s) - $(stat -f%m "$L0_CACHE" 2>/dev/null || stat -c%Y "$L0_CACHE" 2>/dev/null || echo 0))) -lt $CACHE_TTL ]; then
    L0=$(cat "$L0_CACHE")
  else
    L0="[Constitution] NON-NEGOTIABLE: branch-isolation, obsidian-output, authority-boundaries, security-gate, context-first, solid-clean-code, spec-driven, human-writing, squad-routing, full-visibility, sequential-validation, mandatory-qa, arka-supremacy | QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | MUST: conventional-commits, test-coverage, pattern-matching, actionable-output, memory-persistence"
    echo "$L0" > "$L0_CACHE" 2>/dev/null
  fi

  # L4: Git branch
  L4=""
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ -n "$branch" ] && [ "$branch" != "main" ] && [ "$branch" != "master" ] && [ "$branch" != "dev" ]; then
    L4="[branch:$branch]"
  fi

  # L7: Time
  hour=$(date +%H)
  if [ "$hour" -ge 5 ] && [ "$hour" -lt 12 ]; then
    L7="[time:morning]"
  elif [ "$hour" -ge 12 ] && [ "$hour" -lt 18 ]; then
    L7="[time:afternoon]"
  else
    L7="[time:evening]"
  fi

  python_result="$L0 $L4 $L7"
fi

# ─── Output ──────────────────────────────────────────────────────────────
echo "{\"additionalContext\": \"$python_result\"}"

# ─── Metrics ─────────────────────────────────────────────────────────────
elapsed=$(_hook_ms)
if [ "$elapsed" -gt 0 ] 2>/dev/null; then
  echo "{\"hook\":\"user-prompt-submit-v2\",\"ms\":$elapsed}" >> "$CACHE_DIR/hook-metrics.jsonl" 2>/dev/null
fi
