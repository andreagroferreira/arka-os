#!/usr/bin/env bash
# ============================================================================
# ArkaOS — SessionStart Hook
# Fires when Claude Code opens. Version drift check + brief system ID.
# Greeting with logo is handled by UserPromptSubmit (first prompt per session).
# ============================================================================

# ─── Version Drift Detection ───────────────────────────────────────────
SYNC_STATE="$HOME/.arkaos/sync-state.json"
REPO_PATH_FILE="$HOME/.arkaos/.repo-path"
OUTPUT=""

if [ -f "$REPO_PATH_FILE" ]; then
  _REPO_PATH=$(cat "$REPO_PATH_FILE")
  _CURRENT_VERSION=""

  if [ -f "$_REPO_PATH/VERSION" ]; then
    _CURRENT_VERSION=$(cat "$_REPO_PATH/VERSION" | tr -d '[:space:]')
  fi

  if [ -n "$_CURRENT_VERSION" ]; then
    if [ -f "$SYNC_STATE" ]; then
      _SYNCED_VERSION=$(python3 -c "import json; print(json.load(open('$SYNC_STATE'))['version'])" 2>/dev/null || echo "none")
    else
      _SYNCED_VERSION="none"
    fi

    if [ "$_CURRENT_VERSION" != "$_SYNCED_VERSION" ]; then
      OUTPUT="[arka:update-available] ArkaOS core v${_CURRENT_VERSION} installed but last synced version is ${_SYNCED_VERSION}. Run /arka update to sync all projects."
    else
      OUTPUT="[arka:ready] ArkaOS v${_CURRENT_VERSION} synced and ready."
    fi
  fi
fi

if [ -n "$OUTPUT" ]; then
  echo "$OUTPUT"
fi
