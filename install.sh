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

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
AGENTS_DIR="$HOME/.claude/agents"
ARKA_OS_DIR="$HOME/.claude/skills/arka"
OBSIDIAN_VAULT="/Users/andreagroferreira/Documents/Personal"
SHELL_RC="$HOME/.zshrc"

# ─── Uninstall ────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--uninstall" ]; then
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ARKA OS — Uninstalling                                    ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Remove skills
    for skill_dir in "$SKILLS_DIR"/arka*; do
        [ -d "$skill_dir" ] && rm -rf "$skill_dir" && echo -e "  ${GREEN}✓${NC} Removed $(basename "$skill_dir")"
    done

    # Remove agents
    for agent_file in "$AGENTS_DIR"/arka-*.md; do
        [ -f "$agent_file" ] && rm "$agent_file" && echo -e "  ${GREEN}✓${NC} Removed $(basename "$agent_file")"
    done

    # Remove CLI commands
    [ -f "$HOME/.local/bin/arka" ] && rm "$HOME/.local/bin/arka" && echo -e "  ${GREEN}✓${NC} Removed arka CLI"
    [ -f "$HOME/.local/bin/arka-skill" ] && rm "$HOME/.local/bin/arka-skill" && echo -e "  ${GREEN}✓${NC} Removed arka-skill CLI"

    # Remove Pro content
    [ -d "$HOME/.arka-os/pro" ] && rm -rf "$HOME/.arka-os/pro" && echo -e "  ${GREEN}✓${NC} Removed Pro content"
    for pro_skill in "$SKILLS_DIR"/arka-pro-*; do
        [ -d "$pro_skill" ] && rm -rf "$pro_skill" && echo -e "  ${GREEN}✓${NC} Removed $(basename "$pro_skill")"
    done
    for pro_agent in "$AGENTS_DIR"/arka-pro-*.md; do
        [ -f "$pro_agent" ] && rm "$pro_agent" && echo -e "  ${GREEN}✓${NC} Removed $(basename "$pro_agent")"
    done

    # Remove external skills
    [ -d "$HOME/.arka-os/ext-skills" ] && rm -rf "$HOME/.arka-os/ext-skills" && echo -e "  ${GREEN}✓${NC} Removed external skills cache"
    for ext_skill in "$SKILLS_DIR"/arka-ext-*; do
        [ -d "$ext_skill" ] && rm -rf "$ext_skill" && echo -e "  ${GREEN}✓${NC} Removed $(basename "$ext_skill")"
    done
    for ext_agent in "$AGENTS_DIR"/arka-ext-*.md; do
        [ -f "$ext_agent" ] && rm "$ext_agent" && echo -e "  ${GREEN}✓${NC} Removed $(basename "$ext_agent")"
    done

    # Remove ARKA_OS export from shell
    if grep -q 'export ARKA_OS=' "$SHELL_RC" 2>/dev/null; then
        sed -i '' '/# ARKA OS/d' "$SHELL_RC"
        sed -i '' '/export ARKA_OS=/d' "$SHELL_RC"
        echo -e "  ${GREEN}✓${NC} Removed ARKA_OS from $SHELL_RC"
    fi
    if grep -q '# ARKA OS CLI' "$SHELL_RC" 2>/dev/null; then
        sed -i '' '/# ARKA OS CLI/d' "$SHELL_RC"
        sed -i '' '/\.local\/bin/d' "$SHELL_RC"
        echo -e "  ${GREEN}✓${NC} Removed CLI PATH from $SHELL_RC"
    fi

    echo ""
    echo -e "${GREEN}ARKA OS uninstalled.${NC} Obsidian vault content was not removed."
    echo ""
    exit 0
fi

# ─── Banner ───────────────────────────────────────────────────────────────────
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

# Detect update vs fresh install
if [ -d "$ARKA_OS_DIR" ]; then
    echo -e "${BLUE}Updating ARKA OS...${NC}"
    INSTALL_MODE="update"
else
    echo -e "${BLUE}Installing ARKA OS...${NC}"
    INSTALL_MODE="install"
fi
echo ""

# Create directories
mkdir -p "$SKILLS_DIR" "$AGENTS_DIR"

