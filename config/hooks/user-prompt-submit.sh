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
    if [ -n "${ARKAOS_DEBUG:-}" ]; then
      echo "[DEBUG] Detected version: ${_CURRENT_VERSION:-unknown}, synced: ${_SYNCED_VERSION:-none}" >&2
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
SESSION_ID=""
EFFORT_LEVEL=""
if command -v jq &>/dev/null; then
  user_input=$(echo "$input" | jq -r '.userInput // .message // ""' 2>/dev/null)
  SESSION_ID=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)
  # PR46 v2.65.0 — Claude Code W19 ships effort.level in hook stdin.
  # Soft-block nudges (KB-first + meta-tag) are gated by effort: only
  # surfaced at high|xhigh; low/medium skip the nudge to avoid forcing
  # the model to comply with full contracts during cheap exploratory
  # turns. Hard enforcement (PreToolUse flow_enforcer) runs regardless.
  EFFORT_LEVEL=$(echo "$input" | jq -r '.effort.level // ""' 2>/dev/null)
fi
[ -z "$EFFORT_LEVEL" ] && EFFORT_LEVEL="${CLAUDE_EFFORT:-}"

# Decide whether soft-block nudges surface to the next turn.
_ARKA_SURFACE_NUDGES="true"
case "${EFFORT_LEVEL:-high}" in
  low|medium) _ARKA_SURFACE_NUDGES="false" ;;
  *)          _ARKA_SURFACE_NUDGES="true"  ;;
esac

# ─── Flow marker cache invalidation (v2 — new turn, reset ALLOW cache) ──
# Cheap, non-blocking, runs before Synapse so a stuck Python later cannot
# leave a stale marker alive across turns.
if [ -n "$SESSION_ID" ] && command -v python3 &>/dev/null; then
  _INVALIDATE_ROOT="${ARKAOS_ROOT:-}"
  if [ -z "$_INVALIDATE_ROOT" ] && [ -f "$HOME/.arkaos/.repo-path" ]; then
    _INVALIDATE_ROOT=$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null)
  fi
  [ -z "$_INVALIDATE_ROOT" ] && _INVALIDATE_ROOT="$HOME/.arkaos"
  SESSION_ID="$SESSION_ID" PYTHONPATH="$_INVALIDATE_ROOT" python3 -c "
import os
try:
    from core.workflow.marker_cache import invalidate_marker
    invalidate_marker(os.environ.get('SESSION_ID', ''))
except Exception:
    pass
try:
    from core.synapse.kb_cache import invalidate_obsidian_query
    invalidate_obsidian_query(os.environ.get('SESSION_ID', ''))
except Exception:
    pass
" 2>/dev/null || true
fi
# Fallback: try to get the raw text
if [ -z "$user_input" ]; then
  user_input=$(echo "$input" | head -c 2000)
fi

# ─── Load shared workflow classifier ─────────────────────────────────────
_CLASSIFIER_LIB="$(dirname "$0")/_lib/workflow-classifier.sh"
if [ -f "$_CLASSIFIER_LIB" ]; then
  # shellcheck disable=SC1090
  . "$_CLASSIFIER_LIB"
fi

# ─── Try Python Synapse bridge first ────────────────────────────────────
python_result=""
BRIDGE_SCRIPT="${ARKAOS_ROOT}/scripts/synapse-bridge.py"

# Determine which path we're using for debug output
if [ -n "${ARKAOS_DEBUG:-}" ]; then
  echo "[DEBUG] ARKAOS_ROOT=${ARKAOS_ROOT}" >&2
  echo "[DEBUG] BRIDGE_SCRIPT=${BRIDGE_SCRIPT}" >&2
fi

