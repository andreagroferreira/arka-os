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

# ─── Session Greeting (now handled by SessionStart hook via systemMessage) ──
_ARKA_GREETING=""

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
# Resolve ARKAOS_ROOT: env var → .repo-path → $HOME/.arkaos → portable fallback
if [ -n "${ARKAOS_ROOT:-}" ]; then
  : # already set
elif [ -f "$HOME/.arkaos/.repo-path" ]; then
  ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path")
elif [ -d "$HOME/.arkaos" ]; then
  ARKAOS_ROOT="$HOME/.arkaos"
else
  # Portable fallback — matches user-prompt-submit-v2.sh. Power users can
  # override with the ARKA_OS env var. Reached only on corrupt/uninitialised
  # installs; synapse-bridge.py will fail gracefully if the path is wrong.
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

  # Append workflow state to synapse context
  _WF_READER="$ARKAOS_ROOT/core/workflow/state_reader.sh"
  if [ -f "$_WF_READER" ] && bash "$_WF_READER" active 2>/dev/null; then
    _WF_SUM=$(bash "$_WF_READER" summary 2>/dev/null)
    _WF_N=$(echo "$_WF_SUM" | cut -d'|' -f1)
    _WF_P=$(echo "$_WF_SUM" | cut -d'|' -f2)
    _WF_B=$(echo "$_WF_SUM" | cut -d'|' -f4)
    _WF_V=$(echo "$_WF_SUM" | cut -d'|' -f5)
    _WF_TAG="[workflow:${_WF_N}] [phase:${_WF_P}] [branch:${_WF_B}] [violations:${_WF_V}]"
    [ "$_WF_V" != "0" ] && _WF_TAG="WARNING: ${_WF_V} workflow violation(s). $_WF_TAG"
    python_result="${python_result} ${_WF_TAG}"
  fi

  # --- Forge Context Injection ---
  _FORGE_ACTIVE="$HOME/.arkaos/plans/active.yaml"
  if [ -f "$_FORGE_ACTIVE" ]; then
    _FORGE_ID=$(cat "$_FORGE_ACTIVE" 2>/dev/null)
    _FORGE_FILE="$HOME/.arkaos/plans/${_FORGE_ID}.yaml"
    if [ -f "$_FORGE_FILE" ] && command -v python3 &>/dev/null; then
      _FORGE_STATUS=$(FORGE_FILE="$_FORGE_FILE" python3 -c "import yaml,os; d=yaml.safe_load(open(os.environ['FORGE_FILE'])); print(d.get('status',''))" 2>/dev/null)
      _FORGE_TAG="[forge:${_FORGE_ID}] [forge-status:${_FORGE_STATUS}]"
      python_result="${python_result} ${_FORGE_TAG}"
    fi
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

  # L7: Time — intentionally skipped in bash fallback.
  # Low-signal tag that changed every prompt and invalidated prompt cache.
  # The Python TimeLayer (cache_ttl=3600) is authoritative when available.
  L7=""

  # L8: Workflow state
  L8=""
  _WF_READER="$ARKAOS_ROOT/core/workflow/state_reader.sh"
  if [ -f "$_WF_READER" ] && bash "$_WF_READER" active 2>/dev/null; then
    _WF_SUM=$(bash "$_WF_READER" summary 2>/dev/null)
    _WF_N=$(echo "$_WF_SUM" | cut -d'|' -f1)
    _WF_P=$(echo "$_WF_SUM" | cut -d'|' -f2)
    _WF_B=$(echo "$_WF_SUM" | cut -d'|' -f4)
    _WF_V=$(echo "$_WF_SUM" | cut -d'|' -f5)
    L8="[workflow:${_WF_N}] [phase:${_WF_P}] [branch:${_WF_B}] [violations:${_WF_V}]"
    [ "$_WF_V" != "0" ] && L8="WARNING: ${_WF_V} workflow violation(s). $L8"
  fi

  # L9: Forge state
  L9=""
  _FORGE_ACTIVE_FB="$HOME/.arkaos/plans/active.yaml"
  if [ -f "$_FORGE_ACTIVE_FB" ]; then
    _FORGE_ID_FB=$(cat "$_FORGE_ACTIVE_FB" 2>/dev/null)
    _FORGE_FILE_FB="$HOME/.arkaos/plans/${_FORGE_ID_FB}.yaml"
    if [ -f "$_FORGE_FILE_FB" ] && command -v python3 &>/dev/null; then
      _FORGE_STATUS_FB=$(FORGE_FILE="$_FORGE_FILE_FB" python3 -c "import yaml,os; d=yaml.safe_load(open(os.environ['FORGE_FILE'])); print(d.get('status',''))" 2>/dev/null)
      L9="[forge:${_FORGE_ID_FB}] [forge-status:${_FORGE_STATUS_FB}]"
    fi
  fi

  python_result="$L0 $L4 $L7 $L8 $L9"
fi

# ─── Output ──────────────────────────────────────────────────────────────
echo "{\"additionalContext\": \"${_ARKA_GREETING:-}${_SYNC_NOTICE:-}$python_result\"}"

# ─── Metrics ─────────────────────────────────────────────────────────────
elapsed=$(_hook_ms)
if [ "$elapsed" -gt 0 ] 2>/dev/null; then
  echo "{\"hook\":\"user-prompt-submit-v2\",\"ms\":$elapsed}" >> "$CACHE_DIR/hook-metrics.jsonl" 2>/dev/null
fi
