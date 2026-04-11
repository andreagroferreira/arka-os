#!/bin/bash
# ============================================================================
# ARKA OS — MCP Profile Applicator
# Generates .mcp.json and .claude/settings.local.json for a project
# ============================================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCPS_DIR="$(dirname "$SCRIPT_DIR")"
REGISTRY="$MCPS_DIR/registry.json"

usage() {
    echo -e "${CYAN}ARKA OS — MCP Applicator${NC}"
    echo ""
    echo "Usage: apply-mcps.sh <profile> [--project <path>] [--add <mcp-name>]"
    echo ""
    echo "Profiles: base, laravel, nuxt, vue, react, nextjs, ecommerce, full-stack, comms"
    echo ""
    echo "Options:"
    echo "  --project <path>   Target project directory (default: current dir)"
    echo "  --add <name>       Add a single MCP (skip profile)"
    echo "  --list             List all available MCPs"
    echo "  --status           Show MCPs active in target project"
    echo ""
    echo "Examples:"
    echo "  apply-mcps.sh laravel --project ~/Projects/my-app"
    echo "  apply-mcps.sh --add firecrawl"
    echo "  apply-mcps.sh --list"
}

# Check jq is available
if ! command -v jq &>/dev/null; then
    echo -e "${RED}Error: jq is required but not installed.${NC}"
    echo "Install: brew install jq"
    exit 1
fi

# Parse arguments
PROFILE=""
PROJECT_DIR="$(pwd)"
ADD_MCP=""
LIST_MODE=false
STATUS_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)
            PROJECT_DIR="$2"
            shift 2
            ;;
        --add)
            ADD_MCP="$2"
            shift 2
            ;;
        --list)
            LIST_MODE=true
            shift
            ;;
        --status)
            STATUS_MODE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            PROFILE="$1"
            shift
            ;;
    esac
done

# List mode
if $LIST_MODE; then
    echo -e "${CYAN}ARKA OS — Available MCPs${NC}"
    echo ""
    jq -r '.mcpServers | to_entries[] | "  \(.key)\t\(.value.category)\t\(.value.description)"' "$REGISTRY" | column -t -s $'\t'
    echo ""
    echo -e "${CYAN}Profiles:${NC} base, laravel, nuxt, vue, react, nextjs, ecommerce, full-stack, comms"
    exit 0
fi

# Status mode
if $STATUS_MODE; then
    MCP_FILE="$PROJECT_DIR/.mcp.json"
    if [ -f "$MCP_FILE" ]; then
        echo -e "${CYAN}ARKA OS — Active MCPs in ${PROJECT_DIR}${NC}"
        echo ""
        jq -r '.mcpServers | keys[]' "$MCP_FILE" | while read -r name; do
            echo -e "  ${GREEN}✓${NC} $name"
        done
    else
        echo -e "${YELLOW}No .mcp.json found in ${PROJECT_DIR}${NC}"
    fi
    exit 0
fi

# Resolve project directory
PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd)" || {
    echo -e "${RED}Error: Project directory not found: ${PROJECT_DIR}${NC}"
    exit 1
}

# Collect MCP names to apply
MCP_NAMES=()

if [ -n "$ADD_MCP" ]; then
    # Single MCP mode
    MCP_NAMES+=("$ADD_MCP")
    echo -e "${CYAN}Adding MCP: ${ADD_MCP} to ${PROJECT_DIR}${NC}"
elif [ -n "$PROFILE" ]; then
    # Profile mode — resolve base + profile MCPs
    BASE_PROFILE="$MCPS_DIR/profiles/base.json"
    PROFILE_FILE="$MCPS_DIR/profiles/${PROFILE}.json"

    if [ ! -f "$PROFILE_FILE" ]; then
        echo -e "${RED}Error: Profile '${PROFILE}' not found.${NC}"
        echo "Available: base, laravel, nuxt, vue, react, nextjs, ecommerce, full-stack, comms"
        exit 1
    fi

    # Always include base MCPs
    while IFS= read -r mcp; do
        MCP_NAMES+=("$mcp")
    done < <(jq -r '.mcps[]' "$BASE_PROFILE")

    # Add profile-specific MCPs (unless profile IS base)
    if [ "$PROFILE" != "base" ]; then
        while IFS= read -r mcp; do
            MCP_NAMES+=("$mcp")
        done < <(jq -r '.mcps[]' "$PROFILE_FILE")
    fi

    echo -e "${CYAN}Applying profile: ${PROFILE} to ${PROJECT_DIR}${NC}"
else
    usage
    exit 1
fi

# Remove duplicates
MCP_NAMES=($(printf '%s\n' "${MCP_NAMES[@]}" | sort -u))

# Build .mcp.json
echo -e "${CYAN}Generating .mcp.json...${NC}"

MCP_JSON='{"mcpServers":{}}'

MISSING_ENVS=()

