# ARKA OS — External Skill Standard

> How to create and distribute external skills for ARKA OS.

## Skill Structure

An external ARKA OS skill must contain:

```
my-skill/
  SKILL.md              (Required — Claude Code skill definition)
  arka-skill.json       (Required — metadata and version)
  agents/               (Optional — agent definitions)
    *.md
  mcps/                 (Optional — MCPs to register)
    registry-ext.json
  README.md             (Optional — documentation)
```

## Required Files

### SKILL.md

Standard Claude Code skill file with YAML frontmatter:

```markdown
---
name: arka-ext-<skill-name>
description: >
  Description of the skill.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# <Skill Name> — ARKA OS External Skill

## Commands
...

## Workflow
...
```

### arka-skill.json

Metadata file for the skill:

```json
{
  "name": "my-skill",
  "version": "1.0.0",
  "description": "What this skill does",
  "author": "author-name",
  "requires_arka_version": ">=0.2.0",
  "commands": ["/dev my-skill <action>"]
}
```

**Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Skill identifier (kebab-case) |
| `version` | Yes | Semantic version (X.Y.Z) |
| `description` | Yes | One-line description |
| `author` | Yes | Author name or GitHub username |
| `requires_arka_version` | No | Minimum ARKA OS version (e.g., `>=0.2.0`) |
| `commands` | No | List of commands the skill provides |

## Optional Files

### agents/*.md

Agent definitions that get installed as `arka-ext-<skill>-<agent>.md` in `~/.claude/agents/`.

### mcps/registry-ext.json

Additional MCP server definitions. Format matches the main ARKA OS registry. External MCPs are merged into the registry without overwriting built-in MCPs.

```json
{
  "mcpServers": {
    "my-custom-mcp": {
      "command": "npx",
      "args": ["-y", "my-custom-mcp"],
      "category": "external",
      "description": "What this MCP does",
      "required_env": ["MY_API_KEY"]
    }
  }
}
```

## Naming Convention

| Type | Prefix | Example |
|------|--------|---------|
| Built-in ARKA OS | `arka-` | `arka-cto.md`, `arka-dev/` |
| Pro content | `arka-pro-` | `arka-pro-growth-hacker.md` |
| External skill | `arka-ext-` | `arka-ext-geo-seo/`, `arka-ext-geo-seo-analyst.md` |

## Installation

### From GitHub

```bash
arka skill install https://github.com/username/my-skill.git
```

### What happens during installation

1. Repository is cloned to `~/.arka-os/ext-skills/<name>/`
2. `SKILL.md` and `arka-skill.json` are validated
3. `requires_arka_version` is checked against installed version
4. `SKILL.md` is copied to `~/.claude/skills/arka-ext-<name>/`
5. Agents are copied to `~/.claude/agents/arka-ext-<name>-<agent>.md`
6. External MCPs are merged into the registry (without overwriting built-in)
7. Skill is registered in `~/.arka-os/ext-registry.json`

## Management Commands

| Command | Description |
|---------|-------------|
| `arka skill install <url>` | Install from GitHub |
| `arka skill list` | List installed skills |
| `arka skill remove <name>` | Uninstall a skill |
| `arka skill update <name>` | Update to latest version |
| `arka skill create <name>` | Scaffold new skill from template |

Or via Claude Code:

| Command | Description |
|---------|-------------|
| `/dev skill add <url>` | Install from GitHub |
| `/dev skill list` | List installed skills |
| `/dev skill remove <name>` | Uninstall a skill |
| `/dev skill create <name>` | Scaffold new skill |

## Creating a New Skill

```bash
arka skill create my-new-skill
```

This generates a starter directory from the ARKA OS skill template.

## Distribution

1. Create a GitHub repository with the standard structure
2. Users install with: `arka skill install <github-url>`
3. Updates are pulled with: `arka skill update <name>`
