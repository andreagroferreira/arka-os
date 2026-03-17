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

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
AGENTS_DIR="$HOME/.claude/agents"
ARKA_OS_DIR="$HOME/.claude/skills/arka"
SHELL_RC="$HOME/.zshrc"

# ─── Curl Pipe Detection ─────────────────────────────────────────────────────
# If running via `curl ... | bash`, SOURCE_DIR won't contain the repo files.
# In that case, clone the repo to ~/.arka-os/repo and use that as SOURCE_DIR.
if [ ! -f "$SOURCE_DIR/VERSION" ]; then
    REPO_URL="https://github.com/andreagroferreira/arka-os.git"
    CLONE_DIR="$HOME/.arka-os/repo"
    echo ""
    echo -e "${BLUE}Downloading ARKA OS...${NC}"
    if [ -d "$CLONE_DIR/.git" ]; then
        git -C "$CLONE_DIR" fetch --quiet origin
        git -C "$CLONE_DIR" reset --hard origin/master --quiet
        echo -e "  ${GREEN}✓${NC} Updated existing download"
    else
        mkdir -p "$HOME/.arka-os"
        git clone --quiet "$REPO_URL" "$CLONE_DIR"
        echo -e "  ${GREEN}✓${NC} Downloaded ARKA OS"
    fi
    SOURCE_DIR="$CLONE_DIR"
fi

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

    # Remove MCP server
    [ -d "$ARKA_OS_DIR/mcp-server" ] && rm -rf "$ARKA_OS_DIR/mcp-server" && echo -e "  ${GREEN}✓${NC} Removed MCP server"

    # Remove arka-prompts from Claude Desktop config
    CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    if [ -f "$CLAUDE_DESKTOP_CONFIG" ] && command -v jq &>/dev/null; then
        jq 'del(.mcpServers["arka-prompts"])' "$CLAUDE_DESKTOP_CONFIG" > "$CLAUDE_DESKTOP_CONFIG.tmp" && \
            mv "$CLAUDE_DESKTOP_CONFIG.tmp" "$CLAUDE_DESKTOP_CONFIG" && \
            echo -e "  ${GREEN}✓${NC} Removed from Claude Desktop config"
    fi

    # Remove CLI commands
    [ -f "$HOME/.local/bin/arka" ] && rm "$HOME/.local/bin/arka" && echo -e "  ${GREEN}✓${NC} Removed arka CLI"
    [ -f "$HOME/.local/bin/arka-skill" ] && rm "$HOME/.local/bin/arka-skill" && echo -e "  ${GREEN}✓${NC} Removed arka-skill CLI"
    [ -f "$HOME/.local/bin/arka-doctor" ] && rm "$HOME/.local/bin/arka-doctor" && echo -e "  ${GREEN}✓${NC} Removed arka-doctor CLI"

    # Remove hooks from settings
    if [ -f "$HOME/.claude/settings.json" ] && command -v jq &>/dev/null; then
        jq 'del(.hooks)' "$HOME/.claude/settings.json" > "$HOME/.claude/settings.json.tmp" && \
            mv "$HOME/.claude/settings.json.tmp" "$HOME/.claude/settings.json" && \
            echo -e "  ${GREEN}✓${NC} Removed hooks from settings.json"
    fi

    # Remove session digests
    [ -d "$HOME/.arka-os/session-digests" ] && rm -rf "$HOME/.arka-os/session-digests" && echo -e "  ${GREEN}✓${NC} Removed session digests"

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

# ─── User Profile (Onboarding) ──────────────────────────────────────────────
echo -e "${BLUE}[User Profile]${NC}"
PROFILE_FILE="$HOME/.arka-os/profile.json"
mkdir -p "$HOME/.arka-os"

if [ "$INSTALL_MODE" = "update" ] && [ -f "$PROFILE_FILE" ]; then
    PROFILE_NAME=$(jq -r '.user_name // "unknown"' "$PROFILE_FILE" 2>/dev/null || echo "unknown")
    echo -e "  ${GREEN}✓${NC} Profile exists (${PROFILE_NAME})"
    echo -e "  Run ${CYAN}/arka setup${NC} to update your profile"
