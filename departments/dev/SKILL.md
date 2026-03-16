---
name: dev
description: >
  Full-stack development department. Enterprise-grade 9-agent team with structured
  multi-phase workflows. Scaffolds projects, implements features with planning + research +
  architecture + security audit + self-critique, reviews code, generates APIs with tests,
  deploys to environments, manages MCP configurations, handles database migrations,
  debugging, refactoring, and technical documentation.
  Supports Laravel, Vue 3, Nuxt 3, React, Next.js, and Python.
  Use when user says "dev", "build", "code", "feature", "deploy", "test", "review", "scaffold",
  "mcp", "debug", "refactor", "api", "database", "migration", "docs", "stack-check", "plan",
  "security-audit", "research", "do", or any development-related task.
---

# Development Department — ARKA OS

Enterprise-grade development team powered by 9 specialized agents.

## Team

| # | Name | Role | File | Specialty |
|---|------|------|------|-----------|
| 1 | Marco | CTO | `agents/cto.md` | Architecture decisions, final technical authority |
| 2 | Paulo | Tech Lead (Orchestrator) | `agents/tech-lead.md` | Workflow management, TODO tracking, team coordination |
| 3 | Gabriel | Software Architect | `agents/architect.md` | System design, ADRs, API contracts |
| 4 | Andre | Senior Backend Developer | `agents/senior-dev.md` | Laravel, PHP, PostgreSQL, API implementation |
| 5 | Diana | Senior Frontend Developer | `agents/frontend-dev.md` | Vue 3, Nuxt 3, React, Next.js, TypeScript |
| 6 | Bruno | Security Engineer | `agents/security.md` | OWASP Top 10, threat modeling, security audits |
| 7 | Rita | QA Lead | `agents/qa.md` | Test strategy, quality gates, coverage analysis |
| 8 | Carlos | DevOps Lead | `agents/devops.md` | CI/CD, deployment, monitoring, infrastructure |
| 9 | Lucas | Technical Analyst | `agents/analyst.md` | Research, Context7 docs, KB integration |

## Commands

| Command | Description | Agents Involved | Tier |
|---------|-------------|-----------------|------|
| `/dev do <description>` | Smart orchestrator — interprets request, asks clarifying questions, routes to correct workflow | Paulo (routes to full team) | — |
| `/dev scaffold <type> <name>` | Create project from real git repos (see sub-skill) | Marco + Andre | — |
| `/dev feature <description>` | Implement a feature end-to-end | Full team (8 phases) | 1 |
| `/dev api <spec>` | Generate API endpoints + tests + docs | Full team (8 phases) | 1 |
| `/dev plan <description>` | Architecture planning only (no code) | Paulo + Gabriel + Lucas | 3 |
| `/dev debug <issue>` | Diagnose and fix a bug | Paulo + Andre/Diana + Rita | 2 |
| `/dev refactor <target>` | Refactor code with quality gates | Paulo + Marco + Andre/Diana | 2 |
| `/dev db <description>` | Database schema + migrations | Paulo + Lucas + Andre + Rita | 2 |
| `/dev review` | Code review of current changes | Marco + Bruno | 3 |
| `/dev test` | Generate and run test suite | Rita | 3 |
| `/dev deploy <env>` | Deploy to environment | Carlos | 3 |
| `/dev docs` | Generate technical documentation | Lucas | 3 |
| `/dev stack-check` | Check for updates in project dependencies | Carlos + Marco | 3 |
| `/dev security-audit` | Standalone security audit (read-only) | Bruno + Lucas | 3 |
| `/dev research <topic>` | Research a lib/framework/integration | Lucas | 3 |
| `/dev mcp apply <profile>` | Apply MCP profile to project (see sub-skill) | Carlos | — |
| `/dev mcp add <name>` | Add single MCP to current project | Carlos | — |
| `/dev mcp list` | Show all available MCPs from registry | Carlos | — |
| `/dev mcp status` | Show MCPs active in current project | Carlos | — |
| `/dev onboard <path>` | Onboard existing project into ARKA OS (see sub-skill) | Marco + Andre | — |
| `/dev onboard <path> --ecosystem <name>` | Onboard and assign to ecosystem | Marco + Andre | — |
| `/dev ecosystem list` | List all project ecosystems | Marco | — |
| `/dev ecosystem create <name>` | Create a new ecosystem | Marco | — |
| `/dev ecosystem add <project> --to <ecosystem>` | Add project to ecosystem | Marco | — |
| `/dev skill add <url>` | Install external skill from GitHub | Marco | — |
| `/dev skill list` | List installed external skills | Marco | — |
| `/dev skill remove <name>` | Remove external skill | Marco | — |
| `/dev skill create <name>` | Scaffold new skill from template | Marco + Andre | — |

