#!/usr/bin/env bash
# ============================================================================
# ArkaOS — CwdChanged Hook
# Fires when the working directory changes. Detects ecosystem and injects
# project context so Claude knows which squad and stack to use.
# ============================================================================

input=$(cat)
NEW_CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)

# ─── Shared Python resolver (exports ARKA_PY) ──────────────────────────
_ARKA_LIB="$(dirname "${BASH_SOURCE[0]:-$0}")/_lib/arka_python.sh"
if [ -f "$_ARKA_LIB" ]; then . "$_ARKA_LIB"; else ARKA_PY="python3"; fi

if [ -z "$NEW_CWD" ] || [ ! -d "$NEW_CWD" ]; then
  exit 0
fi

# ─── Detect ecosystem from ecosystems.json ─────────────────────────────
# Canonical path is ~/.arkaos/ecosystems.json (ADR 2026-04-17). During the
# deprecation window we fall back to the legacy skill-dir path. The legacy
# fallback is removed in v2.21.0.
ECOSYSTEMS_FILE="$HOME/.arkaos/ecosystems.json"
if [ ! -f "$ECOSYSTEMS_FILE" ] && [ -f "$HOME/.claude/skills/arka/knowledge/ecosystems.json" ]; then
  ECOSYSTEMS_FILE="$HOME/.claude/skills/arka/knowledge/ecosystems.json"
fi
ECOSYSTEM=""
ECOSYSTEM_NAME=""

if [ -f "$ECOSYSTEMS_FILE" ] && command -v "$ARKA_PY" >/dev/null 2>&1; then
  # OWASP A03: NEW_CWD is untrusted harness input. It is passed through the
  # environment (never interpolated into the Python source), and the result
  # is emitted as JSON read by jq — no `eval`, so a crafted cwd can neither
  # break the source string nor inject a shell command.
  _ECO_JSON=$(ARKA_CWD="$NEW_CWD" ARKA_ECO_FILE="$ECOSYSTEMS_FILE" "$ARKA_PY" -c '
import json, os, sys

cwd = os.environ["ARKA_CWD"]
eco_file = os.path.expanduser(os.environ["ARKA_ECO_FILE"])


def emit(eco_id, name):
    print(json.dumps({"ecosystem": eco_id, "name": name}))
    sys.exit(0)


try:
    data = json.load(open(eco_file))
    ecosystems = data.get("ecosystems", {})

    for eco_id, eco in ecosystems.items():
        for proj in eco.get("projects", []):
            if proj in cwd:
                emit(eco_id, eco.get("name", eco_id))

    if "/herd/" in cwd or "/Herd/" in cwd:
        dir_name = os.path.basename(cwd.rstrip("/"))
        for eco_id, eco in ecosystems.items():
            if dir_name in eco.get("projects", []):
                emit(eco_id, eco.get("name", eco_id))
except Exception:
    pass

print(json.dumps({"ecosystem": "", "name": ""}))
' 2>/dev/null)
  ECOSYSTEM=$(echo "$_ECO_JSON" | jq -r '.ecosystem // ""' 2>/dev/null)
  ECOSYSTEM_NAME=$(echo "$_ECO_JSON" | jq -r '.name // ""' 2>/dev/null)
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
# New canonical path: ~/.arkaos/projects/. Legacy fallback remains until v2.21.0.
DIR_NAME=$(basename "$NEW_CWD")
DESCRIPTOR=""
for CANDIDATE in \
  "$HOME/.arkaos/projects/${DIR_NAME}.md" \
  "$HOME/.arkaos/projects/${DIR_NAME}/PROJECT.md" \
  "$HOME/.claude/skills/arka/projects/${DIR_NAME}.md" \
  "$HOME/.claude/skills/arka/projects/${DIR_NAME}/PROJECT.md"; do
  if [ -f "$CANDIDATE" ]; then
    DESCRIPTOR="$CANDIDATE"
    break
  fi
done

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
  # Build the JSON with jq so any quote/backslash in the ecosystem name or
  # descriptor path is escaped, never breaking the envelope (OWASP A03).
  jq -nc --arg ctx "$CONTEXT" '{additionalContext: $ctx}'
fi
