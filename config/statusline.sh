#!/usr/bin/env bash
# ============================================================================
# ARKA OS — Custom Status Line for Claude Code
# Receives JSON via stdin, outputs formatted status bar
# ============================================================================

input=$(cat)

# Extract fields (with safe fallbacks)
MODEL=$(echo "$input" | jq -r '.model.display_name // "unknown"' 2>/dev/null)
CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)
PROJECT_DIR=$(echo "$input" | jq -r '.workspace.project_dir // ""' 2>/dev/null)
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' 2>/dev/null | cut -d. -f1)
COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0' 2>/dev/null)
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0' 2>/dev/null)
ADDED=$(echo "$input" | jq -r '.cost.total_lines_added // 0' 2>/dev/null)
REMOVED=$(echo "$input" | jq -r '.cost.total_lines_removed // 0' 2>/dev/null)

# Project name from directory
if [ -n "$CWD" ]; then
    DIR_NAME=$(basename "$CWD")
elif [ -n "$PROJECT_DIR" ]; then
    DIR_NAME=$(basename "$PROJECT_DIR")
else
    DIR_NAME="arka"
fi

# Git branch (cached for performance)
BRANCH=$(git -C "${CWD:-$PROJECT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "—")

# Progress bar (10 chars)
PCT=${PCT:-0}
FILLED=$((PCT / 10))
EMPTY=$((10 - FILLED))
BAR=""
for ((i=0; i<FILLED; i++)); do BAR+="█"; done
for ((i=0; i<EMPTY; i++)); do BAR+="░"; done

# Format duration
SECS=$((${DURATION_MS:-0} / 1000))
if [ "$SECS" -ge 60 ]; then
    MINS=$((SECS / 60))
    REM_SECS=$((SECS % 60))
    TIME_FMT="${MINS}m${REM_SECS}s"
else
    TIME_FMT="${SECS}s"
fi

# Format cost
COST_FMT=$(printf '$%.2f' "${COST:-0}")

# Output
echo "▲ARKA | ${DIR_NAME} · ${BRANCH} | ${MODEL} | ${BAR} ${PCT}% | +${ADDED} -${REMOVED} | ${TIME_FMT} | ${COST_FMT}"
