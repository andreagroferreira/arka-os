#!/bin/bash
# ============================================================================
# ARKA OS — Environment Setup
# Interactive configuration of API keys for MCP integrations.
# ============================================================================

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ARKA_ENV_DIR="$HOME/.arka-os"
ARKA_ENV_FILE="$ARKA_ENV_DIR/.env"
SHELL_RC="$HOME/.zshrc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="$SCRIPT_DIR/mcps/registry.json"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  ARKA OS — Environment Setup                                ║${NC}"
echo -e "${CYAN}║  Configure API keys for MCP integrations                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Create config directory
mkdir -p "$ARKA_ENV_DIR"

# Load existing env if present
if [ -f "$ARKA_ENV_FILE" ]; then
    source "$ARKA_ENV_FILE"
    echo -e "${GREEN}Loaded existing configuration from ${ARKA_ENV_FILE}${NC}"
    echo ""
fi

# Guidance lookup table
get_guidance() {
    case "$1" in
        CLICKUP_API_KEY)      echo "Go to ClickUp → Settings → Apps → Generate API Token" ;;
        CLICKUP_TEAM_ID)      echo "Go to ClickUp → Settings → Spaces → Team ID in URL" ;;
        FIRECRAWL_API_KEY)    echo "Go to firecrawl.dev → Dashboard → API Keys" ;;
        PG_HOST)              echo "Your PostgreSQL host (e.g., localhost, db.supabase.co)" ;;
        PG_PORT)              echo "Your PostgreSQL port (default: 5432)" ;;
        PG_USER)              echo "Your PostgreSQL username" ;;
        PG_PASSWORD)          echo "Your PostgreSQL password" ;;
        PG_DATABASE)          echo "Your PostgreSQL database name" ;;
        DISCORD_TOKEN)        echo "Go to discord.com/developers → New App → Bot → Token" ;;
        WHATSAPP_API_TOKEN)   echo "Go to developers.facebook.com → WhatsApp → API Setup → Token" ;;
        WHATSAPP_PHONE_ID)    echo "Go to developers.facebook.com → WhatsApp → API Setup → Phone Number ID" ;;
        TEAMS_APP_ID)         echo "Go to portal.azure.com → App Registrations → Application (client) ID" ;;
        TEAMS_APP_SECRET)     echo "Go to portal.azure.com → App Registrations → Certificates & Secrets → New" ;;
        MEMORY_BANK_ROOT)     echo "Directory for persistent memory storage (default: ~/memory-bank)" ;;
        *)                    echo "Check the MCP documentation for this variable" ;;
    esac
}

# Check jq
if ! command -v jq &>/dev/null; then
    echo -e "${YELLOW}jq not found. Install with: brew install jq${NC}"
    exit 1
fi

# ─── ARKA OS Service Keys (AI services) ─────────────────────────────────────
echo -e "${BLUE}[ARKA OS Service Keys]${NC}"
echo -e "  These keys enable AI features like Whisper transcription and LLM routing."
echo ""

SERVICE_KEYS=(
    "OPENAI_API_KEY|Go to platform.openai.com → API Keys"
    "GEMINI_API_KEY|Go to aistudio.google.com → API Keys"
    "OPENROUTER_API_KEY|Go to openrouter.ai → Dashboard → Keys"
    "REPLICATE_API_TOKEN|Go to replicate.com → Account → API Tokens"
    "FAL_KEY|Go to fal.ai → Dashboard → Keys"
)

SERVICE_CONFIGURED=0
SERVICE_SKIPPED=0

for entry in "${SERVICE_KEYS[@]}"; do
    var="${entry%%|*}"
    guidance="${entry#*|}"

    # Check if already set
    current_value="${!var}"
    if [ -n "$current_value" ] && [ "$current_value" != '${'"$var"'}' ]; then
        echo -e "  ${GREEN}✓${NC} $var (already configured)"
        continue
    fi

    echo -e "${BLUE}$var${NC}"
    echo -e "  ${YELLOW}→${NC} $guidance"
    read -rp "  Value (press Enter to skip): " value

    if [ -n "$value" ]; then
        if grep -q "^export $var=" "$ARKA_ENV_FILE" 2>/dev/null; then
            sed -i '' "s|^export $var=.*|export $var=\"$value\"|" "$ARKA_ENV_FILE"
        else
            echo "export $var=\"$value\"" >> "$ARKA_ENV_FILE"
        fi
        SERVICE_CONFIGURED=$((SERVICE_CONFIGURED + 1))
        echo -e "  ${GREEN}✓${NC} Saved"
    else
        SERVICE_SKIPPED=$((SERVICE_SKIPPED + 1))
        echo -e "  ${YELLOW}⏭${NC} Skipped"
    fi
    echo ""
