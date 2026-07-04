# Development

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/dev` · **Lead:** Paulo (Tier 1) · **Agents:** 15 · **Skills:** 43

Development is the largest department in ArkaOS, covering the full spectrum of software engineering — from system architecture and backend APIs to frontend interfaces, data pipelines, AI engineering, security, and DevOps. Every request that involves writing, reviewing, testing, deploying, or designing code routes here.

The department is organized into three sub-squads that operate under Paulo's coordination: **Backend Core** (Laravel, Python, Node/TypeScript API work), **Data Platform** (PostgreSQL, Supabase, ETL pipelines), and **AI Engineering** (RAG pipelines, vector stores, agent orchestration). Marco (CTO, Tier 0) provides strategic oversight and holds veto authority on architectural decisions.

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
