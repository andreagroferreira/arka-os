#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — Stop Hook (thin wrapper, PR-6 v4.1.0 hook hygiene)
#
# Delegates the ENTIRE event to ONE python process:
#   python3 -m core.hooks.stop
#
# WARN mode: this hook NEVER blocks — always exit 0. The entrypoint
# preserves the behavior contract of the previous multi-heredoc version:
#   - DNA fidelity check on the closing assistant message.
#   - Native usage cost capture (native:session rows, pre-WF_MARKER).
#   - Flow completion validation: closing markers ([arka:gate:4],
#     legacy [arka:phase:13], [arka:trivial]), meta_tag_found for the
#     [arka:meta] transparency tag, KB citation soft-block, sycophancy
#     detection, closing-marker soft-block, skill proposer, kb=N
#     reconciliation — all recorded to
#     ~/.arkaos/telemetry/enforcement.jsonl with mode "warn".
#   - [arka:gate:N] checkpoint persistence for structured resume.
#   - Auto-documentor enqueue (flow-required + QG APPROVED + external
#     research). Transcript parsed ONCE and shared by every consumer.
#
# Timeout: 5s | Always exit 0.
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
  exit 0
fi
# Self-root fallback: the wrapper ships next to its python entrypoint, so
# when ARKAOS_ROOT points at a pre-PR-6 install without core/hooks/, use
# the root this script lives in.
if [ ! -f "$ARKAOS_ROOT/core/hooks/stop.py" ]; then
  _SELF_ROOT="$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)"
  if [ -n "$_SELF_ROOT" ] && [ -f "$_SELF_ROOT/core/hooks/stop.py" ]; then
    ARKAOS_ROOT="$_SELF_ROOT"
    export ARKAOS_ROOT
  else
    exit 0
  fi
fi

PYTHONPATH="$ARKAOS_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -m core.hooks.stop
exit 0