# ─── Environment Variable ─────────────────────────────────────────────────────
echo -e "${BLUE}[Environment]${NC}"
if ! grep -q 'export ARKA_OS=' "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# ARKA OS" >> "$SHELL_RC"
    echo "export ARKA_OS=\"$HOME/.claude/skills/arka\"" >> "$SHELL_RC"
    echo -e "  ${GREEN}✓${NC} Added ARKA_OS to $SHELL_RC"
else
    echo -e "  ${GREEN}✓${NC} ARKA_OS already in $SHELL_RC"
fi
export ARKA_OS="$HOME/.claude/skills/arka"

# ─── CLI Command ─────────────────────────────────────────────────────────────
echo -e "${BLUE}[CLI Command]${NC}"
mkdir -p "$HOME/.local/bin"
cp "$SOURCE_DIR/bin/arka" "$HOME/.local/bin/arka"
chmod +x "$HOME/.local/bin/arka"
cp "$SOURCE_DIR/bin/arka-skill" "$HOME/.local/bin/arka-skill"
chmod +x "$HOME/.local/bin/arka-skill"
echo -e "  ${GREEN}✓${NC} arka CLI installed to ~/.local/bin/arka"
echo -e "  ${GREEN}✓${NC} arka-skill CLI installed to ~/.local/bin/arka-skill"

# Ensure ~/.local/bin is in PATH
if ! echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin"; then
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# ARKA OS CLI" >> "$SHELL_RC"
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
        echo -e "  ${GREEN}✓${NC} Added ~/.local/bin to PATH in $SHELL_RC"
    fi
fi

# ─── Versioning ──────────────────────────────────────────────────────────────
echo -e "${BLUE}[Versioning]${NC}"
ARKA_VERSION=$(cat "$SOURCE_DIR/VERSION" 2>/dev/null || echo "unknown")
echo -e "  ${GREEN}✓${NC} ARKA OS v${ARKA_VERSION}"

# ─── Core ───────────────────────────────────────────────────────────────────
echo -e "${BLUE}[Core]${NC}"
mkdir -p "$SKILLS_DIR/arka"
cp "$SOURCE_DIR/arka/SKILL.md" "$SKILLS_DIR/arka/SKILL.md"
cp "$SOURCE_DIR/VERSION" "$SKILLS_DIR/arka/VERSION"
git -C "$SOURCE_DIR" rev-parse HEAD > "$SKILLS_DIR/arka/.installed-commit" 2>/dev/null || echo "unknown" > "$SKILLS_DIR/arka/.installed-commit"
echo "$SOURCE_DIR" > "$SKILLS_DIR/arka/.repo-path"
cp "$SOURCE_DIR/version-check.sh" "$SKILLS_DIR/arka/version-check.sh"
chmod +x "$SKILLS_DIR/arka/version-check.sh"
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

# ─── External Skills System ───────────────────────────────────────────────
echo -e "${BLUE}[External Skills]${NC}"
mkdir -p "$HOME/.arka-os"

# Copy ext-registry only if it doesn't exist (preserve user's installed skills)
if [ ! -f "$HOME/.arka-os/ext-registry.json" ]; then
    cp "$SOURCE_DIR/ext-registry.json" "$HOME/.arka-os/ext-registry.json"
    echo -e "  ${GREEN}✓${NC} External skills registry (new)"
else
    echo -e "  ${GREEN}✓${NC} External skills registry (preserved)"
fi