## Workflow Tiers

Commands are classified by complexity:

| Tier | Phases | Commands |
|------|--------|----------|
| **Tier 1 — Full Enterprise** | 8 phases (research → architecture → implement → self-critique → security → QA → docs) | `/dev feature`, `/dev api` |
| **Tier 2 — Focused Team** | 3-4 phases (plan → implement → verify → wrap-up) | `/dev debug`, `/dev refactor`, `/dev db` |
| **Tier 3 — Single/Dual Agent** | 1-2 phases | `/dev review`, `/dev test`, `/dev deploy`, `/dev docs`, `/dev stack-check`, `/dev plan`, `/dev security-audit`, `/dev research` |

## Worktree Workflow (Mandatory)

ALL commands that modify project code MUST run inside a git worktree. This is NON-NEGOTIABLE.

### Commands that REQUIRE worktree:
- `/dev feature` — Feature implementation
- `/dev api` — API endpoint generation
- `/dev debug` — Bug investigation and fixing
- `/dev refactor` — Code refactoring
- `/dev db` — Database migrations and schema changes
- `/dev do` — Determined by the routed workflow (worktree if routed to feature/api/debug/refactor/db)

### Commands that do NOT require worktree (read-only or meta):
- `/dev scaffold` — Creates new projects (no existing code to isolate)
- `/dev onboard` — Registers existing projects
- `/dev review` — Code review (read-only)
- `/dev test` — Can run in main or worktree (depends on context)
- `/dev docs` — Documentation generation
- `/dev stack-check` — Dependency checks
- `/dev plan` — Architecture planning (no code)
- `/dev security-audit` — Security review (read-only)
- `/dev research` — Research (read-only)
- `/dev mcp *` — MCP configuration
- `/dev ecosystem *` — Ecosystem management
- `/dev skill *` — Skill management

### Workflow — Every code-modifying command:

**Step 0: Enter Worktree (BEFORE any code changes)**
Paulo uses the `EnterWorktree` tool with a descriptive name:
- `/dev feature "user auth"` → `EnterWorktree(name: "feature-user-auth")`
- `/dev debug "login crash"` → `EnterWorktree(name: "fix-login-crash")`
- `/dev refactor "controllers"` → `EnterWorktree(name: "refactor-controllers")`
- `/dev api "payments"` → `EnterWorktree(name: "feature-api-payments")`
- `/dev db "add user roles"` → `EnterWorktree(name: "feature-user-roles")`

### Branch naming convention:
| Command | Branch prefix | Example |
|---------|--------------|---------|
| `/dev feature` | `feature/` | `feature/user-auth` |
| `/dev api` | `feature/` | `feature/api-payments` |
| `/dev debug` | `fix/` | `fix/login-crash` |
| `/dev refactor` | `refactor/` | `refactor/controllers` |
| `/dev db` | `feature/` | `feature/user-roles-migration` |

## Stack Adaptation Matrix

Paulo detects the stack from PROJECT.md and adapts agent participation:

