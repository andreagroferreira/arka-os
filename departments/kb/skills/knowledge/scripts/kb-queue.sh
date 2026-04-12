#!/bin/bash
# ============================================================================
# ARKA OS — KB Queue Dispatcher
# Queues a URL for background download + transcription.
#
# Usage: kb-queue.sh <url> [--persona "Name"]
# Output: job ID (8 chars)
# ============================================================================
set -euo pipefail

URL="${1:-}"
PERSONA=""

# Parse args
shift || true
while [ $# -gt 0 ]; do
    case "$1" in
        --persona) PERSONA="${2:-}"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$URL" ]; then
    echo "Usage: kb-queue.sh <url> [--persona \"Name\"]" >&2
    exit 1
fi

ARKA_DIR="$HOME/.arka-os"
JOBS_FILE="$ARKA_DIR/kb-jobs.json"
LOCK_FILE="$ARKA_DIR/kb-jobs.lock"
CAPS_FILE="$ARKA_DIR/capabilities.json"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$ARKA_DIR"

# ─── Generate job ID ────────────────────────────────────────────────────────

JOB_ID=$(printf '%s%s' "$URL" "$(date +%s%N)" | md5sum 2>/dev/null || printf '%s%s' "$URL" "$(date +%s)" | md5 2>/dev/null)
JOB_ID="${JOB_ID:0:8}"

# ─── Create output directory ────────────────────────────────────────────────

DATE_DIR=$(date +%Y-%m-%d)
OUTPUT_DIR="$ARKA_DIR/media/$DATE_DIR/$JOB_ID"
mkdir -p "$OUTPUT_DIR"

# ─── Determine transcription method ─────────────────────────────────────────

TRANSCRIPTION_METHOD="none"

# Run capabilities check if file doesn't exist or is older than 1 hour
REFRESH_CAPS=false
if [ ! -f "$CAPS_FILE" ]; then
    REFRESH_CAPS=true
elif [ "$(uname)" = "Darwin" ]; then
    CAPS_AGE=$(( $(date +%s) - $(stat -f%m "$CAPS_FILE") ))
    [ "$CAPS_AGE" -gt 3600 ] && REFRESH_CAPS=true
else
    CAPS_AGE=$(( $(date +%s) - $(stat -c%Y "$CAPS_FILE") ))
    [ "$CAPS_AGE" -gt 3600 ] && REFRESH_CAPS=true
fi

if $REFRESH_CAPS && [ -f "$SCRIPTS_DIR/kb-check-capabilities.sh" ]; then
    bash "$SCRIPTS_DIR/kb-check-capabilities.sh" >/dev/null 2>&1
fi

# Read transcription method from capabilities
if [ -f "$CAPS_FILE" ] && command -v jq &>/dev/null; then
    TRANSCRIPTION_METHOD=$(jq -r '.transcription.method // "none"' "$CAPS_FILE")
fi

# ─── Check yt-dlp is available ──────────────────────────────────────────────

if ! command -v yt-dlp &>/dev/null; then
    echo "Error: yt-dlp not found. Install with: brew install yt-dlp" >&2
    exit 1
fi

# ─── Initialize jobs file if needed ─────────────────────────────────────────

(
    flock -x 200

    if [ ! -f "$JOBS_FILE" ]; then
        echo '{"jobs":[]}' > "$JOBS_FILE"
    fi

    # Validate JSON
    if ! jq empty "$JOBS_FILE" 2>/dev/null; then
        echo '{"jobs":[]}' > "$JOBS_FILE"
    fi

    # Add job entry
    NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    tmp="$JOBS_FILE.tmp.$$"
    jq --arg id "$JOB_ID" \
       --arg url "$URL" \
       --arg dir "$OUTPUT_DIR" \
       --arg method "$TRANSCRIPTION_METHOD" \
       --arg persona "$PERSONA" \
       --arg now "$NOW" \
       '.jobs += [{
            "id": $id,
            "url": $url,
            "output_dir": $dir,
            "transcription_method": $method,
            "persona": $persona,
            "status": "queued",
            "title": null,
            "word_count": null,
            "error": null,
            "pid": null,
            "created_at": $now,
            "updated_at": $now
        }]' "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"

) 200>"$LOCK_FILE"

# ─── Launch worker in background ────────────────────────────────────────────

WORKER_SCRIPT="$SCRIPTS_DIR/kb-worker.sh"
if [ ! -f "$WORKER_SCRIPT" ]; then
    echo "Error: Worker script not found: $WORKER_SCRIPT" >&2
    exit 1
fi

nohup bash "$WORKER_SCRIPT" "$JOB_ID" "$URL" "$OUTPUT_DIR" "$TRANSCRIPTION_METHOD" \
    > /dev/null 2>&1 &
WORKER_PID=$!

# Record PID in jobs file
(
    flock -x 200
    tmp="$JOBS_FILE.tmp.$$"
    jq --arg id "$JOB_ID" --argjson pid "$WORKER_PID" \
        '(.jobs[] | select(.id == $id)).pid = $pid' \
        "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"
) 200>"$LOCK_FILE"

# ─── Output ─────────────────────────────────────────────────────────────────

if [ -t 1 ]; then
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    NC='\033[0m'
    echo -e "${GREEN}✓${NC} Queued job ${CYAN}$JOB_ID${NC}"
    echo -e "  URL:    $URL"
    echo -e "  Method: $TRANSCRIPTION_METHOD"
    echo -e "  Output: $OUTPUT_DIR"
    echo -e "  PID:    $WORKER_PID"
    if [ -n "$PERSONA" ]; then
        echo -e "  Persona: $PERSONA"
    fi
else
    echo "$JOB_ID"
fi