# Copy skill template
mkdir -p "$SKILLS_DIR/arka/skill-template"
for tmpl in "$SOURCE_DIR"/skill-template/*; do
    if [ -f "$tmpl" ]; then
        cp "$tmpl" "$SKILLS_DIR/arka/skill-template/"
    fi
done
echo -e "  ${GREEN}✓${NC} Skill template"

# Count external skills
EXT_SKILL_COUNT=$(jq '.skills | length' "$HOME/.arka-os/ext-registry.json" 2>/dev/null || echo "0")
if [ "$EXT_SKILL_COUNT" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} $EXT_SKILL_COUNT external skill(s) installed"
fi

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
    mkdir -p "$OBSIDIAN_VAULT/🧠 Knowledge Base/Frameworks"
    mkdir -p "$OBSIDIAN_VAULT/🧠 Knowledge Base/Raw Transcripts"
    echo -e "  ${GREEN}✓${NC} Obsidian vault directories created"

    # Create MOC pages if they don't exist
    MOC_COUNT=0

    if [ ! -f "$OBSIDIAN_VAULT/Personas MOC.md" ]; then
        cat > "$OBSIDIAN_VAULT/Personas MOC.md" << 'MOCEOF'
---
type: moc
title: Personas MOC
date_created: 2026-03-15
tags:
  - "moc"
  - "persona"
---

# Personas MOC

> Map of Content — All learned expert personas in the knowledge base.

## Personas

*Add persona links here as they are created via `/kb learn`.*

## By Expertise

### Marketing & Sales
*Personas focused on marketing, sales, and growth.*

### Technology & Development
*Personas focused on tech, coding, and engineering.*

### Business & Strategy
*Personas focused on business strategy and leadership.*

### Finance & Investment
*Personas focused on finance, investing, and economics.*

---
*Part of ARKA OS Knowledge Base — [[WizardingCode MOC]]*
MOCEOF
        MOC_COUNT=$((MOC_COUNT + 1))
    fi

    if [ ! -f "$OBSIDIAN_VAULT/Topics MOC.md" ]; then
        cat > "$OBSIDIAN_VAULT/Topics MOC.md" << 'MOCEOF'
---
type: moc
title: Topics MOC
date_created: 2026-03-15
tags:
  - "moc"
  - "topic"
---

# Topics MOC

> Map of Content — All knowledge topics with cross-persona perspectives.

## Topics

*Add topic links here as they are created via `/kb learn`.*

---
*Part of ARKA OS Knowledge Base — [[WizardingCode MOC]]*
MOCEOF
        MOC_COUNT=$((MOC_COUNT + 1))
    fi

    if [ ! -f "$OBSIDIAN_VAULT/Sources MOC.md" ]; then
        cat > "$OBSIDIAN_VAULT/Sources MOC.md" << 'MOCEOF'
---
type: moc
title: Sources MOC
date_created: 2026-03-15
tags:
  - "moc"
  - "source"
---

# Sources MOC

> Map of Content — All processed source materials (videos, articles, books).

## Videos
*Links to processed YouTube video sources.*

## Articles
*Links to processed article sources.*

---
*Part of ARKA OS Knowledge Base — [[WizardingCode MOC]]*
MOCEOF
        MOC_COUNT=$((MOC_COUNT + 1))
    fi

    if [ ! -f "$OBSIDIAN_VAULT/Projects MOC.md" ]; then
        cat > "$OBSIDIAN_VAULT/Projects MOC.md" << 'MOCEOF'
---
type: moc
title: Projects MOC
date_created: 2026-03-15
tags:
  - "moc"
  - "project"
---

# Projects MOC

> Map of Content — All WizardingCode projects.

## Active Projects

*Add project links here as they are scaffolded via `/dev scaffold`.*

## Completed Projects

*Move projects here when completed.*

---
*Part of ARKA OS — [[WizardingCode MOC]]*
MOCEOF
        MOC_COUNT=$((MOC_COUNT + 1))
    fi

    if [ ! -f "$OBSIDIAN_VAULT/WizardingCode MOC.md" ]; then
        cat > "$OBSIDIAN_VAULT/WizardingCode MOC.md" << 'MOCEOF'
---
type: moc
title: WizardingCode MOC
date_created: 2026-03-15
tags:
  - "moc"
  - "wizardingcode"
---

# WizardingCode MOC

> Map of Content — WizardingCode company hub.

## Departments

- [[Projects MOC]] — All projects
- [[Personas MOC]] — Expert personas from knowledge base
- [[Topics MOC]] — Knowledge topics
- [[Sources MOC]] — Processed source materials

## Operations

- `WizardingCode/Marketing/` — Marketing department output
- `WizardingCode/Ecommerce/` — E-commerce department output
- `WizardingCode/Finance/` — Finance department output
- `WizardingCode/Operations/` — Operations department output
- `WizardingCode/Strategy/` — Strategy department output

---
*ARKA OS — WizardingCode Company Operating System*
MOCEOF
        MOC_COUNT=$((MOC_COUNT + 1))
    fi

    if [ $MOC_COUNT -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Created $MOC_COUNT MOC pages in vault"
    else
        echo -e "  ${GREEN}✓${NC} MOC pages already exist"
    fi
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

# ─── ARKA OS Config Directory ─────────────────────────────────────────────
mkdir -p "$HOME/.arka-os"

# ─── Pro Content ──────────────────────────────────────────────────────────
echo -e "${BLUE}[Pro Content]${NC}"
if [ -f "$HOME/.arka-os/pro/.pro-installed-commit" ]; then
    echo -e "  ${GREEN}✓${NC} Pro content installed"
    echo -e "  Run ${CYAN}bash pro-install.sh${NC} to update Pro content"
else
    echo -e "  ${YELLOW}→${NC} Pro content available — https://wizardingcode.com/arka-pro"
    echo -e "  Run ${CYAN}bash pro-install.sh${NC} to install"
fi

# ─── Environment Setup ───────────────────────────────────────────────────
echo ""
read -rp "$(echo -e "${BLUE}Configure API keys for MCPs? (y/N): ${NC}")" SETUP_ENV
if [ "$SETUP_ENV" = "y" ] || [ "$SETUP_ENV" = "Y" ]; then
    bash "$SOURCE_DIR/env-setup.sh"
fi

# ─── Summary ────────────────────────────────────────────────────────────────
echo ""
if [ "$INSTALL_MODE" = "update" ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ARKA OS Updated Successfully                               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
else
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ARKA OS Installed Successfully                             ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
fi
echo ""
echo -e "  Version:      ${CYAN}${ARKA_VERSION}${NC}"
echo -e "  Departments:  ${CYAN}${#DEPARTMENTS[@]}${NC} (dev, marketing, ecommerce, finance, ops, strategy, knowledge)"
echo -e "  Sub-Skills:   ${CYAN}${SUB_SKILL_COUNT}${NC} (scaffold, mcp)"
echo -e "  Personas:     ${CYAN}${AGENT_COUNT}${NC}"
echo -e "  MCP Registry: ${CYAN}${MCP_COUNT:-?}${NC} MCPs, ${CYAN}${PROFILE_COUNT}${NC} profiles"
echo -e "  Obsidian:     ${CYAN}${OBSIDIAN_VAULT}${NC}"
echo -e "  ARKA_OS:      ${CYAN}\$HOME/.claude/skills/arka${NC}"
echo -e "  CLI:          ${CYAN}~/.local/bin/arka${NC}"
echo ""
if [ "$INSTALL_MODE" = "install" ]; then
    echo -e "${YELLOW}NOTE:${NC} Run ${CYAN}source ~/.zshrc${NC} or open a new terminal for \$ARKA_OS to take effect."
    echo ""
fi
echo -e "${BLUE}Quick Start:${NC}"
echo -e "  ${CYAN}arka${NC}                           Open Claude with ARKA OS"
echo -e "  ${CYAN}arka --version${NC}                 Show version"
echo -e "  ${CYAN}arka update${NC}                    Update ARKA OS"
echo -e "  ${CYAN}/arka help${NC}                    Show all commands"
echo -e "  ${CYAN}/arka standup${NC}                 Daily standup"
echo -e "  ${CYAN}/dev scaffold laravel myapp${NC}   New Laravel project"
echo -e "  ${CYAN}/dev mcp list${NC}                 Show available MCPs"
echo -e "  ${CYAN}/dev feature \"...\"${NC}           Build a feature"
echo -e "  ${CYAN}/mkt social \"...\"${NC}            Create social content"
echo -e "  ${CYAN}/kb learn <url>${NC}               Learn from YouTube"
echo -e "  ${CYAN}/strat brainstorm${NC}             Brainstorming session"
echo ""
echo -e "${BLUE}Uninstall:${NC}"
echo -e "  ${CYAN}bash install.sh --uninstall${NC}"
echo ""
