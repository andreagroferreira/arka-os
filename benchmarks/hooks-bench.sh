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
# via the release notes.
#
# Isolation contract (QG blocker, F2-1 redo): hooks run under a
# THROWAWAY HOME with the real venv symlinked in — the production
# interpreter and code paths are measured, but every state write
# (budget ledger, telemetry, markers, session memory) lands in the
# temp dir and dies with the run. A benchmark must never inflate the
# operator's CostGovernor ledger. Payloads are minimal/benign so hooks
# take their early-exit paths — the floor cost every single turn pays.
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

# Throwaway HOME: real venv (symlink) + repo pointer, everything else
# ephemeral. cleanup on any exit.
BENCH_HOME="$(mktemp -d "${TMPDIR:-/tmp}/arka-hooks-bench.XXXXXX")"
mkdir -p "$BENCH_HOME/.arkaos/reorganize-proposals"
REAL_VENV="$HOME/.arkaos/venv"
[ -d "$REAL_VENV" ] && ln -s "$REAL_VENV" "$BENCH_HOME/.arkaos/venv"
printf '%s\n' "$REPO_DIR" > "$BENCH_HOME/.arkaos/.repo-path"
# A benchmark must never spawn long-lived services or background jobs:
# session-start's dashboard-ensure would launch a REAL server per run
# (reproduced: 8 orphan dashboard-api processes from one N=20 run) and
# its stale-aware reorganizer fires whenever today's proposal is
# missing. Disable the first, satisfy the second.
# The hook computes _TODAY with `date -u` (session-start.sh:146) — the
# seed MUST use the same UTC basis (QG redo-1 blocker: a local-date
# seed left a ~1h/day window where the reorganizer fired anyway).
# Belt-and-braces ±1 day also covers a UTC midnight crossing mid-run.
printf '{"dashboard": {"ensure_on_session": false}}\n' > "$BENCH_HOME/.arkaos/config.json"
# BSD date needs an EXPLICIT sign (-v1d SETS day-of-month to 1); GNU
# uses -d. Offsets carry their sign; 0 is plain UTC today.
for _off in "-1" "0" "+1"; do
  if [ "$_off" = "0" ]; then
    _stamp=$(date -u +%Y-%m-%d)
  else
    _stamp=$(date -u -v"${_off}d" +%Y-%m-%d 2>/dev/null \
      || date -u -d "${_off} day" +%Y-%m-%d 2>/dev/null \
      || date -u +%Y-%m-%d)
  fi
  touch "$BENCH_HOME/.arkaos/reorganize-proposals/${_stamp}.md"
done
trap 'rm -rf "$BENCH_HOME"; rm -f "/tmp/arkaos-wf-required/$SESSION" 2>/dev/null || true' EXIT

_now_ns() {
  local t
  t=$(date +%s%N 2>/dev/null || echo "")
  # BSD date can emit a literal trailing 'N' WITH exit 0 (F1-D1 class);
  # accept only pure digits, else fall back to second resolution.
  if [[ "$t" =~ ^[0-9]+$ ]]; then
    echo "$t"
  else
    echo "$(($(date +%s) * 1000000000))"
  fi
}

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
  # F2-6: measure the same entry command settings.json registers — the
  # Node fast-path shim when deployed (and not kill-switched), else the
  # bash wrapper. ARKA_HOOK_FASTPATH=0 benches the delegation baseline.
  script="$HOOKS_DIR/$hook.sh"
  runner="bash"
  if [ "${ARKA_HOOK_FASTPATH:-1}" != "0" ] && [ -f "$HOOKS_DIR/$hook.cjs" ] \
     && command -v node >/dev/null 2>&1; then
    script="$HOOKS_DIR/$hook.cjs"
    runner="node"
  fi
  [ -f "$script" ] || continue
  payload="$(_payload "$hook")"
  times=""
  for _ in $(seq 1 "$N"); do
    start=$(_now_ns)
    # 3>/dev/null: no hook child may inherit an open fd 3 — a background
    # grandchild holding it hangs bats forever (bats waits for fd EOF).
    printf '%s' "$payload" | HOME="$BENCH_HOME" "$runner" "$script" >/dev/null 2>&1 3>/dev/null || true
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
printf '\n  }\n}\n'