if command -v python3 &>/dev/null && [ -f "$BRIDGE_SCRIPT" ]; then
  # Validate ARKAOS_ROOT before calling bridge
  if [ ! -d "$ARKAOS_ROOT" ]; then
    if [ -n "${ARKAOS_DEBUG:-}" ]; then
      echo "[DEBUG] ARKAOS_ROOT is not a valid directory, skipping Python bridge" >&2
    fi
  else
    _bridge_start=$(date +%s%N 2>/dev/null || echo "0")
    # ARKAOS_SESSION_ID lets the bridge persist the injected-KB count for
    # kb=N reconciliation at Stop time (structural honesty PR-2).
    bridge_output=$(echo "{\"user_input\":$(echo "$user_input" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '""')}" \
      | ARKAOS_ROOT="$ARKAOS_ROOT" ARKAOS_SESSION_ID="$SESSION_ID" python3 "$BRIDGE_SCRIPT" --root "$ARKAOS_ROOT" 2>/dev/null)
    _bridge_status=$?

    if [ -n "${ARKAOS_DEBUG:-}" ]; then
      if [ "$_bridge_start" != "0" ] && [ $(date +%s%N 2>/dev/null || echo "0") != "0" ]; then
        _bridge_ms=$(( ($(date +%s%N) - _bridge_start) / 1000000 ))
        echo "[DEBUG] bridge completed in ${_bridge_ms}ms, exit=$_bridge_status" >&2
      fi
      echo "[DEBUG] bridge_output length=${#bridge_output}" >&2
    fi

    if [ -n "$bridge_output" ] && [ $_bridge_status -eq 0 ]; then
      python_result=$(echo "$bridge_output" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('context_string',''))" 2>/dev/null)
      if [ -n "${ARKAOS_DEBUG:-}" ]; then
        echo "[DEBUG] python_result length=${#python_result}" >&2
      fi
    elif [ -n "${ARKAOS_DEBUG:-}" ]; then
      echo "[DEBUG] bridge failed or returned empty, exit=$_bridge_status" >&2
    fi
  fi

  # Append workflow state to synapse context (always, if python result was set)
  if [ -n "$python_result" ]; then
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

    # --- Knowledge Auto-Inject (On-Demand via Session Cache) ---
    if [ -n "$python_result" ] && [[ "$python_result" == *"[knowledge:"* ]]; then
      _KB_SESSION_ID="${ARKAOS_SESSION_ID:-${CLAUDE_SESSION_ID:-bridge-$$}}"
      _KB_PROJECT_HASH=$(echo "$ARKAOS_ROOT" | md5sum 2>/dev/null | cut -c1-12 || echo "default")
      _KB_CACHE_DIR="/tmp/arkaos-kb-${_KB_PROJECT_HASH}"

      if [ -n "${ARKAOS_DEBUG:-}" ]; then
        echo "[DEBUG] KB session_id=${_KB_SESSION_ID}, project_hash=${_KB_PROJECT_HASH}" >&2
      fi

      if [ -d "$_KB_CACHE_DIR" ] && command -v python3 &>/dev/null; then
        _KB_CONTENT=$(python3 -c "
import sys
sys.path.insert(0, '$ARKAOS_ROOT')
from core.synapse.kb_cache import KBSessionCache
cache = KBSessionCache(session_id='$_KB_SESSION_ID', project_path='$ARKAOS_ROOT')
results = cache.get_overlap('''$user_input''', threshold=0.3)
if results:
    snippets = []
    for r in results[:3]:
        src = r.get('source', '').split('/')[-1] if r.get('source') else ''
        txt = r.get('text', '')[:200].replace('\n', ' ')
        snippets.append(f'{src}: {txt}' if src else txt)
    print(' | '.join(snippets))
" 2>/dev/null)

        if [ -n "$_KB_CONTENT" ]; then
          if [ -n "${ARKAOS_DEBUG:-}" ]; then
            echo "[DEBUG] KB auto-inject: ${#_KB_CONTENT} chars of knowledge" >&2
          fi
          python_result="${_KB_CONTENT} ${python_result}"
        fi
      fi
    fi
  fi
fi

# ─── Fallback: Bash-only context (if Python unavailable) ────────────────
if [ -z "$python_result" ]; then
  if [ -n "${ARKAOS_DEBUG:-}" ]; then
    echo "[DEBUG] Using bash fallback (python_result was empty)" >&2
  fi
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

# ─── Token Hygiene suggestions (non-blocking) ───────────────────────────
_HYGIENE=""
_HYGIENE_SCRIPT="$(dirname "$0")/token-hygiene.sh"
if [ -f "$_HYGIENE_SCRIPT" ]; then
  # Extract transcript path from input JSON if present
  _TRANSCRIPT=""
  if command -v jq &>/dev/null; then
    _TRANSCRIPT=$(echo "$input" | jq -r '.transcript_path // ""' 2>/dev/null)
  fi
  _HYGIENE=$(ARKA_PROMPT="$user_input" \
             ARKA_TRANSCRIPT_PATH="$_TRANSCRIPT" \
             CLAUDE_CONTEXT_USED="${CLAUDE_CONTEXT_USED:-}" \
             bash "$_HYGIENE_SCRIPT" 2>/dev/null)
fi

# ─── Persistent Routing Reminder ────────────────────────────────────────
# High-salience tag — ensures squad routing persists across conversation turns,
# not just on turn 1 when /arka skill content is fresh. See spec:
# docs/superpowers/specs/2026-04-14-persistent-routing-reminder-design.md
_ROUTE_REMINDER="
[ARKA:ROUTE]
EVERY response MUST route through a department squad.
NO generic assistant replies. Announce the squad before responding.
When [knowledge:N chunks] is present, cite at least one source.
If [knowledge:N chunks] is absent on a non-trivial ArkaOS topic, query Obsidian first."

# ─── Workflow Classifier (hard enforcement for creation/implementation) ──
# Uses the shared _lib/workflow-classifier.sh. When a creation/implementation
# verb is detected, the session is marked as flow-required so PreToolUse
# can block Write/Edit/MultiEdit until the agent emits [arka:routing] or
# [arka:trivial]. Explicit slash commands and bang shells pass through.
_WORKFLOW_DIRECTIVE=""
if [ -n "$user_input" ] && command -v arka_wf_classify &>/dev/null; then
  if [ "$(arka_wf_classify "$user_input")" = "true" ]; then
    # Mark session as flow-required (consumed by pre-tool-use.sh and stop.sh)
    if command -v arka_wf_mark_required &>/dev/null; then
      arka_wf_mark_required "$SESSION_ID"
    fi
    _WORKFLOW_DIRECTIVE="
[ARKA:WORKFLOW-REQUIRED] CREATION/IMPLEMENTATION detected — the 4-gate evidence
flow applies (constitution rule evidence-flow; source arka/skills/flow/SKILL.md).
G1 CONTEXT ([arka:routing] + grounding) -> G2 PLAN (explicit approval) ->
G3 EXECUTE (real test run + exit 0 on record) -> G4 REVIEW (executable checks).
Emit [arka:gate:N] at each gate start. No writes before G2 approval.
Trivial bypass: [arka:trivial] <reason>, single file, under 10 lines."
  fi
fi

# ─── Cognitive context injection (PR4 v2.26.0 hooks-as-retrieval) ───────
# Read the context cache populated by the previous PostToolUse turn and
# inject any KB hits as an `[arka:context]` advisory. The Python helper
# has internal TTL filtering (10 min) and returns empty when there is no
# fresh cache, so this stays a no-op until the cognitive layer has data
# to share.
_ARKA_CONTEXT_HITS=""
if [ -n "$SESSION_ID" ]; then
  _ARKAOS_REPO=$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null || echo "")
  if [ -n "$_ARKAOS_REPO" ] && [ -d "$_ARKAOS_REPO" ]; then
    _ARKA_CONTEXT_HITS=$(PYTHONPATH="$_ARKAOS_REPO" python3 -m core.cognition.retrieval inject "$SESSION_ID" 2>/dev/null)
  fi
