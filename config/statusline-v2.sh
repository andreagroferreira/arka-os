#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — Status Line for Claude Code
# Two-line color-coded display showing session context and metrics
# ============================================================================

input=$(cat)

# ─── Extract fields ──���───────────────────────────────────────────────────
if ! command -v jq &>/dev/null; then
  echo "▲ARKAOS v2 | jq not found"
  exit 0
fi

eval "$(echo "$input" | jq -r '
  @sh "model=\(.session.model // "unknown")",
  @sh "total_in=\(.context_window.total_input_tokens // 0)",
  @sh "total_out=\(.context_window.total_output_tokens // 0)",
  @sh "max_ctx=\(.context_window.context_window_size // 200000)",
  @sh "cost=\(.cost_usd // 0)",
  @sh "duration=\(.session.duration_seconds // 0)"
' 2>/dev/null)" 2>/dev/null

# ─── Format tokens (K/M) ────────────────────────────────────────────────
format_tokens() {
  local n=$1
  if [ "$n" -ge 1000000 ] 2>/dev/null; then
    printf "%.1fM" "$(echo "scale=1; $n/1000000" | bc 2>/dev/null || echo "?")"
  elif [ "$n" -ge 1000 ] 2>/dev/null; then
    printf "%.1fK" "$(echo "scale=1; $n/1000" | bc 2>/dev/null || echo "?")"
  else
    echo "${n:-0}"
  fi
}

# ─── Context percentage ─────────────────────────────────────────────────
pct=0
if [ "${max_ctx:-0}" -gt 0 ] 2>/dev/null; then
  pct=$(( (${total_in:-0} * 100) / ${max_ctx} ))
fi

# ─── Color based on context usage ────────────────────────────────────────
if [ "$pct" -ge 90 ]; then
  color="\033[5;31m"  # Blinking red
elif [ "$pct" -ge 80 ]; then
  color="\033[31m"    # Red
elif [ "$pct" -ge 60 ]; then
  color="\033[33m"    # Yellow
else
  color="\033[32m"    # Green
fi
reset="\033[0m"

# ─── Progress bar ───────��────────────────────────────────────────────────
filled=$(( pct / 10 ))
empty=$(( 10 - filled ))
bar=""
for ((i=0; i<filled; i++)); do bar+="█"; done
for ((i=0; i<empty; i++)); do bar+="░"; done

# ─── Git info (cached) ──────────────────────────────────────────────────
branch=""
if git rev-parse --is-inside-work-tree &>/dev/null; then
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ "$branch" = "main" ] || [ "$branch" = "master" ]; then
    branch=""
  fi
fi

# ─── Project name ────────────────────────────────────────────────────────
project=$(basename "$(pwd)")

# ─── Duration ─────���──────────────────────────────────────────────────────
dur=""
if [ "${duration:-0}" -gt 0 ] 2>/dev/null; then
  mins=$(( duration / 60 ))
  secs=$(( duration % 60 ))
  if [ "$mins" -gt 0 ]; then
    dur="${mins}m${secs}s"
  else
    dur="${secs}s"
  fi
fi

# ─── Line 1: Context ────────────────────────────────────────────────────
line1="▲ARKAOS"
[ -n "$project" ] && line1+="  ${project}"
[ -n "$branch" ] && line1+="  on ${branch}"
line1+="  |  ${model:-Opus}"

# ─── Line 2: Metrics ────────────────────────────────────────────────────
in_fmt=$(format_tokens "${total_in:-0}")
out_fmt=$(format_tokens "${total_out:-0}")

line2="${bar} ${pct}%  |  ${in_fmt} in ${out_fmt} out"
[ -n "$dur" ] && line2+="  |  ${dur}"
[ "${cost:-0}" != "0" ] && line2+="  |  \$${cost}"

# ─── Output ────────────────────────────────────��─────────────────────────
echo -e "${line1}"
echo -e "${color}${line2}${reset}"
