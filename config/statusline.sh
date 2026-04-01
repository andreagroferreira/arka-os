#!/usr/bin/env bash
# ============================================================================
# ARKA OS — Two-Line Color-Coded Status Line for Claude Code
# Receives JSON via stdin, outputs formatted two-line status bar
# ============================================================================

input=$(cat)

# ─── Extract fields (single jq call for performance) ──────────────────────
eval "$(echo "$input" | jq -r '
  @sh "MODEL=\(.model.display_name // "unknown")",
  @sh "CWD=\(.cwd // "")",
  @sh "PROJECT_DIR=\(.workspace.project_dir // "")",
  @sh "PCT=\(.context_window.used_percentage // 0 | floor)",
  @sh "INPUT_TOKENS=\(.context_window.total_input_tokens // 0)",
  @sh "OUTPUT_TOKENS=\(.context_window.total_output_tokens // 0)",
  @sh "COST=\(.cost.total_cost_usd // 0)",
  @sh "DURATION_MS=\(.cost.total_duration_ms // 0)",
  @sh "ADDED=\(.cost.total_lines_added // 0)",
  @sh "REMOVED=\(.cost.total_lines_removed // 0)"
' 2>/dev/null)" 2>/dev/null || {
  # Fallback: individual extractions if single-call fails
  MODEL=$(echo "$input" | jq -r '.model.display_name // "unknown"' 2>/dev/null)
  CWD=$(echo "$input" | jq -r '.cwd // ""' 2>/dev/null)
  PROJECT_DIR=$(echo "$input" | jq -r '.workspace.project_dir // ""' 2>/dev/null)
  PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' 2>/dev/null | cut -d. -f1)
  INPUT_TOKENS=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0' 2>/dev/null)
  OUTPUT_TOKENS=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0' 2>/dev/null)
  COST=$(echo "$input" | jq -r '.cost.total_cost_usd // 0' 2>/dev/null)
  DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0' 2>/dev/null)
  ADDED=$(echo "$input" | jq -r '.cost.total_lines_added // 0' 2>/dev/null)
  REMOVED=$(echo "$input" | jq -r '.cost.total_lines_removed // 0' 2>/dev/null)
}

# ─── Project name ─────────────────────────────────────────────────────────
WORK_DIR="${CWD:-$PROJECT_DIR}"
DIR_NAME=$(basename "${WORK_DIR:-arka}")

# ─── Git info (cached for 5s) ─────────────────────────────────────────────
GIT_CACHE="/tmp/arka-statusline-git-cache"
CACHE_MAX_AGE=5
BRANCH=""

if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
  CACHE_KEY=$(echo "$WORK_DIR" | md5 2>/dev/null || echo "$WORK_DIR" | md5sum 2>/dev/null | cut -d' ' -f1)
  CACHE_FILE="${GIT_CACHE}-${CACHE_KEY}"

  if [ -f "$CACHE_FILE" ] && [ $(($(date +%s) - $(stat -f%m "$CACHE_FILE" 2>/dev/null || stat -c%Y "$CACHE_FILE" 2>/dev/null || echo 0))) -lt $CACHE_MAX_AGE ]; then
    # Read from cache
    BRANCH=$(cat "$CACHE_FILE" 2>/dev/null)
  else
    # Fresh git query
    BRANCH=$(git -C "$WORK_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    # Write cache
    echo "${BRANCH}" > "$CACHE_FILE" 2>/dev/null
  fi
fi

# ─── Colors ───────────────────────────────────────────────────────────────
C_RESET='\033[0m'
C_CYAN='\033[0;36m'
C_DIM='\033[2m'
C_WHITE='\033[1;37m'
C_GREEN='\033[0;32m'
C_YELLOW='\033[1;33m'
C_RED='\033[0;31m'
C_BLINK_RED='\033[5;31m'

# Context color based on percentage
PCT=${PCT:-0}
if [ "$PCT" -ge 90 ]; then
  C_BAR="$C_BLINK_RED"
elif [ "$PCT" -ge 80 ]; then
  C_BAR="$C_RED"
elif [ "$PCT" -ge 60 ]; then
  C_BAR="$C_YELLOW"
else
  C_BAR="$C_GREEN"
fi

# ─── Format tokens (K/M) ─────────────────────────────────────────────────
format_tokens() {
  local n="${1:-0}"
  if [ "$n" -ge 1000000 ]; then
    printf "%.1fM" "$(echo "scale=1; $n / 1000000" | bc 2>/dev/null || echo "0")"
  elif [ "$n" -ge 1000 ]; then
    printf "%.1fK" "$(echo "scale=1; $n / 1000" | bc 2>/dev/null || echo "0")"
  else
    echo "${n}"
  fi
}

IN_FMT=$(format_tokens "$INPUT_TOKENS")
OUT_FMT=$(format_tokens "$OUTPUT_TOKENS")

# ─── Progress bar (10 chars) ──────────────────────────────────────────────
FILLED=$((PCT / 10))
EMPTY=$((10 - FILLED))
BAR=""
for ((i=0; i<FILLED; i++)); do BAR+="█"; done
for ((i=0; i<EMPTY; i++)); do BAR+="░"; done

# ─── Format duration ──────────────────────────────────────────────────────
SECS=$((${DURATION_MS:-0} / 1000))
if [ "$SECS" -ge 3600 ]; then
  HOURS=$((SECS / 3600))
  MINS=$(((SECS % 3600) / 60))
  TIME_FMT="${HOURS}h${MINS}m"
elif [ "$SECS" -ge 60 ]; then
  MINS=$((SECS / 60))
  REM_SECS=$((SECS % 60))
  TIME_FMT="${MINS}m${REM_SECS}s"
else
  TIME_FMT="${SECS}s"
fi

# ─── Format cost ──────────────────────────────────────────────────────────
COST_FMT=$(printf '$%.2f' "${COST:-0}")

# ─── Build Line 1: Context bar ───────────────────────────────────────────
LINE1="${C_CYAN}▲ARKA${C_RESET}  ${C_WHITE}${DIR_NAME}${C_RESET}"

# Git branch (hidden on main/master to reduce noise)
if [ -n "$BRANCH" ] && [ "$BRANCH" != "main" ] && [ "$BRANCH" != "master" ]; then
  LINE1+="  ${C_DIM}on${C_RESET} ${C_GREEN}${BRANCH}${C_RESET}"
fi

LINE1+="  ${C_DIM}|${C_RESET}  ${MODEL}"

# ─── Build Line 2: Metrics bar ───────────────────────────────────────────
LINE2="${C_BAR}${BAR} ${PCT}%${C_RESET}"
LINE2+="  ${C_DIM}|${C_RESET}  ${IN_FMT} in ${OUT_FMT} out"
LINE2+="  ${C_DIM}|${C_RESET}  ${C_GREEN}+${ADDED}${C_RESET} ${C_RED}-${REMOVED}${C_RESET}"
LINE2+="  ${C_DIM}|${C_RESET}  ${TIME_FMT}"
LINE2+="  ${C_DIM}|${C_RESET}  ${COST_FMT}"

# ─── Output ───────────────────────────────────────────────────────────────
echo -e "$LINE1"
echo -e "$LINE2"
