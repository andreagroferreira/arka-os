---
name: dev/codebase-onboard
description: >
  Analyze an existing codebase and generate onboarding documentation: architecture, patterns, setup, key files.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Codebase Onboarding — `/dev codebase-onboard`

> **Agent:** Paulo (Dev Lead) | **Framework:** Developer Experience, Architecture Documentation

## What It Does

Analyzes an existing codebase to generate onboarding documentation. Maps architecture, identifies patterns, documents setup, and highlights key files a new developer needs to understand.

## Analysis Steps

| Step | What to Discover | How |
|------|-----------------|-----|
| 1. Stack Detection | Languages, frameworks, versions | `package.json`, `composer.json`, `pyproject.toml`, `Gemfile` |
| 2. Structure Map | Directory layout, entry points | Top-level dirs, `src/`, `app/`, config files |
| 3. Architecture | Patterns (MVC, DDD, microservices) | Folder naming, dependency injection, service layers |
| 4. Data Layer | Database, ORM, migrations | Schema files, models, migration history |
| 5. API Surface | Routes, controllers, endpoints | Route files, OpenAPI specs, Postman collections |
| 6. Testing | Test framework, coverage, conventions | Test dirs, config files, CI test steps |
| 7. DevOps | CI/CD, Docker, deployment | `.github/workflows/`, `Dockerfile`, deploy configs |
| 8. Key Files | Config, env, entry points | `.env.example`, main configs, bootstrap files |

## Audience Depth

| Audience | Focus | Skip |
|----------|-------|------|
| Junior Dev | Setup + guardrails + common tasks | Deep architecture rationale |
| Senior Dev | Architecture + patterns + operational concerns | Basic setup details |
| Contractor | Scoped ownership + integration boundaries | Internal team processes |

## Codebase Signals to Detect

| Signal | Files | Indicates |
|--------|-------|-----------|
| Laravel | `artisan`, `composer.json` (laravel/framework) | PHP backend, Eloquent ORM |
| Nuxt/Vue | `nuxt.config.ts`, `vue.config.js` | Vue frontend, SSR capable |
| Next.js | `next.config.js`, `app/` directory | React frontend, App Router |
| Docker | `Dockerfile`, `docker-compose.yml` | Containerized deployment |
| Monorepo | `turbo.json`, `nx.json`, `pnpm-workspace.yaml` | Multi-package workspace |

## Quality Checklist

- [ ] Setup instructions tested on clean environment
- [ ] All commands are copy-pasteable and time-bounded
- [ ] Architecture decisions documented with "why" not just "what"
- [ ] Key files listed with purpose explanation
- [ ] Common tasks documented (run tests, add feature, deploy)
- [ ] Troubleshooting section covers known gotchas

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No README or outdated README → flag onboarding barrier
- No local dev setup instructions → flag contributor friction
- Missing architecture diagram → flag understanding gap

## Output

```markdown
## Codebase Onboarding: <project-name>

### Stack
- **Backend:** Laravel 11 / PHP 8.3
- **Frontend:** Nuxt 3 / Vue 3 / TypeScript
- **Database:** PostgreSQL 16, Redis 7
- **Infrastructure:** Docker, GitHub Actions, AWS

### Architecture Overview
- Pattern: Service-Repository (thin controllers)
- Auth: Laravel Sanctum (SPA + API tokens)
- Queue: Redis-backed, Horizon dashboard

### Key Files
| File | Purpose |
|------|---------|
| `routes/api.php` | All API route definitions |
| `app/Services/` | Business logic layer |
| `app/Http/Requests/` | Form validation |
| `.env.example` | Required environment variables |

### Local Setup (estimated: 15 minutes)
1. `git clone <repo> && cd <project>`
2. `cp .env.example .env`
3. `composer install && npm install`
4. `php artisan key:generate`
5. `php artisan migrate --seed`
6. `npm run dev` (Vite dev server)
   Verify: `http://localhost:8000` loads

### Common Tasks
| Task | Command |
|------|---------|
| Run tests | `php artisan test` |
| Add migration | `php artisan make:migration` |
| Queue worker | `php artisan horizon` |
| Fresh seed | `php artisan migrate:fresh --seed` |

### Gotchas
- Redis must be running for queue/cache
- `.env` DB_HOST differs between Docker and Herd
- Run `npm run build` before testing SSR locally
```
