#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — Token Hygiene Suggestions
# Non-blocking proactive suggestions for token-efficient usage.
# Called by user-prompt-submit.sh. Emits suggestion strings to stdout, one
# per line. Never blocks. Never errors out (swallow everything).
# ============================================================================

# Inputs (env):
#   ARKA_PROMPT          — raw user prompt text
#   ARKA_TRANSCRIPT_PATH — path to Claude Code transcript jsonl (optional)
#   CLAUDE_CONTEXT_USED  — context percent used (optional, if runtime exposes)

set +e  # never fail

_prompt="${ARKA_PROMPT:-}"
_transcript="${ARKA_TRANSCRIPT_PATH:-}"
_suggestions=""

_emit() {
  if [ -z "$_suggestions" ]; then
    _suggestions="$1"
  else
    _suggestions="$_suggestions $1"
  fi
}

# ─── Check 1: Context % monitor ─────────────────────────────────────────
# Prefer runtime-provided env var. If transcript exists we could count, but
# the runtime value is canonical when present.
if [ -n "${CLAUDE_CONTEXT_USED:-}" ]; then
  _ctx="$CLAUDE_CONTEXT_USED"
  # strip % if present
  _ctx="${_ctx%\%}"
  if [ -n "$_ctx" ] && [ "$_ctx" -eq "$_ctx" ] 2>/dev/null; then
    if [ "$_ctx" -gt 80 ]; then
      _emit "[arka:warn] Context at ${_ctx}% — /compact recommended NOW."
    elif [ "$_ctx" -gt 60 ]; then
      _emit "[arka:suggest] Context at ${_ctx}% — consider /compact."
    fi
  fi
else
  : # TODO: runtime does not yet expose context usage reliably; skip.
fi

# ─── Check 2: Topic drift detector ──────────────────────────────────────
# Compare keywords in current prompt against last 3 user messages in the
# transcript (if available). Pure bash/awk — no external semantic libs.
if [ -n "$_transcript" ] && [ -f "$_transcript" ] && [ -n "$_prompt" ]; then
  _STOPWORDS=" the a an and or but if then of for to in on at by with from is are was were be been being do does did have has had this that these those it its as i you we they he she them my your our their so not no yes can will would could should may might must need want fix make use get set add remove "

  _kw() {
    # extract lowercase word tokens > 3 chars, drop stopwords, output uniq
    echo "$1" | tr '[:upper:]' '[:lower:]' \
      | tr -c 'a-z0-9' '\n' \
      | awk 'length($0) > 3' \
      | awk -v sw=" $(echo " ")$_STOPWORDS" '{
          key=" "$0" ";
          if (index(ENVIRON["_STOPWORDS"], key)==0) print $0
        }' \
      | sort -u
  }
  export _STOPWORDS
  _cur_kw=$(_kw "$_prompt" | head -20)
  # pull last 3 user messages from transcript jsonl
  _prior=$(tail -n 200 "$_transcript" 2>/dev/null \
    | python3 -c "
import sys, json
msgs=[]
for line in sys.stdin:
    try:
        o=json.loads(line)
    except Exception:
        continue
    if o.get('type')=='user' or o.get('role')=='user':
        c=o.get('content') or o.get('message',{}).get('content','')
        if isinstance(c, list):
            c=' '.join(p.get('text','') for p in c if isinstance(p,dict))
        msgs.append(str(c))
print('\n'.join(msgs[-3:]))
" 2>/dev/null)

  if [ -n "$_prior" ] && [ -n "$_cur_kw" ]; then
    _prior_kw=$(_kw "$_prior")
    _cur_count=$(echo "$_cur_kw" | grep -c .)
    if [ "$_cur_count" -gt 2 ]; then
      _overlap=$(comm -12 <(echo "$_cur_kw") <(echo "$_prior_kw") | grep -c .)
      # percent overlap
      _pct=$(( _overlap * 100 / _cur_count ))
      if [ "$_pct" -lt 30 ]; then
        _emit "[arka:suggest] Topic shift detected — consider /clear for a fresh session."
      fi
    fi
  fi
fi

# ─── Check 3: Large paste detector ──────────────────────────────────────
if [ -n "$_prompt" ]; then
  _chars=${#_prompt}
  if [ "$_chars" -gt 2000 ] && echo "$_prompt" | grep -q '```'; then
    _emit "[arka:suggest] Large paste detected (${_chars} chars) — consider @filepath reference for better token economy."
  fi
fi

# ─── Check 4: Vague reference detector ──────────────────────────────────
if [ -n "$_prompt" ]; then
  _lower=$(echo "$_prompt" | tr '[:upper:]' '[:lower:]')
  _vague=0
  for phrase in "fix the bug" "that file" "the error" "esse ficheiro" "esse erro" "aquele bug"; do
    if echo "$_lower" | grep -qF "$phrase"; then
      _vague=1
      break
    fi
  done
  if [ "$_vague" -eq 1 ] && ! echo "$_prompt" | grep -q '@'; then
    _emit "[arka:suggest] Vague reference — use @path/to/file.ext for precision."
  fi
fi

echo -n "$_suggestions"
