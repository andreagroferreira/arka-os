#!/usr/bin/env bash
# ============================================================================
# ArkaOS — SessionStart Hook
# Uses systemMessage (same protocol as claude-mem) for guaranteed display.
# ============================================================================

# ─── Profile ───────────────────────────────────────────────────────────
NAME="founder"
COMPANY="WizardingCode"
VERSION="2.x"

# ─── Shared Python resolver (exports ARKA_PY) ──────────────────────────
_ARKA_LIB="$(dirname "${BASH_SOURCE[0]:-$0}")/_lib/arka_python.sh"
if [ -f "$_ARKA_LIB" ]; then . "$_ARKA_LIB"; else ARKA_PY="python3"; fi

if [ -f "$HOME/.arkaos/profile.json" ] && command -v "$ARKA_PY" >/dev/null 2>&1; then
  NAME=$("$ARKA_PY" -c "import json; p=json.load(open('$HOME/.arkaos/profile.json')); print(p.get('name', p.get('role', 'founder')))" 2>/dev/null || echo "founder")
  COMPANY=$("$ARKA_PY" -c "import json; print(json.load(open('$HOME/.arkaos/profile.json')).get('company', 'WizardingCode'))" 2>/dev/null || echo "WizardingCode")
fi

if [ -f "$HOME/.arkaos/.repo-path" ]; then
  REPO=$(cat "$HOME/.arkaos/.repo-path")
  [ -f "$REPO/VERSION" ] && VERSION=$(cat "$REPO/VERSION" | tr -d '[:space:]')
fi
# .repo-path may point at a purged npx cache — the installer's snapshot
# keeps the drift banner alive ("2.x" is the untouched default above).
if [ "$VERSION" = "2.x" ] && [ -f "$HOME/.arkaos/lib/VERSION" ]; then
  VERSION=$(tr -d '[:space:]' < "$HOME/.arkaos/lib/VERSION")
fi

# ─── Static greeting (cache-friendly) ──────────────────────────────────
# Time-of-day branching removed: it invalidated prompt cache 3x/day without
# meaningful signal. Static greeting keeps SessionStart output stable.
GREETING="Olá"

# ─── Version drift ─────────────────────────────────────────────────────
SYNC_STATE="$HOME/.arkaos/sync-state.json"
DRIFT=""

if [ -f "$SYNC_STATE" ]; then
  SYNCED=$("$ARKA_PY" -c "import json; print(json.load(open('$SYNC_STATE'))['version'])" 2>/dev/null || echo "none")
  if [ "$SYNCED" != "$VERSION" ]; then
    DRIFT="\\n[arka:update-available] Core v${VERSION} != synced v${SYNCED}. Run /arka update."
  fi
else
  DRIFT="\\n[arka:update-available] Never synced. Run /arka update."
fi

# ─── Build message ─────────────────────────────────────────────────────
MSG="\\n╔══════════════════════════════════════════════╗\\n"
MSG+="║                                              ║\\n"
MSG+="║              A R K A   O S                   ║\\n"
MSG+="║                                              ║\\n"
MSG+="║   The Operating System for AI Teams          ║\\n"
MSG+="║                  by WizardingCode            ║\\n"
MSG+="║                                              ║\\n"
MSG+="╚══════════════════════════════════════════════╝\\n"
MSG+="\\n"
MSG+="${GREETING}, ${NAME} (${COMPANY})\\n"
# ─── Active Workflow ──────────────────────────────────────────────────
STATE_READER="$REPO/core/workflow/state_reader.sh"
if [ -n "$REPO" ] && [ -f "$STATE_READER" ] && bash "$STATE_READER" active 2>/dev/null; then
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

# --- Forge Plan Display ---
_FORGE_PLANS="$HOME/.arkaos/plans"
_FORGE_ACTIVE="$_FORGE_PLANS/active.yaml"
_FORGE_LINE=""

