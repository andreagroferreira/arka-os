#!/usr/bin/env bash
# ============================================================================
# ARKA OS — PostToolUse Hook (Gotchas Memory)
# Detects errors from tool output and tracks recurring patterns
# Timeout: 5s | Output: JSON to stdout
# ============================================================================

input=$(cat)

# ─── Performance Timing ──────────────────────────────────────────────────
_HOOK_START=$(date +%s 2>/dev/null)
_HOOK_START_NS=$(date +%s%N 2>/dev/null || echo "0")
_hook_ms() {
  local end_ns=$(date +%s%N 2>/dev/null || echo "0")
  if [ "$_HOOK_START_NS" != "0" ] && [ "$end_ns" != "0" ] && [ ${#end_ns} -gt 10 ]; then
    echo $(( (end_ns - _HOOK_START_NS) / 1000000 ))
  else
    echo $(( ($(date +%s) - _HOOK_START) * 1000 ))
  fi
}

# Extract fields
TOOL_NAME=$(echo "$input" | jq -r '.tool_name // ""' 2>/dev/null)
TOOL_OUTPUT=$(echo "$input" | jq -r '.tool_output // ""' 2>/dev/null)
EXIT_CODE=$(echo "$input" | jq -r '.exit_code // "0"' 2>/dev/null)
CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)

# Only process if there was an error
if [ "$EXIT_CODE" = "0" ] || [ -z "$EXIT_CODE" ]; then
  # Also check for error patterns in output even with exit code 0
  if ! echo "$TOOL_OUTPUT" | grep -qiE '(error:|fatal:|exception:|failed|ENOENT|EACCES|EPERM|panic:)'; then
    echo '{}'
    exit 0
  fi
fi

# ─── Extract Error Pattern ────────────────────────────────────────────────
# Get first meaningful error line (skip blank lines, timestamps)
ERROR_LINE=$(echo "$TOOL_OUTPUT" | grep -iE '(error|fatal|exception|failed|ENOENT|EACCES|EPERM|panic|cannot|not found|permission denied)' | head -1)

if [ -z "$ERROR_LINE" ]; then
  # Fallback: first non-empty line of output for non-zero exit
  ERROR_LINE=$(echo "$TOOL_OUTPUT" | head -5 | tail -1)
fi

[ -z "$ERROR_LINE" ] && { echo '{}'; exit 0; }

# Normalize: remove timestamps, hashes, paths with unique segments, line numbers
PATTERN=$(echo "$ERROR_LINE" | \
  sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}[^ ]*/TIMESTAMP/g' | \
  sed -E 's/[0-9a-f]{7,40}/HASH/g' | \
  sed -E 's/line [0-9]+/line N/g' | \
  sed -E 's/:[0-9]+:/:N:/g' | \
  head -c 200)

[ -z "$PATTERN" ] && { echo '{}'; exit 0; }

# ─── Categorize ──────────────────────────────────────────────────────────
CATEGORY="general"
if echo "$ERROR_LINE" | grep -qiE '(artisan|eloquent|laravel|blade|migration|composer|php )'; then
  CATEGORY="laravel"
elif echo "$ERROR_LINE" | grep -qiE '(npm|node|vue|react|nuxt|next|vite|webpack|typescript|tsx|jsx)'; then
  CATEGORY="frontend"
elif echo "$ERROR_LINE" | grep -qiE '(git |merge|rebase|checkout|branch|commit|push|pull)'; then
  CATEGORY="git"
elif echo "$ERROR_LINE" | grep -qiE '(sql|postgres|mysql|database|migration|table|column|constraint)'; then
  CATEGORY="database"
elif echo "$ERROR_LINE" | grep -qiE '(permission|denied|EACCES|EPERM|chmod|chown|sudo)'; then
  CATEGORY="permissions"
elif echo "$ERROR_LINE" | grep -qiE '(test|assert|expect|jest|phpunit|bats|coverage)'; then
  CATEGORY="testing"
fi

# ─── Match Fix Suggestion ────────────────────────────────────────────────
SUGGESTION=""
FIXES_FILE="${ARKA_OS:-$HOME/.claude/skills/arka}/config/gotchas-fixes.json"
# Also check repo path
if [ ! -f "$FIXES_FILE" ]; then
  REPO_PATH=$(cat "${ARKA_OS:-$HOME/.claude/skills/arka}/.repo-path" 2>/dev/null || echo "")
  [ -n "$REPO_PATH" ] && FIXES_FILE="$REPO_PATH/config/gotchas-fixes.json"
fi
if [ -f "$FIXES_FILE" ] && command -v jq &>/dev/null; then
  SUGGESTION=$(jq -r --arg err "$ERROR_LINE" '
    .fixes[] | select(.pattern_match as $p | $err | test($p; "i")) | .suggestion
  ' "$FIXES_FILE" 2>/dev/null | head -1)
fi

# ─── Detect Active Project ───────────────────────────────────────────────
PROJECT=""
if [ -n "$CWD" ]; then
  # Try to extract project name from CWD
  REPO_PATH=$(cat "${ARKA_OS:-$HOME/.claude/skills/arka}/.repo-path" 2>/dev/null || echo "")
  if [ -n "$REPO_PATH" ] && [ -d "$REPO_PATH/projects" ]; then
    for proj_dir in "$REPO_PATH/projects"/*/; do
      [ -f "$proj_dir/.project-path" ] || continue
      PROJ_PATH=$(cat "$proj_dir/.project-path" 2>/dev/null)
      if [ -n "$PROJ_PATH" ] && [[ "$CWD" == "$PROJ_PATH"* ]]; then
        PROJECT=$(basename "$proj_dir")
        break
      fi
    done
  fi
  # Fallback: use directory name
  [ -z "$PROJECT" ] && PROJECT=$(basename "$CWD")
fi

# ─── Store in gotchas.json ────────────────────────────────────────────────
GOTCHAS_FILE="$HOME/.arkaos/gotchas.json"
mkdir -p "$HOME/.arkaos"

# Use flock for concurrent safety (fallback if flock not available on macOS)
LOCK_FILE="$HOME/.arkaos/gotchas.lock"
if command -v flock &>/dev/null; then
  LOCK_CMD="flock -w 3 200"
else
  LOCK_CMD="true"
fi
(
  eval "$LOCK_CMD" || { echo '{}'; exit 0; }

  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # Initialize if missing or invalid
  if [ ! -f "$GOTCHAS_FILE" ] || ! jq empty "$GOTCHAS_FILE" 2>/dev/null; then
    echo '[]' > "$GOTCHAS_FILE"
  fi

  # Check if pattern already exists
  EXISTING_IDX=$(jq -r --arg pat "$PATTERN" \
    'to_entries[] | select(.value.pattern == $pat) | .key' \
    "$GOTCHAS_FILE" 2>/dev/null | head -1)

  if [ -n "$EXISTING_IDX" ] && [ "$EXISTING_IDX" -ge 0 ] 2>/dev/null; then
    # Increment count, update last_seen, add project if new, add suggestion if missing
    jq --argjson idx "$EXISTING_IDX" \
       --arg now "$NOW" \
       --arg proj "$PROJECT" \
       --arg sug "$SUGGESTION" \
       '.[$idx].count += 1 |
        .[$idx].last_seen = $now |
        (if $proj != "" and ($proj | IN(.[$idx].projects[]?) | not) then .[$idx].projects += [$proj] else . end) |
        (if $sug != "" and ((.[$idx].suggestion // "") == "") then .[$idx].suggestion = $sug else . end)' \
       "$GOTCHAS_FILE" > "$GOTCHAS_FILE.tmp" 2>/dev/null && mv "$GOTCHAS_FILE.tmp" "$GOTCHAS_FILE"
  else
    # Add new entry
    jq --arg pat "$PATTERN" \
       --arg full "$ERROR_LINE" \
       --arg cat "$CATEGORY" \
       --arg tool "$TOOL_NAME" \
       --arg now "$NOW" \
       --arg proj "$PROJECT" \
       --arg sug "$SUGGESTION" \
       '. += [{
         "pattern": $pat,
         "full_pattern": ($full | .[0:500]),
         "category": $cat,
         "tool": $tool,
         "count": 1,
         "first_seen": $now,
         "last_seen": $now,
         "projects": (if $proj != "" then [$proj] else [] end),
         "suggestion": (if $sug != "" then $sug else null end)
       }]' \
       "$GOTCHAS_FILE" > "$GOTCHAS_FILE.tmp" 2>/dev/null && mv "$GOTCHAS_FILE.tmp" "$GOTCHAS_FILE"
  fi

  # Keep top 100 sorted by count
  jq 'sort_by(-.count) | .[0:100]' "$GOTCHAS_FILE" > "$GOTCHAS_FILE.tmp" 2>/dev/null && \
    mv "$GOTCHAS_FILE.tmp" "$GOTCHAS_FILE"

) 200>"$LOCK_FILE"

# ─── Log Metrics ─────────────────────────────────────────────────────────
_DURATION_MS=$(_hook_ms)
METRICS_FILE="$HOME/.arkaos/hook-metrics.json"
METRICS_LOCK="$HOME/.arkaos/hook-metrics.lock"
mkdir -p "$HOME/.arkaos"
(
  if command -v flock &>/dev/null; then flock -w 2 200; else true; fi
  [ ! -f "$METRICS_FILE" ] && echo '[]' > "$METRICS_FILE"
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq --argjson dur "$_DURATION_MS" --arg ts "$NOW" --arg hook "post-tool-use" \
    '. += [{"hook": $hook, "duration_ms": $dur, "timestamp": $ts}] | .[-500:]' \
    "$METRICS_FILE" > "$METRICS_FILE.tmp" 2>/dev/null && mv "$METRICS_FILE.tmp" "$METRICS_FILE"
) 200>"$METRICS_LOCK" 2>/dev/null

# Silent output — no context injection needed from PostToolUse
echo '{}'
