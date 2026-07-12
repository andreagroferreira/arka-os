#!/usr/bin/env bash
# ArkaOS hook latency harness (F2-1 — Claude Code integration reform).
#
# Measures REAL end-to-end wall time of each hook wrapper (bash spawn +
# resolver + python) with synthetic payloads, N runs each, p50/p95.
# This is the permanent version of the ad-hoc measurement in the F2
# plan: every later perf claim (F2-2 session-start consolidation, F2-6
# fast-path shims) cites a before/after from THIS harness.
#
# Usage: bash benchmarks/hooks-bench.sh [N]   (default N=20)
# Output: JSON to stdout — merge into benchmarks/results.md by hand or
# via the release notes. Runs against the REAL environment (real HOME,
# real venv): the point is production latency, not lab latency.
# Payloads are minimal/benign so hooks take their early-exit paths —
# the floor cost every single turn pays.
#
# Scope note (on record): no always-on per-turn timing telemetry ships
# with this harness — a hook-latency.jsonl nobody reads would be the
# exact write-only-telemetry antipattern the F1 campaign closed (G1).
# On-demand reproducible measurement beats ambient noise.

set -euo pipefail

N="${1:-20}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_DIR/config/hooks"
SESSION="bench-$$"

_now_ns() { date +%s%N 2>/dev/null || echo "$(($(date +%s) * 1000000000))"; }

# hook_name -> payload (kept benign: early-exit floor cost).
_payload() {
  case "$1" in
    user-prompt-submit)
      printf '{"session_id":"%s","prompt":"bench: estado do sistema","cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
    pre-tool-use)
      printf '{"session_id":"%s","tool_name":"Glob","tool_input":{"pattern":"*.md"},"cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
    post-tool-use)
      printf '{"session_id":"%s","tool_name":"Glob","tool_response":{"output":"ok"},"exit_code":"0","cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
    stop)
      printf '{"session_id":"%s","transcript_path":"","stop_hook_active":"false","cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
    session-start)
      printf '{"session_id":"%s","cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
    pre-compact)
      printf '{"session_id":"%s","transcript_path":"","cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
    cwd-changed)
      printf '{"session_id":"%s","cwd":"%s"}' "$SESSION" "$REPO_DIR" ;;
  esac
}

_percentile() {  # $1 = sorted ms list (newline), $2 = percentile (50/95)
  local sorted="$1" pct="$2"
  local count idx
  count=$(printf '%s\n' "$sorted" | sed '/^$/d' | wc -l | tr -d ' ')
  [ "$count" -eq 0 ] && { echo 0; return; }
  idx=$(( (count * pct + 99) / 100 ))
  [ "$idx" -lt 1 ] && idx=1
  printf '%s\n' "$sorted" | sed '/^$/d' | sed -n "${idx}p"
}

HOOKS="user-prompt-submit pre-tool-use post-tool-use stop session-start pre-compact cwd-changed"

echo "{"
printf '  "n_runs": %s,\n  "measured_at": "%s",\n  "hooks": {\n' "$N" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
first=1
for hook in $HOOKS; do
  script="$HOOKS_DIR/$hook.sh"
  [ -f "$script" ] || continue
  payload="$(_payload "$hook")"
  times=""
  for _ in $(seq 1 "$N"); do
    start=$(_now_ns)
    printf '%s' "$payload" | bash "$script" >/dev/null 2>&1 || true
    end=$(_now_ns)
    times="${times}$(( (end - start) / 1000000 ))
"
  done
  sorted=$(printf '%s' "$times" | sort -n)
  p50=$(_percentile "$sorted" 50)
  p95=$(_percentile "$sorted" 95)
  [ "$first" -eq 0 ] && printf ',\n'
  first=0
  printf '    "%s": {"p50_ms": %s, "p95_ms": %s}' "$hook" "$p50" "$p95"
done
# Belt-and-braces: drop any marker a bench session id left behind.
rm -f "/tmp/arkaos-wf-required/$SESSION" 2>/dev/null || true
printf '\n  }\n}\n'
