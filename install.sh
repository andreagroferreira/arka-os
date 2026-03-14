#!/bin/bash
# ============================================================================
# ARKA OS — Claude Code Installation
# WizardingCode Company Operating System
# ============================================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}║${NC}   ${GREEN}█████╗ ██████╗ ██╗  ██╗ █████╗      ██████╗ ███████╗${NC}      ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${GREEN}██╔══██╗██╔══██╗██║ ██╔╝██╔══██╗    ██╔═══██╗██╔════╝${NC}     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${GREEN}███████║██████╔╝█████╔╝ ███████║    ██║   ██║███████╗${NC}     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${GREEN}██╔══██║██╔══██╗██╔═██╗ ██╔══██║    ██║   ██║╚════██║${NC}     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${GREEN}██║  ██║██║  ██║██║  ██╗██║  ██║    ╚██████╔╝███████║${NC}     ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}   ${GREEN}╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝     ╚═════╝ ╚══════╝${NC}     ${CYAN}║${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}║${NC}   ${YELLOW}WizardingCode Company Operating System${NC}                     ${CYAN}║${NC}"
echo -e "${CYAN}║                                                              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
AGENTS_DIR="$HOME/.claude/agents"
OBSIDIAN_VAULT="/Users/andreagroferreira/Documents/Personal"

echo -e "${BLUE}Installing ARKA OS...${NC}"
echo ""

# Create directories
mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

# ─── Core ───────────────────────────────────────────────────────────────────
echo -e "${BLUE}[Core]${NC}"
mkdir -p "$SKILLS_DIR/arka"
cp "$SOURCE_DIR/arka/SKILL.md" "$SKILLS_DIR/arka/SKILL.md"
echo -e "  ${GREEN}✓${NC} arka (main orchestrator)"

# ─── Department Skills ──────────────────────────────────────────────────────
DEPARTMENTS=("dev" "marketing" "ecommerce" "finance" "operations" "strategy" "knowledge")
echo -e "${BLUE}[Departments]${NC}"
for dept in "${DEPARTMENTS[@]}"; do
    if [ -f "$SOURCE_DIR/departments/$dept/SKILL.md" ]; then
        dept_skill_name="arka-$dept"
        mkdir -p "$SKILLS_DIR/$dept_skill_name"
        cp "$SOURCE_DIR/departments/$dept/SKILL.md" "$SKILLS_DIR/$dept_skill_name/SKILL.md"
        echo -e "  ${GREEN}✓${NC} $dept"
    fi
done

# ─── Sub-Skills (scaffold, mcp) ────────────────────────────────────────────
echo -e "${BLUE}[Sub-Skills]${NC}"
SUB_SKILL_COUNT=0
for skill_dir in "$SOURCE_DIR"/departments/*/skills/*/; do
    if [ -f "${skill_dir}SKILL.md" ]; then
        skill_name="arka-$(basename "$skill_dir")"
        mkdir -p "$SKILLS_DIR/$skill_name"
        cp "${skill_dir}SKILL.md" "$SKILLS_DIR/$skill_name/SKILL.md"
        echo -e "  ${GREEN}✓${NC} $(basename "$skill_dir")"
        SUB_SKILL_COUNT=$((SUB_SKILL_COUNT + 1))
    fi
done