fi

# ─── KB citation nudge (PR18 v2.40.0) ────────────────────────────────────
# Read the cite-check result written by the previous Stop hook. If the
# last assistant turn was on an ArkaOS topic without any citation, surface
# the suggestion to the model in this turn's additionalContext. One-shot:
# the file is deleted after read so the nudge does not repeat across turns.
_KB_CITE_NUDGE=""
if [ -n "$SESSION_ID" ] && [ "$_ARKA_SURFACE_NUDGES" = "true" ]; then
  _CITE_FILE="/tmp/arkaos-cite/${SESSION_ID}.json"
  if [ -f "$_CITE_FILE" ]; then
    if command -v jq &>/dev/null; then
      # NOTE: do not use `// true` here — jq's `//` treats false as needing
      # the default, which would suppress the nudge in the exact case we
      # care about. Read .passed raw and compare to the literal "false".
      _CITE_PASSED=$(jq -r '.passed' "$_CITE_FILE" 2>/dev/null)
      _CITE_SUGGEST=$(jq -r '.suggestion // ""' "$_CITE_FILE" 2>/dev/null)
      if [ "$_CITE_PASSED" = "false" ] && [ -n "$_CITE_SUGGEST" ] && [ "$_CITE_SUGGEST" != "null" ]; then
        _KB_CITE_NUDGE="[arka:suggest] ${_CITE_SUGGEST}"
      fi
    fi
    rm -f "$_CITE_FILE" 2>/dev/null
  fi
fi

