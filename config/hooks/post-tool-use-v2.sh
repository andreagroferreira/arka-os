#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — PostToolUse Hook (Error Pattern Tracking)
# Tracks recurring errors from tool output for gotchas system
# Timeout: 5s
# ============================================================================

input=$(cat)

ARKAOS_HOME="${HOME}/.arkaos"
GOTCHAS_FILE="$ARKAOS_HOME/gotchas.json"

mkdir -p "$ARKAOS_HOME" 2>/dev/null

# ─── Check for errors ────────────────────────────────────────────────────
exit_code=""
tool_output=""

if command -v jq &>/dev/null; then
  exit_code=$(echo "$input" | jq -r '.exitCode // ""' 2>/dev/null)
  tool_output=$(echo "$input" | jq -r '.output // ""' 2>/dev/null | head -c 2000)
fi

# Only track if there's an error
if [ "$exit_code" = "0" ] || [ -z "$exit_code" ]; then
  # Check for error patterns in output
  if ! echo "$tool_output" | grep -qiE '(error|exception|fatal|failed|denied|not found)'; then
    exit 0
  fi
fi

# ─── Extract and normalize error pattern ─────────────────────────────────
error_line=$(echo "$tool_output" | grep -iE '(error|exception|fatal|failed)' | head -1 | head -c 200)

if [ -z "$error_line" ]; then
  exit 0
fi

# Normalize: remove timestamps, hashes, line numbers
pattern=$(echo "$error_line" | sed -E \
  -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9:.]+//g' \
  -e 's/[a-f0-9]{7,40}//g' \
  -e 's/line [0-9]+/line N/g' \
  -e 's/[0-9]+ms/Nms/g' \
  -e 's/\s+/ /g' \
  | head -c 150)

# ─── Categorize ──────────────────────────────────────────────────────────
category="general"
if echo "$error_line" | grep -qiE '(laravel|artisan|eloquent|migration|php)'; then
  category="laravel"
elif echo "$error_line" | grep -qiE '(vue|nuxt|react|next|npm|node|webpack|vite)'; then
  category="frontend"
elif echo "$error_line" | grep -qiE '(git|merge|rebase|checkout|branch)'; then
  category="git"
elif echo "$error_line" | grep -qiE '(postgres|mysql|sqlite|database|query|migration)'; then
  category="database"
elif echo "$error_line" | grep -qiE '(permission|denied|access|chmod|chown)'; then
  category="permissions"
elif echo "$error_line" | grep -qiE '(test|assert|expect|jest|phpunit|pytest)'; then
  category="testing"
fi

# ─── Store gotcha (concurrent-safe with flock) ───────────────────────────
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cwd=$(pwd)
project=$(basename "$cwd")

(
  flock -w 2 200 || exit 0

  # Initialize if empty
  if [ ! -f "$GOTCHAS_FILE" ] || [ ! -s "$GOTCHAS_FILE" ]; then
    echo "[]" > "$GOTCHAS_FILE"
  fi

  if command -v python3 &>/dev/null; then
    python3 -c "
import json, sys
try:
    with open('$GOTCHAS_FILE') as f:
        gotchas = json.load(f)
except:
    gotchas = []

pattern = '''$pattern'''
found = False
for g in gotchas:
    if g.get('pattern') == pattern:
        g['count'] = g.get('count', 1) + 1
        g['last_seen'] = '$timestamp'
        if '$project' not in g.get('projects', []):
            g.setdefault('projects', []).append('$project')
        found = True
        break

if not found:
    gotchas.append({
        'pattern': pattern,
        'category': '$category',
        'count': 1,
        'first_seen': '$timestamp',
        'last_seen': '$timestamp',
        'projects': ['$project'],
    })

# Keep top 100
gotchas.sort(key=lambda g: g.get('count', 0), reverse=True)
gotchas = gotchas[:100]

with open('$GOTCHAS_FILE', 'w') as f:
    json.dump(gotchas, f, indent=2)
" 2>/dev/null
  fi

) 200>"$GOTCHAS_FILE.lock"