# ─── Personas (Agents) ─────────────────────────────────────────────────────
echo -e "${BLUE}[Personas]${NC}"
AGENT_COUNT=0
for agent_file in "$SOURCE_DIR"/departments/*/agents/*.md; do
    if [ -f "$agent_file" ]; then
        agent_name="arka-$(basename "$agent_file" .md)"
        cp "$agent_file" "$AGENTS_DIR/$agent_name.md"
        echo -e "  ${GREEN}✓${NC} $(basename "$agent_file" .md)"
        AGENT_COUNT=$((AGENT_COUNT + 1))
    fi
done

# ─── MCP System ────────────────────────────────────────────────────────────
echo -e "${BLUE}[MCP System]${NC}"
mkdir -p "$SKILLS_DIR/arka/mcps/profiles" "$SKILLS_DIR/arka/mcps/stacks" "$SKILLS_DIR/arka/mcps/scripts"

# Copy registry
if [ -f "$SOURCE_DIR/mcps/registry.json" ]; then
    cp "$SOURCE_DIR/mcps/registry.json" "$SKILLS_DIR/arka/mcps/registry.json"
    MCP_COUNT=$(jq '.mcpServers | length' "$SOURCE_DIR/mcps/registry.json" 2>/dev/null || echo "?")
    echo -e "  ${GREEN}✓${NC} MCP registry ($MCP_COUNT MCPs)"
fi

# Copy profiles
PROFILE_COUNT=0
for profile in "$SOURCE_DIR"/mcps/profiles/*.json; do
    if [ -f "$profile" ]; then
        cp "$profile" "$SKILLS_DIR/arka/mcps/profiles/"
        PROFILE_COUNT=$((PROFILE_COUNT + 1))
    fi
done
echo -e "  ${GREEN}✓${NC} MCP profiles ($PROFILE_COUNT profiles)"

# Copy stacks
for stack in "$SOURCE_DIR"/mcps/stacks/*.json; do
    if [ -f "$stack" ]; then
        cp "$stack" "$SKILLS_DIR/arka/mcps/stacks/"
    fi
done
echo -e "  ${GREEN}✓${NC} Stack configurations"

# Copy scripts
for script in "$SOURCE_DIR"/mcps/scripts/*.sh; do
    if [ -f "$script" ]; then
        cp "$script" "$SKILLS_DIR/arka/mcps/scripts/"
        chmod +x "$SKILLS_DIR/arka/mcps/scripts/$(basename "$script")"
    fi
done
echo -e "  ${GREEN}✓${NC} MCP apply script"

# ─── Knowledge Base / Obsidian ──────────────────────────────────────────────
echo -e "${BLUE}[Knowledge Base / Obsidian]${NC}"
mkdir -p "$SKILLS_DIR/arka/knowledge"

if [ -f "$SOURCE_DIR/knowledge/INDEX.md" ]; then
    cp "$SOURCE_DIR/knowledge/INDEX.md" "$SKILLS_DIR/arka/knowledge/INDEX.md"
    echo -e "  ${GREEN}✓${NC} Knowledge base index"
fi

if [ -f "$SOURCE_DIR/knowledge/obsidian-config.json" ]; then
    cp "$SOURCE_DIR/knowledge/obsidian-config.json" "$SKILLS_DIR/arka/knowledge/obsidian-config.json"
    echo -e "  ${GREEN}✓${NC} Obsidian configuration"
fi

# Verify Obsidian vault
if [ -d "$OBSIDIAN_VAULT" ]; then
    echo -e "  ${GREEN}✓${NC} Obsidian vault found at $OBSIDIAN_VAULT"

    # Create ARKA OS directories in vault if they don't exist
    mkdir -p "$OBSIDIAN_VAULT/WizardingCode/Marketing"
    mkdir -p "$OBSIDIAN_VAULT/WizardingCode/Ecommerce"
    mkdir -p "$OBSIDIAN_VAULT/WizardingCode/Finance"
    mkdir -p "$OBSIDIAN_VAULT/WizardingCode/Operations"
    mkdir -p "$OBSIDIAN_VAULT/WizardingCode/Strategy"
    mkdir -p "$OBSIDIAN_VAULT/Personas"
    mkdir -p "$OBSIDIAN_VAULT/Sources/Videos"
    mkdir -p "$OBSIDIAN_VAULT/Sources/Articles"
    mkdir -p "$OBSIDIAN_VAULT/Topics"
    mkdir -p "$OBSIDIAN_VAULT/Projects"
    echo -e "  ${GREEN}✓${NC} Obsidian vault directories created"
else
    echo -e "  ${YELLOW}⚠${NC} Obsidian vault not found at $OBSIDIAN_VAULT"
fi

# Verify Obsidian MCP
if npx @bitbonsai/mcpvault@latest --help &>/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Obsidian MCP (mcpvault)"
else
    echo -e "  ${YELLOW}⚠${NC} Obsidian MCP — will be installed on first use (npx @bitbonsai/mcpvault)"
fi

# ─── Prerequisites ──────────────────────────────────────────────────────────
echo -e "${BLUE}[Prerequisites]${NC}"
command -v claude &>/dev/null && echo -e "  ${GREEN}✓${NC} Claude Code" || echo -e "  ${YELLOW}⚠${NC} Claude Code not found"
command -v jq &>/dev/null && echo -e "  ${GREEN}✓${NC} jq (JSON processing)" || echo -e "  ${YELLOW}⚠${NC} jq not found — install: brew install jq"
command -v yt-dlp &>/dev/null && echo -e "  ${GREEN}✓${NC} yt-dlp (video download)" || echo -e "  ${YELLOW}⚠${NC} yt-dlp not found — install: brew install yt-dlp"
command -v whisper &>/dev/null && echo -e "  ${GREEN}✓${NC} Whisper (transcription)" || echo -e "  ${YELLOW}⚠${NC} Whisper not found — install: pip install openai-whisper"
command -v ffmpeg &>/dev/null && echo -e "  ${GREEN}✓${NC} ffmpeg (audio processing)" || echo -e "  ${YELLOW}⚠${NC} ffmpeg not found — install: brew install ffmpeg"
command -v python3 &>/dev/null && echo -e "  ${GREEN}✓${NC} Python $(python3 --version 2>&1 | cut -d' ' -f2)" || echo -e "  ${RED}✗${NC} Python 3 not found"
command -v php &>/dev/null && echo -e "  ${GREEN}✓${NC} PHP $(php -v 2>&1 | head -1 | cut -d' ' -f2)" || echo -e "  ${YELLOW}⚠${NC} PHP not found"
command -v composer &>/dev/null && echo -e "  ${GREEN}✓${NC} Composer" || echo -e "  ${YELLOW}⚠${NC} Composer not found"
command -v pnpm &>/dev/null && echo -e "  ${GREEN}✓${NC} pnpm" || echo -e "  ${YELLOW}⚠${NC} pnpm not found — install: npm install -g pnpm"
command -v herd &>/dev/null && echo -e "  ${GREEN}✓${NC} Laravel Herd" || echo -e "  ${YELLOW}⚠${NC} Laravel Herd not found — https://herd.laravel.com"

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ARKA OS Installed Successfully                             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Departments:  ${CYAN}${#DEPARTMENTS[@]}${NC} (dev, marketing, ecommerce, finance, ops, strategy, knowledge)"
echo -e "  Sub-Skills:   ${CYAN}${SUB_SKILL_COUNT}${NC} (scaffold, mcp)"
echo -e "  Personas:     ${CYAN}${AGENT_COUNT}${NC}"
echo -e "  MCP Registry: ${CYAN}${MCP_COUNT:-?}${NC} MCPs, ${CYAN}${PROFILE_COUNT}${NC} profiles"
echo -e "  Obsidian:     ${CYAN}${OBSIDIAN_VAULT}${NC}"
echo ""
echo -e "${BLUE}Quick Start:${NC}"
echo -e "  ${CYAN}/arka help${NC}                    Show all commands"
echo -e "  ${CYAN}/arka standup${NC}                 Daily standup"
echo -e "  ${CYAN}/dev scaffold laravel myapp${NC}   New Laravel project"
echo -e "  ${CYAN}/dev mcp list${NC}                 Show available MCPs"
echo -e "  ${CYAN}/dev feature \"...\"${NC}           Build a feature"
echo -e "  ${CYAN}/mkt social \"...\"${NC}            Create social content"
echo -e "  ${CYAN}/kb learn <url>${NC}               Learn from YouTube"
echo -e "  ${CYAN}/strat brainstorm${NC}             Brainstorming session"
echo ""
