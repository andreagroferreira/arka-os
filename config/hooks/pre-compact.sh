#!/usr/bin/env bash
# ============================================================================
# ARKA OS — PreCompact Hook
# Saves session digest before context compaction
# Timeout: 30s | No LLM analysis — raw context preservation
# ============================================================================

input=$(cat)

# ─── Performance Timing ──────────────────────────────────────────────────
_HOOK_START=$(date +%s 2>/dev/null)
_HOOK_START_NS=$(date +%s%N 2>/dev/null || echo "0")
_hook_ms() {
  local end_ns=$(date +%s%N 2>/dev/null || echo "0")
  if [ "$_HOOK_START_NS" != "0" ] && [ "$end_ns" != "0" ] && [ ${#end_ns} -gt 10 ]; then
    echo $(( (end_ns - _HOOK_START_NS) / 1000000 ))
  else
    echo $(( ($(date +%s) - _HOOK_START) * 1000 ))
  fi
}

# Extract fields
SESSION_ID=$(echo "$input" | jq -r '.session_id // "unknown"' 2>/dev/null)
TRANSCRIPT=$(echo "$input" | jq -r '.transcript // ""' 2>/dev/null)

# ─── Setup ────────────────────────────────────────────────────────────────
DIGEST_DIR="$HOME/.arkaos/session-digests"
mkdir -p "$DIGEST_DIR"

SHORT_ID=$(echo "$SESSION_ID" | head -c 8)
# Content-hash filename → deduplicable and cache-friendly.
# Falls back to session id + transcript head so identical compactions collapse.
if command -v shasum &>/dev/null; then
  DIGEST_ID=$(printf '%s' "${SESSION_ID:-default}-$(printf '%s' "$TRANSCRIPT" | head -c 200 | tr -d '\n')" | shasum -a 256 | cut -c1-16)
else
  DIGEST_ID=$(printf '%s' "${SESSION_ID:-default}-$(printf '%s' "$TRANSCRIPT" | head -c 200 | tr -d '\n')" | md5 | cut -c1-16)
fi
DIGEST_FILE="${DIGEST_DIR}/digest-${SHORT_ID}-${DIGEST_ID}.md"

# ─── Extract Context ──────────────────────────────────────────────────────
# Get last 50 lines of transcript
if [ -n "$TRANSCRIPT" ]; then
  TAIL_LINES=$(echo "$TRANSCRIPT" | tail -50)
else
  TAIL_LINES="(no transcript available)"
fi

# Extract last 5 assistant messages from JSON if available.
# The previous filter used `last(5)` which in jq returns the LAST element
# of the generator `5` (the constant 5 itself), so the pipeline collapsed
# to `5 | .[]` and always produced nothing. Use the array slice `[-5:]`
# to actually take the last up-to-five elements, then iterate.
ASSISTANT_MSGS=""
if echo "$input" | jq -e '.messages' &>/dev/null; then
  ASSISTANT_MSGS=$(echo "$input" | jq -r '
    [.messages[] | select(.role == "assistant") | .content][-5:] | .[]
  ' 2>/dev/null)
fi

# ─── Write Digest ─────────────────────────────────────────────────────────
cat > "$DIGEST_FILE" << DIGEST_EOF
---
type: session-digest
session_id: ${SESSION_ID}
digest_id: ${DIGEST_ID}
trigger: pre-compact
---

# Session Digest — ${DIGEST_ID}

**Session:** \`${SESSION_ID}\`
**Digest:** \`${DIGEST_ID}\`
**Trigger:** Context compaction

## Last Assistant Messages

${ASSISTANT_MSGS:-_(none captured)_}

## Transcript Tail (last 50 lines)

\`\`\`
${TAIL_LINES}
\`\`\`
DIGEST_EOF

# ─── Auto-Cleanup: Keep Only Last 50 Digests ─────────────────────────────
DIGEST_COUNT=$(ls -1 "$DIGEST_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
if [ "$DIGEST_COUNT" -gt 50 ]; then
  REMOVE_COUNT=$((DIGEST_COUNT - 50))
  ls -1t "$DIGEST_DIR"/*.md | tail -"$REMOVE_COUNT" | xargs rm -f 2>/dev/null
fi

# ─── Log Metrics ─────────────────────────────────────────────────────────
_DURATION_MS=$(_hook_ms)
METRICS_FILE="$HOME/.arkaos/hook-metrics.json"
METRICS_LOCK="$HOME/.arkaos/hook-metrics.lock"
mkdir -p "$HOME/.arkaos"
(
  if command -v flock &>/dev/null; then flock -w 2 200; else true; fi
  [ ! -f "$METRICS_FILE" ] && echo '[]' > "$METRICS_FILE"
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq --argjson dur "$_DURATION_MS" --arg ts "$NOW" --arg hook "pre-compact" \
    '. += [{"hook": $hook, "duration_ms": $dur, "timestamp": $ts}] | .[-500:]' \
    "$METRICS_FILE" > "$METRICS_FILE.tmp" 2>/dev/null && mv "$METRICS_FILE.tmp" "$METRICS_FILE"
) 200>"$METRICS_LOCK" 2>/dev/null

# ─── Output ───────────────────────────────────────────────────────────────
# Silent — no output needed for PreCompact hook
echo '{}'
