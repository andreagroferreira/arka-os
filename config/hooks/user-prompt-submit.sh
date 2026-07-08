#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — UserPromptSubmit Hook (thin wrapper, PR-6 v4.1.0 hook hygiene)
#
# Delegates the ENTIRE event to ONE python process:
#   python3 -m core.hooks.user_prompt_submit
#
# The entrypoint preserves the behavior contract of the previous
# ~31-spawn-site version:
#   - V1 migration + sync-version detection ([arka:update-available]).
#   - Per-turn cache reset: marker_cache.invalidate_marker +
#     kb_cache.invalidate_obsidian_query.
#   - Synapse bridge (scripts/synapse-bridge.py::run_bridge) called
#     in-process — 12-layer context injection, no second interpreter.
#   - Workflow-state / forge tags, KB auto-inject, bash-parity fallback
#     context (constitution L0, branch, workflow, forge).
#   - Token hygiene (context %, topic drift, large paste, vague ref).
#   - Persistent [ARKA:ROUTE] reminder + workflow classifier that marks
#     the session flow-required ([ARKA:WORKFLOW-REQUIRED]).
#   - One-shot nudges (KB-cite, meta-tag, closing-marker) gated by
#     effort level; cognitive context injection.
#
# Timeout: 10s | Output: JSON to stdout | Target: <100ms
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

_ARKA_L0_FALLBACK='{"additionalContext": "[Constitution] NON-NEGOTIABLE: branch-isolation, security-gate, mandatory-qa, evidence-flow, arkaos-not-yes-man, excellence-mandate | QUALITY-GATE: marta-cqo, eduardo-copy, francisca-tech-ux | MUST (28) incl.: squad-routing, spec-driven, conventional-commits, test-coverage, subagent-discipline, persona-vs-artifact"}'

if ! command -v "$ARKA_PY" >/dev/null 2>&1; then
  echo "$_ARKA_L0_FALLBACK"
  exit 0
fi
# Self-root fallback: the wrapper ships next to its python entrypoint, so
# when ARKAOS_ROOT points at a pre-PR-6 install without core/hooks/, use
# the root this script lives in.
if [ ! -f "$ARKAOS_ROOT/core/hooks/user_prompt_submit.py" ]; then
  _SELF_ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
  if [ -n "$_SELF_ROOT" ] && [ -f "$_SELF_ROOT/core/hooks/user_prompt_submit.py" ]; then
    ARKAOS_ROOT="$_SELF_ROOT"
    export ARKAOS_ROOT
  else
    echo "$_ARKA_L0_FALLBACK"
    exit 0
  fi
fi

# Interpreter resolution handled by the shared resolver (ARKA_PY): prefers
# the ArkaOS venv (has pyyaml/pydantic), falls back to a yaml-capable python3.
PYTHONPATH="$ARKAOS_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  exec "$ARKA_PY" -m core.hooks.user_prompt_submit