else
    echo ""
    echo -e "  ${CYAN}Let's personalize ARKA OS for you.${NC}"
    echo -e "  ${CYAN}Press Enter to skip any question and use the default value.${NC}"
    echo -e "  ${CYAN}Look for the ${YELLOW}>>>${CYAN} arrow when your input is needed.${NC}"
    echo ""

    read -rp "$(echo -e "  ${YELLOW}>>>${NC} What's your name? ")" P_NAME < /dev/tty
    P_NAME="${P_NAME:-}"

    read -rp "$(echo -e "  ${YELLOW}>>>${NC} Company name? ${CYAN}(default: WizardingCode)${NC} ")" P_COMPANY < /dev/tty
    P_COMPANY="${P_COMPANY:-WizardingCode}"

    echo -e "  ${BLUE}What's your role?${NC}"
    echo -e "    1) developer  2) founder  3) manager  4) agency  5) team-member"
    read -rp "$(echo -e "  ${YELLOW}>>>${NC} Pick 1-5, or type custom: ")" P_ROLE_CHOICE < /dev/tty
    case "$P_ROLE_CHOICE" in
        1) P_ROLE="developer" ;;
        2) P_ROLE="founder" ;;
        3) P_ROLE="manager" ;;
        4) P_ROLE="agency" ;;
        5) P_ROLE="team-member" ;;
        "") P_ROLE="" ;;
        *) P_ROLE="$P_ROLE_CHOICE" ;;
    esac

    echo -e "  ${BLUE}What industry?${NC}"
    echo -e "    1) SaaS  2) Agency  3) E-commerce  4) Services  5) Other"
    read -rp "$(echo -e "  ${YELLOW}>>>${NC} Pick 1-5, or type custom: ")" P_INDUSTRY_CHOICE < /dev/tty
    case "$P_INDUSTRY_CHOICE" in
        1) P_INDUSTRY="SaaS" ;;
        2) P_INDUSTRY="Agency" ;;
        3) P_INDUSTRY="E-commerce" ;;
        4) P_INDUSTRY="Services" ;;
        5) P_INDUSTRY="Other" ;;
        "") P_INDUSTRY="" ;;
        *) P_INDUSTRY="$P_INDUSTRY_CHOICE" ;;
    esac

    read -rp "$(echo -e "  ${YELLOW}>>>${NC} Projects directory? ${CYAN}(default: ~/Projects)${NC} ")" P_PROJECTS_DIR < /dev/tty
    P_PROJECTS_DIR="${P_PROJECTS_DIR:-$HOME/Projects}"
    # Expand ~ to $HOME
    P_PROJECTS_DIR="${P_PROJECTS_DIR/#\~/$HOME}"

    read -rp "$(echo -e "  ${YELLOW}>>>${NC} Documents directory? ${CYAN}(default: ~/Documents)${NC} ")" P_DOCS_DIR < /dev/tty
    P_DOCS_DIR="${P_DOCS_DIR:-$HOME/Documents}"
    P_DOCS_DIR="${P_DOCS_DIR/#\~/$HOME}"

    read -rp "$(echo -e "  ${YELLOW}>>>${NC} Main objectives? ${CYAN}(comma-separated, e.g.: launch SaaS, grow marketing)${NC} ")" P_OBJECTIVES_RAW < /dev/tty

    # Build objectives JSON array
    if [ -n "$P_OBJECTIVES_RAW" ]; then
        P_OBJECTIVES_JSON=$(echo "$P_OBJECTIVES_RAW" | jq -R 'split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))' 2>/dev/null || echo "[]")
    else
        P_OBJECTIVES_JSON="[]"
    fi

    # Save profile
    if command -v jq &>/dev/null; then
        jq -n \
            --arg name "$P_NAME" \
            --arg company "$P_COMPANY" \
            --arg role "$P_ROLE" \
            --arg industry "$P_INDUSTRY" \
            --arg projects "$P_PROJECTS_DIR" \
            --arg docs "$P_DOCS_DIR" \
            --argjson objectives "$P_OBJECTIVES_JSON" \
            --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            '{
                user_name: $name,
                company_name: $company,
                role: $role,
                industry: $industry,
                projects_dir: $projects,
                documents_dir: $docs,
                objectives: $objectives,
                preferred_departments: [],
                onboarded_at: $date,
                onboarding_version: "1"
            }' > "$PROFILE_FILE"
        echo ""
        echo -e "  ${GREEN}✓${NC} Profile saved to ~/.arka-os/profile.json"
    else
        # Fallback without jq — write raw JSON
        cat > "$PROFILE_FILE" << PROFILE_EOF
{
  "user_name": "$P_NAME",
  "company_name": "$P_COMPANY",
  "role": "$P_ROLE",
  "industry": "$P_INDUSTRY",
  "projects_dir": "$P_PROJECTS_DIR",
  "documents_dir": "$P_DOCS_DIR",
  "objectives": [],
  "preferred_departments": [],
  "onboarded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "onboarding_version": "1"
}
PROFILE_EOF
        echo ""
        echo -e "  ${GREEN}✓${NC} Profile saved to ~/.arka-os/profile.json"
    fi
fi