done

echo -e "  Service keys: ${CYAN}${SERVICE_CONFIGURED}${NC} configured, ${CYAN}${SERVICE_SKIPPED}${NC} skipped"
echo ""

# ─── MCP Integration Keys ───────────────────────────────────────────────────
echo -e "${BLUE}[MCP Integration Keys]${NC}"
echo ""

# Read all required env vars from registry
ENV_VARS=$(jq -r '.mcpServers | to_entries[] | .value.required_env[]?' "$REGISTRY" 2>/dev/null | sort -u)

if [ -z "$ENV_VARS" ]; then
    echo -e "${GREEN}No environment variables to configure.${NC}"
    exit 0
fi

CONFIGURED=0
SKIPPED=0

for var in $ENV_VARS; do
    # Check if already set
    current_value="${!var}"
    if [ -n "$current_value" ] && [ "$current_value" != '${'"$var"'}' ]; then
        echo -e "  ${GREEN}✓${NC} $var (already configured)"
        continue
    fi

    # Show guidance and ask for value
    guidance=$(get_guidance "$var")
    echo -e "${BLUE}$var${NC}"
    echo -e "  ${YELLOW}→${NC} $guidance"
    read -rp "  Value (press Enter to skip): " value

    if [ -n "$value" ]; then
        # Add or update in env file
        if grep -q "^export $var=" "$ARKA_ENV_FILE" 2>/dev/null; then
            sed -i '' "s|^export $var=.*|export $var=\"$value\"|" "$ARKA_ENV_FILE"
        else
            echo "export $var=\"$value\"" >> "$ARKA_ENV_FILE"
        fi
        CONFIGURED=$((CONFIGURED + 1))
        echo -e "  ${GREEN}✓${NC} Saved"
    else
        SKIPPED=$((SKIPPED + 1))
        echo -e "  ${YELLOW}⏭${NC} Skipped"
    fi
    echo ""
done

# Source env in shell RC (with duplicate check)
if [ -f "$ARKA_ENV_FILE" ]; then
    if ! grep -q 'source.*\.arka-os/\.env' "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# ARKA OS Environment" >> "$SHELL_RC"
        echo '[ -f "$HOME/.arka-os/.env" ] && source "$HOME/.arka-os/.env"' >> "$SHELL_RC"
        echo -e "${GREEN}✓${NC} Added env sourcing to $SHELL_RC"
    fi
fi

# ─── Capability Detection ────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}[Capability Detection]${NC}"
# Source env so capabilities check sees the new keys
[ -f "$ARKA_ENV_FILE" ] && source "$ARKA_ENV_FILE"

CAPS_SCRIPT="$SCRIPT_DIR/departments/kb/scripts/kb-check-capabilities.sh"
if [ -f "$CAPS_SCRIPT" ]; then
    bash "$CAPS_SCRIPT" 2>/dev/null
elif [ -f "$HOME/.claude/skills/arka-knowledge/scripts/kb-check-capabilities.sh" ]; then
    bash "$HOME/.claude/skills/arka-knowledge/scripts/kb-check-capabilities.sh" 2>/dev/null
else
    echo -e "  ${YELLOW}⚠${NC} Capability check script not found — run install.sh first"
fi

echo ""
echo -e "${GREEN}═══ Environment Setup Complete ═══${NC}"
echo -e "  Service keys: ${CYAN}${SERVICE_CONFIGURED}${NC} configured"
echo -e "  MCP keys:     ${CYAN}${CONFIGURED}${NC} configured, ${CYAN}${SKIPPED}${NC} skipped"
echo -e "  Env file:     ${CYAN}${ARKA_ENV_FILE}${NC}"
echo -e "  Capabilities: ${CYAN}${ARKA_ENV_DIR}/capabilities.json${NC}"
echo ""
echo -e "Run ${CYAN}source ~/.zshrc${NC} to load the new variables."
echo -e "${GREEN}══════════════════════════════════${NC}"
