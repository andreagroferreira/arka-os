#!/bin/bash
# ============================================================================
# ARKA OS — KB Status Checker
# Shows status of queued/running/ready/completed jobs.
#
# Usage: kb-status.sh [job-id] [--json]
# ============================================================================

ARKA_DIR="$HOME/.arka-os"
JOBS_FILE="$ARKA_DIR/kb-jobs.json"
LOCK_FILE="$ARKA_DIR/kb-jobs.lock"

JOB_ID=""
JSON_MODE=false

# Parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --json) JSON_MODE=true; shift ;;
        *)      JOB_ID="$1"; shift ;;
    esac
done

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ─── Check jobs file exists ─────────────────────────────────────────────────

if [ ! -f "$JOBS_FILE" ]; then
    if $JSON_MODE; then
        echo '{"jobs":[]}'
    else
        echo -e "${YELLOW}No jobs found.${NC} Queue a URL with: /kb learn <url>"
    fi
    exit 0
fi

if ! command -v jq &>/dev/null; then
    echo "Error: jq not found. Install with: brew install jq" >&2
    exit 1
fi

# ─── Validate running PIDs ──────────────────────────────────────────────────

(
    flock -x 200

    # Check each running/downloading/transcribing job's PID
    ACTIVE_IDS=$(jq -r '.jobs[] | select(.status == "downloading" or .status == "transcribing" or .status == "queued") | .id' "$JOBS_FILE" 2>/dev/null)

    CHANGED=false
    for id in $ACTIVE_IDS; do
        PID=$(jq -r --arg id "$id" '.jobs[] | select(.id == $id) | .pid // empty' "$JOBS_FILE")
        if [ -n "$PID" ] && ! kill -0 "$PID" 2>/dev/null; then
            # PID is dead — mark as failed
            NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
            tmp="$JOBS_FILE.tmp.$$"
            jq --arg id "$id" --arg t "$NOW" \
                '(.jobs[] | select(.id == $id)) |= (.status = "failed" | .error = "Worker process died unexpectedly" | .updated_at = $t)' \
                "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"
            CHANGED=true
        fi
    done

) 200>"$LOCK_FILE"

# ─── Single job detail ──────────────────────────────────────────────────────

