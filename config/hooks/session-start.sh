#!/usr/bin/env bash
# ============================================================================
# ArkaOS — SessionStart Hook
# Uses systemMessage (same protocol as claude-mem) for guaranteed display.
# ============================================================================

# ─── Profile ───────────────────────────────────────────────────────────
NAME="founder"
COMPANY="WizardingCode"
VERSION="2.x"

if [ -f "$HOME/.arkaos/profile.json" ] && command -v python3 &>/dev/null; then
  NAME=$(python3 -c "import json; p=json.load(open('$HOME/.arkaos/profile.json')); print(p.get('name', p.get('role', 'founder')))" 2>/dev/null || echo "founder")
  COMPANY=$(python3 -c "import json; print(json.load(open('$HOME/.arkaos/profile.json')).get('company', 'WizardingCode'))" 2>/dev/null || echo "WizardingCode")
fi

if [ -f "$HOME/.arkaos/.repo-path" ]; then
  REPO=$(cat "$HOME/.arkaos/.repo-path")
  [ -f "$REPO/VERSION" ] && VERSION=$(cat "$REPO/VERSION" | tr -d '[:space:]')
fi

# ─── Time greeting ─────────────────────────────────────────────────────
HOUR=$(date +%H)
if [ "$HOUR" -ge 5 ] && [ "$HOUR" -lt 12 ]; then GREETING="Bom dia"
elif [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 19 ]; then GREETING="Boa tarde"
else GREETING="Boa noite"; fi

# ─── Version drift ─────────────────────────────────────────────────────
SYNC_STATE="$HOME/.arkaos/sync-state.json"
DRIFT=""

if [ -f "$SYNC_STATE" ]; then
  SYNCED=$(python3 -c "import json; print(json.load(open('$SYNC_STATE'))['version'])" 2>/dev/null || echo "none")
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
  if [ -f "$_FORGE_FILE" ] && command -v python3 &>/dev/null; then
    _FORGE_NAME=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(d.get('name',''))" 2>/dev/null)
    _FORGE_STATUS=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(d.get('status',''))" 2>/dev/null)
    _FORGE_PHASES=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(len(d.get('plan_phases',[])))" 2>/dev/null)
    _FORGE_BRANCH=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(d.get('governance',{}).get('branch_strategy',''))" 2>/dev/null)

    if [ "$_FORGE_STATUS" = "approved" ]; then
      _FORGE_LINE="  ⚒ Forge plan pending: ${_FORGE_NAME} | Phases: ${_FORGE_PHASES} | /forge resume"
    elif [ "$_FORGE_STATUS" = "executing" ]; then
      _FORGE_LINE="  ⚒ Forge executing: ${_FORGE_NAME} | Phases: ${_FORGE_PHASES} | Branch: ${_FORGE_BRANCH}"
    fi
  fi
fi

MSG+="ArkaOS v${VERSION} | 65 agents | 17 departments | 244+ skills"
[ -n "$_FORGE_LINE" ] && MSG+="\\n${_FORGE_LINE}"
MSG+="${DRIFT}"

# ─── Output as systemMessage (same protocol as claude-mem) ─────────────
python3 -c "
import json
msg = '''$(echo -e "$MSG")'''
print(json.dumps({'systemMessage': msg}))
"