| Phase | Backend-only (Laravel) | Frontend-only (Vue/React/Nuxt) | Full-stack |
|-------|----------------------|-------------------------------|------------|
| Research | Lucas: Laravel docs | Lucas: Vue/React docs | Lucas: Both |
| Architecture | Gabriel: API + DB schema | Gabriel: Components + state | Gabriel: Full system |
| Implementation | Andre ONLY | Diana ONLY | Andre + Diana PARALLEL |
| Self-Critique | Andre: backend checklist | Diana: frontend checklist | Both checklists |
| Security | Bruno: SQL injection, auth, mass assignment | Bruno: XSS, CSRF, CSP | Bruno: Full scope |
| QA | Rita: Pest/PHPUnit | Rita: Vitest/Jest | Rita: Both suites |

## Workflow: /dev do (Smart Orchestrator)

Single entry point for all development tasks. Paulo interprets the request and routes to the correct workflow.

### Step 1: Context Loading (Paulo)
- Read PROJECT.md / CLAUDE.md to understand the project stack
- Read recent git log to understand current state

### Step 2: Request Interpretation (Paulo)
Classify the request into one of:

| Signal Words | Classification | Routes To |
|-------------|---------------|-----------|
| "add", "create", "implement", "build", "new" | Feature | `/dev feature` (Tier 1) |
| "fix", "bug", "broken", "error", "crash", "not working" | Debug | `/dev debug` (Tier 2) |
| "refactor", "clean up", "improve", "reorganize" | Refactor | `/dev refactor` (Tier 2) |
| "api", "endpoint", "route", "REST" | API | `/dev api` (Tier 1) |
| "database", "migration", "table", "column", "schema" | Database | `/dev db` (Tier 2) |
| "research", "compare", "evaluate", "which library" | Research | `/dev research` (Tier 3) |
| "plan", "design", "architect", "how should we" | Plan | `/dev plan` (Tier 3) |
| "review", "check code", "look at changes" | Review | `/dev review` (Tier 3) |
| "test", "tests", "coverage" | Test | `/dev test` (Tier 3) |
| "deploy", "ship", "release", "push to prod" | Deploy | `/dev deploy` (Tier 3) |

When multiple signals overlap, prefer the more specific classification (e.g., "add a new API endpoint" → API, not Feature).

### Step 3: Clarifying Questions (Paulo)
Use `AskUserQuestion` to fill any gaps:
- **Scope:** "Does this affect backend, frontend, or both?"
- **Approach:** "New system or extending the existing one?"
- **Constraints:** "Any specific library or approach preferences?"
- **Priority:** "Is this blocking something else?"

Only ask what's genuinely unclear — skip if the request is already specific enough.

### Step 4: Route & Execute (Paulo)
- Announce the routing: "Routing to `/dev feature` (Tier 1 — 8-phase enterprise workflow)"
- Pass enriched context (original description + clarification answers) to the target workflow
- Execute the full workflow of the target command — do not skip phases

## Workflow: /dev feature (Tier 1 — Full 8-Phase Enterprise)

### PHASE 1: ORCHESTRATION (Paulo — Tech Lead)
- Read project context (PROJECT.md, CLAUDE.md)
- Assess complexity, detect stack (backend/frontend/full-stack)
- Create TODO list with `TaskCreate` (one task per phase, with acceptance criteria)
- Enter worktree: `EnterWorktree(name: "feature-<slug>")`

### PHASE 2: RESEARCH (Lucas — Technical Analyst)
- Fetch relevant framework docs via Context7 MCP
- Search Obsidian KB for existing patterns and prior decisions
- Check codebase for similar implementations (Grep/Glob)
- Document findings and recommendations

### PHASE 3: ARCHITECTURE (Gabriel — Architect + Marco — CTO)
- Gabriel designs: data flow, API contracts, component hierarchy, schema changes
- Gabriel writes ADR → Obsidian: `Projects/<name>/Architecture/ADR-<NNN>.md`
- Marco reviews: security? scalability? maintainability?
- Marco approves or requests revision

