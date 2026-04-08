#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — UserPromptSubmit Hook (Synapse v2 Bridge)
# Calls Python Synapse engine for 8-layer context injection
# Timeout: 10s | Output: JSON to stdout | Target: <100ms
# ============================================================================

input=$(cat)

# ─── V1 Migration Detection ─────────────────────────────────────────────
V1_PATHS=("$HOME/.claude/skills/arka-os" "$HOME/.claude/skills/arkaos")
MIGRATION_MARKER="$HOME/.arkaos/migrated-from-v1"

for v1_path in "${V1_PATHS[@]}"; do
  if [ -d "$v1_path" ] && [ ! -f "$MIGRATION_MARKER" ]; then
    echo "{\"additionalContext\": \"[MIGRATION] ArkaOS v1 detected at $v1_path. Run: npx arkaos migrate — This will backup v1, preserve your data, and install v2. See: https://github.com/andreagroferreira/arka-os#install\"}"
    exit 0
  fi
done

# ─── Sync Version Detection ────────────────────────────────────────────
SYNC_STATE="$HOME/.arkaos/sync-state.json"
ARKAOS_VERSION_FILE="$HOME/.arkaos/.repo-path"

if [ -f "$ARKAOS_VERSION_FILE" ]; then
  _REPO_PATH=$(cat "$ARKAOS_VERSION_FILE")
  if [ -f "$_REPO_PATH/VERSION" ]; then
    _CURRENT_VERSION=$(cat "$_REPO_PATH/VERSION")
  elif [ -f "$_REPO_PATH/package.json" ]; then
    _CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$_REPO_PATH/package.json'))['version'])" 2>/dev/null || echo "")
  fi

  if [ -n "${_CURRENT_VERSION:-}" ]; then
    if [ -f "$SYNC_STATE" ]; then
      _SYNCED_VERSION=$(python3 -c "import json; print(json.load(open('$SYNC_STATE'))['version'])" 2>/dev/null || echo "none")
    else
      _SYNCED_VERSION="none"
    fi

    if [ "$_CURRENT_VERSION" != "$_SYNCED_VERSION" ]; then
      _SYNC_NOTICE="[arka:update-available] ArkaOS v${_CURRENT_VERSION} installed (synced: ${_SYNCED_VERSION}). Run /arka update to sync all projects. "
    fi
  fi
fi

# ─── Session Greeting (first prompt only, per-session) ─────────────────
_ARKA_GREETING=""
_SESSION_MARKER="/tmp/arkaos-greeted-$$"
if [ ! -f "$_SESSION_MARKER" ]; then
  touch "$_SESSION_MARKER"

  _GR_NAME="founder"
  _GR_COMPANY="WizardingCode"
  _GR_VERSION="2.x"

  if [ -f "$HOME/.arkaos/profile.json" ] && command -v python3 &>/dev/null; then
    _GR_NAME=$(python3 -c "import json; p=json.load(open('$HOME/.arkaos/profile.json')); print(p.get('name', p.get('role', 'founder')))" 2>/dev/null || echo "founder")
    _GR_COMPANY=$(python3 -c "import json; print(json.load(open('$HOME/.arkaos/profile.json')).get('company', 'WizardingCode'))" 2>/dev/null || echo "WizardingCode")
  fi

  if [ -f "$HOME/.arkaos/.repo-path" ]; then
    _GR_REPO=$(cat "$HOME/.arkaos/.repo-path")
    [ -f "$_GR_REPO/VERSION" ] && _GR_VERSION=$(cat "$_GR_REPO/VERSION" | tr -d '[:space:]')
  fi

  _HOUR=$(date +%H)
  if [ "$_HOUR" -ge 5 ] && [ "$_HOUR" -lt 12 ]; then _GR_TIME="Bom dia"
  elif [ "$_HOUR" -ge 12 ] && [ "$_HOUR" -lt 19 ]; then _GR_TIME="Boa tarde"
  else _GR_TIME="Boa noite"; fi

  _ARKA_GREETING="[arka:greeting] ARKA OS v${_GR_VERSION} | ${_GR_TIME}, ${_GR_NAME} (${_GR_COMPANY}) | 65 agents, 17 departments, 244+ skills | IMPORTANT: Display the ArkaOS branded greeting to the user as your FIRST output. Show the ARKA OS name prominently and welcome the user. "
fi

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
  ARKAOS_ROOT="/Users/andreagroferreira/.npm/_npx/67d92defd11b9985/node_modules/arkaos"
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
echo "{\"additionalContext\": \"${_ARKA_GREETING:-}${_SYNC_NOTICE:-}$python_result\"}"

# ─── Metrics ─────────────────────────────────────────────────────────────
elapsed=$(_hook_ms)
if [ "$elapsed" -gt 0 ] 2>/dev/null; then
  echo "{\"hook\":\"user-prompt-submit-v2\",\"ms\":$elapsed}" >> "$CACHE_DIR/hook-metrics.jsonl" 2>/dev/null
fi
