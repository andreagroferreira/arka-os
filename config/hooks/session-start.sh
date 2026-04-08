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
MSG="╔══════════════════════════════════════════════╗\\n"
MSG+="║                                              ║\\n"
MSG+="║              A R K A   O S                   ║\\n"
MSG+="║                                              ║\\n"
MSG+="║   The Operating System for AI Teams          ║\\n"
MSG+="║                  by WizardingCode            ║\\n"
MSG+="║                                              ║\\n"
MSG+="╚══════════════════════════════════════════════╝\\n"
MSG+="\\n"
MSG+="${GREETING}, ${NAME} (${COMPANY})\\n"
MSG+="ArkaOS v${VERSION} | 65 agents | 17 departments | 244+ skills"
MSG+="${DRIFT}"

# ─── Output as systemMessage (same protocol as claude-mem) ─────────────
python3 -c "
import json
msg = '''$(echo -e "$MSG")'''
print(json.dumps({'systemMessage': msg}))
"