for mcp_name in "${MCP_NAMES[@]}"; do
    # Check MCP exists in registry
    MCP_ENTRY=$(jq -r ".mcpServers.\"$mcp_name\" // empty" "$REGISTRY")
    if [ -z "$MCP_ENTRY" ]; then
        echo -e "  ${YELLOW}⚠${NC} Unknown MCP: $mcp_name (skipped)"
        continue
    fi

    # Check if it's HTTP or command type
    MCP_TYPE=$(echo "$MCP_ENTRY" | jq -r '.type // "command"')

    if [ "$MCP_TYPE" = "http" ]; then
        # HTTP MCP — just type + url
        MCP_URL=$(echo "$MCP_ENTRY" | jq -r '.url')
        MCP_JSON=$(echo "$MCP_JSON" | jq --arg name "$mcp_name" --arg url "$MCP_URL" \
            '.mcpServers[$name] = {"type": "http", "url": $url}')
    else
        # Command MCP — command + args + optional env
        MCP_CMD=$(echo "$MCP_ENTRY" | jq -r '.command')
        MCP_ARGS=$(echo "$MCP_ENTRY" | jq -c '.args')
        MCP_ENV=$(echo "$MCP_ENTRY" | jq -c '.env // {}')

        # Replace {cwd} and {home} placeholders
        MCP_ARGS=$(echo "$MCP_ARGS" | sed "s|{cwd}|$PROJECT_DIR|g; s|{home}|$HOME|g")
        MCP_ENV=$(echo "$MCP_ENV" | sed "s|{cwd}|$PROJECT_DIR|g; s|{home}|$HOME|g")

        if [ "$MCP_ENV" = "{}" ]; then
            MCP_JSON=$(echo "$MCP_JSON" | jq --arg name "$mcp_name" --arg cmd "$MCP_CMD" --argjson args "$MCP_ARGS" \
                '.mcpServers[$name] = {"command": $cmd, "args": $args}')
        else
            MCP_JSON=$(echo "$MCP_JSON" | jq --arg name "$mcp_name" --arg cmd "$MCP_CMD" --argjson args "$MCP_ARGS" --argjson env "$MCP_ENV" \
                '.mcpServers[$name] = {"command": $cmd, "args": $args, "env": $env}')

            # Track env vars that need values
            for env_var in $(echo "$MCP_ENV" | jq -r 'to_entries[] | select(.value | startswith("$")) | .key'); do
                MISSING_ENVS+=("$mcp_name: $env_var")
            done
        fi
    fi

    echo -e "  ${GREEN}✓${NC} $mcp_name"
done

# If adding to existing .mcp.json, merge
EXISTING_MCP="$PROJECT_DIR/.mcp.json"
if [ -n "$ADD_MCP" ] && [ -f "$EXISTING_MCP" ]; then
    MCP_JSON=$(jq -s '.[0] * .[1]' "$EXISTING_MCP" <(echo "$MCP_JSON"))
fi

# Write .mcp.json
echo "$MCP_JSON" | jq '.' > "$PROJECT_DIR/.mcp.json"
echo -e "${GREEN}✓${NC} Created ${PROJECT_DIR}/.mcp.json"

# Generate .claude/settings.local.json
CLAUDE_DIR="$PROJECT_DIR/.claude"
mkdir -p "$CLAUDE_DIR"

SETTINGS_FILE="$CLAUDE_DIR/settings.local.json"

# Build server names list for enabledMcpjsonServers
ENABLED_SERVERS=$(echo "$MCP_JSON" | jq '[.mcpServers | keys[]]')

SETTINGS_JSON=$(jq -n \
    --argjson servers "$ENABLED_SERVERS" \
    '{
        "enableAllProjectMcpServers": true,
        "enabledMcpjsonServers": $servers,
        "permissions": {
            "allow": [
                "Read",
                "Grep",
                "Glob",
                "WebFetch"
            ]
        }
    }')

# If settings already exist, merge (preserve existing permissions)
if [ -f "$SETTINGS_FILE" ]; then
    SETTINGS_JSON=$(jq -s '
        .[0] as $existing |
        .[1] as $new |
        $existing * $new |
        .enabledMcpjsonServers = ($existing.enabledMcpjsonServers // [] | . + $new.enabledMcpjsonServers | unique)
    ' "$SETTINGS_FILE" <(echo "$SETTINGS_JSON"))
fi

echo "$SETTINGS_JSON" | jq '.' > "$SETTINGS_FILE"
echo -e "${GREEN}✓${NC} Created ${SETTINGS_FILE}"

# Summary
echo ""
echo -e "${GREEN}═══ MCPs Applied Successfully ═══${NC}"
echo -e "  Profile:   ${CYAN}${PROFILE:-single-add}${NC}"
echo -e "  Project:   ${CYAN}${PROJECT_DIR}${NC}"
echo -e "  MCPs:      ${CYAN}${#MCP_NAMES[@]}${NC}"
echo -e "  Files:     .mcp.json, .claude/settings.local.json"

if [ ${#MISSING_ENVS[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠ Environment variables need configuration:${NC}"
    for env_info in "${MISSING_ENVS[@]}"; do
        echo -e "  ${YELLOW}→${NC} $env_info"
    done
    echo -e "  Set these in your shell or .env file."
fi

echo -e "${GREEN}═════════════════════════════════${NC}"