# ─── CLI Command ─────────────────────────────────────────────────────────────
echo -e "${BLUE}[CLI Command]${NC}"
mkdir -p "$HOME/.local/bin"
cp "$SOURCE_DIR/bin/arka" "$HOME/.local/bin/arka"
chmod +x "$HOME/.local/bin/arka"
cp "$SOURCE_DIR/bin/arka-skill" "$HOME/.local/bin/arka-skill"
chmod +x "$HOME/.local/bin/arka-skill"
cp "$SOURCE_DIR/bin/arka-doctor" "$HOME/.local/bin/arka-doctor"
chmod +x "$HOME/.local/bin/arka-doctor"
echo -e "  ${GREEN}✓${NC} arka CLI installed to ~/.local/bin/arka"
echo -e "  ${GREEN}✓${NC} arka-skill CLI installed to ~/.local/bin/arka-skill"
echo -e "  ${GREEN}✓${NC} arka-doctor CLI installed to ~/.local/bin/arka-doctor"

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
cp "$SOURCE_DIR/config/system-prompt.sh" "$SKILLS_DIR/arka/system-prompt.sh"
chmod +x "$SKILLS_DIR/arka/system-prompt.sh"
cp "$SOURCE_DIR/config/statusline.sh" "$SKILLS_DIR/arka/statusline.sh"
chmod +x "$SKILLS_DIR/arka/statusline.sh"
echo -e "  ${GREEN}✓${NC} arka (main orchestrator)"

# ─── Department Skills ──────────────────────────────────────────────────────
DEPARTMENTS=("dev" "marketing" "ecommerce" "finance" "operations" "strategy" "knowledge")
echo -e "${BLUE}[Departments]${NC}"
for dept in "${DEPARTMENTS[@]}"; do
    if [ -f "$SOURCE_DIR/departments/$dept/SKILL.md" ]; then
        dept_skill_name="arka-$dept"
        mkdir -p "$SKILLS_DIR/$dept_skill_name"
        cp "$SOURCE_DIR/departments/$dept/SKILL.md" "$SKILLS_DIR/$dept_skill_name/SKILL.md"
        # Copy bundled resources (scripts, references, assets) if they exist
        for resource_dir in scripts references assets; do
            if [ -d "$SOURCE_DIR/departments/$dept/$resource_dir" ]; then
                cp -r "$SOURCE_DIR/departments/$dept/$resource_dir" "$SKILLS_DIR/$dept_skill_name/"
            fi
        done
        echo -e "  ${GREEN}✓${NC} $dept"
    fi
done

# ─── Sub-Skills (scaffold, mcp, onboard, etc.) ───────────────────────────
echo -e "${BLUE}[Sub-Skills]${NC}"
SUB_SKILL_COUNT=0
for skill_dir in "$SOURCE_DIR"/departments/*/skills/*/; do
    if [ -f "${skill_dir}SKILL.md" ]; then
        skill_name="arka-$(basename "$skill_dir")"
        mkdir -p "$SKILLS_DIR/$skill_name"
        cp "${skill_dir}SKILL.md" "$SKILLS_DIR/$skill_name/SKILL.md"
        # Copy bundled resources (scripts, references, assets) if they exist
        for resource_dir in scripts references assets; do
            if [ -d "${skill_dir}$resource_dir" ]; then
                cp -r "${skill_dir}$resource_dir" "$SKILLS_DIR/$skill_name/"
            fi
        done
        echo -e "  ${GREEN}✓${NC} $(basename "$skill_dir")"
        SUB_SKILL_COUNT=$((SUB_SKILL_COUNT + 1))
    fi
done

# ─── Make KB Scripts Executable ────────────────────────────────────────────
if [ -d "$SKILLS_DIR/arka-knowledge/scripts" ]; then
    chmod +x "$SKILLS_DIR/arka-knowledge/scripts/"*.sh 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} KB scripts made executable"
fi

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

# ─── Agent Memory ──────────────────────────────────────────────────────────
echo -e "${BLUE}[Agent Memory]${NC}"
AGENT_MEMORY_DIR="$HOME/.claude/agent-memory"
AGENT_MEMORY_TEMPLATE="$SOURCE_DIR/config/agent-memory-template.md"
AGENT_MEMORY_COUNT=0
AGENT_NAMES=("cto" "tech-lead" "architect" "senior-dev" "frontend-dev" "security" "devops" "qa" "analyst" "cfo" "coo" "content-creator" "ecommerce-manager" "strategist" "knowledge-curator")
AGENT_DISPLAY_NAMES=("CTO Marco" "Tech Lead Paulo" "Architect Gabriel" "Senior Dev Andre" "Frontend Dev Diana" "Security Bruno" "DevOps Carlos" "QA Rita" "Analyst Lucas" "CFO Helena" "COO Sofia" "Content Creator Luna" "E-commerce Manager Ricardo" "Strategist Tomas" "Knowledge Curator Clara")

