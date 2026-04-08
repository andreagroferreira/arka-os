#!/usr/bin/env bash
# ============================================================================
# ArkaOS — CwdChanged Hook
# Fires when the working directory changes. Detects ecosystem and injects
# project context so Claude knows which squad and stack to use.
# ============================================================================

input=$(cat)
NEW_CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)

if [ -z "$NEW_CWD" ] || [ ! -d "$NEW_CWD" ]; then
  exit 0
fi

# ─── Detect ecosystem from ecosystems.json ─────────────────────────────
ECOSYSTEMS_FILE="$HOME/.claude/skills/arka/knowledge/ecosystems.json"
ECOSYSTEM=""
ECOSYSTEM_NAME=""

if [ -f "$ECOSYSTEMS_FILE" ] && command -v python3 &>/dev/null; then
  eval "$(python3 -c "
import json, os, sys

cwd = '$NEW_CWD'
eco_file = os.path.expanduser('$ECOSYSTEMS_FILE')

try:
    data = json.load(open(eco_file))
    ecosystems = data.get('ecosystems', {})

    for eco_id, eco in ecosystems.items():
        projects = eco.get('projects', [])
        for proj in projects:
            # Check if cwd contains the project name
            if proj in cwd:
                print(f'ECOSYSTEM=\"{eco_id}\"')
                print(f'ECOSYSTEM_NAME=\"{eco.get(\"name\", eco_id)}\"')
                sys.exit(0)

    # No match by project name, try by path patterns
    if '/herd/' in cwd or '/Herd/' in cwd:
        dir_name = os.path.basename(cwd.rstrip('/'))
        for eco_id, eco in ecosystems.items():
            for proj in eco.get('projects', []):
                if proj == dir_name:
                    print(f'ECOSYSTEM=\"{eco_id}\"')
                    print(f'ECOSYSTEM_NAME=\"{eco.get(\"name\", eco_id)}\"')
                    sys.exit(0)
except Exception:
    pass

print('ECOSYSTEM=\"\"')
print('ECOSYSTEM_NAME=\"\"')
" 2>/dev/null)"
fi

# ─── Detect stack ──────────────────────────────────────────────────────
STACK="unknown"
if [ -f "$NEW_CWD/composer.json" ]; then
  STACK="laravel"
elif [ -f "$NEW_CWD/package.json" ]; then
  if grep -q '"nuxt"' "$NEW_CWD/package.json" 2>/dev/null; then
    STACK="nuxt"
  elif grep -q '"next"' "$NEW_CWD/package.json" 2>/dev/null; then
    STACK="nextjs"
  elif grep -q '"react"' "$NEW_CWD/package.json" 2>/dev/null; then
    STACK="react"
  elif grep -q '"vue"' "$NEW_CWD/package.json" 2>/dev/null; then
    STACK="vue"
  else
    STACK="node"
  fi
elif [ -f "$NEW_CWD/pyproject.toml" ]; then
  STACK="python"
fi

# ─── Check for project descriptor ─────────────────────────────────────
DIR_NAME=$(basename "$NEW_CWD")
DESCRIPTOR=""
DESCRIPTOR_FILE="$HOME/.claude/skills/arka/projects/${DIR_NAME}.md"
DESCRIPTOR_DIR="$HOME/.claude/skills/arka/projects/${DIR_NAME}/PROJECT.md"

if [ -f "$DESCRIPTOR_FILE" ]; then
  DESCRIPTOR="$DESCRIPTOR_FILE"
elif [ -f "$DESCRIPTOR_DIR" ]; then
  DESCRIPTOR="$DESCRIPTOR_DIR"
fi

# ─── Build context output ─────────────────────────────────────────────
CONTEXT=""

if [ -n "$ECOSYSTEM" ]; then
  CONTEXT="[arka:project-context] Ecosystem: ${ECOSYSTEM_NAME} (${ECOSYSTEM}) | Stack: ${STACK} | Use /arka-${ECOSYSTEM} for dedicated squad routing."
elif [ "$STACK" != "unknown" ]; then
  CONTEXT="[arka:project-context] Stack: ${STACK} | No ecosystem assigned. Use /arka onboard to register this project."
fi

if [ -n "$DESCRIPTOR" ]; then
  CONTEXT="${CONTEXT} Descriptor: ${DESCRIPTOR}"
fi

if [ -n "$CONTEXT" ]; then
  echo "{\"additionalContext\": \"${CONTEXT}\"}"
fi
