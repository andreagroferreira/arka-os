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
    forge) ;; # forge reads its own state file — fall through to main case
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

  forge)
    _FORGE_ACTIVE="$HOME/.arkaos/plans/active.yaml"
    if [ ! -f "$_FORGE_ACTIVE" ]; then
      echo "none"
      exit 0
    fi
    _FORGE_ID=$(cat "$_FORGE_ACTIVE" 2>/dev/null)
    _FORGE_FILE="$HOME/.arkaos/plans/${_FORGE_ID}.yaml"
    if [ ! -f "$_FORGE_FILE" ]; then
      echo "none"
      exit 0
    fi
    if command -v python3 &>/dev/null; then
      _F_NAME=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(d.get('name',''))" 2>/dev/null)
      _F_STATUS=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(d.get('status',''))" 2>/dev/null)
      _F_PHASES=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(len(d.get('plan_phases',[])))" 2>/dev/null)
      _F_BRANCH=$(python3 -c "import yaml; d=yaml.safe_load(open('$_FORGE_FILE')); print(d.get('governance',{}).get('branch_strategy',''))" 2>/dev/null)
      echo "${_FORGE_ID}|${_F_NAME}|${_F_STATUS}|${_F_PHASES}|${_F_BRANCH}"
    else
      echo "${_FORGE_ID}|||0|"
    fi
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: state-reader.sh {active|phase|check|violations|summary|forge} [arg]" >&2
    exit 1
    ;;
esac