# ─── Meta-tag nudge (PR30 v2.49.0) ───────────────────────────────────────
# Mirror of the KB citation nudge but for the [arka:meta] one-liner
# contract. One-shot; deleted after read.
_META_TAG_NUDGE=""
if [ -n "$SESSION_ID" ] && [ "$_ARKA_SURFACE_NUDGES" = "true" ]; then
  _META_FILE="/tmp/arkaos-meta/${SESSION_ID}.json"
  if [ -f "$_META_FILE" ]; then
    if command -v jq &>/dev/null; then
      _META_PASSED=$(jq -r '.passed' "$_META_FILE" 2>/dev/null)
      _META_SUGGEST=$(jq -r '.suggestion // ""' "$_META_FILE" 2>/dev/null)
      if [ "$_META_PASSED" = "false" ] && [ -n "$_META_SUGGEST" ] && [ "$_META_SUGGEST" != "null" ]; then
        _META_TAG_NUDGE="[arka:suggest] ${_META_SUGGEST}"
      fi
    fi
    rm -f "$_META_FILE" 2>/dev/null
  fi
fi

# ─── Closing-marker nudge (PR59 v2.76.0) ─────────────────────────────────
# Mirror of meta-tag nudge but for [arka:gate:4] / [arka:trivial]
# closing markers. One-shot; deleted after read.
_CLOSING_MARKER_NUDGE=""
if [ -n "$SESSION_ID" ] && [ "$_ARKA_SURFACE_NUDGES" = "true" ]; then
  _CLOSING_FILE="/tmp/arkaos-closing/${SESSION_ID}.json"
  if [ -f "$_CLOSING_FILE" ]; then
    if command -v jq &>/dev/null; then
      _CLOSING_PASSED=$(jq -r '.passed' "$_CLOSING_FILE" 2>/dev/null)
      _CLOSING_SUGGEST=$(jq -r '.suggestion // ""' "$_CLOSING_FILE" 2>/dev/null)
      if [ "$_CLOSING_PASSED" = "false" ] && [ -n "$_CLOSING_SUGGEST" ] && [ "$_CLOSING_SUGGEST" != "null" ]; then
        _CLOSING_MARKER_NUDGE="[arka:suggest] ${_CLOSING_SUGGEST}"
      fi
    fi
    rm -f "$_CLOSING_FILE" 2>/dev/null
  fi
fi

# ─── Output ──────────────────────────────────────────────────────────────
_OUT_CONTEXT="${_ARKA_GREETING:-}${_SYNC_NOTICE:-}${_ROUTE_REMINDER}${_WORKFLOW_DIRECTIVE} $python_result"
[ -n "$_HYGIENE" ] && _OUT_CONTEXT="$_OUT_CONTEXT $_HYGIENE"
[ -n "$_KB_CITE_NUDGE" ] && _OUT_CONTEXT="$_OUT_CONTEXT
$_KB_CITE_NUDGE"
[ -n "$_META_TAG_NUDGE" ] && _OUT_CONTEXT="$_OUT_CONTEXT
$_META_TAG_NUDGE"
[ -n "$_CLOSING_MARKER_NUDGE" ] && _OUT_CONTEXT="$_OUT_CONTEXT
$_CLOSING_MARKER_NUDGE"
[ -n "$_ARKA_CONTEXT_HITS" ] && _OUT_CONTEXT="$_OUT_CONTEXT
$_ARKA_CONTEXT_HITS"
# Escape for JSON
_OUT_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<< "$_OUT_CONTEXT" 2>/dev/null)
if [ -n "$_OUT_JSON" ]; then
  echo "{\"additionalContext\": $_OUT_JSON}"
else
  echo "{\"additionalContext\": \"${_ARKA_GREETING:-}${_SYNC_NOTICE:-}$python_result\"}"
fi

# ─── Metrics ─────────────────────────────────────────────────────────────
# Count @-mentions in the prompt for at_mention_frequency telemetry. Mirrors
# the claude_code.at_mention OpenTelemetry event introduced in Claude Code
# 2.1.122, but works on any version because we count from the same input
# the hook already receives.
at_mentions=$(printf '%s' "$user_input" | grep -oE '(^|[[:space:]])@[A-Za-z0-9_./-]+' | wc -l | tr -d ' ')
elapsed=$(_hook_ms)
if [ "$elapsed" -gt 0 ] 2>/dev/null; then
  echo "{\"hook\":\"user-prompt-submit-v2\",\"ms\":$elapsed,\"at_mentions\":${at_mentions:-0}}" >> "$CACHE_DIR/hook-metrics.jsonl" 2>/dev/null
fi
