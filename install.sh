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

echo -e "${BLUE}Installing ARKA OS...${NC}"
echo ""

# Create directories
mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

# Install main orchestrator
echo -e "${BLUE}[Core]${NC}"
mkdir -p "$SKILLS_DIR/arka"
cp "$SOURCE_DIR/arka/SKILL.md" "$SKILLS_DIR/arka/SKILL.md"
echo -e "  ${GREEN}✓${NC} arka (main orchestrator)"

# Install department skills
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

# Install all agents from all departments
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

# Install knowledge base structure
echo -e "${BLUE}[Knowledge Base]${NC}"
mkdir -p "$SKILLS_DIR/arka/knowledge"
if [ -f "$SOURCE_DIR/knowledge/INDEX.md" ]; then
    cp "$SOURCE_DIR/knowledge/INDEX.md" "$SKILLS_DIR/arka/knowledge/INDEX.md"
    echo -e "  ${GREEN}✓${NC} Knowledge base initialized"
fi

# Check prerequisites
echo -e "${BLUE}[Prerequisites]${NC}"
command -v claude &>/dev/null && echo -e "  ${GREEN}✓${NC} Claude Code" || echo -e "  ${YELLOW}⚠${NC} Claude Code not found"
command -v yt-dlp &>/dev/null && echo -e "  ${GREEN}✓${NC} yt-dlp (video download)" || echo -e "  ${YELLOW}⚠${NC} yt-dlp not found — install: brew install yt-dlp"
command -v whisper &>/dev/null && echo -e "  ${GREEN}✓${NC} Whisper (transcription)" || echo -e "  ${YELLOW}⚠${NC} Whisper not found — install: pip install openai-whisper"
command -v ffmpeg &>/dev/null && echo -e "  ${GREEN}✓${NC} ffmpeg (audio processing)" || echo -e "  ${YELLOW}⚠${NC} ffmpeg not found — install: brew install ffmpeg"
command -v python3 &>/dev/null && echo -e "  ${GREEN}✓${NC} Python $(python3 --version 2>&1 | cut -d' ' -f2)" || echo -e "  ${RED}✗${NC} Python 3 not found"

# Summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ARKA OS Installed Successfully                             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Departments:  ${CYAN}${#DEPARTMENTS[@]}${NC} (dev, marketing, ecommerce, finance, ops, strategy, knowledge)"
echo -e "  Personas:     ${CYAN}${AGENT_COUNT}${NC}"
echo ""
echo -e "${BLUE}Quick Start:${NC}"
echo -e "  ${CYAN}/arka help${NC}              Show all commands"
echo -e "  ${CYAN}/arka standup${NC}           Daily standup"
echo -e "  ${CYAN}/dev feature \"...\"${NC}     Build a feature"
echo -e "  ${CYAN}/mkt social \"...\"${NC}      Create social content"
echo -e "  ${CYAN}/kb learn <url>${NC}         Learn from YouTube"
echo -e "  ${CYAN}/strat brainstorm${NC}       Brainstorming session"
echo ""
