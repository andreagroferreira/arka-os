# arka-onboard — MCP Configuration & Registration

Referenced from SKILL.md. Read only when needed.

## Step 5: Determine MCP Profile

Map detected stack to MCP profile using the same mapping as scaffold:

| Detected Framework | MCP Profile |
|-------------------|-------------|
| Laravel | `laravel` |
| Laravel + ecommerce indicators | `ecommerce` |
| Nuxt | `nuxt` |
| Vue (without Nuxt) | `vue` |
| React (without Next) | `react` |
| Next.js | `nextjs` |
| Monorepo (Laravel + frontend) | `full-stack` |
| Other / Unknown | `base` |

## Step 6: Ecosystem Assignment

If `--ecosystem <name>` was provided:
1. Read `knowledge/ecosystems.json`
2. If ecosystem exists, add this project to it
3. If not, create the ecosystem and add this project

If no ecosystem flag, ask the user:
- "Create new ecosystem" → ask for name, then create
- "Join existing ecosystem" → show list, let user pick
- "Standalone (no ecosystem)" → skip

Ecosystem entry format:
```json
{
  "name": "project-name",
  "role": "api|frontend|admin|worker|docs|landing",
  "stack": "Laravel 11",
  "path": "/absolute/path/to/project"
}
```

## Step 7: User Confirmation

Present the analysis summary and ask to proceed:

```
═══ ARKA OS — Project Analysis ═══
Name:          <name>
Path:          <path>
Framework:     <framework> <version>
Language:      <language>
Architecture:  <type>
Stack:         <technologies>
Database:      <db>
Auth:          <auth>
Testing:       <testing>
Metrics:       <X> models, <Y> components, <Z> migrations, <W> tests
MCP Profile:   <profile> (<N> MCPs)
Ecosystem:     <ecosystem or "standalone">
Git:           <total commits>, <branches> branches, <contributors> contributors
═══════════════════════════════════

Proceed with onboarding? (Y/n)
```

## Step 8: Generate PROJECT.md

Create `PROJECT.md` in the project root with all detected context:

```markdown
# <name> — WizardingCode Project

## Stack
- **Framework:** <framework> <version>
- **Language:** <language>
- **Database:** <database>
- **Cache:** <cache>
- **Queue:** <queue>
- **Auth:** <auth>
- **Payments:** <payments>
- **CSS:** <css>
- **Testing:** <testing>

## Architecture
- **Type:** <monolith|api-only|monorepo|frontend-spa>
- **Patterns:** <Services, Repositories, etc.>

## Key Paths
- Models: `app/Models/`
- Controllers: `app/Http/Controllers/`
- Routes: `routes/`
- Migrations: `database/migrations/`
- Tests: `tests/`
- Components: `components/` or `src/components/`

## Conventions
- TypeScript: <yes/no>
- Linting: <ESLint/PHPStan/none>
- Formatting: <Prettier/none>
- Docker: <yes/no>

## Ecosystem
- **Ecosystem:** <name or "standalone">
- **Role:** <api/frontend/admin/worker>

## Current State
- Total commits: <N>
- Active branches: <list>
- Top contributors: <list>
- Last commit: <date and message>

## MCPs Active
- <list from applied profile>

## Decisions
- **Onboarded:** <date> via ARKA OS v<version>
- **MCP Profile:** <profile>
```

## Step 9: Register in ARKA OS

```bash
mkdir -p "$ARKA_OS/projects/<name>"
cp "<path>/PROJECT.md" "$ARKA_OS/projects/<name>/PROJECT.md"
echo "<absolute-path>" > "$ARKA_OS/projects/<name>/.project-path"
```

The `.project-path` file stores the absolute path so system commands like `/arka standup` can find and reference the actual project.

## Step 10: Apply MCP Profile

```bash
bash "$ARKA_OS/mcps/scripts/apply-mcps.sh" <profile> --project "<path>"
```

This generates `.mcp.json` and `.claude/settings.local.json` in the project.

## Step 11: Create Obsidian Documentation

Create pages in the Obsidian vault at `{{OBSIDIAN_VAULT}}`:

**Home page:** `Projects/<name>/Home.md`
```markdown
---
type: project
name: <name>
stack:
  - <framework>
  - <language>
status: active
date_created: <YYYY-MM-DD>
ecosystem: <ecosystem or null>
tags:
  - project
  - <framework-kebab-case>
---

# <name>

> Onboarded into ARKA OS on <date>

## Overview
- **Framework:** <framework>
- **Architecture:** <type>
- **Stack:** <technologies>

## Architecture
- [[<name> - Architecture]]

## Links
- Local: `<path>`
- ARKA OS: `projects/<name>/PROJECT.md`

---
*Part of the [[Projects MOC]]*
```

**Architecture overview:** `Projects/<name>/Architecture/Overview.md`
```markdown
---
type: adr-log
project: <name>
date_created: <YYYY-MM-DD>
tags:
  - architecture
  - adr
---

# Architecture — <name>

## ADR-000: Project Onboarded
- **Date:** <today>
- **Decision:** Onboarded existing project into ARKA OS
- **Stack:** <full stack details>
- **Architecture:** <type> with <patterns>
- **MCP Profile:** <profile>
```

**Update Projects MOC:** Append `- [[<name>]]` to the Active Projects section.

**Ecosystem MOC** (if ecosystem assigned): Create or update `Projects/Ecosystems/<ecosystem>.md`:
```markdown
---
type: ecosystem
name: <ecosystem>
date_updated: <YYYY-MM-DD>
tags:
  - ecosystem
  - project
---

# <ecosystem> Ecosystem

## Projects
| Project | Role | Stack | Path |
|---------|------|-------|------|
| [[<name>]] | <role> | <stack> | `<path>` |

---
*Part of the [[Projects MOC]]*
```

## Step 12: Report

```
═══ ARKA OS — Project Onboarded ═══
Name:          <name>
Framework:     <framework>
Architecture:  <type>
MCPs:          <count> active (<profile> profile)
Ecosystem:     <ecosystem or "standalone">
PROJECT.md:    <path>/PROJECT.md
Obsidian:      Projects/<name>/Home.md
════════════════════════════════════

Next steps:
  cd <path>
  /dev feature "describe your first feature"
  /dev review    (review current code)
```

## Ecosystem Subcommand Workflows

### /dev ecosystem list

1. Read `knowledge/ecosystems.json`
2. Display all ecosystems with their projects:

```
═══ ARKA OS — Ecosystems ═══
<ecosystem-name>
  • <project> (<role>) — <stack> — <path>
  • <project> (<role>) — <stack> — <path>

<ecosystem-name>
  • <project> (<role>) — <stack> — <path>
═════════════════════════════
```

### /dev ecosystem create <name>

1. Read `knowledge/ecosystems.json`
2. Create new ecosystem entry: `"<name>": { "projects": [] }`
3. Write back
4. Confirm creation

### /dev ecosystem add <project> --to <ecosystem>

1. Read `knowledge/ecosystems.json`
2. Read `projects/<project>/PROJECT.md` to get stack info
3. Read `projects/<project>/.project-path` to get path
4. Ask user for role (api/frontend/admin/worker/docs/landing)
5. Add to ecosystem
6. Write back
7. Update Ecosystem MOC in Obsidian

## Error Handling

- If path doesn't exist: suggest common directories, ask for correct path
- If already onboarded: show existing PROJECT.md, ask if re-onboard
- If no git repo: skip git analysis steps, warn user
- If detection script fails: fall back to manual file inspection
- If MCP apply fails: warn but continue (MCPs can be applied later)
- If Obsidian vault not configured: skip Obsidian steps, warn user