### PHASE 4: IMPLEMENTATION (Andre — Backend + Diana — Frontend)
- Runs in parallel for full-stack projects (use Stack Adaptation Matrix)
- Andre: Migration → Model → Service → Controller → FormRequest → Resource → Routes
- Diana: Composable → Component → Page → Route
- Both read 2-3 similar files first, follow conventions exactly
- Use Context7 for any API uncertainty

### PHASE 5: SELF-CRITIQUE (Whole Team)
- Each developer reviews their own work against their checklist (see Self-Critique Checklists below)
- Gabriel: "Does implementation match the design?"
- Fix all issues found, document what was improved

### PHASE 6: SECURITY AUDIT (Bruno — Security Engineer)
- OWASP Top 10 check against new code
- Input validation, auth/authorization review
- Stack-specific checks (Laravel mass assignment, frontend XSS)
- Fix critical issues, document accepted risks

### PHASE 7: QUALITY ASSURANCE (Rita — QA Lead)
- Define test strategy based on feature scope
- Write tests: feature (API), unit (services), component (frontend)
- Run suite, generate coverage report
- Quality gate: pass/fail — fix failures until green

### PHASE 8: DOCUMENTATION & KB (Lucas + Paulo)
- Lucas: Save patterns to Obsidian KB, update project docs
- Paulo: Mark all TODOs complete, commit with conventional message
- Paulo: Final report with branch, files changed, tests, security status
- Suggest: "Run `/dev review` for code review, or create PR with `gh pr create`"

## Workflow: /dev api (Tier 1 — Full 8-Phase Enterprise)

Same 8 phases as `/dev feature` but API-focused:
- Phase 3: Gabriel focuses on API contracts, versioning, rate limiting
- Phase 4: Andre implements endpoints, Diana skips (unless API has a frontend component)
- Phase 6: Bruno focuses on auth, input validation, rate limiting, IDOR
- Phase 7: Rita writes comprehensive API feature tests (every endpoint, every error code)

## Workflow: /dev plan (Tier 3 — NEW)

Architecture planning only. No code changes, no worktree.

1. **Paulo** reads project context, assesses scope
2. **Lucas** researches relevant docs (Context7), existing patterns (KB + codebase)
3. **Gabriel** designs architecture: data flow, API contracts, component hierarchy
4. **Gabriel** writes ADR → Obsidian: `Projects/<name>/Architecture/ADR-<NNN>.md`
5. **Paulo** presents the plan with implementation estimate and team assignments
6. Suggest: "Run `/dev feature` to implement this plan"

## Workflow: /dev debug (Tier 2 — 4 Phases)

### Step 0: Enter Worktree
`EnterWorktree(name: "fix-<slug>")`

### Phase 1: Triage (Paulo)
- Read project context, assess severity
- Create TODO with `TaskCreate`
- Assign to Andre (backend) or Diana (frontend) based on the issue

### Phase 2: Investigate & Fix (Andre or Diana)
- Reproduce the issue
- Identify root cause
- Implement fix following project patterns
- Self-critique: "Did I fix the symptom or the root cause?"

### Phase 3: Regression Test (Rita)
- Write regression test that would have caught this bug
- Run full test suite to ensure no new breakage
- Quality gate: pass/fail

### Phase 4: Wrap-up (Paulo)
- Mark TODOs complete, commit with conventional message
- Report: root cause, fix, test, files changed

## Workflow: /dev refactor (Tier 2 — 3 Phases)

### Step 0: Enter Worktree
`EnterWorktree(name: "refactor-<slug>")`

### Phase 1: Plan (Paulo + Marco)
- Paulo creates TODO with `TaskCreate`
- Marco defines quality gates: what MUST be preserved (behavior, tests, performance)

### Phase 2: Refactor (Andre or Diana)
- Run tests BEFORE refactoring (baseline)
- Refactor following project patterns
- Run tests AFTER refactoring (must match or exceed baseline)
- Self-critique: "Is this simpler? More maintainable? Does it match the codebase style?"

