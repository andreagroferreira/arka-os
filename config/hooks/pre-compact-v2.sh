#!/usr/bin/env bash
# ============================================================================
# ArkaOS v2 — PreCompact Hook (Session Digest Preservation)
# Saves session context before compaction to prevent loss
# Timeout: 30s
# ============================================================================

input=$(cat)

ARKAOS_HOME="${HOME}/.arkaos"
DIGEST_DIR="$ARKAOS_HOME/session-digests"

mkdir -p "$DIGEST_DIR" 2>/dev/null

# ─── Extract session data ────────────────────────────────────────────────
timestamp=$(date +"%Y%m%d-%H%M%S")
short_id=$(echo "$timestamp" | md5sum 2>/dev/null | head -c 8 || echo "$RANDOM")
digest_file="$DIGEST_DIR/${timestamp}-${short_id}.md"

# ─── Save digest ─────────────────────────────────────────────────────────
{
  echo "# Session Digest — $timestamp"
  echo ""
  echo "## Last Context (before compaction)"
  echo ""

  if command -v jq &>/dev/null; then
    # Extract transcript lines
    echo "$input" | jq -r '.transcript // ""' 2>/dev/null | tail -50
    echo ""
    echo "## Last Assistant Messages"
    echo ""
    echo "$input" | jq -r '.messages[]? | select(.role == "assistant") | .content' 2>/dev/null | tail -c 5000
  else
    echo "$input" | tail -100
  fi
} > "$digest_file" 2>/dev/null

# ─── Cleanup: keep only last 50 digests ──────────────────────────────────
digest_count=$(ls -1 "$DIGEST_DIR"/*.md 2>/dev/null | wc -l)
if [ "$digest_count" -gt 50 ]; then
  ls -1t "$DIGEST_DIR"/*.md | tail -n +51 | xargs rm -f 2>/dev/null
fi
