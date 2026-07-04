# 14 · Use Cases

← [Home](Home.md)

End-to-end scenarios organized by role. Each one shows the plain-language request, which department(s) engage, how the 4-gate evidence flow and Quality Gate apply, and what you receive at the end.

Numbers, frameworks, and agent names are canonical. The system has 82 agents across 17 departments, 267 skills, and a mandatory Quality Gate (Marta + Eduardo + Francisca) on every workflow.

---

## Contents

- [Developer — Feature with full workflow](#developer--laravel-feature-with-full-workflow)
- [Developer — Security audit](#developer--security-audit)
- [Founder — SaaS idea validation](#founder--saas-idea-validation)
- [Founder — Product launch across departments](#founder--cross-department-product-launch)
- [Marketer — Email launch sequence](#marketer--email-launch-sequence)
- [Agency owner — Client onboarding and brand identity](#agency-owner--client-onboarding-and-brand-identity)

---

## Developer — Laravel feature with full workflow

**Request:**

```
/dev feature "user authentication with email/password, OAuth2 (Google, GitHub),
and magic-link login"
```

**Departments engaged:** Development (Paulo)

**What happens across the 4 gates:**

| Gate | What ArkaOS does |
|---|---|
| G1 CONTEXT | Synapse reads project context (stack, branch, recent commits); routes to Development → Paulo; Marco (CTO) is called because this touches security architecture; KB queried for prior auth patterns — Laravel Sanctum, Passport, and Socialite compared, with citations |
| G2 PLAN | Short plan: scope, files touched, the exact verification commands. Presented for your explicit approval |
| G3 EXECUTE | Paulo dispatches backend and frontend specialists in parallel; the gate closes only with `[arka:gate:3] evidence: php artisan test -> exit 0 (…)` on record |
| G4 REVIEW | Linter, type-checker, coverage report, and security grep run over the diff; the Quality Gate verdict derives from that output |
| 8–9 | Plan presented (ADR drafted: Sanctum + Socialite + signed URLs); you approve |
| 10 | TODO list: migrations → models → AuthService → controllers → FormRequests → feature tests → security review |
| 11 | Each TODO runs: implement → full test suite → OWASP security check → Quality Gate |
| 13 | Summary with file paths, test results, and open items |

**Quality Gate:** Marta orchestrates Eduardo (reviews error message copy for clarity) and Francisca (verifies test coverage and OWASP compliance). Binary APPROVED/REJECTED — no partial passes.

**Deliverable:**

- Migrations for `users`, `oauth_providers`, `magic_link_tokens`
- `AuthService` with registration, OAuth, and magic-link methods
- Controllers with FormRequest validation
- Feature tests covering happy paths, edge cases, and error states
- ADR in your Obsidian vault
- Security report (passed/flagged items)

---

## Developer — Security audit

**Request:**

```
/dev security-audit
```

**Department engaged:** Development (Paulo → Rita, Security Engineer)

**What happens:**

Rita scans the entire codebase against OWASP Top 10. The evidence flow runs at a focused depth: Gate 1 reads all controllers, middleware, and route files; Gate 2 maps the audit scope for approval; Gate 3 runs each check and collects findings as raw tool output.

**Checks performed:**

- SQL injection (raw queries, unparameterized inputs)
- XSS (unescaped output, missing CSP headers)
- CSRF protection on state-changing routes
- Authentication bypass (missing middleware, insecure defaults)
- Secrets in source (API keys, tokens)
- Insecure dependency versions (known CVEs)
- Rate limiting on sensitive endpoints

**Deliverable — example output structure:**

```
Security Audit Report

CRITICAL (fix immediately):
- app/Http/Controllers/SearchController.php:42
  Raw SQL with user input in LIKE clause
  Fix: use parameterized binding

HIGH (fix before next release):
- No rate limiting on /api/login
  Fix: add ThrottleRequests middleware

PASSED: CSRF, Blade XSS escaping, HTTPS redirect, session config
```

Quality Gate reviews the report for completeness before it reaches you.

---

## Founder — SaaS idea validation

**Request:**

```
/saas validate-idea "A platform matching freelance CFOs with startups that
just raised seed rounds. $500/mo per startup, CFO earns $400, we keep $100.
US market."
```

**Department engaged:** SaaS (Tiago), with Finance (Helena) and Strategy (Tomas) pulled in at Gate 1 for cross-department inputs.

**Evidence-flow highlights:**

- Gate 1 (CONTEXT): KB queried for marketplace unit economics patterns and fractional-executive market data, cited inline.
- Gate 2 (PLAN): The not-yes-man rule applies — thin margins are flagged with reference-company evidence and pricing adjustments proposed; the plan ships with three pivot options for a single approval.
- Gate 3 (EXECUTE): Validation scorecard built with quantified assumptions stated inline.

**Deliverable — example scorecard:**

```
VALIDATION SCORECARD

MARKET:
  TAM: fractional CFO services (US)
  SAM: seed-stage startups requiring part-time CFO
  SOM: achievable in first 2 years via outbound + communities
  Verdict: adequate, but niche

UNIT ECONOMICS:
  Revenue per match: $100/mo
  Average retention: ~8 months (until startup hires full-time)
  LTV: ~$800 per startup
  Target CAC: <$200 for 4:1 LTV/CAC ratio
  Risk: two-sided marketplace acquisition cost
  Verdict: thin margins, volume-dependent

RECOMMENDATION: PIVOT BEFORE BUILDING
  Option A — raise take rate to $200/mo
  Option B — add bookkeeping/tax prep for expansion revenue
  Option C — target Series A+ for longer retention and higher willingness to pay
```

---

## Founder — Cross-department product launch

This scenario shows how ArkaOS coordinates multiple departments in a single request.

**Request:**

```
/do "We're launching a new SaaS plan tier next month — $99/mo with AI features.
Need the landing page, email sequence, brand assets, and a Shopify-ready
checkout flow."
```

**Departments engaged simultaneously:**

| Department | Lead | Scope |
|---|---|---|
| Landing Pages | Ines | Hero, pricing section, feature comparison, FAQ copy |
| Marketing | Luna | 6-email pre-launch sequence (Brunson formula + AIDA) |
| Brand | Valentina | Visual treatment for the new tier — color, badge, iconography |
| E-Commerce | Ricardo | Checkout flow, plan-upgrade UX, pricing anchoring |
| SaaS | Tiago | PLG metrics for the new tier, trial-to-paid conversion targets |

**How the evidence flow handles cross-department work:**

- Gate 1: Sofia (COO) is called to coordinate the squad matrix.
- Gate 2: A consolidated plan across all departments — with dependencies made explicit — is presented for a single approval gate.
- Gate 3: Each department's TODO list runs independently in parallel tracks.
- Gate 4: The Quality Gate aggregates final approval from each track's check results.

**Deliverable:**

- Landing page copy (hero through FAQ, with conversion rationale per section)
- 6-email sequence with subject-line variants
- Visual brand spec for the new tier
- Checkout flow with pricing anchoring and upgrade prompts
- PLG metrics baseline for the tier

All outputs saved to your Obsidian vault under the relevant department paths.

---

## Marketer — Email launch sequence

**Request:**

```
/mkt email-sequence "Online course teaching Python to career changers, $197
one-time, launching in 3 weeks, audience is professionals aged 25-40 making
a tech switch"
```

**Department engaged:** Marketing (Luna → email marketing specialist)

**What happens:**

Luna's team maps the emotional journey from initial awareness through purchase decision, then writes each email using Brunson's launch formula layered with the AIDA framework. Gate 2 (PLAN) specifically tests messaging against the target audience's known objections before asking for approval.

**Deliverable — email structure:**

```
Email 1: Teaser (Day -14)
  Subject variants (3), preview text, story-driven body, soft CTA

Email 2: Problem agitation (Day -10)
  Anchors the pain of stalling on a career change

Email 3: Solution reveal (Day -7)
  Introduces the course — outcome-first framing

Email 4: Social proof (Day -3)
  Student results, specifics over adjectives

Email 5: Objection handling (Day -1)
  Addresses price, time, and "I'm not technical" blockers

Email 6: Launch day (Day 0)
  Urgency + final CTA
```

Eduardo (Quality Gate Copy reviewer) checks every email for AI cliches, grammar, and tone consistency before the output lands in your vault.

---

## Agency owner — Client onboarding and brand identity

This scenario is typical for agencies using ArkaOS to run work across multiple client projects (see [15 · Ecosystems](15-Ecosystems.md) for the multi-project setup).

**Request:**

```
/brand identity-system "AI-powered legal document tool for small businesses,
name is Clearlaw, values are simplicity and accessibility, competitors feel
corporate and intimidating"
```

**Department engaged:** Brand (Valentina), with Quality (Marta) as mandatory gate.

**Evidence-flow highlights:**

- Gate 1 (CONTEXT): KB queried for brand archetype patterns and competitor visual audits. Any prior Clearlaw context from the ecosystem is injected automatically.
- Gate 3 (EXECUTE): Valentina dispatches a brand strategist and visual designer in parallel. The strategist runs the Primal Branding + 12 Archetypes analysis; the designer builds the color system and typography direction.
- Gate 4 (REVIEW): WCAG contrast ratios are verified on every color pair — the check output feeds the Quality Gate verdict.

**Deliverable:**

```
BRAND IDENTITY BRIEF

ARCHETYPE: The Sage (primary) + The Everyman (secondary)
POSITIONING: "Legal clarity without the complexity"

VOICE:
  Scale: Professional [===|====] Casual (60/40)
  Keywords: clear, simple, confident, helpful
  Never: jargon, legalese, condescending

COLORS (all pairs pass WCAG AA):
  Primary:   #1B4D6E — trust, depth
  Secondary: #F4A261 — approachability
  Neutral:   #F8F9FA — clean background
  Accent:    #2D9CDB — action, links

TYPOGRAPHY:
  Headings: geometric sans-serif
  Body: humanist sans-serif

VISUAL PRINCIPLES:
  1. White space over decoration
  2. Icons over illustrations
  3. One accent color per screen
```

Saved to `Brand/Clearlaw/identity-system.md` in your Obsidian vault with full rationale and Marta's APPROVED stamp.

---

## Quick reference by role

| Role | Common starting point | Departments typically engaged |
|---|---|---|
| Developer | `/dev feature "..."` or plain description | Development, Quality Gate |
| Security-focused dev | `/dev security-audit` | Development (Rita) |
| Founder validating | `/saas validate-idea "..."` | SaaS, Finance, Strategy |
| Founder launching | `/do "launch [product]"` | Landing, Marketing, Brand, E-Commerce, SaaS |
| Marketer | `/mkt email-sequence "..."` | Marketing, Content |
| Content creator | `/content hook-write "..."` | Content, Marketing |
| Agency owner | `/brand identity-system "..."` | Brand, then project ecosystem |
| Finance/investor prep | `/fin financial-model "..."` | Finance, Strategy |
| Leadership/team | `/lead okr-set "..."` | Leadership, Organization |

---

Related: [03 · The Evidence Flow (4 Gates)](03-The-13-Phase-Flow.md) · [04 · Departments](04-Departments/README.md) · [10 · Quality Gate](10-Quality-Gate.md) · [15 · Ecosystems](15-Ecosystems.md) · [Home](Home.md)
