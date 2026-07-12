#!/bin/bash
# ============================================================================
# ARKA OS — KB Background Worker
# Handles one job: download audio → transcribe → mark ready
# Launched by kb-queue.sh via nohup
#
# Usage: kb-worker.sh <job-id> <url> <output-dir> <transcription-method>
# ============================================================================

JOB_ID="$1"
URL="$2"
OUTPUT_DIR="$3"
TRANSCRIPTION_METHOD="${4:-none}"

ARKA_DIR="$HOME/.arka-os"
JOBS_FILE="$ARKA_DIR/kb-jobs.json"
LOCK_FILE="$ARKA_DIR/kb-jobs.lock"
WORKER_LOG="$OUTPUT_DIR/worker.log"

# Redirect all output to worker log
exec > "$WORKER_LOG" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Worker started for job $JOB_ID"
echo "  URL: $URL"
echo "  Output: $OUTPUT_DIR"
echo "  Transcription: $TRANSCRIPTION_METHOD"

# Load env for API keys
[ -f "$ARKA_DIR/.env" ] && source "$ARKA_DIR/.env"

# ─── State update helper ────────────────────────────────────────────────────

update_job() {
    local field="$1"
    local value="$2"
    (
        flock -x 200
        if command -v jq &>/dev/null && [ -f "$JOBS_FILE" ]; then
            local tmp="$JOBS_FILE.tmp.$$"
            jq --arg id "$JOB_ID" --arg val "$value" \
                '(.jobs[] | select(.id == $id)).'$field' = $val' \
                "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"
        fi
    ) 200>"$LOCK_FILE"
}

update_job_status() {
    local status="$1"
    local now
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    (
        flock -x 200
        if command -v jq &>/dev/null && [ -f "$JOBS_FILE" ]; then
            local tmp="$JOBS_FILE.tmp.$$"
            jq --arg id "$JOB_ID" --arg s "$status" --arg t "$now" \
                '(.jobs[] | select(.id == $id)) |= (.status = $s | .updated_at = $t)' \
                "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"
        fi
    ) 200>"$LOCK_FILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Status → $status"
}

fail_job() {
    local error_msg="$1"
    (
        flock -x 200
        if command -v jq &>/dev/null && [ -f "$JOBS_FILE" ]; then
            local tmp="$JOBS_FILE.tmp.$$"
            local now
            now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
            jq --arg id "$JOB_ID" --arg err "$error_msg" --arg t "$now" \
                '(.jobs[] | select(.id == $id)) |= (.status = "failed" | .error = $err | .updated_at = $t)' \
                "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"
        fi
    ) 200>"$LOCK_FILE"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FAILED: $error_msg"
    exit 1
}

# ─── Step 1: Download ───────────────────────────────────────────────────────

update_job_status "downloading"

if ! command -v yt-dlp &>/dev/null; then
    fail_job "yt-dlp not found. Install with: brew install yt-dlp"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Downloading audio..."

# Download audio + metadata
yt-dlp -x --audio-format wav --audio-quality 0 \
    --write-info-json \
    -o "$OUTPUT_DIR/audio.%(ext)s" \
    "$URL" > "$OUTPUT_DIR/download.log" 2>&1

if [ $? -ne 0 ]; then
    fail_job "yt-dlp download failed. Check $OUTPUT_DIR/download.log"
fi

# Find the audio file (yt-dlp may produce different extensions during conversion)
AUDIO_FILE="$OUTPUT_DIR/audio.wav"
if [ ! -f "$AUDIO_FILE" ]; then
    # Try to find any audio file produced
    AUDIO_FILE=$(find "$OUTPUT_DIR" -name "audio.*" -not -name "*.json" -not -name "*.log" | head -1)
    if [ -z "$AUDIO_FILE" ] || [ ! -f "$AUDIO_FILE" ]; then
        fail_job "Audio file not found after download"
    fi
fi

# Extract metadata from yt-dlp JSON
INFO_JSON=$(find "$OUTPUT_DIR" -name "*.info.json" | head -1)
if [ -n "$INFO_JSON" ] && [ -f "$INFO_JSON" ]; then
    jq '{title: .title, duration: .duration, duration_string: .duration_string, channel: .channel, upload_date: .upload_date, thumbnail: .thumbnail, description: (.description // "" | .[0:500])}' \
        "$INFO_JSON" > "$OUTPUT_DIR/metadata.json" 2>/dev/null || true

    # Update job with title
    TITLE=$(jq -r '.title // "Unknown"' "$OUTPUT_DIR/metadata.json" 2>/dev/null || echo "Unknown")
    update_job "title" "$TITLE"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Title: $TITLE"
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Download complete: $AUDIO_FILE"