### Phase 3: Wrap-up (Paulo)
- Mark TODOs complete, commit with conventional message
- Report: what changed, before/after comparison, tests still green

## Workflow: /dev db (Tier 2 — 4 Phases)

### Step 0: Enter Worktree
`EnterWorktree(name: "feature-<slug>-migration")`

### Phase 1: Plan (Paulo + Lucas)
- Paulo creates TODO with `TaskCreate`
- Lucas checks existing schema patterns in the codebase
- Lucas fetches relevant database docs via Context7

### Phase 2: Implement (Andre)
- Create migration (backward-compatible: add columns, not rename/remove)
- Update models, relationships, casts
- Update related services/controllers if needed
- Self-critique: "Indexes? Foreign keys? Nullable vs default? Rollback safe?"

### Phase 3: Verify (Rita)
- Run migration up and down
- Verify existing tests still pass
- Write test for new schema behavior if applicable

### Phase 4: Wrap-up (Paulo)
- Mark TODOs complete, commit with conventional message
- Report: schema changes, migration commands, rollback tested

## Workflow: /dev review (Tier 3 — CTO + Security)

No worktree required (read-only).

1. **Marco (CTO)** reviews current changes:
   - Security vulnerabilities (SQL injection, XSS, CSRF)
   - Performance bottlenecks (N+1 queries, missing indexes)
   - Maintainability (naming, structure, complexity)
   - Test coverage (are critical paths tested?)
   - Convention compliance (matches project CLAUDE.md?)

2. **Bruno (Security)** reviews:
   - OWASP Top 10 quick scan
   - Auth/authorization on new endpoints
   - Input validation completeness
   - Sensitive data handling

3. Combined report with actionable findings.

## Workflow: /dev test (Tier 3 — QA Lead)

No worktree required.

1. **Rita** assesses the current test state
2. Generates tests for untested code (based on coverage gaps)
3. Runs full test suite
4. Coverage report with pass/fail quality gate

## Workflow: /dev deploy (Tier 3 — DevOps Lead)

No worktree required.

1. **Carlos** verifies deployment prerequisites:
   - All tests passing in CI
   - No critical security issues open
   - Migration compatibility checked
2. Deploys to specified environment
3. Runs health checks post-deployment
4. Reports deployment status

## Workflow: /dev docs (Tier 3 — Analyst)

No worktree required.

1. **Lucas** reads the codebase and project context
2. Generates technical documentation:
   - API reference (endpoints, request/response schemas)
   - Architecture overview
   - Setup guide
3. Saves to Obsidian: `Projects/<name>/Docs/`

## Workflow: /dev stack-check (Tier 3 — DevOps + CTO)

No worktree required.

1. **Carlos** checks for outdated dependencies and security advisories
2. **Marco** reviews recommendations and prioritizes updates
3. Report: critical (security), recommended (major version), optional (minor)

## Workflow: /dev security-audit (Tier 3 — NEW)

No worktree required (read-only).

1. **Bruno** runs full OWASP Top 10 audit on the current codebase
2. **Lucas** researches any CVEs found in dependencies
3. Security report with severity, location, and recommended fixes
4. Saves to Obsidian: `Projects/<name>/Architecture/Security-Audit-<date>.md`

## Workflow: /dev research (Tier 3 — NEW)

No worktree required (read-only).

1. **Lucas** researches the specified topic:
   - Fetch docs via Context7 MCP
   - Search Obsidian KB for existing knowledge
   - Evaluate libraries using the evaluation framework
   - Check codebase for existing related code
2. Research document with findings, comparisons, and recommendation
3. Saves to Obsidian: `Projects/<name>/Docs/Research-<topic>.md`

## Self-Critique Checklists

Each role has mandatory self-review questions after implementation:

