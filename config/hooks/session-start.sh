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

# ─── Resolve the root via the shared resolver (one root per session) ───
# Reading .repo-path raw diverged from every other hook: the file points
# at an npx cache that `npm cache clean` can purge, while
# arka_resolve_root falls through to the ~/.arkaos/lib snapshot. The
# chosen root AND source both travel to the entrypoint so the session
# can name the root it actually ran from ([arka:root]).
REPO=""
ARKA_ROOT_SOURCE="legacy"
if command -v arka_resolve_root >/dev/null 2>&1; then
  [ -n "${ARKAOS_ROOT:-}" ] && ARKA_ROOT_SOURCE="env"
  REPO="$(arka_resolve_root)"
  if [ "$ARKA_ROOT_SOURCE" != "env" ]; then
    if [ -f "$HOME/.arkaos/.repo-path" ] \
       && [ "$REPO" = "$(cat "$HOME/.arkaos/.repo-path" 2>/dev/null)" ]; then
      ARKA_ROOT_SOURCE="repo-path"
    elif [ "$REPO" = "$HOME/.arkaos/lib" ]; then
      ARKA_ROOT_SOURCE="lib-snapshot"
    else
      ARKA_ROOT_SOURCE="fallback"
    fi
  fi
elif [ -f "$HOME/.arkaos/.repo-path" ]; then
  REPO=$(cat "$HOME/.arkaos/.repo-path")
fi
export ARKA_ROOT_SOURCE
export ARKA_ROOT="$REPO"

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
