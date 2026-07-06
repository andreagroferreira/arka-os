#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — PreToolUse Hook (thin wrapper, PR-6 v4.1.0 hook hygiene)
#
# Delegates the ENTIRE event to ONE python process:
#   python3 -m core.hooks.pre_tool_use
#
# The entrypoint preserves the full gate chain and behavior contract of the
# previous 5-8-process version:
#   1. KB-first gate — core/workflow/research_gate.py::evaluate_research_gate
#      (nudge on first external research call, deny on the second)
#   2. Specialist-dispatch gate — core/workflow/specialist_enforcer.py
#   3. Fast allow for non-flow-gated tools
#   4. CostGovernor budget check (stdlib-only; runs even when PyYAML is
#      missing from the ambient python3)
#   5. Evidence-flow gate — core/workflow/flow_enforcer.py
#
# Allow semantics: no stdout, exit 0 (nudges/warnings on stderr).
# Deny semantics: hookSpecificOutput.permissionDecision=deny JSON on stdout,
# `[ARKA:ENFORCEMENT]` / `[ARKA:KB-FIRST]` / `[ARKA:SPECIALIST]` on stderr,
# exit 2. Env bypasses (ARKA_BYPASS_FLOW, ARKA_BYPASS_KB_FIRST) and feature
# flags are honored inside the python modules. Timeout: 10s.
# ============================================================================

# ─── Resolve ARKAOS_ROOT (env → .repo-path → ~/.arkaos → portable) ──────
if [ -z "${ARKAOS_ROOT:-}" ]; then
  if [ -f "$HOME/.arkaos/.repo-path" ]; then
    ARKAOS_ROOT=$(cat "$HOME/.arkaos/.repo-path")
  elif [ -d "$HOME/.arkaos" ]; then
    ARKAOS_ROOT="$HOME/.arkaos"
  else
    ARKAOS_ROOT="${ARKA_OS:-$HOME/.claude/skills/arkaos}"
  fi
fi
export ARKAOS_ROOT

# ─── Shared Python resolver (exports ARKA_PY) ──────────────────────────
_ARKA_LIB="$(dirname "${BASH_SOURCE[0]:-$0}")/_lib/arka_python.sh"
if [ -f "$_ARKA_LIB" ]; then . "$_ARKA_LIB"; else ARKA_PY="python3"; fi

# ─── Degrade gracefully (fail open, same as before) ─────────────────────
if ! command -v "$ARKA_PY" >/dev/null 2>&1; then
  exit 0
fi
# Self-root fallback: the wrapper ships next to its python entrypoint, so
# when ARKAOS_ROOT points at a pre-PR-6 install without core/hooks/, use
# the root this script lives in.
if [ ! -f "$ARKAOS_ROOT/core/hooks/pre_tool_use.py" ]; then
  _SELF_ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
  if [ -n "$_SELF_ROOT" ] && [ -f "$_SELF_ROOT/core/hooks/pre_tool_use.py" ]; then
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
  exec "$ARKA_PY" -m core.hooks.pre_tool_use
