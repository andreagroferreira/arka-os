---
name: fovory
description: >
  Fovory ecosystem orchestrator. Supplier-to-Shopify integration engine with custom Laravel codebase
  (fovory-supplier-sync) AND Shopify store operations. Routes to dev squad for code work and
  operations/marketing squad for store management. 45 models, 74 actions, 1471 tests, AI module
  with providers/agents/personas/triggers, AI enrichment pipeline (auto-enrich entities with
  translations/SEO/GEO/AEO), supplier driver system (Foxway/Realtime/StockFirmati), product import
  system, variants CRUD, e-commerce settings. Use when user says "fovory", "supplier sync",
  "shopify", or wants to work on Fovory projects.
---

# Fovory Ecosystem Orchestrator — ARKA OS

Dedicated orchestrator for the Fovory ecosystem.
**Dual nature** — custom Laravel codebase (supplier sync engine) + Shopify store operations/marketing.

## Ecosystem Overview

| Project | Type | Stack | Path | Status |
|---------|------|-------|------|--------|
| **fovory-supplier-sync** | Supplier Integration Engine | Laravel 13 + Vue 3 + Inertia.js 3 + Nuxt UI 4 | `~/Herd/fovory-supplier-sync` | Active |
| **Fovory Shopify Store** | E-commerce Store | Shopify (millions of products) | Shopify Admin / MCP | Active |

## Squad (compact)

**Dev Squad (fovory-supplier-sync):** Tech Lead, Backend Dev (Laravel 13/PHP 8.4/Actions), Frontend Dev (Vue 3/Inertia/Nuxt UI 4), AI Specialist (Laravel AI SDK), Security Engineer (OWASP/Sanctum/Fortify), QA (Pest 5 + Playwright).

**Ops & Marketing Squad (Shopify):** Operations Manager (COO), E-Commerce Manager, Product Manager, Marketing Strategist, Content Creator, Ads Specialist, Email Marketing, SEO Specialist, Analytics Specialist, Pricing Strategist.

See `references/integration.md` for full role matrix, tech stack details, and integration mechanics.

## Routing

Auto-discoverable via `/arka do` or `/do`. Synapse routes "fovory", "supplier sync", "shopify store", "shopify operations" here. Direct invocation: `/fovory`.

## Commands

### Development (fovory-supplier-sync)

| Command | Description | Workflow |
|---------|-------------|----------|
| `/fovory <description>` | Auto-detect, plan, route | Auto |
| `/fovory feature <desc>` | New feature (full enterprise flow) | Enterprise |
| `/fovory forge <desc>` | Forge-plan complex feature | Forge + Enterprise |
| `/fovory debug <issue>` | Debug with root cause | Focused |
| `/fovory refactor <scope>` | Refactor + Clean Code audit | Focused |
| `/fovory review` | Code review of changes | Specialist |
| `/fovory test` | Run full Pest suite | Specialist |
| `/fovory plan <desc>` | Plan only (no code) | Planning |
| `/fovory status` | Branch, tests, commits, store overview | — |
| `/fovory docs` | Update Obsidian docs | — |
| `/fovory context` | Full ecosystem context | — |

### Store Operations (Shopify)

| Command | Description |
|---------|-------------|
| `/fovory products [import\|translate\|pricing]` | Catalog management |
| `/fovory marketing [plan\|social\|email\|ads]` | Marketing ops |
| `/fovory analytics` | Performance dashboard |
| `/fovory audit` | Full store audit (5 parallel agents) |
| `/fovory strategy <topic>` | Strategic analysis |
| `/fovory seo` | SEO audit |

## Workflow Tiers

| Tier | When | Phases |
|------|------|--------|
| **Enterprise** | Features, architecture, multi-file | 8 phases (0-7) |
| **Focused** | Bugs, refactors, store ops | 5 phases (1,2,3,5,7) |
| **Specialist** | Reviews, tests | 3 phases (4,5,7) |

Full phase-by-phase orchestration (Spec → Forge → Context → Analysis → Plan Approval → Execute → Self-Critique → Quality Gate → Report), `/fovory status` and `/fovory context` scripts, and the plan/report templates live in `references/workflows.md`.

## Quality Gate (NON-NEGOTIABLE)

Every workflow ends in Quality Gate. Marta (CQO) dispatches Eduardo (Copy) and Francisca (Tech/UX) in parallel. Binary APPROVED/REJECTED. REJECTED returns to Execution with specific feedback. See `references/workflows.md` for checklist detail.

## Project Conventions (fovory-supplier-sync) — NON-NEGOTIABLE

UDashboardPanel layout (never raw divs) · UModal forms (never USlideover) · Dropzone uploads (never native inputs) · `bun run build` (never npm) · Always paginate · Pest 5 + Playwright mandatory · `vendor/bin/pint --dirty --format agent` after PHP · Actions in `app/Actions/` · Form Requests for validation · Conventional commits (no Co-Authored-By) · One phase at a time, wait for approval · Spec before code · Browser-verify before done.

## References

- `references/workflows.md` — Full orchestration phases, plan/report templates, status & context commands, Quality Gate checklists.
- `references/integration.md` — Shopify integration mechanics, supplier pipelines, Laravel codebase specifics, tech stack, modules, marketing channels, analytics, Obsidian output paths.

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/Fovory/` (see `references/integration.md` for vault tree).