if [ -f "$_FORGE_ACTIVE" ]; then
  _FORGE_ID=$(cat "$_FORGE_ACTIVE" 2>/dev/null)
  _FORGE_FILE="$_FORGE_PLANS/${_FORGE_ID}.yaml"
  if [ -f "$_FORGE_FILE" ] && command -v "$ARKA_PY" >/dev/null 2>&1; then
    _FORGE_NAME=$(FORGE_FILE="$_FORGE_FILE" "$ARKA_PY" -c "import yaml,os; d=yaml.safe_load(open(os.environ['FORGE_FILE'])); print(d.get('name',''))" 2>/dev/null)
    _FORGE_STATUS=$(FORGE_FILE="$_FORGE_FILE" "$ARKA_PY" -c "import yaml,os; d=yaml.safe_load(open(os.environ['FORGE_FILE'])); print(d.get('status',''))" 2>/dev/null)
    _FORGE_PHASES=$(FORGE_FILE="$_FORGE_FILE" "$ARKA_PY" -c "import yaml,os; d=yaml.safe_load(open(os.environ['FORGE_FILE'])); print(len(d.get('plan_phases',[])))" 2>/dev/null)
    _FORGE_BRANCH=$(FORGE_FILE="$_FORGE_FILE" "$ARKA_PY" -c "import yaml,os; d=yaml.safe_load(open(os.environ['FORGE_FILE'])); print(d.get('governance',{}).get('branch_strategy',''))" 2>/dev/null)

    if [ "$_FORGE_STATUS" = "approved" ]; then
      _FORGE_LINE="  ⚒ Forge plan pending: ${_FORGE_NAME} | Phases: ${_FORGE_PHASES} | /forge resume"
    elif [ "$_FORGE_STATUS" = "executing" ]; then
      _FORGE_LINE="  ⚒ Forge executing: ${_FORGE_NAME} | Phases: ${_FORGE_PHASES} | Branch: ${_FORGE_BRANCH}"
    fi
  fi
fi

# Counts intentionally omitted (prompt-surface P0 2026-07-08): hand-typed
# numbers drift from docs_stats.py truth and change no model behavior.
MSG+="ArkaOS v${VERSION}"
[ -n "$_FORGE_LINE" ] && MSG+="\\n${_FORGE_LINE}"
MSG+="${DRIFT}"

# ─── Evidence Flow Contract (top-of-session, highest priority) ──────────
MSG+="\\n\\n[ARKA:EVIDENCE-FLOW] NON-NEGOTIABLE. Every non-trivial request runs the 4-gate evidence flow (constitution rule evidence-flow; source arka/skills/flow/SKILL.md):"
MSG+="\\n  G1 CONTEXT ([arka:routing] <dept> -> <lead> + KB/graph grounding, cite or declare gap)"
MSG+="\\n  G2 PLAN (short plan -> EXPLICIT user approval; silence != approval)"
MSG+="\\n  G3 EXECUTE (closes only with real test run on record: command + exit 0)"
MSG+="\\n  G4 REVIEW (executable checks: lint/type/coverage/security/spell -> honest summary)"
MSG+="\\nEmit [arka:gate:N] at each gate start. Gates pass on evidence, never on narration."
MSG+="\\nBypass ONLY via [arka:trivial] <reason> for single-file edits under 10 lines."

# ─── Transparency tag contract (PR12 v2.34.0) ───────────────────────────
MSG+="\\n\\n[ARKA:META-TAG] Every substantive response ends with a single line:"
MSG+="\\n  [arka:meta] kb=N research=X persona=Y gap=Z critic=W"
MSG+="\\nFields: kb=N (Obsidian/KB notes consulted), research=X (MCPs invoked: perplexity,exa,context7,firecrawl,xmcp or 'none'), persona=Y (advisor name or 'orchestrator'), gap=Z (KB gap topic or 'none'), critic=W (passed|failed|skipped)."
MSG+="\\nMandatory after: EFFECT tool calls, plan/recommendation outputs, QG verdicts. Optional for pure read-only status replies."
MSG+="\\nAbsence is measured by the Stop hook (warn-only in v2.34.0) before promotion to hard enforcement."