# ─── Step 2: Transcribe ─────────────────────────────────────────────────────

update_job_status "transcribing"

case "$TRANSCRIPTION_METHOD" in
    local_whisper)
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Transcribing with local Whisper..."
        whisper "$AUDIO_FILE" \
            --model medium \
            --language auto \
            --output_format txt \
            --output_dir "$OUTPUT_DIR" \
            > "$OUTPUT_DIR/transcribe.log" 2>&1

        if [ $? -ne 0 ]; then
            fail_job "Whisper transcription failed. Check $OUTPUT_DIR/transcribe.log"
        fi

        # Whisper outputs as <filename>.txt — find it
        TRANSCRIPT=$(find "$OUTPUT_DIR" -name "*.txt" -not -name "transcribe.log" -not -name "download.log" -not -name "worker.log" | head -1)
        if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
            cp "$TRANSCRIPT" "$OUTPUT_DIR/audio.txt" 2>/dev/null || true
        fi
        ;;

    openai_api)
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Transcribing with OpenAI Whisper API..."

        if [ -z "${OPENAI_API_KEY:-}" ]; then
            fail_job "OPENAI_API_KEY not set. Run: bash env-setup.sh"
        fi

        # Check file size — OpenAI limit is 25MB
        FILE_SIZE=$(stat -f%z "$AUDIO_FILE" 2>/dev/null || stat -c%s "$AUDIO_FILE" 2>/dev/null || echo "0")
        if [ "$FILE_SIZE" -gt 26214400 ]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] File too large for API ($FILE_SIZE bytes). Compressing..."
            if command -v ffmpeg &>/dev/null; then
                ffmpeg -i "$AUDIO_FILE" -ac 1 -ar 16000 -b:a 32k "$OUTPUT_DIR/audio_compressed.mp3" \
                    >> "$OUTPUT_DIR/transcribe.log" 2>&1
                AUDIO_FILE="$OUTPUT_DIR/audio_compressed.mp3"
            else
                fail_job "Audio file too large and ffmpeg not available for compression"
            fi
        fi

        # Call OpenAI API
        RESPONSE=$(curl -s -X POST "https://api.openai.com/v1/audio/transcriptions" \
            -H "Authorization: Bearer $OPENAI_API_KEY" \
            -F "file=@$AUDIO_FILE" \
            -F "model=whisper-1" \
            -F "response_format=text" \
            2>> "$OUTPUT_DIR/transcribe.log")

        if [ -z "$RESPONSE" ]; then
            fail_job "OpenAI API returned empty response. Check $OUTPUT_DIR/transcribe.log"
        fi

        # Check for API error
        if echo "$RESPONSE" | jq -e '.error' &>/dev/null 2>&1; then
            ERROR_MSG=$(echo "$RESPONSE" | jq -r '.error.message // "Unknown API error"')
            fail_job "OpenAI API error: $ERROR_MSG"
        fi

        echo "$RESPONSE" > "$OUTPUT_DIR/audio.txt"
        ;;

    none)
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] No transcription method available. Download-only mode."
        echo "[Download-only mode — no transcription available]" > "$OUTPUT_DIR/audio.txt"
        update_job_status "ready"
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Worker finished (download-only)"
        exit 0
        ;;

    *)
        fail_job "Unknown transcription method: $TRANSCRIPTION_METHOD"
        ;;
esac

# Verify transcript exists
if [ ! -f "$OUTPUT_DIR/audio.txt" ] || [ ! -s "$OUTPUT_DIR/audio.txt" ]; then
    fail_job "Transcription produced no output"
fi

WORD_COUNT=$(wc -w < "$OUTPUT_DIR/audio.txt" | tr -d ' ')
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Transcription complete: $WORD_COUNT words"

# Update word count in job
update_job "word_count" "$WORD_COUNT"

# ─── Done — mark ready for processing ───────────────────────────────────────

update_job_status "ready"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Worker finished. Job $JOB_ID is ready for processing."
