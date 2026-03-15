#!/bin/bash
# ============================================================================
# ARKA OS Pro — Premium Content Installer
# Installs Pro agents, skills, and knowledge packs from the private repo.
# ============================================================================
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PRO_REPO="git@github.com:wizardingcode/arka-os-pro.git"
PRO_DIR="$HOME/.arka-os/pro"
SKILLS_DIR="$HOME/.claude/skills"
AGENTS_DIR="$HOME/.claude/agents"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  ARKA OS Pro — Premium Content Installer                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Ensure base directories exist
mkdir -p "$HOME/.arka-os" "$SKILLS_DIR" "$AGENTS_DIR"

# Step 1: Check SSH access to private repo
echo -e "${BLUE:-}Checking access to Pro repository...${NC}"
if ! git ls-remote "$PRO_REPO" &>/dev/null; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  Access denied to ARKA OS Pro repository.                   ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "To get access to ARKA OS Pro:"
    echo -e "  1. Visit ${CYAN}https://wizardingcode.com/arka-pro${NC}"
    echo -e "  2. Complete your purchase"
    echo -e "  3. Add your SSH key to the private repo"
    echo -e "  4. Run this script again"
    echo ""
    exit 1
fi

# Step 2: Clone or pull
if [ -d "$PRO_DIR/.git" ]; then
    echo -e "Updating Pro content..."
    cd "$PRO_DIR" && git pull --ff-only
else
    echo -e "Cloning Pro content..."
    git clone "$PRO_REPO" "$PRO_DIR"
fi

# Step 3: Install Pro skills
SKILL_COUNT=0
if [ -d "$PRO_DIR/skills" ]; then
    for skill_dir in "$PRO_DIR"/skills/*/; do
        if [ -f "${skill_dir}SKILL.md" ]; then
            skill_name="arka-pro-$(basename "$skill_dir")"
            mkdir -p "$SKILLS_DIR/$skill_name"
            cp -r "${skill_dir}"* "$SKILLS_DIR/$skill_name/"
            echo -e "  ${GREEN}✓${NC} Skill: $(basename "$skill_dir")"
            SKILL_COUNT=$((SKILL_COUNT + 1))
        fi
    done
fi

# Step 4: Install Pro agents
AGENT_COUNT=0
if [ -d "$PRO_DIR/agents" ]; then
    for agent_file in "$PRO_DIR"/agents/*.md; do
        if [ -f "$agent_file" ]; then
            agent_name="arka-pro-$(basename "$agent_file")"
            cp "$agent_file" "$AGENTS_DIR/$agent_name"
            echo -e "  ${GREEN}✓${NC} Agent: $(basename "$agent_file" .md)"
            AGENT_COUNT=$((AGENT_COUNT + 1))
        fi
    done
fi

# Step 5: Install knowledge packs
KB_COUNT=0
if [ -d "$PRO_DIR/knowledge" ]; then
    mkdir -p "$SKILLS_DIR/arka/knowledge"
    for pack in "$PRO_DIR"/knowledge/*.json; do
        if [ -f "$pack" ]; then
            cp "$pack" "$SKILLS_DIR/arka/knowledge/"
            echo -e "  ${GREEN}✓${NC} Knowledge: $(basename "$pack" .json)"
            KB_COUNT=$((KB_COUNT + 1))
        fi
    done
fi

# Step 6: Track installation
git -C "$PRO_DIR" rev-parse HEAD > "$HOME/.arka-os/pro/.pro-installed-commit"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ARKA OS Pro — Installed Successfully                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Skills:     ${CYAN}${SKILL_COUNT}${NC}"
echo -e "  Agents:     ${CYAN}${AGENT_COUNT}${NC}"
echo -e "  Knowledge:  ${CYAN}${KB_COUNT}${NC}"
echo ""
