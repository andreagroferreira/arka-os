---
name: arka-rothbard100
description: >
  Rothbard 100 ecosystem orchestrator. Dedicated command for all Rothbard 100 event work.
  Routes tasks to specialized squad roles (PM, frontend developer, content creator,
  SEO/marketing, security engineer, QA tester, DevOps). Presents execution plans for
  approval before proceeding. Currently manages 1 project: rothbard100-landing (Nuxt 4
  landing page for libertarian event celebrating Murray Rothbard's centenary, Porto, 27 Jun 2026).
  Organized by Cataláxia EDITORA. Hosted on Cloudflare Pages.
  Use when user says "rothbard100", "rothbard", or wants to work on any Rothbard 100 project.
---

# Rothbard 100 Ecosystem Orchestrator — ARKA OS

Dedicated orchestrator for all Rothbard 100 event platform work. The Rothbard 100 is a libertarian event celebrating the 100th anniversary of Murray Rothbard, organized by Cataláxia EDITORA.

## Ecosystem Overview

| Project | Type | Stack | Path |
|---------|------|-------|------|
| **rothbard100-landing** | Landing Page (SSG) | Nuxt 4.4.2 + Nuxt UI v4.5.1 + Tailwind CSS 4 + TypeScript | `/Users/andreagroferreira/Work/rothbard100-landing` |

### Event Details

| Property | Value |
|----------|-------|
| Date | 27 Junho 2026, 09:00 (GMT+1) |
| Location | Porto, Portugal |
| Organizer | Cataláxia EDITORA |
| Contact | parcerias@rothbard100.pt |

### Future Projects (Planned)

| Project | Type | Status |
|---------|------|--------|
| rothbard100-registration | Registration App | planned |
| rothbard100-crm | Event CRM | planned |

## Commands

| Command | Description |
|---------|-------------|
| `/rothbard100 <description>` | Describe what you need — orchestrator analyzes, plans, and routes |
| `/rothbard100 status` | Status of all Rothbard 100 projects |
| `/rothbard100 plan <description>` | Plan only (no code) |
| `/rothbard100 feature <description>` | Implement a feature |
| `/rothbard100 debug <issue>` | Debug an issue |
| `/rothbard100 review` | Code review |
| `/rothbard100 test` | Run tests |
| `/rothbard100 deploy <env>` | Deploy |
| `/rothbard100 content <description>` | Create/update landing page copy and content |
| `/rothbard100 seo` | SEO audit and optimization |
| `/rothbard100 docs` | Update Obsidian documentation |
| `/rothbard100 context` | Show full ecosystem context |
| `/rothbard100 scaffold <name>` | Scaffold a new project into the ecosystem |

## Squad (Compact)

| Role | Agent Type | Specialty |
|------|-----------|-----------|
| Project Manager | `tech-lead` | Sprint planning, task breakdown, plan presentation |
| Frontend Developer | `frontend-dev` | Nuxt 4, Vue 3, TypeScript, Tailwind CSS 4, Nuxt UI 4 |
| Content Creator | `content-marketer` | Copy, messaging, event storytelling |
| SEO/Marketing | `cro-specialist` | Landing page optimization, conversion, meta tags |
| Security Engineer | `security-eng` | XSS, CSP, form validation, data protection |
| QA Tester | `qa-eng` | Vitest, Playwright, responsive testing, performance |
| DevOps | `devops-eng` | Cloudflare Pages deployment, CI/CD, CDN |

Full squad routing details: see `references/squad.md`.

## Brand Identity

| Property | Value |
|----------|-------|
| Primary Color | `#FFC939` (gold / amber) |
| Secondary Color | `#000000` (black) |
| Theme | Dark, premium, revolutionary |
| Font | Inter (400–900) |
| Mode | Light only (forced via colorMode) |
| Tone | Bold, intellectual, freedom-focused |

## Constitution (NON-NEGOTIABLE)

| Rule | Enforcement |
|------|-------------|
| `branch-isolation` | Feature branches or worktrees, never direct on main |
| `spec-driven` | Spec before implementation (features, APIs, components) |
| `solid-clean-code` | SOLID + Clean Code on all code |
| `mandatory-qa` | Build must pass. Tests where applicable. |
| `quality-gate` | Marta + Eduardo + Francisca APPROVE before delivery |
| `conventional-commits` | feat:, fix:, etc. |
| `no-mechanical-copy` | Content Creator adapts — never copy-paste user text |
| `self-critique` | Self-critique phase before presenting |
| `auto-deploy` | Push to main triggers Cloudflare Pages. Never manual deploy. |

## Complexity Routing

| Tier | Examples | Workflow |
|------|----------|----------|
| Quick | Status check, typo fix, single config | Direct execution |
| Standard | Content update, SEO change, component, bug fix | Standard Workflow (8 phases) |
| Complex | New feature, architecture change, multi-locale overhaul | Forge → Standard Workflow |

Complex tasks invoke `/arka-forge` first for multi-perspective planning before execution.

## References

- `references/workflows.md` — 8-phase orchestration workflow, status/content/seo/context/scaffold flows, execution report templates
- `references/squad.md` — Full squad routing details, architectural notes, components, tech stack, conventions, Obsidian output

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/Rothbard100/`
