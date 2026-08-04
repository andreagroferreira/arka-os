# Development

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/dev` · **Lead:** Paulo (Tier 1) · **Agents:** 15 · **Skills:** 65

Development is the largest department in ArkaOS, covering the full spectrum of software engineering — from system architecture and backend APIs to frontend interfaces, data pipelines, AI engineering, security, and DevOps. Every request that involves writing, reviewing, testing, deploying, or designing code routes here.

The department is organized into three sub-squads that operate under Paulo's coordination: **Backend Core** (Laravel, Python, Node/TypeScript API work), **Data Platform** (PostgreSQL, Supabase, ETL pipelines), and **AI Engineering** (RAG pipelines, vector stores, agent orchestration). Marco (CTO, Tier 0) provides strategic oversight and holds veto authority on architectural decisions.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 36 | 65 | 15 |

**Commands** (36 via `/dev`):

| Command | What it does |
| --- | --- |
| `/dev api <spec>` | Design and implement API endpoints |
| `/dev architecture <system>` | Architecture design with ADR |
| `/dev clean-review <file>` | Clean Code + SOLID compliance review |
| `/dev db <action>` | Database design, migrations, query optimization |
| `/dev ddd <domain>` | Domain-Driven Design modeling session |
| `/dev debug <issue>` | Systematic debugging with root cause analysis |
| `/dev do <description>` | Smart routing to the right dev command |
| `/dev ecosystem add <project> --to <ecosystem>` | Add existing project to ecosystem |
| `/dev ecosystem create <name>` | Create a new ecosystem |
| `/dev ecosystem list` | List all ecosystems and their projects |
| `/dev feature <description>` | Implement a new feature (full enterprise workflow) |
| `/dev mcp add <name> [--project <path>]` | Add a single MCP to a project |
| ... | 24 more — full list in [docs/COMMANDS.md](../../docs/COMMANDS.md) |

**Skills** (65 — 64 sub-skills plus the `/dev` hub):

| Skill | What it does |
| --- | --- |
| `adversarial-review` | Adversarial code review with 3 hostile personas (Saboteur, New Hire, Security Auditor) that hunts edge case... |
| `agent-design` | Design multi-agent system architectures — supervisor/swarm/pipeline patterns, agent role definitions, tool... |
| `agent-workflow` | Design production-grade multi-agent workflows — pattern selection (sequential, parallel, router, orchestrat... |
| `ai-assisted-dev` | AI-assisted development practice: prompt engineering for code generation, structured review of AI output, a... |
| `ai-security` | AI/ML-specific security assessment with OWASP ML Top 10, NIST AI RMF, and MITRE ATLAS technique mapping: pr... |
| `animated-website` | Convert an MP4 video into a luxury scroll-animated single-file website: extracts frames to optimized WebP (... |
| `api-design` | Design REST or GraphQL APIs with resource modeling, versioning, pagination, error contracts, and documentat... |
| `app-test` | Build, launch, and click through a native app (macOS or iOS Simulator) via Computer Use — exercises every c... |
| `architecture-design` | Design system architecture with Clean Architecture, Hexagonal, or DDD patterns and produce an ADR (Architec... |
| `build-fix` | Systematic build-failure diagnosis: read the FIRST error bottom-up, reproduce it in isolation, classify it... |
| `changelog` | Generate changelogs from git history using Conventional Commits: lints commit messages, detects the SemVer... |
| `ci-cd-pipeline` | Design and generate CI/CD pipelines from the detected project stack — GitHub Actions or GitLab CI with lint... |
| `clean-code-review` | Focused Clean Code (Uncle Bob) + SOLID sweep of a file or PR — naming, function size, nesting depth, dead c... |
| `click-path-audit` | Simulates every interactive handler call-by-call to find bugs a normal read skips over — shared-state side... |
| `code-review` | General code review of a file, diff, or PR against Clean Code, SOLID, test coverage, and baseline security... |
| `codebase-onboard` | Analyze an existing codebase and generate onboarding documentation for new developers: stack detection, arc... |
| `db-design` | Database design with the DBA (Vasco): schema modeling, normalization, index strategy, RLS policies, and mig... |
| `db-schema` | Design a feature's database schema: normalization to 3NF, relationship mapping, cross-cutting concerns (tim... |
| `ddd-model` | Domain-Driven Design modeling with the Evans/Vernon playbook: bounded contexts, aggregates, domain events,... |
| `demo-gif` | Record a GIF demo of a browser user flow: navigates to a URL, executes the described interactions (click, t... |
| `dependency-audit` | Audit project dependencies across ecosystems (npm, Composer, pip, Go, Cargo) for known CVEs, license compli... |
| `deploy` | Deploy to an environment with blue-green/canary strategy: pre-deploy checks, deployment execution, and post... |
| `dev-hub` | Full-stack development department. Enterprise-grade 15-agent team with structured multi-phase workflows. Im... |
| `devops-pipeline` | CI/CD pipeline design following the Three Ways (Gene Kim) and GitOps: build, test, deploy stages with blue-... |
| `diagram` | Turn a spec, plan, or system description into an interactive diagram the user opens in a browser — one self... |
| `docs` | Generate or update project documentation — README, API docs, and architecture docs — saved to the project a... |
| `env-secrets` | Audit environment files and source for leaked secrets (OWASP Secrets Management): .gitignore coverage, hard... |
| `evaluator-build-loop` | Adversarial build loop for UI work: a generator implements against a weighted rubric while an independent,... |
| `exploit-triage` | Reviews code for the vulnerabilities that are actually reachable and actually exploitable — SSRF, auth bypa... |
| `incident` | Incident response with Google SRE incident management: severity classification (SEV1-4), incident commander... |
| `laravel-review` | Laravel/PHP review against ArkaOS conventions — mass assignment, N+1 queries, Blade XSS, business logic lea... |
| `mcp` | MCP (Model Context Protocol) management for projects: apply pre-configured MCP profiles (laravel, nuxt, eco... |
| `mcp-builder` | Build production-ready MCP servers from API contracts: scaffold from OpenAPI specs, generate typed tool man... |
| `ml-adoption-playbook` | Decides whether a problem needs ML at all, then adds it to a non-ML codebase the cheap way — heuristic base... |
| `mle-workflow` | Turns model work into a production ML system — data contracts, reproducible training, measurable eval gates... |
| `observability` | Design observability strategies with Google SRE practice: SLI/SLO frameworks with error budgets, golden sig... |
| `onboard` | Onboard EXISTING projects into ARKA OS: auto-detects stack from composer.json/package.json/.env, analyzes a... |
| `opensource-release` | Takes an internal module or repo public WITHOUT taking its secrets with it: extract the component, scrub co... |
| `performance-audit` | Performance audit against Google/industry budgets: Core Web Vitals (LCP, INP, CLS), API latency percentiles... |
| `performance-profiler` | Performance profiling with measure-first discipline: establish a baseline (P50/P95/P99, RPS, memory), ident... |
| `pr-test-analyzer` | Judges whether a PR's tests would catch the change breaking — maps changed code to its tests, finds unteste... |
| `python-review` | Python review against ArkaOS conventions — missing type hints, mutable default arguments, bare excepts, unv... |
| `rag-architect` | Design RAG pipelines end-to-end: chunking strategies, embedding model selection, vector database comparison... |
| `react-review` | React / Next.js review for the framework's own traps — stale closures in hooks, dependency arrays that lie,... |
| `red-team` | Offensive security engagement planning with MITRE ATT&CK and the Cyber Kill Chain: technique scoring, attac... |
| `refactor-plan` | Plan a refactoring with Martin Fowler's catalog: identify code smells, select refactoring patterns, assess... |
| `release` | Release planning and execution with SemVer and DORA practice: version bump detection from conventional comm... |
| `research` | Dev-scoped technical research (Lucas, Analyst): library evaluation, framework/package selection, code patte... |
| `runbook` | Generate operational runbooks from service analysis (Google SRE): service overview, health checks, step-by-... |
| `safety-review` | Audits a change or an automation for destructive, irreversible operations — bulk deletes, DROP/TRUNCATE, fo... |
| `scaffold` | Project scaffolding from real git starter repos: creates NEW Laravel, Nuxt, Vue, React, or Next.js projects... |
| `scroll-world` | Build an immersive scroll-scrubbed "fly through the world" landing page for any industry or brand using Hig... |
| `security-audit` | OWASP Top 10 (2025) security audit: access control, cryptographic failures, injection, misconfiguration, pl... |
| `security-compliance` | Security audit preparation and ISO 27001 certification support: ISMS gap analysis against clauses 4-10, Ann... |
| `silent-failure-hunter` | Hunts silent failures — swallowed exceptions, errors coerced to null, fallbacks that mask a broken path, lo... |
| `skill-audit` | Audit AI agent skill directories for security risks BEFORE installation (OWASP LLM Top 10): code execution... |
| `spec` | Spec-driven development gate, constitution MUST rule spec-driven (Constitution #7 — no code without an appr... |
| `spec-miner` | Mines a spec OUT of an existing codebase: maps entry points into capabilities, samples the code under an ex... |
| `stack-check` | Audit the current tech stack through a 12-Factor lens: framework and runtime versions, dependency health, s... |
| `tdd-cycle` | Test-Driven Development with Kent Beck's Red-Green-Refactor cycle: write the failing test first, minimum co... |
| `tech-debt` | Identify, classify, score, and prioritize technical debt (Ward Cunningham metaphor + cost-of-delay): six de... |
| `type-design-analyzer` | Scores whether a module's types make illegal states unrepresentable — across encapsulation, invariant expre... |
| `typescript-review` | TypeScript/Node review for the holes the compiler waves through — `any` and unsafe casts, unhandled promise... |
| `vue-review` | Vue 3 / Nuxt review for the framework's own traps — lost reactivity, SSR hydration mismatches, missing keys... |
| `watch` | Watch a video (URL or local file) so the agent can answer questions about what is on screen and what is sai... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Marco | Chief Technology Officer | 0 |
| Gabriel | Software Architect | 1 |
| Paulo | Tech Lead | 1 |
| Andre | Backend Core Lead | 2 |
| Bruno | Security Engineer | 2 |
| Carlos | DevOps Lead | 2 |
| Diana | Senior Frontend Developer | 2 |
| Rita | QA Engineer | 2 |
| Vasco | Data Platform Lead (Database & Data Engineer) | 2 |
| Salvador | AI Engineering Specialist | 2 |
| Diogo | Python Backend Specialist | 2 |
| Vera | Node.js / TypeScript Backend Specialist | 2 |
| Gonçalo | Laravel Specialist | 2 |
| Duarte | Data / ETL Engineer | 2 |
| Maria | Research Assistant | 3 |

## Frameworks

- **Clean Architecture** (Uncle Bob) — enforced across all services; thin controllers, business logic in the domain layer
- **SOLID** — SRP, OCP, LSP, ISP, DIP are NON-NEGOTIABLE; Francisca (Quality Gate) audits compliance
- **Domain-Driven Design** (Evans / Vernon) — bounded contexts, event storming, aggregate design
- **TDD Cycle** (Beck) — red-green-refactor on every feature; Rita enforces the Testing Pyramid (Cohn)
- **Hexagonal / Ports & Adapters** (Cockburn) — isolates domain from infrastructure, used by Diogo and Vera
- **DORA Metrics** (Forsgren) — deployment frequency, lead time, MTTR, change failure rate guide Paulo's delivery
- **OWASP Top 10** (2025) — Bruno's baseline for every security review; paired with STRIDE threat modeling
- **CQRS / Event Sourcing** — applied by Gabriel for read/write separation in complex bounded contexts
- **GitOps** (Gene Kim / Three Ways) — Carlos manages infra state via single source of truth in version control
- **Retrieval-Augmented Generation** — Salvador's ground-before-generate principle for all AI feature work
- **Normalization (3NF/BCNF) + Index Strategy** — Vasco's schema design baseline, validated with EXPLAIN ANALYZE
- **Shape Up Appetite** (Singer) — Paulo uses fixed time, variable scope to bound feature cycles
- **Wardley Maps** — Gabriel uses these for technology positioning and build-vs-buy decisions

## What you can ask for

- "Plan the architecture for a multi-tenant SaaS" → `/dev architecture-design`
- "Build a REST API endpoint with validation and tests" → `/dev api-design`
- "Set up CI/CD with GitHub Actions and Docker" → `/dev ci-cd-pipeline`
- "Run a security audit on the codebase" → `/dev security-audit`
- "Design the database schema for this domain" → `/dev db-schema`
- "Review this code for SOLID violations and clean code issues" → `/dev clean-code-review`
- "Write the technical spec before we build" → `/dev spec`
- "Set up a RAG pipeline with vector search" → `/dev rag-architect`
- "Scaffold a new Laravel or Nuxt project" → `/dev scaffold`
- "Profile and fix the performance bottleneck" → `/dev performance-profiler`

## How a request flows here

1. **Paulo receives the routed request** and assigns it to the relevant sub-squad or specialist.
2. **Spec gate** — Gabriel or Paulo drafts a technical spec via `/dev spec`. No implementation starts without an approved spec. This is NON-NEGOTIABLE.
3. **Specialist implements** with TDD (Rita reviews test coverage), following SOLID and Clean Architecture standards.
4. **QA full suite** — Rita runs unit, integration, and end-to-end tests (Playwright, Jest, PHPUnit, pytest). All tests must pass.
5. **Security review** — Bruno audits against OWASP Top 10 and STRIDE threat model.
6. **Quality Gate** — Marta (CQO) orchestrates Eduardo (copy/language) and Francisca (technical/UX). Binary APPROVED/REJECTED. Nothing ships without this gate.

The full [Evidence Flow](../03-The-13-Phase-Flow.md) governs every non-trivial request, including approval gates before implementation begins.

## When to use it

Reach for `/dev` any time a request involves code — new features, refactoring, APIs, database design, infrastructure, security hardening, AI pipelines, performance work, or scaffolding a new project. For cross-cutting concerns (e.g., a new product feature that also needs a landing page), this department handles the technical implementation while other departments handle their respective domains in parallel.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
