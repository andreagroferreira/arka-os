#!/usr/bin/env bash
# ============================================================================
# ArkaOS — Workflow State Reader (for hooks)
# Reads ~/.arkaos/workflow-state.json and outputs requested fields.
# Dependencies: jq (required)
# ============================================================================

STATE_FILE="$HOME/.arkaos/workflow-state.json"

if [ ! -f "$STATE_FILE" ]; then
  case "${1:-}" in
    active) exit 1 ;;
    summary) exit 1 ;;
    violations) echo "0"; exit 0 ;;
    phase) echo "none"; exit 0 ;;
    check) exit 1 ;;
    *) echo "No active workflow"; exit 1 ;;
  esac
fi

CMD="${1:-summary}"
ARG="${2:-}"

case "$CMD" in
  active)
    exit 0
    ;;

  phase)
    if [ -z "$ARG" ]; then
      echo "Usage: state-reader.sh phase <name>" >&2
      exit 1
    fi
    STATUS=$(jq -r ".phases.\"$ARG\".status // \"unknown\"" "$STATE_FILE" 2>/dev/null)
    echo "$STATUS"
    ;;

  check)
    if [ -z "$ARG" ]; then
      echo "Usage: state-reader.sh check <name>" >&2
      exit 1
    fi
    STATUS=$(jq -r ".phases.\"$ARG\".status // \"pending\"" "$STATE_FILE" 2>/dev/null)
    [ "$STATUS" = "completed" ] && exit 0 || exit 1
    ;;

  violations)
    COUNT=$(jq '.violations | length' "$STATE_FILE" 2>/dev/null || echo "0")
    echo "$COUNT"
    ;;

  summary)
    WORKFLOW=$(jq -r '.workflow // ""' "$STATE_FILE" 2>/dev/null)
    BRANCH=$(jq -r '.branch // ""' "$STATE_FILE" 2>/dev/null)
    VIOLATIONS=$(jq '.violations | length' "$STATE_FILE" 2>/dev/null || echo "0")
    TOTAL=$(jq '.phases | length' "$STATE_FILE" 2>/dev/null || echo "0")
    COMPLETED=$(jq '[.phases[] | select(.status == "completed")] | length' "$STATE_FILE" 2>/dev/null || echo "0")
    CURRENT=$(jq -r '[.phases | to_entries[] | select(.value.status == "in_progress")] | .[0].key // "none"' "$STATE_FILE" 2>/dev/null)
    [ "$CURRENT" = "null" ] && CURRENT="none"
    echo "${WORKFLOW}|${CURRENT}|${COMPLETED}/${TOTAL}|${BRANCH}|${VIOLATIONS}"
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: state-reader.sh {active|phase|check|violations|summary} [arg]" >&2
    exit 1
    ;;
esac