if [ -n "$JOB_ID" ]; then
    JOB=$(jq --arg id "$JOB_ID" '.jobs[] | select(.id == $id)' "$JOBS_FILE" 2>/dev/null)

    if [ -z "$JOB" ] || [ "$JOB" = "null" ]; then
        echo "Job not found: $JOB_ID" >&2
        exit 1
    fi

    if $JSON_MODE; then
        echo "$JOB" | jq .
        exit 0
    fi

    STATUS=$(echo "$JOB" | jq -r '.status')
    URL=$(echo "$JOB" | jq -r '.url')
    TITLE=$(echo "$JOB" | jq -r '.title // "Pending..."')
    DIR=$(echo "$JOB" | jq -r '.output_dir')
    METHOD=$(echo "$JOB" | jq -r '.transcription_method')
    PERSONA=$(echo "$JOB" | jq -r '.persona // "Not assigned"')
    WORDS=$(echo "$JOB" | jq -r '.word_count // "—"')
    ERROR=$(echo "$JOB" | jq -r '.error // ""')
    CREATED=$(echo "$JOB" | jq -r '.created_at')
    UPDATED=$(echo "$JOB" | jq -r '.updated_at')

    # Status color
    case "$STATUS" in
        queued)       STATUS_COLOR="$YELLOW" ;;
        downloading)  STATUS_COLOR="$BLUE" ;;
        transcribing) STATUS_COLOR="$BLUE" ;;
        ready)        STATUS_COLOR="$GREEN" ;;
        analyzing)    STATUS_COLOR="$CYAN" ;;
        completed)    STATUS_COLOR="$GREEN" ;;
        failed)       STATUS_COLOR="$RED" ;;
        *)            STATUS_COLOR="$NC" ;;
    esac

    echo ""
    echo -e "${CYAN}═══ Job: $JOB_ID ═══${NC}"
    echo -e "  Status:    ${STATUS_COLOR}$STATUS${NC}"
    echo -e "  Title:     $TITLE"
    echo -e "  URL:       $URL"
    echo -e "  Method:    $METHOD"
    echo -e "  Persona:   $PERSONA"
    echo -e "  Words:     $WORDS"
    echo -e "  Output:    $DIR"
    echo -e "  Created:   $CREATED"
    echo -e "  Updated:   $UPDATED"
    if [ -n "$ERROR" ]; then
        echo -e "  ${RED}Error:     $ERROR${NC}"
    fi

    # Show available files
    if [ -d "$DIR" ]; then
        echo ""
        echo -e "  ${CYAN}Files:${NC}"
        for f in "$DIR"/*; do
            [ -f "$f" ] || continue
            SIZE=$(ls -lh "$f" | awk '{print $5}')
            echo -e "    $(basename "$f") ($SIZE)"
        done
    fi

    echo -e "${CYAN}══════════════════════${NC}"
    exit 0
fi

# ─── Summary table ──────────────────────────────────────────────────────────

if $JSON_MODE; then
    jq . "$JOBS_FILE"
    exit 0
fi

TOTAL=$(jq '.jobs | length' "$JOBS_FILE")
if [ "$TOTAL" -eq 0 ]; then
    echo -e "${YELLOW}No jobs found.${NC} Queue a URL with: /kb learn <url>"
    exit 0
fi

echo ""
echo -e "${CYAN}═══ ARKA OS — KB Job Queue ═══${NC}"
echo ""
printf "  ${CYAN}%-10s %-12s %-40s %s${NC}\n" "ID" "STATUS" "TITLE" "METHOD"
printf "  %-10s %-12s %-40s %s\n" "──────────" "────────────" "────────────────────────────────────────" "──────────"

jq -r '.jobs[] | [.id, .status, (.title // "Pending..."), .transcription_method] | @tsv' "$JOBS_FILE" | while IFS=$'\t' read -r id status title method; do
    # Truncate title
    if [ ${#title} -gt 38 ]; then
        title="${title:0:35}..."
    fi

    # Status color
    case "$status" in
        queued)       SC="$YELLOW" ;;
        downloading)  SC="$BLUE" ;;
        transcribing) SC="$BLUE" ;;
        ready)        SC="$GREEN" ;;
        analyzing)    SC="$CYAN" ;;
        completed)    SC="$GREEN" ;;
        failed)       SC="$RED" ;;
        *)            SC="$NC" ;;
    esac

    printf "  %-10s ${SC}%-12s${NC} %-40s %s\n" "$id" "$status" "$title" "$method"
done

# Summary counts
QUEUED=$(jq '[.jobs[] | select(.status == "queued")] | length' "$JOBS_FILE")
ACTIVE=$(jq '[.jobs[] | select(.status == "downloading" or .status == "transcribing")] | length' "$JOBS_FILE")
READY=$(jq '[.jobs[] | select(.status == "ready")] | length' "$JOBS_FILE")
COMPLETED=$(jq '[.jobs[] | select(.status == "completed")] | length' "$JOBS_FILE")
FAILED=$(jq '[.jobs[] | select(.status == "failed")] | length' "$JOBS_FILE")

echo ""
echo -e "  Queued: ${YELLOW}$QUEUED${NC}  Active: ${BLUE}$ACTIVE${NC}  Ready: ${GREEN}$READY${NC}  Completed: ${GREEN}$COMPLETED${NC}  Failed: ${RED}$FAILED${NC}"
echo ""

if [ "$READY" -gt 0 ]; then
    echo -e "  ${GREEN}$READY job(s) ready for processing.${NC} Run: /kb process <job-id>"
fi

echo -e "${CYAN}═══════════════════════════════${NC}"