# ─── Model Fabric routing (consumption layer) ───────────────────────────
# Feed the operator's ~/.arkaos/models.yaml back to the orchestrator so
# dashboard/CLI model choices actually govern agent dispatch. Cheap
# (single python read); skipped silently if the config can't be resolved.
if [ -n "$REPO" ]; then
  # ARKA_PY already resolves to the venv python (has pydantic + yaml); the
  # ambient python3 usually lacks them and routing_directive() would return "".
  if command -v "$ARKA_PY" >/dev/null 2>&1 || [ -x "$ARKA_PY" ]; then
    _MF_DIRECTIVE=$(cd "$REPO" && PYTHONPATH="$REPO" "$ARKA_PY" -c "
try:
    from core.runtime.model_routing_context import routing_directive
    print(routing_directive())
except Exception:
    pass
" 2>/dev/null)
    if [ -n "$_MF_DIRECTIVE" ]; then
      MSG+="\\n\\n${_MF_DIRECTIVE}"
    fi
  fi
fi

# ─── Stale-aware reorganizer trigger (PR24 v2.46.0) ─────────────────────
# If today's proposal file is missing, fire the reorganizer in the
# background with a 30s timeout. Best-effort, never blocks session
# start. Multiple sessions per day no-op because the file now exists.
if [ -n "$REPO" ] && command -v "$ARKA_PY" >/dev/null 2>&1; then
  _PROPOSAL_DIR="$HOME/.arkaos/reorganize-proposals"
  _TODAY="$(date -u +%Y-%m-%d).md"
  if [ ! -f "$_PROPOSAL_DIR/$_TODAY" ]; then
    (
      cd "$REPO" && timeout 30s "$ARKA_PY" -m core.cognition.reorganizer_cli >/dev/null 2>&1
    ) &
    disown 2>/dev/null || true
  fi
fi

# ─── Dashboard ensure (v4.1.2) ──────────────────────────────────────────
# Safety net for the login autostart (`npx arkaos autostart enable`): if the
# dashboard is healthy this is two curl health checks (~50ms); if not, it
# starts API+UI. Background + disown so it never touches the 5s budget.
# Toggle off: ~/.arkaos/config.json -> {"dashboard": {"ensure_on_session": false}}
if [ -n "$REPO" ] && [ -f "$REPO/scripts/start-dashboard.sh" ]; then
  _DASH_ENSURE=$("$ARKA_PY" -c "import json; print(json.load(open('$HOME/.arkaos/config.json')).get('dashboard',{}).get('ensure_on_session', True))" 2>/dev/null || echo "True")
  if [ "$_DASH_ENSURE" = "True" ] || [ "$_DASH_ENSURE" = "true" ]; then
    mkdir -p "$HOME/.arkaos/logs"
    (
      # GNU `timeout` is absent on stock macOS — degrade to an unbounded
      # run; the launcher itself is bounded (health wait + start).
      if command -v timeout >/dev/null 2>&1; then
        ARKAOS_NO_BROWSER=1 timeout 90s bash "$REPO/scripts/start-dashboard.sh" ensure >> "$HOME/.arkaos/logs/dashboard-ensure.log" 2>&1
      else
        ARKAOS_NO_BROWSER=1 bash "$REPO/scripts/start-dashboard.sh" ensure >> "$HOME/.arkaos/logs/dashboard-ensure.log" 2>&1
      fi
    ) &
    disown 2>/dev/null || true
  fi
fi

# --- Session Memory Resume Context ---
if command -v "$ARKA_PY" >/dev/null 2>&1 && [ -n "$REPO" ]; then
  _SESSION_CTX=$(cd "$REPO" && "$ARKA_PY" -c "
import sys
sys.path.insert(0, '$REPO')
try:
    from core.memory.rehydrator import build_resume_context
    ctx = build_resume_context()
    if ctx:
        print('\\n[SESSION] ' + ctx.replace('\\n', '\\n[SESSION] '))
except Exception:
    pass
" 2>/dev/null)
  [ -n "$_SESSION_CTX" ] && MSG+="\\n${_SESSION_CTX}"
fi

# --- Session Semantic Memory Recap (F1-A3) ---
# Compact importance+recency recap from ~/.arkaos/session-memory.db.
# Best-effort: any failure or empty store contributes nothing.
if command -v "$ARKA_PY" >/dev/null 2>&1 && [ -n "$REPO" ]; then
  _MEM_RECAP=$(cd "$REPO" && PYTHONPATH="$REPO" "$ARKA_PY" -m core.hooks.session_start "$PWD" 2>/dev/null || true)
  [ -n "$_MEM_RECAP" ] && MSG+="\\n\\n${_MEM_RECAP}"
fi

# ─── Output as systemMessage (same protocol as claude-mem) ─────────────
# OWASP A03: MSG carries profile-derived NAME/COMPANY. Pass it through the
# environment (with \n already expanded) rather than interpolating it into
# the Python source, so a name containing quotes or ''' cannot break the
# script or the JSON envelope.
ARKA_MSG="$(echo -e "$MSG")" "$ARKA_PY" -c "
import json, os
print(json.dumps({'systemMessage': os.environ['ARKA_MSG']}))
"
