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
    bridge_output=$(echo "{\"user_input\":$(echo "$user_input" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo '""')}" \
      | ARKAOS_ROOT="$ARKAOS_ROOT" python3 "$BRIDGE_SCRIPT" --root "$ARKAOS_ROOT" 2>/dev/null)
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
# Classifies the user prompt. If it looks like a creation/implementation/
# modification request that is NOT already routed with an explicit /prefix,
# emits a directive that the agent MUST acknowledge with [arka:routing]
# BEFORE using any write tool. Trivial quick questions pass through
# untouched. Explicit slash commands pass through untouched.
_WORKFLOW_DIRECTIVE=""
if [ -n "$user_input" ]; then
  # Skip: explicit slash command (already routed)
  _FIRST_CHAR=$(echo "$user_input" | head -c 1)
  if [ "$_FIRST_CHAR" != "/" ] && [ "$_FIRST_CHAR" != "!" ]; then
    # Match creation/implementation verbs in EN and PT (case-insensitive).
    _VERB_PATTERN='(criar?|crie[ms]?|cria[mr]?|adicionar?|adiciona[mr]?|implementar?|implementa[mr]?|desenvolver?|desenvolve[mr]?|construir?|constru[ií]a?[mr]?|fazer?|faz[ae][mr]?|refactor(izar?)?|corrigir?|corrige[mr]?|consertar?|conserta[mr]?|create[sd]?|creating|build(s|ing)?|add(s|ed|ing)?|implement(s|ed|ing)?|develop(s|ed|ing)?|fix(es|ed|ing)?|refactor(s|ed|ing)?|make[sd]?|making)'
    _NOUN_PATTERN='(feature|funcionalidade|skill|squad|agent[e]?|workflow|endpoint|api|component[e]?|module|m[oó]dulo|page|p[aá]gina|hook|pipeline|integration|integra[cç][aã]o|dashboard|report|report[eó]|script|test[es]?)'
    if echo "$user_input" | grep -qiE "\b${_VERB_PATTERN}\b"; then
      _WORKFLOW_DIRECTIVE="
[ARKA:WORKFLOW-REQUIRED] Your user request matched a CREATION/IMPLEMENTATION pattern.
The ArkaOS mandatory 13-phase flow applies. It is NON-NEGOTIABLE (constitution rule
mandatory-flow). You MUST walk every phase, in order, emitting a [arka:phase:N] tag
before each:
  1. Input — restate the request verbatim.
  2. Get context — profile, repo, git, cwd tag, session digests.
  3. Decide route — emit [arka:routing] <dept> -> <lead>.
  4. Call hierarchy — escalate to Tier 0 if strategic/cross-dept/security/financial.
  5. Research — query Obsidian + vector DB, cite sources or declare the gap.
  6. Call team — dispatch specialists via Agent tool.
  7. Plan — run six parallel reviewers: positive, devil's advocate, Q&A, KB research,
     best-solution validator, pessimistic. Synthesise into a spec.
  8. Present plan — save to Obsidian + vector DB + ~/.arkaos/plans/, print inline.
  9. Wait approval — EXPLICIT user go. Silence is NOT approval.
 10. TODO list — atomic, ordered, independently verifiable.
 11. Per-todo loop — team call -> complete -> QA (all tests, E2E, Playwright) ->
     Security review -> Quality Gate (Marta + Eduardo + Francisca, Opus) -> Document.
     Each step loops back on fail. No compound gates.
 12. Loop until TODO is exhausted.
 13. Detailed summary — what was done, where, how to verify, what is still open.

No Write, Edit, Bash-with-side-effects, or Agent dispatch before Phase 7 completes
for the affected item. No advancing a todo until QA AND Security AND Quality Gate
all pass for it. Phase 5 and Phase 8 require Obsidian/KB writes, not just reads.

Trivial override: single-file edit under 10 lines with imperative verb
(rename X, fix typo in Y). Emit [arka:trivial] <reason> as first line and proceed.
Anything else runs the full 13 phases. Source: arka/skills/flow/SKILL.md.

This is enforced by the hook and the session-start systemMessage, not by convention.
Skipping violates: mandatory-flow, squad-routing, spec-driven, mandatory-qa,
sequential-validation, full-visibility, arka-supremacy."
    fi
  fi
fi

# ─── Output ──────────────────────────────────────────────────────────────
_OUT_CONTEXT="${_ARKA_GREETING:-}${_SYNC_NOTICE:-}${_ROUTE_REMINDER}${_WORKFLOW_DIRECTIVE} $python_result"
[ -n "$_HYGIENE" ] && _OUT_CONTEXT="$_OUT_CONTEXT $_HYGIENE"
# Escape for JSON
_OUT_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<< "$_OUT_CONTEXT" 2>/dev/null)
if [ -n "$_OUT_JSON" ]; then
  echo "{\"additionalContext\": $_OUT_JSON}"
else
  echo "{\"additionalContext\": \"${_ARKA_GREETING:-}${_SYNC_NOTICE:-}$python_result\"}"
fi

# ─── Metrics ─────────────────────────────────────────────────────────────
elapsed=$(_hook_ms)
if [ "$elapsed" -gt 0 ] 2>/dev/null; then
  echo "{\"hook\":\"user-prompt-submit-v2\",\"ms\":$elapsed}" >> "$CACHE_DIR/hook-metrics.jsonl" 2>/dev/null
fi
