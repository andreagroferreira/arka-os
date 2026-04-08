#!/bin/bash
# ============================================================================
# ARKA OS — KB Media Cleanup
# Removes old media directories for completed jobs.
#
# Usage: kb-cleanup.sh [--older-than 90d] [--dry-run]
# ============================================================================

ARKA_DIR="$HOME/.arka-os"
MEDIA_DIR="$ARKA_DIR/media"
JOBS_FILE="$ARKA_DIR/kb-jobs.json"
LOCK_FILE="$ARKA_DIR/kb-jobs.lock"

MAX_DAYS=90
DRY_RUN=false

# Parse args
while [ $# -gt 0 ]; do
    case "$1" in
        --older-than)
            MAX_DAYS=$(echo "${2:-90d}" | sed 's/d$//')
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if [ ! -d "$MEDIA_DIR" ]; then
    echo -e "${YELLOW}No media directory found.${NC}"
    exit 0
fi

if ! command -v jq &>/dev/null; then
    echo "Error: jq not found. Install with: brew install jq" >&2
    exit 1
fi

echo ""
echo -e "${CYAN}═══ ARKA OS — KB Media Cleanup ═══${NC}"
echo -e "  Removing completed jobs older than ${CYAN}${MAX_DAYS} days${NC}"
if $DRY_RUN; then
    echo -e "  ${YELLOW}DRY RUN — no files will be deleted${NC}"
fi
echo ""

CUTOFF_DATE=$(date -v-${MAX_DAYS}d +%Y-%m-%d 2>/dev/null || date -d "-${MAX_DAYS} days" +%Y-%m-%d 2>/dev/null)
if [ -z "$CUTOFF_DATE" ]; then
    echo "Error: Could not calculate cutoff date" >&2
    exit 1
fi

echo -e "  Cutoff date: $CUTOFF_DATE"
echo ""

TOTAL_FREED=0
DIRS_REMOVED=0

# Iterate date directories
for date_dir in "$MEDIA_DIR"/*/; do
    [ -d "$date_dir" ] || continue
    DIR_DATE=$(basename "$date_dir")

    # Check if date directory is older than cutoff
    if [[ "$DIR_DATE" > "$CUTOFF_DATE" ]] || [[ "$DIR_DATE" == "$CUTOFF_DATE" ]]; then
        continue
    fi

    # Check each job directory inside the date dir
    for job_dir in "$date_dir"*/; do
        [ -d "$job_dir" ] || continue
        JOB_ID=$(basename "$job_dir")

        # Check if this job is completed in the jobs file
        if [ -f "$JOBS_FILE" ]; then
            STATUS=$(jq -r --arg id "$JOB_ID" '.jobs[] | select(.id == $id) | .status // "unknown"' "$JOBS_FILE" 2>/dev/null)

            # Only remove completed jobs
            if [ "$STATUS" != "completed" ] && [ "$STATUS" != "unknown" ]; then
                echo -e "  ${YELLOW}SKIP${NC} $DIR_DATE/$JOB_ID (status: $STATUS)"
                continue
            fi
        fi

        # Calculate directory size
        DIR_SIZE=$(du -sk "$job_dir" 2>/dev/null | cut -f1)
        DIR_SIZE_MB=$(echo "scale=1; $DIR_SIZE / 1024" | bc 2>/dev/null || echo "$DIR_SIZE KB")

        if $DRY_RUN; then
            echo -e "  ${YELLOW}WOULD REMOVE${NC} $DIR_DATE/$JOB_ID (${DIR_SIZE_MB}MB)"
        else
            rm -rf "$job_dir"
            echo -e "  ${GREEN}REMOVED${NC} $DIR_DATE/$JOB_ID (${DIR_SIZE_MB}MB)"

            # Remove job from jobs file
            if [ -f "$JOBS_FILE" ]; then
                (
                    flock -x 200
                    tmp="$JOBS_FILE.tmp.$$"
                    jq --arg id "$JOB_ID" '.jobs = [.jobs[] | select(.id != $id)]' \
                        "$JOBS_FILE" > "$tmp" && mv "$tmp" "$JOBS_FILE"
                ) 200>"$LOCK_FILE"
            fi
        fi

        TOTAL_FREED=$((TOTAL_FREED + DIR_SIZE))
        DIRS_REMOVED=$((DIRS_REMOVED + 1))
    done

    # Remove empty date directories
    if ! $DRY_RUN; then
        rmdir "$date_dir" 2>/dev/null || true
    fi
done

# Summary
echo ""
FREED_MB=$(echo "scale=1; $TOTAL_FREED / 1024" | bc 2>/dev/null || echo "${TOTAL_FREED}KB")
if $DRY_RUN; then
    echo -e "${YELLOW}DRY RUN:${NC} Would remove ${CYAN}$DIRS_REMOVED${NC} directories, freeing ~${CYAN}${FREED_MB}MB${NC}"
else
    echo -e "${GREEN}Cleaned up:${NC} ${CYAN}$DIRS_REMOVED${NC} directories, freed ~${CYAN}${FREED_MB}MB${NC}"
fi
echo -e "${CYAN}══════════════════════════════════${NC}"
