# ARKA OS — WizardingCode Company Operating System

> AI-Powered Company OS. One system. Multiple departments. Infinite capability.

## Identity

- **Company:** WizardingCode
- **System:** ARKA OS
- **Owner:** Andrea Groferreira
- **Purpose:** AI-augmented company operating system that manages development, marketing, e-commerce, finance, operations, and strategy through specialized departments and personas

## Core Principles

1. **One System, Many Departments** — Everything lives here. No scattered projects.
2. **Personas Are Team Members** — Each agent has a name, personality, expertise, and opinion.
3. **Knowledge Compounds** — Every interaction can grow the knowledge base.
4. **Context Is King** — Always read project CLAUDE.md before working on a project.
5. **Action Over Theory** — Every output must be actionable, not academic.
6. **Client-Ready Always** — Reports, proposals, code — ready to deliver without editing.

## Tech Stack (Default)

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Laravel 11 (PHP 8.3) | Primary backend framework |
| Frontend | Vue 3 (Composition API) + TypeScript | Always `<script setup>` |
| SSR/Full-stack | Nuxt 3 | For full-stack apps |
| Database | PostgreSQL (via Supabase) | Default DB |
| CSS | Tailwind CSS | Utility-first |
| Python | Python 3.11+ | Scripts, AI, automation |
| Deploy | Vercel / Azure | Depends on project |
| Auth | Laravel Sanctum / Supabase Auth | Depends on project |

## Coding Standards

- **Laravel:** Services + Repositories pattern, Form Requests, API Resources, Feature Tests
- **Vue/Nuxt:** Composition API only, TypeScript, composables for shared logic
- **Python:** Type hints, docstrings, virtual environments
- **Git:** Conventional commits, feature branches, PR reviews
- **Never:** Options API, raw SQL in controllers, business logic in controllers

## Department Commands

| Department | Prefix | Purpose |
|-----------|--------|---------|
| Core System | `/arka` | System-level commands (standup, monitor, status) |
| Development | `/dev` | Code, build, deploy, review |
| Marketing | `/mkt` | Social media, content, affiliates, ads |
| E-commerce | `/ecom` | Store management, products, optimization |
| Finance | `/fin` | Financial planning, investment, negotiation |
| Operations | `/ops` | Automations, tasks, emails, calendar |
| Strategy | `/strat` | Market analysis, brainstorming, planning |
| Knowledge | `/kb` | Learn, personas, search, apply |

## Active Projects

Check `projects/` directory for project-specific context. Each project has:
- `PROJECT.md` — Full context (client, stack, decisions, conventions)
- Project-specific overrides to global standards

## Memory System

- `knowledge/personas/` — Expert personas learned from content
- `knowledge/topics/` — Knowledge organized by subject
- `knowledge/sources/` — Raw transcriptions and source material
- `.claude/memory/` — Session-to-session memory

## MCP Integrations

Configured MCPs extend ARKA OS capabilities:
- **Supabase** — Database management
- **Shopify** — E-commerce stores
- **ClickUp** — Task management
- **Gmail** — Email communication
- **Google Calendar** — Scheduling
- **Google Drive** — Document storage
- **Canva** — Visual design
- **Context7** — Up-to-date library documentation
- **Chrome** — Browser automation
- **InvoiceExpress** — Invoicing

## How To Work

1. **Starting a task:** Read relevant department skill + project CLAUDE.md
2. **Making decisions:** Consult appropriate persona (CTO for tech, CFO for money)
3. **Learning something new:** Use `/kb learn` to add to knowledge base
4. **Cross-department work:** Skills can reference other departments
5. **Updating knowledge:** After completing work, update relevant memory files
