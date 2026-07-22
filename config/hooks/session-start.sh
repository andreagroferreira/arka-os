#!/usr/bin/env bash
# ============================================================================
# ArkaOS — SessionStart Hook (thin wrapper, F2-2 hook-hygiene completion)
#
# ONE python process (core.hooks.session_start) builds the entire
# systemMessage — the 13 inline python spawns of the previous version
# live there now (baseline 251ms p50 before consolidation). This file
# only resolves the interpreter and execs; with no usable interpreter
# it emits a static banner and exits 0 (fail-open, stdlib-free).
# ============================================================================

# _HOOK_CWD captured BEFORE any cd — inside a compound command $PWD
# would expand after the cd (QG blocker, F1-A3: cross-project leak).
_HOOK_CWD="$PWD"
export ARKA_HOOK_CWD="$_HOOK_CWD"

# ─── Shared Python resolver (exports ARKA_PY) ──────────────────────────
_ARKA_LIB="$(dirname "${BASH_SOURCE[0]:-$0}")/_lib/arka_python.sh"
if [ -f "$_ARKA_LIB" ]; then . "$_ARKA_LIB"; else ARKA_PY="python3"; fi

REPO=""
[ -f "$HOME/.arkaos/.repo-path" ] && REPO=$(cat "$HOME/.arkaos/.repo-path")

# The MODULE file is the guard, not just core/: an older installed
# snapshot without it would exec into "No module named ..." (exit 1,
# empty output — a broken SessionStart instead of a degraded banner).
if [ -n "$REPO" ] && [ -f "$REPO/core/hooks/session_start.py" ] \
   && command -v "$ARKA_PY" >/dev/null 2>&1; then
  cd "$REPO" 2>/dev/null || true
  PYTHONPATH="$REPO" exec "$ARKA_PY" -m core.hooks.session_start
fi

# ─── Degraded fallback: static banner, valid JSON, exit 0 ──────────────
cat <<'EOF'
{"systemMessage": "\n  ▲  A R K A   O S\n     The Operating System for AI Agent Teams\n\n  Olá, founder\n  degraded: no usable interpreter — run npx arkaos doctor"}
EOF
exit 0
