---
name: dev
description: >
  Development department. Scaffolds projects, implements features, reviews code,
  manages APIs, testing, and deployment. Uses Laravel, Vue 3, Nuxt 3, Python.
  Use when user says "dev", "build", "code", "feature", "deploy", "test", "review".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Development Department — ARKA OS

Full-stack development team powered by specialized personas.

## Commands

| Command | Description | Personas Involved |
|---------|-------------|-------------------|
| `/dev scaffold <type>` | Generate new project structure | CTO + Senior Dev |
| `/dev feature <description>` | Implement a feature end-to-end | CTO + Senior Dev + QA |
| `/dev api <spec>` | Generate API endpoints + tests + docs | Senior Dev + QA |
| `/dev review` | Code review of current changes | CTO + QA |
| `/dev test` | Generate and run test suite | QA |
| `/dev deploy <env>` | Deploy to environment | DevOps |
| `/dev db <description>` | Database schema + migrations | Senior Dev |
| `/dev refactor <target>` | Refactor code with quality gates | CTO + Senior Dev |
| `/dev debug <issue>` | Diagnose and fix a bug | Senior Dev |
| `/dev docs` | Generate technical documentation | Senior Dev |
| `/dev stack-check` | Check for updates in project dependencies | DevOps + CTO |

## Workflow: /dev feature

1. **CTO** reads project CLAUDE.md/PROJECT.md → decides architecture approach
2. **Senior Dev** implements using project conventions:
   - Laravel: Migration → Model → Service → Controller → FormRequest → Resource → Routes
   - Vue/Nuxt: Composable → Component → Page → Route
3. **QA** generates tests (Feature tests for API, component tests for frontend)
4. **Senior Dev** runs tests and fixes failures
5. All output follows the project's established patterns

## Context Loading

Before ANY development command:
1. Detect which project we're in (check for PROJECT.md or CLAUDE.md)
2. Load project-specific stack, conventions, and patterns
3. Use Context7 MCP to fetch latest docs for the project's framework versions
4. Apply project standards, NOT global defaults (unless no project context)

## Stack Templates

| Type | Stack | Command |
|------|-------|---------|
| SaaS (Full-stack) | Nuxt 3 + Supabase + Tailwind | `/dev scaffold saas` |
| API Backend | Laravel 11 + PostgreSQL | `/dev scaffold api` |
| Frontend SPA | Vue 3 + TypeScript + Vite | `/dev scaffold spa` |
| Landing Page | Nuxt 3 + Tailwind | `/dev scaffold landing` |
| Python Service | FastAPI + PostgreSQL | `/dev scaffold python-api` |
