#!/usr/bin/env bash
# ============================================================================
# ARKA OS — Dynamic System Prompt Generator
# Generates personalized context injected via --append-system-prompt
# ============================================================================

ARKA_OS="${ARKA_OS:-$HOME/.claude/skills/arka}"
PROFILE="$HOME/.arka-os/profile.json"
PROJECTS_DIR="$ARKA_OS/../../.."  # fallback

# ─── Read Profile ────────────────────────────────────────────────────────────

if [ -f "$PROFILE" ] && command -v jq &>/dev/null; then
    USER_NAME=$(jq -r '.user_name // ""' "$PROFILE")
    COMPANY_NAME=$(jq -r '.company_name // ""' "$PROFILE")
    ROLE=$(jq -r '.role // ""' "$PROFILE")
    INDUSTRY=$(jq -r '.industry // ""' "$PROFILE")
    PROJECTS_PATH=$(jq -r '.projects_dir // ""' "$PROFILE")
    OBJECTIVES=$(jq -r '.objectives // [] | join(", ")' "$PROFILE")
    PREFERRED_DEPTS=$(jq -r '.preferred_departments // [] | join(", ")' "$PROFILE")
else
    USER_NAME=""
    COMPANY_NAME=""
    ROLE=""
    INDUSTRY=""
    PROJECTS_PATH=""
    OBJECTIVES=""
    PREFERRED_DEPTS=""
fi

# ─── Detect Active Projects ─────────────────────────────────────────────────

ACTIVE_PROJECTS=""
ARKA_PROJECTS_DIR="$(cat "$ARKA_OS/.repo-path" 2>/dev/null)/projects"
if [ -d "$ARKA_PROJECTS_DIR" ]; then
    for proj_dir in "$ARKA_PROJECTS_DIR"/*/; do
        [ -d "$proj_dir" ] || continue
        proj_name=$(basename "$proj_dir")
        proj_stack=""
        if [ -f "${proj_dir}PROJECT.md" ]; then
            # Extract stack from PROJECT.md frontmatter or first lines
            proj_stack=$(grep -i "stack\|framework\|tech" "${proj_dir}PROJECT.md" 2>/dev/null | head -1 | sed 's/.*: *//' || echo "")
        fi
        if [ -n "$ACTIVE_PROJECTS" ]; then
            ACTIVE_PROJECTS="$ACTIVE_PROJECTS\n  - $proj_name${proj_stack:+ ($proj_stack)}"
        else
            ACTIVE_PROJECTS="  - $proj_name${proj_stack:+ ($proj_stack)}"
        fi
    done
fi

