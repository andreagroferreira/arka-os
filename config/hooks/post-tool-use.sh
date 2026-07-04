#!/usr/bin/env bash
# ============================================================================
# ARKA OS — PostToolUse Hook (thin wrapper, PR-6 v4.1.0 hook hygiene)
#
# Delegates the ENTIRE event to ONE python process:
#   python3 -m core.hooks.post_tool_use
#
# The entrypoint preserves the behavior contract of the previous
# ~38-spawn-site version:
#   - Flow marker cache: detects [arka:routing] / [arka:trivial] in the
#     assistant message and persists via core.workflow.marker_cache
#     write_marker so PreToolUse can short-circuit the transcript scan.
#   - CQO REJECTED experience auto-record + APPROVED pattern stubs.
#   - Activation tracking for every Task/Agent dispatch.
#   - Gotchas memory (~/.arkaos/gotchas.json) with fix suggestions.
#   - Workflow violation rules + enforcement engine + forge scope-creep
#     (delegated once to the ArkaOS venv python when the ambient python3
#     lacks PyYAML — mirrors the old ARKAOS_PY resolution).
#   - Cognition capture enqueue (detached background process).
#   - Hook metrics. Output: JSON to stdout. Timeout: 5s.
# ============================================================================

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

if ! command -v python3 &>/dev/null; then
  echo '{}'
  exit 0
fi
# Self-root fallback: the wrapper ships next to its python entrypoint, so
# when ARKAOS_ROOT points at a pre-PR-6 install without core/hooks/, use
# the root this script lives in.
if [ ! -f "$ARKAOS_ROOT/core/hooks/post_tool_use.py" ]; then
  _SELF_ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
  if [ -n "$_SELF_ROOT" ] && [ -f "$_SELF_ROOT/core/hooks/post_tool_use.py" ]; then
    ARKAOS_ROOT="$_SELF_ROOT"
    export ARKAOS_ROOT
  else
    echo '{}'
    exit 0
  fi
fi

PYTHONPATH="$ARKAOS_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  exec python3 -m core.hooks.post_tool_use
