#!/bin/bash
# ============================================================================
# ARKA OS — Version Check
# Checks for updates by comparing local and remote commit hashes.
# Silent fail on network errors. Only checks once per 24 hours.
# ============================================================================

ARKA_OS="${ARKA_OS:-$HOME/.claude/skills/arka}"
VERSION_FILE="$ARKA_OS/VERSION"
COMMIT_FILE="$ARKA_OS/.installed-commit"
REPO_PATH_FILE="$ARKA_OS/.repo-path"
LAST_CHECK_FILE="$ARKA_OS/.last-update-check"

# Exit silently if critical files are missing
[ -f "$VERSION_FILE" ] || exit 0
[ -f "$COMMIT_FILE" ] || exit 0
[ -f "$REPO_PATH_FILE" ] || exit 0

LOCAL_VERSION=$(cat "$VERSION_FILE" 2>/dev/null)
LOCAL_COMMIT=$(cat "$COMMIT_FILE" 2>/dev/null)
REPO_PATH=$(cat "$REPO_PATH_FILE" 2>/dev/null)

# Check 24h cache — only verify once per day
if [ -f "$LAST_CHECK_FILE" ]; then
    LAST_CHECK=$(cat "$LAST_CHECK_FILE" 2>/dev/null)
    NOW=$(date +%s)
    DIFF=$((NOW - LAST_CHECK))
    # 86400 seconds = 24 hours
    [ "$DIFF" -lt 86400 ] && exit 0
fi

# Attempt to get remote HEAD (3s timeout, silent fail)
REMOTE_COMMIT=""
if [ -d "$REPO_PATH/.git" ]; then
    REMOTE_COMMIT=$(cd "$REPO_PATH" && git ls-remote --heads origin master 2>/dev/null | head -1 | cut -f1)
fi

# If we couldn't reach remote, fail silently
if [ -z "$REMOTE_COMMIT" ]; then
    # Still update timestamp so we don't retry immediately
    date +%s > "$LAST_CHECK_FILE" 2>/dev/null
    exit 0
fi

# Update check timestamp
date +%s > "$LAST_CHECK_FILE" 2>/dev/null

# Compare hashes
if [ "$LOCAL_COMMIT" != "$REMOTE_COMMIT" ]; then
    REMOTE_VERSION=""
    if [ -d "$REPO_PATH" ]; then
        REMOTE_VERSION=$(cd "$REPO_PATH" && git show "origin/master:VERSION" 2>/dev/null | tr -d '[:space:]')
    fi
    echo ""
    echo "  ╔═══════════════════════════════════════════════════╗"
    echo "  ║  ARKA OS update available!                        ║"
    echo "  ║  Current: v${LOCAL_VERSION}  →  Latest: v${REMOTE_VERSION:-unknown}          ║"
    echo "  ║  Run: arka update                                 ║"
    echo "  ╚═══════════════════════════════════════════════════╝"
    echo ""
fi