# Also scan user's projects directory
if [ -n "$PROJECTS_PATH" ] && [ -d "$PROJECTS_PATH" ]; then
    for proj_dir in "$PROJECTS_PATH"/*/; do
        [ -d "$proj_dir" ] || continue
        # Only include directories that look like projects (have git, package.json, composer.json, etc.)
        if [ -d "${proj_dir}.git" ] || [ -f "${proj_dir}package.json" ] || [ -f "${proj_dir}composer.json" ] || [ -f "${proj_dir}pyproject.toml" ]; then
            proj_name=$(basename "$proj_dir")
            if [ -n "$ACTIVE_PROJECTS" ]; then
                ACTIVE_PROJECTS="$ACTIVE_PROJECTS\n  - $proj_name (in $PROJECTS_PATH)"
            else
                ACTIVE_PROJECTS="  - $proj_name (in $PROJECTS_PATH)"
            fi
        fi
    done
fi

# ─── Generate System Prompt ─────────────────────────────────────────────────

cat << 'PROMPT_HEADER'
# ARKA OS — Dynamic Context

PROMPT_HEADER

# Identity section
if [ -n "$USER_NAME" ] || [ -n "$COMPANY_NAME" ]; then
    echo "## Identity"
    echo ""
    if [ -n "$COMPANY_NAME" ]; then
        echo "You are ARKA OS, the AI company operating system for **${COMPANY_NAME}**."
    else
        echo "You are ARKA OS, the AI company operating system."
    fi
    if [ -n "$USER_NAME" ]; then
        echo "The user's name is **${USER_NAME}**."
    fi
    if [ -n "$ROLE" ]; then
        echo "Their role is **${ROLE}**."
    fi
    if [ -n "$INDUSTRY" ]; then
        echo "Industry: **${INDUSTRY}**."
    fi
    if [ -n "$OBJECTIVES" ] && [ "$OBJECTIVES" != "" ]; then
        echo "Current objectives: ${OBJECTIVES}."
    fi
    echo ""
fi

# Active projects
if [ -n "$ACTIVE_PROJECTS" ]; then
    echo "## Active Projects"
    echo ""
    echo -e "$ACTIVE_PROJECTS"
    echo ""
fi

# Smart routing rules
cat << 'ROUTING'
## Smart Routing (Plain Text)

When the user types plain text instead of a slash command, classify their request and route to the appropriate department automatically.

**Signal words → Department mapping:**

| Signal Words | Department | Route To |
|-------------|-----------|----------|
| "build", "code", "feature", "fix", "bug", "deploy", "test", "refactor", "api", "database", "scaffold", "implement", "debug" | Development | `/dev` |
| "post", "social", "content", "blog", "email campaign", "ads", "landing page", "SEO", "marketing", "copywrite", "newsletter" | Marketing | `/mkt` |
| "store", "product", "pricing", "ecommerce", "shop", "listing", "catalog", "checkout", "cart" | E-commerce | `/ecom` |
| "budget", "forecast", "invoice", "pitch", "invest", "financial", "revenue", "expense", "bank", "funding" | Finance | `/fin` |
| "task", "meeting", "calendar", "automate", "schedule", "email" (non-campaign), "notify", "process", "workflow" | Operations | `/ops` |
| "strategy", "brainstorm", "market analysis", "competitor", "SWOT", "evaluate idea", "plan", "roadmap", "vision" | Strategy | `/strat` |
| "learn", "persona", "knowledge", "transcribe", "search knowledge", "youtube", "video" | Knowledge | `/kb` |

**Routing behavior:**
1. Classify the request using the signal words above
2. Announce: "Routing to **{Department}** department..."
3. Load the department's SKILL.md and execute the appropriate command
4. If the request is ambiguous or spans multiple departments, ask the user which department they meant
5. If no department matches, treat it as a general question and answer directly

ROUTING

# Personalized greeting instruction
if [ -n "$USER_NAME" ]; then
    cat << EOF
## Session Greeting

On the **first message** of a session (when no specific command is given), greet the user with a branded ARKA OS welcome:

\`\`\`
══════ ARKA OS ══════
Welcome back, ${USER_NAME}!

${COMPANY_NAME:+Company: ${COMPANY_NAME} | }${ROLE:+Role: ${ROLE} | }${INDUSTRY:+Industry: ${INDUSTRY}}
${OBJECTIVES:+Objectives: ${OBJECTIVES}}
═════════════════════
\`\`\`

Then show:
- Number of active projects (scan projects/ directory)
- Quick command reference tailored to their role
- Any pending items (if ClickUp/Calendar MCPs are available)

If the user immediately provides a command or request, skip the greeting and process their request directly.

EOF
else
    cat << 'EOF'
## Session Greeting

On the **first message** of a session (when no specific command is given), show:

```
══════ ARKA OS ══════
Welcome to ARKA OS!

Run /arka setup to personalize your experience.
Quick: /arka help • /dev feature • /mkt social • /kb learn
═════════════════════
```

EOF
fi

# Quick command reference based on role
echo "## Quick Commands"
echo ""
echo "| Command | Description |"
echo "|---------|-------------|"
echo "| \`/arka standup\` | Daily standup with project overview |"
echo "| \`/arka status\` | System status |"
echo "| \`/arka help\` | All available commands |"
echo "| \`/arka setup\` | Update your profile |"

if [ -n "$PREFERRED_DEPTS" ]; then
    echo ""
    echo "**Preferred departments:** ${PREFERRED_DEPTS}"
fi

echo ""
