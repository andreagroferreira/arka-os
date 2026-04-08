#!/usr/bin/env bash
# ============================================================================
# ArkaOS — SessionStart Hook
# Fires when Claude Code opens. Shows branded greeting + version drift check.
# Output goes to stdout → persisted context Claude sees immediately.
# ============================================================================

# ─── Version Drift Detection ───────────────────────────────────────────
SYNC_STATE="$HOME/.arkaos/sync-state.json"
REPO_PATH_FILE="$HOME/.arkaos/.repo-path"
SYNC_NOTICE=""

if [ -f "$REPO_PATH_FILE" ]; then
  _REPO_PATH=$(cat "$REPO_PATH_FILE")
  _CURRENT_VERSION=""

  if [ -f "$_REPO_PATH/VERSION" ]; then
    _CURRENT_VERSION=$(cat "$_REPO_PATH/VERSION" | tr -d '[:space:]')
  elif [ -f "$_REPO_PATH/package.json" ]; then
    _CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$_REPO_PATH/package.json'))['version'])" 2>/dev/null)
  fi

  if [ -n "$_CURRENT_VERSION" ]; then
    if [ -f "$SYNC_STATE" ]; then
      _SYNCED_VERSION=$(python3 -c "import json; print(json.load(open('$SYNC_STATE'))['version'])" 2>/dev/null || echo "none")
    else
      _SYNCED_VERSION="none"
    fi

    if [ "$_CURRENT_VERSION" != "$_SYNCED_VERSION" ]; then
      SYNC_NOTICE="
[arka:update-available] ArkaOS core v${_CURRENT_VERSION} (last synced: ${_SYNCED_VERSION}). Run /arka update to sync all projects."
    fi
  fi
fi

# ─── Profile Data ──────────────────────────────────────────────────────
GREETING_NAME="founder"
GREETING_COMPANY="WizardingCode"
GREETING_LANG="en"
GREETING_VERSION="2.x"

if [ -f "$HOME/.arkaos/profile.json" ] && command -v python3 &>/dev/null; then
  eval "$(python3 -c "
import json, os
p = json.load(open(os.path.expanduser('~/.arkaos/profile.json')))
print(f'GREETING_NAME=\"{p.get(\"name\", p.get(\"role\", \"founder\"))}\"')
print(f'GREETING_COMPANY=\"{p.get(\"company\", \"WizardingCode\")}\"')
print(f'GREETING_LANG=\"{p.get(\"language\", \"en\")}\"')
" 2>/dev/null)"
fi

if [ -n "${_CURRENT_VERSION:-}" ]; then
  GREETING_VERSION="$_CURRENT_VERSION"
fi

# ─── Time-based greeting ──────────────────────────────────────────────
HOUR=$(date +%H)
if [ "$HOUR" -ge 5 ] && [ "$HOUR" -lt 12 ]; then
  TIME_GREETING_PT="Bom dia"
  TIME_GREETING_EN="Good morning"
elif [ "$HOUR" -ge 12 ] && [ "$HOUR" -lt 19 ]; then
  TIME_GREETING_PT="Boa tarde"
  TIME_GREETING_EN="Good afternoon"
else
  TIME_GREETING_PT="Boa noite"
  TIME_GREETING_EN="Good evening"
fi

if [ "$GREETING_LANG" = "pt" ]; then
  TIME_GREETING="$TIME_GREETING_PT"
else
  TIME_GREETING="$TIME_GREETING_EN"
fi

# ─── Output ───────────────────────────────────────────────────────────
cat << EOF
[arka:session-start]

     _    ____  _  __    _    ___  ____
    / \  |  _ \| |/ /   / \  / _ \/ ___|
   / _ \ | |_) | ' /   / _ \| | | \___ \\
  / ___ \|  _ <| . \  / ___ \ |_| |___) |
 /_/   \_\_| \_\_|\_\/_/   \_\___/|____/

  ${TIME_GREETING}, ${GREETING_NAME} (${GREETING_COMPANY})
  ArkaOS v${GREETING_VERSION} | 65 agents | 17 departments | 244+ skills
  Type /arka help or describe what you need.
${SYNC_NOTICE}
EOF
