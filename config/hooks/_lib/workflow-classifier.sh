#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — Shared Workflow Classifier
#
# Decides whether a user prompt triggers the mandatory 13-phase flow.
# Used by: user-prompt-submit.sh, pre-tool-use.sh, stop.sh.
#
# Contract:
#   arka_wf_classify "<prompt text>"  → echoes "true" or "false", exits 0.
#   arka_wf_mark_required "<session_id>"  → writes marker file.
#   arka_wf_is_required "<session_id>"  → exits 0 if required, 1 otherwise.
#   arka_wf_clear_required "<session_id>"  → removes marker file.
#
# Markers live under /tmp/arkaos-wf-required/<session_id>.
# Python path for mark/clear: delegates to flow_enforcer.py when available,
# otherwise falls back to touching the marker file directly.
# ============================================================================

ARKA_WF_REQUIRED_DIR="${ARKA_WF_REQUIRED_DIR:-/tmp/arkaos-wf-required}"

# Reject any session_id outside [A-Za-z0-9._-]{1,128}. Protects the marker
# directory from path-traversal writes (CWE-22). Must stay in sync with
# core/workflow/flow_enforcer.py::_safe_session_id.
arka_wf_safe_session_id() {
  local session_id="${1:-}"
  [ -z "$session_id" ] && return 1
  [ ${#session_id} -gt 128 ] && return 1
  case "$session_id" in
    *[!A-Za-z0-9._-]*) return 1 ;;
  esac
  return 0
}

# Verb + noun patterns shared with the original inline classifier in
# user-prompt-submit.sh. Keep in sync when adding new intent verbs.
ARKA_WF_VERB_PATTERN='(criar?|crie[ms]?|cria[mr]?|adicionar?|adiciona[mr]?|implementar?|implementa[mr]?|desenvolver?|desenvolve[mr]?|construir?|constru[ií]a?[mr]?|fazer?|faz[ae][mr]?|refactor(izar?)?|corrigir?|corrige[mr]?|consertar?|conserta[mr]?|create[sd]?|creating|build(s|ing)?|add(s|ed|ing)?|implement(s|ed|ing)?|develop(s|ed|ing)?|fix(es|ed|ing)?|refactor(s|ed|ing)?|make[sd]?|making)'

# Classify: returns "true" if the prompt looks like a creation/
# implementation/modification request, "false" otherwise.
# Skips: explicit slash commands (already routed) and bang shells.
arka_wf_classify() {
  local text="${1:-}"
  [ -z "$text" ] && { echo "false"; return 0; }

  local first_char
  first_char=$(printf '%s' "$text" | head -c 1)
  if [ "$first_char" = "/" ] || [ "$first_char" = "!" ]; then
    echo "false"
    return 0
  fi

  if echo "$text" | grep -qiE "\b${ARKA_WF_VERB_PATTERN}\b"; then
    echo "true"
  else
    echo "false"
  fi
}

# Mark that the flow is required for this session. Safe no-op if session_id
# is empty or fails the allowlist check.
arka_wf_mark_required() {
  local session_id="${1:-}"
  arka_wf_safe_session_id "$session_id" || return 0
  mkdir -p "$ARKA_WF_REQUIRED_DIR" 2>/dev/null
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "$ARKA_WF_REQUIRED_DIR/$session_id" 2>/dev/null
}

# Test whether flow is required. Exit code 0 = required, 1 = not required.
arka_wf_is_required() {
  local session_id="${1:-}"
  arka_wf_safe_session_id "$session_id" || return 1
  [ -f "$ARKA_WF_REQUIRED_DIR/$session_id" ]
}

# Clear the requirement marker. Safe no-op if absent or unsafe.
arka_wf_clear_required() {
  local session_id="${1:-}"
  arka_wf_safe_session_id "$session_id" || return 0
  rm -f "$ARKA_WF_REQUIRED_DIR/$session_id" 2>/dev/null
  return 0
}

# When invoked directly (not sourced), expose a simple CLI for ad-hoc use.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  case "${1:-}" in
    classify)   arka_wf_classify "${2:-}" ;;
    mark)       arka_wf_mark_required "${2:-}" ;;
    is-required) arka_wf_is_required "${2:-}" && echo "true" || echo "false" ;;
    clear)      arka_wf_clear_required "${2:-}" ;;
    *)
      echo "Usage: $0 {classify <text>|mark <session_id>|is-required <session_id>|clear <session_id>}" >&2
      exit 64
      ;;
  esac
fi
