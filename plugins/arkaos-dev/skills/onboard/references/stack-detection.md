# arka-onboard — Stack Detection

Referenced from SKILL.md. Read only when needed.

## Step 1: Validate Path

```python
python3 "$ARKA_OS/../arka-onboard/scripts/detect-stack.py" "<path>" --json
```

If the path doesn't exist, resolve relative to `$HOME` or common project directories (`~/Herd/`, `~/Projects/`, `~/Code/`).

Check if already onboarded: look for `projects/<name>/PROJECT.md` in `$ARKA_OS`.

## Step 2: Auto-Detect Stack

Run the bundled detection script:

```bash
python3 "$(dirname "$0")/scripts/detect-stack.py" "<resolved-path>" --json
```

This returns a JSON report with:
- **Framework** — Laravel, Nuxt, Vue, React, Next.js, Django, FastAPI, etc.
- **Language** — PHP, TypeScript, Python, etc.
- **Stack** — full list of detected technologies
- **Database** — PostgreSQL, MySQL, SQLite, Supabase
- **Cache/Queue** — Redis, Horizon
- **Auth** — Sanctum, Passport, NextAuth, Supabase Auth
- **Payments** — Stripe, Paddle
- **CSS** — Tailwind, Sass, Nuxt UI, shadcn/ui
- **Testing** — Pest, PHPUnit, Vitest, Jest, Playwright
- **Architecture** — monolith, api-only, monorepo, frontend-spa
- **Patterns** — Services, Repositories, Actions, DTOs
- **Conventions** — TypeScript, ESLint, Prettier, PHPStan, Docker
- **Metrics** — models, controllers, migrations, components, pages, tests
- **MCP Profile** — recommended profile (laravel/nuxt/vue/react/nextjs/full-stack/base)

If the script is not available, detect manually by reading:
- `composer.json` — PHP/Laravel dependencies
- `package.json` — Node.js/frontend dependencies
- `nuxt.config.ts` / `next.config.ts` — framework config
- `.env.example` or `.env` — database, cache, queue, payment keys
- `docker-compose.yml` — infrastructure setup

## Step 3: Architecture Analysis

Glob the project directory to understand its structure:

```
# Laravel
app/Models/*.php         → count models
app/Http/Controllers/    → count controllers
database/migrations/     → count migrations
routes/*.php             → count route files
app/Services/            → Services pattern?
app/Repositories/        → Repository pattern?
tests/                   → count tests

# Frontend
components/**/*.vue|tsx  → count components
pages/**/*.vue|tsx       → count pages
composables/             → composables pattern?
stores/                  → state management?
```

Determine:
- **Monolith** — backend + frontend views in one repo
- **API-only** — backend without frontend views
- **Monorepo** — `api/` + `frontend/` or `apps/` + `packages/`
- **Frontend SPA** — no backend, just frontend

## Step 4: Git Analysis

Read-only git commands to understand project history:

```bash
git -C "<path>" remote -v                    # remotes
git -C "<path>" branch -a                    # branches
git -C "<path>" log --oneline -10            # recent commits
git -C "<path>" shortlog -sn --no-merges | head -5  # top contributors
git -C "<path>" rev-list --count HEAD        # total commits
```