if [ -f "$AGENT_MEMORY_TEMPLATE" ]; then
    for i in "${!AGENT_NAMES[@]}"; do
        agent="${AGENT_NAMES[$i]}"
        display="${AGENT_DISPLAY_NAMES[$i]}"
        mem_dir="$AGENT_MEMORY_DIR/arka-$agent"
        mem_file="$mem_dir/MEMORY.md"
        mkdir -p "$mem_dir"
        if [ ! -f "$mem_file" ]; then
            sed -e "s|{{AGENT_NAME}}|$agent|g" \
                -e "s|{{AGENT_DISPLAY_NAME}}|$display|g" \
                -e "s|{{DATE}}|$(date +%Y-%m-%d)|g" \
                "$AGENT_MEMORY_TEMPLATE" > "$mem_file"
            AGENT_MEMORY_COUNT=$((AGENT_MEMORY_COUNT + 1))
        fi
    done
    if [ "$AGENT_MEMORY_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Created $AGENT_MEMORY_COUNT agent memory files"
    else
        echo -e "  ${GREEN}✓${NC} All $((${#AGENT_NAMES[@]})) agent memory files exist (preserved)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Agent memory template not found"
fi

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

# ─── ARKA Prompts MCP Server ──────────────────────────────────────────────
echo -e "${BLUE}[ARKA Prompts MCP]${NC}"
MCP_SERVER_SRC="$SOURCE_DIR/mcps/arka-prompts"
MCP_SERVER_DST="$SKILLS_DIR/arka/mcp-server"
if [ -d "$MCP_SERVER_SRC" ]; then
    mkdir -p "$MCP_SERVER_DST"
    cp "$MCP_SERVER_SRC/server.py" "$MCP_SERVER_DST/server.py"
    cp "$MCP_SERVER_SRC/commands.py" "$MCP_SERVER_DST/commands.py"
    cp "$MCP_SERVER_SRC/pyproject.toml" "$MCP_SERVER_DST/pyproject.toml"
    echo -e "  ${GREEN}✓${NC} MCP server files copied"

    # Replace placeholder in installed registry
    if [ -f "$SKILLS_DIR/arka/mcps/registry.json" ]; then
        sed -i '' "s|{{ARKA_PROMPTS_DIR}}|$MCP_SERVER_DST|g" "$SKILLS_DIR/arka/mcps/registry.json"
        echo -e "  ${GREEN}✓${NC} Registry placeholder replaced"
    fi

    # Install dependencies with uv (preferred) or pip fallback
    if command -v uv &>/dev/null; then
        (cd "$MCP_SERVER_DST" && uv sync --quiet 2>/dev/null) && \
            echo -e "  ${GREEN}✓${NC} Dependencies installed (uv)" || \
            echo -e "  ${YELLOW}⚠${NC} uv sync failed — will install on first run"
    elif command -v pip3 &>/dev/null; then
        pip3 install -q "mcp[cli]>=1.2.0" 2>/dev/null && \
            echo -e "  ${GREEN}✓${NC} Dependencies installed (pip)" || \
            echo -e "  ${YELLOW}⚠${NC} pip install failed — install manually: pip install 'mcp[cli]>=1.2.0'"
    else
        echo -e "  ${YELLOW}⚠${NC} Neither uv nor pip found — install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi

    # Claude Desktop integration (macOS)
    CLAUDE_DESKTOP_DIR="$HOME/Library/Application Support/Claude"
    CLAUDE_DESKTOP_CONFIG="$CLAUDE_DESKTOP_DIR/claude_desktop_config.json"
    if [ -d "$CLAUDE_DESKTOP_DIR" ]; then
        if command -v jq &>/dev/null; then
            # Create config if it doesn't exist
            if [ ! -f "$CLAUDE_DESKTOP_CONFIG" ]; then
                echo '{"mcpServers":{}}' > "$CLAUDE_DESKTOP_CONFIG"
            fi
            # Merge arka-prompts into Claude Desktop config
            MCP_ENTRY=$(jq -n \
                --arg dir "$MCP_SERVER_DST" \
                '{
                    "command": "uv",
                    "args": ["--directory", $dir, "run", "server.py"],
                    "env": {
                        "ARKA_OS": "'"$HOME"'/.claude/skills/arka"
                    }
                }')
            jq --argjson entry "$MCP_ENTRY" '.mcpServers["arka-prompts"] = $entry' \
                "$CLAUDE_DESKTOP_CONFIG" > "$CLAUDE_DESKTOP_CONFIG.tmp" && \
                mv "$CLAUDE_DESKTOP_CONFIG.tmp" "$CLAUDE_DESKTOP_CONFIG"
            echo -e "  ${GREEN}✓${NC} Claude Desktop config updated"
        else
            echo -e "  ${YELLOW}⚠${NC} jq not found — Claude Desktop config not updated"
        fi
    fi
else
    echo -e "  ${YELLOW}⚠${NC} MCP server source not found"
fi

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

# Copy ecosystems registry (preserve existing if present)
if [ -f "$SOURCE_DIR/knowledge/ecosystems.json" ]; then
    if [ ! -f "$SKILLS_DIR/arka/knowledge/ecosystems.json" ]; then
        cp "$SOURCE_DIR/knowledge/ecosystems.json" "$SKILLS_DIR/arka/knowledge/ecosystems.json"
        echo -e "  ${GREEN}✓${NC} Ecosystems registry (new)"
    else
        echo -e "  ${GREEN}✓${NC} Ecosystems registry (preserved)"
    fi
fi

# ─── Auto-detect Obsidian Vault ─────────────────────────────────────────────
OBSIDIAN_VAULT=""
FOUND_VAULTS=()
SEARCH_DIRS=(
    "$HOME/Documents"
    "$HOME"
    "$HOME/Obsidian"
    "$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents"
)
for dir in "${SEARCH_DIRS[@]}"; do
    [ -d "$dir" ] || continue
    while IFS= read -r vault_marker; do
        FOUND_VAULTS+=("$(dirname "$vault_marker")")
    done < <(find "$dir" -maxdepth 3 -name ".obsidian" -type d 2>/dev/null)
done

# Deduplicate vaults
UNIQUE_VAULTS=()
for v in "${FOUND_VAULTS[@]}"; do
    ALREADY=false
    for u in "${UNIQUE_VAULTS[@]}"; do
        [ "$v" = "$u" ] && ALREADY=true && break
    done
    $ALREADY || UNIQUE_VAULTS+=("$v")
done

if [ ${#UNIQUE_VAULTS[@]} -eq 1 ]; then
    OBSIDIAN_VAULT="${UNIQUE_VAULTS[0]}"
    echo -e "  ${GREEN}✓${NC} Obsidian vault auto-detected: $OBSIDIAN_VAULT"
elif [ ${#UNIQUE_VAULTS[@]} -gt 1 ]; then
    echo -e "  ${BLUE}Found multiple Obsidian vaults:${NC}"
    for i in "${!UNIQUE_VAULTS[@]}"; do
        echo -e "    ${CYAN}$((i+1)))${NC} ${UNIQUE_VAULTS[$i]}"
    done
    echo ""
    if [ -t 0 ] || [ -e /dev/tty ]; then
        read -rp "$(echo -e "  ${YELLOW}>>>${NC} Pick a vault (1-${#UNIQUE_VAULTS[@]}), or Enter to skip: ")" VAULT_CHOICE < /dev/tty 2>/dev/null
    else
        VAULT_CHOICE=""
    fi
    if [ -n "$VAULT_CHOICE" ] && [ "$VAULT_CHOICE" -ge 1 ] 2>/dev/null && [ "$VAULT_CHOICE" -le ${#UNIQUE_VAULTS[@]} ] 2>/dev/null; then
        OBSIDIAN_VAULT="${UNIQUE_VAULTS[$((VAULT_CHOICE-1))]}"
        echo -e "  ${GREEN}✓${NC} Using vault: $OBSIDIAN_VAULT"
    else
        echo -e "  ${YELLOW}⚠${NC} Skipped Obsidian vault selection (non-interactive)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} No Obsidian vaults found automatically"
    if [ -t 0 ] || [ -e /dev/tty ]; then
        read -rp "$(echo -e "  ${YELLOW}>>>${NC} Obsidian vault path (or Enter to skip): ")" MANUAL_VAULT < /dev/tty 2>/dev/null
    else
        MANUAL_VAULT=""
    fi
    if [ -n "$MANUAL_VAULT" ] && [ -d "$MANUAL_VAULT" ]; then
        OBSIDIAN_VAULT="$MANUAL_VAULT"
        echo -e "  ${GREEN}✓${NC} Using vault: $OBSIDIAN_VAULT"
    elif [ -n "$MANUAL_VAULT" ]; then
        echo -e "  ${RED}✗${NC} Directory not found: $MANUAL_VAULT"
    else
        echo -e "  ${YELLOW}⚠${NC} Skipped — you can configure this later in obsidian-config.json"
    fi
fi

# Update obsidian-config.json with detected vault path
if [ -n "$OBSIDIAN_VAULT" ] && [ -f "$SKILLS_DIR/arka/knowledge/obsidian-config.json" ]; then
    if command -v jq &>/dev/null; then
        jq --arg vp "$OBSIDIAN_VAULT" '.vault_path = $vp' "$SKILLS_DIR/arka/knowledge/obsidian-config.json" > "$SKILLS_DIR/arka/knowledge/obsidian-config.json.tmp"
        mv "$SKILLS_DIR/arka/knowledge/obsidian-config.json.tmp" "$SKILLS_DIR/arka/knowledge/obsidian-config.json"
    else
        # Fallback: use sed if jq is not available
        sed -i '' "s|\"vault_path\":.*|\"vault_path\": \"$OBSIDIAN_VAULT\",|" "$SKILLS_DIR/arka/knowledge/obsidian-config.json" 2>/dev/null || true
    fi
fi

# Replace vault placeholder in all installed skill files
if [ -n "$OBSIDIAN_VAULT" ]; then
    find "$SKILLS_DIR" -name "SKILL.md" -exec sed -i '' "s|{{OBSIDIAN_VAULT}}|$OBSIDIAN_VAULT|g" {} +
    # Also update knowledge INDEX
    if [ -f "$SKILLS_DIR/arka/knowledge/INDEX.md" ]; then
        sed -i '' "s|{{OBSIDIAN_VAULT}}|$OBSIDIAN_VAULT|g" "$SKILLS_DIR/arka/knowledge/INDEX.md"
    fi
    # Also update MCP registry (Obsidian vault path in args)
    if [ -f "$SKILLS_DIR/arka/mcps/registry.json" ]; then
        sed -i '' "s|{{OBSIDIAN_VAULT}}|$OBSIDIAN_VAULT|g" "$SKILLS_DIR/arka/mcps/registry.json"
    fi
    echo -e "  ${GREEN}✓${NC} Vault path applied to all skill files"
fi

# Set up Obsidian vault directories
if [ -n "$OBSIDIAN_VAULT" ] && [ -d "$OBSIDIAN_VAULT" ]; then

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
    echo -e "  ${YELLOW}⚠${NC} Obsidian vault not configured — vault directories not created"
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

# ─── Capability Detection ──────────────────────────────────────────────────
echo -e "${BLUE}[Capabilities]${NC}"
CAPS_SCRIPT="$SOURCE_DIR/departments/knowledge/scripts/kb-check-capabilities.sh"
if [ -f "$CAPS_SCRIPT" ]; then
    # Run silently, just show summary
    bash "$CAPS_SCRIPT" >/dev/null 2>&1 || true
    if [ -f "$HOME/.arka-os/capabilities.json" ] && command -v jq &>/dev/null; then
        T_METHOD=$(jq -r '.transcription.method // "none"' "$HOME/.arka-os/capabilities.json")
        T_NOTE=$(jq -r '.transcription.note // "Unknown"' "$HOME/.arka-os/capabilities.json")
        case "$T_METHOD" in
            local_whisper) echo -e "  ${GREEN}✓${NC} Transcription: $T_NOTE" ;;
            openai_api)    echo -e "  ${GREEN}✓${NC} Transcription: $T_NOTE" ;;
            none)          echo -e "  ${YELLOW}⚠${NC} Transcription: $T_NOTE" ;;
        esac
        echo -e "  ${GREEN}✓${NC} Capabilities written to ~/.arka-os/capabilities.json"
    else
        echo -e "  ${YELLOW}⚠${NC} Could not read capabilities (jq may be missing)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} Capability check script not found"
fi

# ─── ARKA OS Config Directory ─────────────────────────────────────────────
mkdir -p "$HOME/.arka-os"
mkdir -p "$HOME/.arka-os/media"

# ─── Pro Content ──────────────────────────────────────────────────────────
echo -e "${BLUE}[Pro Content]${NC}"
if [ -f "$HOME/.arka-os/pro/.pro-installed-commit" ]; then
    echo -e "  ${GREEN}✓${NC} Pro content installed"
    echo -e "  Run ${CYAN}bash pro-install.sh${NC} to update Pro content"
else
    echo -e "  ${YELLOW}→${NC} Pro content available — https://wizardingcode.com/arka-pro"
    echo -e "  Run ${CYAN}bash pro-install.sh${NC} to install"
fi

# ─── Hooks ────────────────────────────────────────────────────────────────
echo -e "${BLUE}[Hooks]${NC}"
HOOKS_DEST="$SKILLS_DIR/arka/hooks"
mkdir -p "$HOOKS_DEST"
if [ -d "$SOURCE_DIR/config/hooks" ]; then
    for hook_file in "$SOURCE_DIR"/config/hooks/*.sh; do
        [ -f "$hook_file" ] || continue
        cp "$hook_file" "$HOOKS_DEST/"
        chmod +x "$HOOKS_DEST/$(basename "$hook_file")"
        echo -e "  ${GREEN}✓${NC} $(basename "$hook_file")"
    done
else
    echo -e "  ${YELLOW}⚠${NC} No hooks found in source"
fi

# ─── Settings (Status Line + Hooks) ──────────────────────────────────────
echo -e "${BLUE}[Settings]${NC}"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"
STATUSLINE_PATH="$SKILLS_DIR/arka/statusline.sh"
HOOKS_DIR="$SKILLS_DIR/arka/hooks"

if command -v jq &>/dev/null; then
    # Build ARKA settings from template with resolved paths
    ARKA_SETTINGS=$(cat "$SOURCE_DIR/config/settings-template.json" 2>/dev/null | \
        sed "s|{{STATUSLINE_PATH}}|$STATUSLINE_PATH|g" | \
        sed "s|{{HOOKS_DIR}}|$HOOKS_DIR|g")

    # Validate template produced valid JSON
    if [ -z "$ARKA_SETTINGS" ] || ! echo "$ARKA_SETTINGS" | jq empty 2>/dev/null; then
        echo -e "  ${YELLOW}⚠${NC} Settings template produced invalid JSON — using field-by-field merge"
        ARKA_SETTINGS=""
    fi

    if [ -f "$CLAUDE_SETTINGS" ]; then
        if [ -n "$ARKA_SETTINGS" ]; then
            # Write ARKA settings to temp file to avoid process substitution issues
            ARKA_SETTINGS_TMP=$(mktemp)
            echo "$ARKA_SETTINGS" > "$ARKA_SETTINGS_TMP"
            # Recursive merge: ARKA values update, user values preserved
            if jq -s '.[0] * .[1]' "$CLAUDE_SETTINGS" "$ARKA_SETTINGS_TMP" > "$CLAUDE_SETTINGS.tmp" 2>/dev/null && \
               jq empty "$CLAUDE_SETTINGS.tmp" 2>/dev/null; then
                mv "$CLAUDE_SETTINGS.tmp" "$CLAUDE_SETTINGS"
                echo -e "  ${GREEN}✓${NC} Status line + hooks merged into settings.json"
            else
                rm -f "$CLAUDE_SETTINGS.tmp"
                echo -e "  ${YELLOW}⚠${NC} Merge failed — using field-by-field assignment"
                ARKA_SETTINGS=""
            fi
            rm -f "$ARKA_SETTINGS_TMP"
        fi

        # Fallback: field-by-field assignment if merge failed or ARKA_SETTINGS empty
        if [ -z "$ARKA_SETTINGS" ]; then
            jq --arg cmd "$STATUSLINE_PATH" \
               '.statusLine = {"type":"command","command":$cmd,"padding":2}' \
               "$CLAUDE_SETTINGS" > "$CLAUDE_SETTINGS.tmp" && mv "$CLAUDE_SETTINGS.tmp" "$CLAUDE_SETTINGS"
            jq --arg ups "$HOOKS_DIR/user-prompt-submit.sh" \
               --arg pc "$HOOKS_DIR/pre-compact.sh" \
               --arg ptu "$HOOKS_DIR/post-tool-use.sh" \
               '.hooks.UserPromptSubmit = [{"hooks":[{"type":"command","command":$ups,"timeout":10}]}] |
                .hooks.PreCompact = [{"hooks":[{"type":"command","command":$pc,"timeout":30}]}] |
                .hooks.PostToolUse = [{"hooks":[{"type":"command","command":$ptu,"timeout":5}]}]' \
               "$CLAUDE_SETTINGS" > "$CLAUDE_SETTINGS.tmp" && mv "$CLAUDE_SETTINGS.tmp" "$CLAUDE_SETTINGS"
            echo -e "  ${GREEN}✓${NC} Status line + hooks applied via field assignment"
        fi

        # Post-merge verification: ensure hooks exist, force-apply if missing
        if ! jq -e '.hooks.UserPromptSubmit' "$CLAUDE_SETTINGS" &>/dev/null; then
            echo -e "  ${YELLOW}⚠${NC} Hooks missing after merge — force-applying..."
            jq --arg ups "$HOOKS_DIR/user-prompt-submit.sh" \
               --arg pc "$HOOKS_DIR/pre-compact.sh" \
               --arg ptu "$HOOKS_DIR/post-tool-use.sh" \
               '.hooks.UserPromptSubmit = [{"hooks":[{"type":"command","command":$ups,"timeout":10}]}] |
                .hooks.PreCompact = [{"hooks":[{"type":"command","command":$pc,"timeout":30}]}] |
                .hooks.PostToolUse = [{"hooks":[{"type":"command","command":$ptu,"timeout":5}]}]' \
               "$CLAUDE_SETTINGS" > "$CLAUDE_SETTINGS.tmp" && mv "$CLAUDE_SETTINGS.tmp" "$CLAUDE_SETTINGS"
            echo -e "  ${GREEN}✓${NC} Hooks force-applied"
        fi
    else
        # Create new settings file
        if [ -n "$ARKA_SETTINGS" ]; then
            echo "$ARKA_SETTINGS" > "$CLAUDE_SETTINGS"
        else
            # Build from scratch with jq
            jq -n --arg cmd "$STATUSLINE_PATH" \
                  --arg ups "$HOOKS_DIR/user-prompt-submit.sh" \
                  --arg pc "$HOOKS_DIR/pre-compact.sh" \
                  --arg ptu "$HOOKS_DIR/post-tool-use.sh" \
                  '{
                    statusLine: {"type":"command","command":$cmd,"padding":2},
                    hooks: {
                      UserPromptSubmit: [{"hooks":[{"type":"command","command":$ups,"timeout":10}]}],
                      PreCompact: [{"hooks":[{"type":"command","command":$pc,"timeout":30}]}],
                      PostToolUse: [{"hooks":[{"type":"command","command":$ptu,"timeout":5}]}]
                    }
                  }' > "$CLAUDE_SETTINGS"
        fi
        echo -e "  ${GREEN}✓${NC} Settings file created with status line + hooks"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} jq not found — add statusLine and hooks manually to ~/.claude/settings.json"
fi

# ─── Install Manifest ─────────────────────────────────────────────────────
echo -e "${BLUE}[Install Manifest]${NC}"
MANIFEST_FILE="$HOME/.arka-os/install-manifest.json"
OLD_MANIFEST="$HOME/.arka-os/install-manifest.old.json"

# Save old manifest for update comparison
if [ -f "$MANIFEST_FILE" ] && [ "$INSTALL_MODE" = "update" ]; then
    cp "$MANIFEST_FILE" "$OLD_MANIFEST"
fi

if command -v jq &>/dev/null; then
    # Collect all installed files and their SHA256 checksums
    MANIFEST_FILES='{}'
    for f in \
        "$SKILLS_DIR/arka/SKILL.md" \
        "$SKILLS_DIR/arka/VERSION" \
        "$SKILLS_DIR/arka/statusline.sh" \
        "$SKILLS_DIR/arka/system-prompt.sh" \
        "$SKILLS_DIR/arka/version-check.sh" \
        "$HOME/.local/bin/arka" \
        "$HOME/.local/bin/arka-skill" \
        "$HOME/.local/bin/arka-doctor"
    do
        [ -f "$f" ] || continue
        HASH=$(shasum -a 256 "$f" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
        REL_PATH=$(echo "$f" | sed "s|$HOME|~|")
        MANIFEST_FILES=$(echo "$MANIFEST_FILES" | jq --arg k "$REL_PATH" --arg v "$HASH" '. + {($k): $v}')
    done

    # Add agent files
    for agent_file in "$AGENTS_DIR"/arka-*.md; do
        [ -f "$agent_file" ] || continue
        HASH=$(shasum -a 256 "$agent_file" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
        REL_PATH=$(echo "$agent_file" | sed "s|$HOME|~|")
        MANIFEST_FILES=$(echo "$MANIFEST_FILES" | jq --arg k "$REL_PATH" --arg v "$HASH" '. + {($k): $v}')
    done

    # Add hook files
    for hook_file in "$SKILLS_DIR/arka/hooks/"*.sh; do
        [ -f "$hook_file" ] || continue
        HASH=$(shasum -a 256 "$hook_file" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
        REL_PATH=$(echo "$hook_file" | sed "s|$HOME|~|")
        MANIFEST_FILES=$(echo "$MANIFEST_FILES" | jq --arg k "$REL_PATH" --arg v "$HASH" '. + {($k): $v}')
    done

    # Add department skill files
    for skill_md in "$SKILLS_DIR"/arka-*/SKILL.md; do
        [ -f "$skill_md" ] || continue
        HASH=$(shasum -a 256 "$skill_md" 2>/dev/null | cut -d' ' -f1 || echo "unknown")
        REL_PATH=$(echo "$skill_md" | sed "s|$HOME|~|")
        MANIFEST_FILES=$(echo "$MANIFEST_FILES" | jq --arg k "$REL_PATH" --arg v "$HASH" '. + {($k): $v}')
    done

    FILE_COUNT=$(echo "$MANIFEST_FILES" | jq 'length')
    jq -n \
        --arg ver "$ARKA_VERSION" \
        --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg mode "$INSTALL_MODE" \
        --argjson files "$MANIFEST_FILES" \
        '{
            version: $ver,
            installed_at: $date,
            install_mode: $mode,
            files: $files
        }' > "$MANIFEST_FILE"
    echo -e "  ${GREEN}✓${NC} Manifest written ($FILE_COUNT files tracked)"

    # On update: check for user-customized files
    if [ -f "$OLD_MANIFEST" ]; then
        CUSTOMIZED=0
        while IFS=$'\t' read -r key old_hash; do
            EXPANDED_PATH=$(echo "$key" | sed "s|^~|$HOME|")
            [ -f "$EXPANDED_PATH" ] || continue
            CURRENT_HASH=$(shasum -a 256 "$EXPANDED_PATH" 2>/dev/null | cut -d' ' -f1)
            if [ "$CURRENT_HASH" != "$old_hash" ]; then
                # File was customized by user — already overwritten, note it
                CUSTOMIZED=$((CUSTOMIZED + 1))
            fi
        done < <(jq -r '.files | to_entries[] | [.key, .value] | @tsv' "$OLD_MANIFEST" 2>/dev/null)
        if [ "$CUSTOMIZED" -gt 0 ]; then
            echo -e "  ${YELLOW}⚠${NC} $CUSTOMIZED file(s) had local changes (overwritten by update)"
        fi
        rm -f "$OLD_MANIFEST"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} jq not found — manifest not generated"
fi

# ─── Environment Setup ───────────────────────────────────────────────────
echo ""
if [ -t 0 ] || [ -e /dev/tty ]; then
    read -rp "$(echo -e "${YELLOW}>>>${NC} Configure API keys for MCPs? ${CYAN}(y/N)${NC} ")" SETUP_ENV < /dev/tty 2>/dev/null || SETUP_ENV="N"
else
    SETUP_ENV="N"
fi
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
echo -e "  Obsidian:     ${CYAN}${OBSIDIAN_VAULT:-not configured}${NC}"
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
echo -e "  ${CYAN}arka doctor${NC}                    Health check system"
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
