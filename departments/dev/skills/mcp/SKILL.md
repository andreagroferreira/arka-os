---
name: arka-dev-mcp
description: >
  MCP (Model Context Protocol) management for projects. Apply pre-configured MCP profiles,
  add or remove individual MCP servers, list all available MCPs from the registry, and check
  which MCPs are active in a project. Generates .mcp.json and .claude/settings.local.json.
  Use when user says "mcp", "apply mcp", "add mcp", "mcp status", "mcp list", "remove mcp",
  "model context protocol", "mcp profile", or wants to configure Claude Code integrations.
---

# MCP Management — ARKA OS Dev Department

Manage Model Context Protocol (MCP) servers for projects. MCPs extend Claude Code with external tool integrations.

## Commands

| Command | Description |
|---------|-------------|
| `/dev mcp apply <profile> [--project <path>]` | Apply MCP profile to a project |
| `/dev mcp add <name> [--project <path>]` | Add a single MCP to a project |
| `/dev mcp list` | Show all available MCPs from the registry |
| `/dev mcp status [--project <path>]` | Show active MCPs in a project |
| `/dev mcp remove <name> [--project <path>]` | Remove an MCP from a project |

## Profiles

| Profile | MCPs Included | Use For |
|---------|---------------|---------|
| `base` | obsidian, context7, playwright, memory-bank, sentry, gh-grep, clickup, firecrawl, supabase | All projects |
| `laravel` | base + laravel-boost, serena | Laravel backends |
| `nuxt` | base + nuxt, nuxt-ui | Nuxt 3/4 apps |
| `vue` | base + nuxt-ui | Vue 3 SPAs |
| `react` | base + next-devtools | React SPAs |
| `nextjs` | base + next-devtools, supabase | Next.js apps |
| `ecommerce` | base + laravel-boost, serena, mirakl, shopify-dev | E-commerce projects |
| `full-stack` | base + laravel-boost, serena, nuxt, nuxt-ui | Laravel + Nuxt apps |
| `comms` | base + slack, discord, whatsapp, teams | Messaging platforms |

## How It Works

### /dev mcp apply <profile>

1. Read the MCP registry at `mcps/registry.json`
2. Read the profile file at `mcps/profiles/<profile>.json`
3. Resolve base + profile MCPs (profiles extend base automatically)
4. Run the apply script:
   ```bash
   bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" <profile> --project <path>
   ```
5. This generates:
   - `.mcp.json` in the project root (MCP server definitions)
   - `.claude/settings.local.json` (enables MCPs + base permissions)
6. Report what was installed

### /dev mcp add <name>

Add a single MCP without applying a full profile:
```bash
bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" --add <name> --project <path>
```
This merges the new MCP into the existing `.mcp.json`.

### /dev mcp list

```bash
bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" --list
```

Shows all MCPs from the registry with their category and description.

### /dev mcp status

```bash
bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" --status --project <path>
```

Shows which MCPs are currently active in the project's `.mcp.json`.

### /dev mcp remove <name>

1. Read project's `.mcp.json`
2. Remove the specified MCP entry
3. Update `.claude/settings.local.json` to remove from `enabledMcpjsonServers`
4. Report the change

## Registry

The central MCP registry lives at `mcps/registry.json`. Each entry contains:
- `command` + `args` (for local MCPs) OR `type` + `url` (for HTTP MCPs)
- `category` — which profile group it belongs to
- `description` — what the MCP does
- `env` — required environment variables (if any)
- `required_env` — list of env var names that must be set

## Environment Variables

Some MCPs require API keys or configuration. These are defined in the registry's `env` field.
When applying MCPs that need env vars, the script will warn which ones need to be set.

The user should set these in their shell profile or project `.env`, or run `bash env-setup.sh`:
- `CLICKUP_API_KEY` / `CLICKUP_TEAM_ID` — ClickUp integration
- `FIRECRAWL_API_KEY` — Firecrawl web scraping
- `PG_HOST` / `PG_PORT` / `PG_USER` / `PG_PASSWORD` / `PG_DATABASE` — PostgreSQL direct access
- `DISCORD_TOKEN` — Discord bot integration
- `WHATSAPP_API_TOKEN` / `WHATSAPP_PHONE_ID` — WhatsApp Business API
- `TEAMS_APP_ID` / `TEAMS_APP_SECRET` — Microsoft Teams
