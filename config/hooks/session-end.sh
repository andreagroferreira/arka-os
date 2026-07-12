#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — session-end Hook (thin wrapper, F2-4)
#
# Delegates the ENTIRE event to ONE python process:
#   python3 -m core.hooks.session_end
#
# Writes a final session digest immediately (PreCompact only fires on
# compaction) and marks the session ended. Best-effort, never blocks.
# Fail-open: no usable interpreter => exit 0. Timeout: 15s.
# ============================================================================

# ─── Shared Python resolver (exports ARKA_PY) ──────────────────────────
_ARKA_LIB="$(dirname "${BASH_SOURCE[0]:-$0}")/_lib/arka_python.sh"
if [ -f "$_ARKA_LIB" ]; then . "$_ARKA_LIB"; else ARKA_PY="python3"; fi

# ─── Resolve ARKAOS_ROOT (validated — see arka_resolve_root in _lib) ────
# .repo-path can point at a purged npx cache; the shared resolver falls
# through to the ~/.arkaos/lib snapshot instead of exporting a dead root.
if command -v arka_resolve_root >/dev/null 2>&1; then
  ARKAOS_ROOT="$(arka_resolve_root)"
elif [ -z "${ARKAOS_ROOT:-}" ]; then
  # Legacy chain (pre-snapshot _lib deployment)
  if [ -f "$HOME/.arkaos/.repo-path" ]; then
    ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path")
  elif [ -d "$HOME/.arkaos" ]; then
    ARKAOS_ROOT="$HOME/.arkaos"
  else
    ARKAOS_ROOT="${ARKA_OS:-$HOME/.claude/skills/arkaos}"
  fi
fi
export ARKAOS_ROOT

# ─── Degrade gracefully (fail open, same as before) ─────────────────────
if ! command -v "$ARKA_PY" >/dev/null 2>&1; then
  exit 0
fi
# Self-root fallback: the wrapper ships next to its python entrypoint, so
# when ARKAOS_ROOT points at a pre-PR-6 install without core/hooks/, use
# the root this script lives in.
if [ ! -f "$ARKAOS_ROOT/core/hooks/session_end.py" ]; then
  _SELF_ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
  if [ -n "$_SELF_ROOT" ] && [ -f "$_SELF_ROOT/core/hooks/session_end.py" ]; then
    ARKAOS_ROOT="$_SELF_ROOT"
    export ARKAOS_ROOT
  else
    exit 0
  fi
fi

# ─── Single python process; stdin/stdout/stderr/exit-code pass through ──
# Interpreter resolution handled by the shared resolver (ARKA_PY): prefers
# the ArkaOS venv (has pyyaml/pydantic), falls back to a yaml-capable python3.
PYTHONPATH="$ARKAOS_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$ARKA_PY" -m core.hooks.session_end