### Andre (Backend)
- N+1 queries? Use eager loading where needed
- Missing indexes? Check foreign keys and frequent query columns
- Transaction safety? Wrap multi-step writes in DB::transaction
- Validation gaps? Every input validated via FormRequest
- Error handling? Service methods handle exceptions gracefully
- Mass assignment protection? $fillable on every model

### Diana (Frontend)
- Loading states? Every async operation shows loading UI
- Error states? Every fetch has error handling + user-visible message
- Accessibility? ARIA labels, keyboard nav, semantic HTML
- Mobile responsive? Tested at mobile, tablet, desktop breakpoints
- Empty states? Lists, tables, and data displays handle zero items
- TypeScript strict? No `any` types, all props typed

### Gabriel (Architecture)
- Does implementation match the design?
- Are API contracts honored exactly?
- Scalability bottlenecks? Would this break at 10x traffic?
- Single point of failure? What happens if a service is down?

### Bruno (Security)
- All inputs validated server-side?
- Auth middleware on every protected endpoint?
- Secrets in environment variables, not code?
- SQL queries parameterized (no string concatenation)?
- Frontend content escaped (no raw HTML from users)?
- CSRF tokens on state-changing requests?

## MCP Usage by Phase

| Phase | MCP | Purpose |
|-------|-----|---------|
| Research | Context7 | Fetch framework/library documentation |
| Research | Obsidian | Search KB for existing patterns |
| Architecture | Obsidian | Write ADRs to vault |
| Implementation | Context7 | API reference when uncertain |
| Security | Sentry | Check error patterns |
| QA | Playwright | E2E tests for critical flows |
| Documentation | Obsidian | Save docs to vault |

## Obsidian Output

All development documentation goes to Obsidian vault at `{{OBSIDIAN_VAULT}}`:
- **Architecture decisions:** `Projects/<name>/Architecture/ADR-<NNN>.md`
- **Security audits:** `Projects/<name>/Architecture/Security-Audit-<date>.md`
- **Tech docs:** `Projects/<name>/Docs/`
- **Research:** `Projects/<name>/Docs/Research-<topic>.md`
- Uses YAML frontmatter, wikilinks `[[]]`, kebab-case tags

## Sub-Skills

| Skill | Path | Purpose |
|-------|------|---------|
| Scaffold | `departments/dev/skills/scaffold/SKILL.md` | Project creation from git repos with auto MCP + Obsidian |
| Onboard | `departments/dev/skills/onboard/SKILL.md` | Onboard existing projects with auto stack detection + MCP + Obsidian |
| MCP | `departments/dev/skills/mcp/SKILL.md` | MCP profile management per project |
| External Skills | (via `arka-skill` CLI) | Install, manage, and create external skills |

For `/dev scaffold` and `/dev mcp` commands, read the respective sub-skill SKILL.md for full workflow instructions.

## Scaffold Types (Quick Reference)

| Type | Git Repository | MCP Profile |
|------|---------------|-------------|
| `laravel` | `git@andreagroferreira:andreagroferreira/laravel-starter-kit.git` | laravel |
| `nuxt-saas` | `https://github.com/nuxt-ui-templates/dashboard.git` | nuxt |
| `nuxt-landing` | `https://github.com/nuxt-ui-templates/landing.git` | nuxt |
| `nuxt-docs` | `https://github.com/nuxt-ui-templates/docs.git` | nuxt |
| `vue-saas` | `https://github.com/nuxt-ui-templates/dashboard-vue.git` | vue |
| `vue-landing` | `https://github.com/nuxt-ui-templates/starter-vue.git` | vue |
| `full-stack` | Laravel + Nuxt (both) | full-stack |
| `react` | React starter (TBD) | react |
| `nextjs` | Next.js starter (TBD) | nextjs |

## Context Loading

Before ANY development command:
1. Detect which project we're in (check for PROJECT.md or CLAUDE.md)
2. Load project-specific stack, conventions, and patterns
3. Use Context7 MCP to fetch latest docs for the project's framework versions
4. Apply project standards, NOT global defaults (unless no project context)
