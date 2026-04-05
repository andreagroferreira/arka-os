# ArkaOS Use Cases

Real scenarios organized by role. Each use case shows what you type, what ArkaOS does, and what you get back.

## For Developers

### "I need to add user authentication to my Laravel app"

**What you type:**

```
/dev feature "user authentication with email/password, OAuth2 (Google, GitHub),
and magic link login"
```

**What ArkaOS does:**

The 9-phase enterprise workflow activates. Paulo (Tech Lead) orchestrates:

1. **Spec phase** -- Paulo and Gabriel create a feature specification with acceptance criteria, data models, and API contracts. You review and approve.
2. **Research phase** -- Lucas researches Laravel Sanctum vs Passport, OAuth2 libraries, and magic link implementations. Gabriel reviews existing architecture.
3. **Architecture phase** -- Gabriel writes an ADR (Architecture Decision Record) choosing Sanctum + Socialite + signed URLs. Marco (CTO) reviews. You approve.
4. **Implementation** -- Andre writes the backend (migrations, models, services, controllers, form requests). Mariana builds the frontend (login forms, OAuth buttons, email templates). They work in parallel.
5. **Testing** -- Tiago writes feature tests: registration, login, OAuth callback, magic link flow, password reset, invalid credentials.
6. **Security audit** -- Rita checks for OWASP vulnerabilities: CSRF protection, rate limiting, token storage, session fixation.
7. **Self-critique** -- The implementation is reviewed against the spec. Gaps are fixed.
8. **Quality Gate** -- Marta dispatches Eduardo (copy review on error messages) and Francisca (code quality, test coverage). Both must approve.

**What you get:**

- Migrations for users, oauth_providers, and magic_link_tokens tables
- Models with relationships and casts
- AuthService with registration, login, OAuth, and magic link methods
- Controllers with FormRequest validation
- Feature tests covering happy paths, edge cases, and error states
- ADR saved to your Obsidian vault

---

### "Review my code for security vulnerabilities"

**What you type:**

```
/dev security-audit
```

**What ArkaOS does:**

Rita (Security Engineer) scans your entire codebase using OWASP Top 10 as the framework:

1. Reads all controllers, middleware, and route files
2. Checks for SQL injection (raw queries, unparameterized inputs)
3. Checks for XSS (unescaped output, missing CSP headers)
4. Checks for CSRF protection on state-changing routes
5. Checks for authentication bypass (missing middleware, insecure defaults)
6. Checks for secrets in code (API keys, passwords, tokens in source)
7. Checks for insecure dependencies (known CVEs)

**What you get:**

```
Security Audit Report

CRITICAL (fix immediately):
- app/Http/Controllers/SearchController.php:42
  Raw SQL query with user input: DB::select("SELECT * FROM products WHERE name LIKE '%$query%'")
  Fix: Use parameterized query with bindings

- .env.example:18
  Contains actual API key (not a placeholder)
  Fix: Replace with EXAMPLE_KEY=your-key-here

HIGH (fix before next release):
- app/Http/Middleware/Cors.php:12
  Access-Control-Allow-Origin: * on authenticated routes
  Fix: Whitelist specific origins

MEDIUM:
- No rate limiting on /api/login endpoint
  Fix: Add ThrottleRequests middleware

Passed: CSRF protection, XSS escaping (Blade), session configuration, HTTPS redirect
```

---

### "Set up CI/CD pipeline for this project"

**What you type:**

```
/dev ci-cd-pipeline "GitHub Actions, Laravel app, deploy to DigitalOcean"
```

**What ArkaOS does:**

Nuno (DevOps Engineer) creates a complete CI/CD pipeline:

1. Analyzes your project stack (Laravel, PHP version, database, frontend build)
2. Generates GitHub Actions workflow YAML with stages: lint, test, build, deploy
3. Creates deployment scripts for DigitalOcean (SSH deploy with zero-downtime)
4. Adds environment configuration templates
5. Documents the pipeline in your Obsidian vault

**What you get:**

- `.github/workflows/ci.yml` -- lint + test on every PR
- `.github/workflows/deploy.yml` -- deploy on merge to main
- `deploy.sh` -- zero-downtime deployment script
- Environment variable documentation
- Rollback procedure documentation

---

### "Analyze tech debt in my codebase"

**What you type:**

```
/dev tech-debt
```

**What ArkaOS does:**

Lucas (Analyst) and Andre (Senior Dev) scan your codebase:

1. Identify functions over 30 lines (complexity hotspots)
2. Find nesting deeper than 3 levels
3. Detect duplicated logic across files
4. Count TODO/FIXME comments
5. Check for god classes and models
6. Analyze test coverage gaps
7. Estimate fix time for each category

**What you get:**

A prioritized tech debt report with estimated hours per fix, organized by severity. The report includes specific file paths and line numbers, not vague recommendations.

---

## For Marketing and Business

### "Create a complete email sequence for product launch"

**What you type:**

```
/mkt email-sequence "Online course teaching Python to complete beginners,
$197 one-time, launching in 3 weeks, audience is career changers aged 25-40"
```

**What ArkaOS does:**

Joana (Email Marketing) creates a 6-email launch sequence using Brunson's launch formula and AIDA framework:

1. Analyzes the product, audience, and price point
2. Maps the emotional journey from awareness to purchase
3. Writes each email with subject lines (3 variants), preview text, body, and CTA
4. Includes send timing recommendations

**What you get:**

```
Email 1: Teaser (Day -14)
Subject A: "The skill that's replacing college degrees"
Subject B: "Why 50,000 people switched careers this year"
Subject C: "I was stuck in a cubicle until I learned this"
Preview: "No CS degree needed. No prior experience."

Body: [Full email copy, 250 words, story-driven opening,
       curiosity hook about Python's demand, soft CTA to reply]

---

Email 2: Problem Agitation (Day -10)
Subject A: "The $40K mistake most career changers make"
...

Email 3: Solution Reveal (Day -7)
Email 4: Social Proof (Day -3)
Email 5: Objection Handling (Day -1)
Email 6: Launch Day (Day 0) -- urgency + final CTA
```

All 6 emails saved to your Obsidian vault, formatted and ready to paste into your email platform.

---

### "Audit my website SEO and fix issues"

**What you type:**

```
/mkt seo-audit
```

**What ArkaOS does:**

Sara (SEO Specialist) runs a structured audit:

1. Crawls your site pages and checks on-page factors
2. Analyzes meta tags, headings, images, internal linking
3. Checks technical SEO: sitemap, robots.txt, page speed indicators, mobile
4. Reviews content quality: keyword density, readability, content gaps
5. Compares against top 3 competitors for target keywords

**What you get:**

A prioritized audit report with:
- Critical issues (blocking SEO performance)
- High-priority fixes (significant impact, moderate effort)
- Quick wins (low effort, immediate improvement)
- Content gap analysis with keyword opportunities
- Competitor comparison table

Each issue includes what is wrong, why it matters, and exactly how to fix it.

---

### "Generate viral content hooks for TikTok"

**What you type:**

```
/content hook-write "productivity tips for software developers,
casual and relatable tone, targeting devs aged 22-35"
```

**What ArkaOS does:**

Rafael (Content Strategist) generates hooks using the STEPPS framework (Social Currency, Triggers, Emotion, Public, Practical Value, Stories):

**What you get:**

```
10 Viral Hooks for TikTok

CURIOSITY GAP HOOKS:
1. "The VS Code shortcut that saves me 2 hours every day"
   [Pattern: Specific benefit + common tool = high relatability]

2. "Stop writing console.log — use this instead"
   [Pattern: Challenge common behavior + promise better alternative]

3. "I mass-deleted 40% of my codebase and nothing broke"
   [Pattern: Shocking action + unexpected outcome]

CONTRARIAN HOOKS:
4. "Unpopular opinion: you don't need to learn algorithms"
   [Pattern: Challenge sacred belief + implied better path]

5. "Senior devs don't write more code — they delete it"
   [Pattern: Counterintuitive truth about expertise]

STORY HOOKS:
6. "I got fired for writing clean code — here's why"
   [Pattern: Personal stakes + paradox]

...

Each hook includes:
- Opening frame text (what appears on screen)
- Retention strategy (how to hold past 3 seconds)
- CTA suggestion (comment prompt for engagement)
```

---

### "Build a landing page with high-converting copy"

**What you type:**

```
/landing copy-framework "SaaS tool that automates invoice processing,
$49/mo for small businesses, main pain point is manual data entry taking 10+ hours/week"
```

**What ArkaOS does:**

Ines (Landing Lead) and Joao (Copywriter) create landing page copy using AIDA and PAS frameworks, with a Hormozi-style value stack:

**What you get:**

Complete landing page copy structure:
- Hero section with headline (3 variants), subheadline, and CTA
- Problem section with pain point agitation
- Solution section with feature-benefit mapping
- Social proof section with testimonial prompts
- Value stack with Grand Slam Offer structure
- Pricing section with anchoring strategy
- FAQ section with objection handling
- Final CTA with urgency element

Each section includes the copy text, layout notes, and conversion rationale explaining why each element is structured that way.

---

## For Founders and CTOs

### "Validate my SaaS idea before building"

**What you type:**

```
/saas validate-idea "A platform that matches freelance CFOs with
startups that just raised seed rounds. $500/mo per startup,
CFOs get $400, we keep $100. Target: US market."
```

**What ArkaOS does:**

Tiago (SaaS Strategist) runs a structured 5-point validation:

1. **Market sizing** -- TAM/SAM/SOM for fractional CFO market and seed-stage startups
2. **Competitor analysis** -- Existing solutions (Pilot, Bench, Toptal Finance)
3. **Unit economics** -- Revenue per transaction, LTV projections, marketplace take rate analysis
4. **Technical feasibility** -- Build complexity assessment, MVP scope
5. **GTM fit** -- Channel-market fit, customer acquisition strategy

**What you get:**

```
VALIDATION SCORECARD: 68/100

MARKET SIZE:
  TAM: $12B (fractional CFO services, US)
  SAM: $480M (seed-stage startups needing CFO)
  SOM: $4.8M (first 2 years, organic + outbound)
  Verdict: Adequate market, but niche

COMPETITORS (3 direct, 4 adjacent):
  Direct: Pilot (funded, broader scope), Zeni (AI-first),
          Kruze Consulting (established)
  Gap: None focus exclusively on seed-stage matching
  Moat risk: Low -- easy for Pilot to add matching feature

UNIT ECONOMICS:
  Revenue per match: $100/mo
  Average retention: 8 months (until startup hires full-time)
  LTV: $800 per startup
  Target CAC: < $200 (for 4:1 LTV/CAC)
  Marketplace challenge: must acquire both sides
  Verdict: Thin margins, volume-dependent

RECOMMENDATION: PIVOT BEFORE BUILDING
  The $100/mo take rate with 8-month retention creates thin
  unit economics. Consider:
  1. Increase take rate to $200/mo (charge startups $600)
  2. Add value-added services (tax prep, bookkeeping) for expansion revenue
  3. Target Series A+ instead of seed (longer retention, higher willingness to pay)
```

---

### "Create a financial model for investor pitch"

**What you type:**

```
/fin financial-model "Series A raise, $5M target, current: $1.2M ARR,
growing 15% MoM, 72% gross margin, 18-month runway needed"
```

**What ArkaOS does:**

Helena (CFO) and Vasco (Financial Analyst) build a comprehensive model:

1. Revenue projection (3 scenarios: base, bull, bear)
2. Cost structure with headcount plan
3. Unit economics evolution over time
4. Cash flow with fundraising milestones
5. Dilution analysis
6. Key metrics investors look for at Series A

**What you get:**

A complete 3-year financial model with:
- Monthly revenue projections (3 scenarios)
- Headcount plan with salary costs by role
- Gross margin and operating margin trajectory
- Cash runway with and without funding
- Use of funds breakdown ($5M allocation)
- Key metrics dashboard: ARR, NRR, CAC, LTV, burn multiple
- Sensitivity tables showing outcomes at different growth rates

Output is structured for direct inclusion in a pitch deck with data tables and narrative summaries.

---

### "Design the brand identity for my startup"

**What you type:**

```
/brand identity-system "AI-powered legal document platform for small businesses,
name is 'Clearlaw', values are simplicity and accessibility, competitors feel
corporate and intimidating"
```

**What ArkaOS does:**

Valentina (Creative Director) runs the full brand identity workflow:

1. Mateus (Brand Strategist) determines archetype, positioning, and voice
2. Isabel (Visual Designer) creates color palette, typography direction, and visual principles
3. The system checks accessibility (WCAG contrast ratios)
4. Valentina reviews for coherence and signs off

**What you get:**

```
BRAND IDENTITY: Clearlaw

ARCHETYPE: The Sage (primary) + The Everyman (secondary)
  "Making legal clarity accessible to everyone"

POSITIONING:
  For: Small business owners who need legal documents
  Unlike: Traditional legal services that are expensive and confusing
  We: Make legal documents simple, fast, and affordable
  Because: AI understands legal language so you don't have to

VOICE:
  Tone scale: Professional [===|====] Casual (60/40)
  Keywords: Clear, simple, confident, helpful
  Never: Jargon, legalese, condescending, robotic
  Example: "Your NDA is ready. Plain English, legally solid."

COLORS:
  Primary: #1B4D6E (deep teal -- trust, professionalism)
  Secondary: #F4A261 (warm amber -- approachability, energy)
  Neutral: #F8F9FA (light gray -- clean, modern)
  Accent: #2D9CDB (bright blue -- action, clarity)
  All pairs pass WCAG AA contrast requirements

TYPOGRAPHY DIRECTION:
  Headings: Geometric sans-serif (modern, clean)
  Body: Humanist sans-serif (readable, friendly)

VISUAL PRINCIPLES:
  1. White space is your friend -- never crowd the interface
  2. Icons over illustrations -- clarity over decoration
  3. One accent color per screen -- guide the eye, don't overwhelm
```

---

### "Plan the Q3 OKRs for my team"

**What you type:**

```
/lead okr-set "Engineering team, 12 people, main goals: reduce tech debt,
ship billing v2, improve deployment reliability. Company goal is reaching
$5M ARR by end of year."
```

**What ArkaOS does:**

Rodrigo (Leadership Lead) creates a cascaded OKR structure:

1. Aligns team objectives to the company-level $5M ARR goal
2. Creates 3 objectives with 3 key results each
3. Maps each KR to specific initiatives
4. Adds health metrics to track along the way

**What you get:**

```
Q3 OKRs: Engineering Team

OBJECTIVE 1: Ship Billing v2 to unlock expansion revenue
  KR1: Billing v2 in production with 0 critical bugs by Aug 15
  KR2: 95% of existing customers migrated to new billing by Sep 15
  KR3: Self-service plan upgrades live, reducing support tickets by 40%
  Initiative: 2 engineers dedicated, 6-week build cycle

OBJECTIVE 2: Reduce tech debt to increase development velocity
  KR1: Reduce average PR cycle time from 4.2 days to 2.0 days
  KR2: Eliminate 5 of top 10 tech debt hotspots (per debt analyzer)
  KR3: Increase test coverage from 62% to 80% on critical paths
  Initiative: 20% time allocation, rotating debt sprints

OBJECTIVE 3: Improve deployment reliability to support growth
  KR1: Achieve 99.9% uptime (from current 99.4%)
  KR2: Zero-downtime deploys on 100% of releases (currently 70%)
  KR3: Mean time to recovery under 15 minutes (currently 45 min)
  Initiative: Dedicated DevOps sprint in week 2, monitoring overhaul

HEALTH METRICS (track but don't optimize):
  - Team satisfaction score (pulse survey)
  - Unplanned work ratio (target < 20%)
  - On-call burden (target: max 1 incident/week per person)
```

---

## Quick Reference: What to Type for Common Tasks

| I want to... | Type this |
|--------------|-----------|
| Fix a bug | Describe the bug in plain language |
| Build a feature | `/dev feature "description"` |
| Review code | `/dev code-review` |
| Audit SEO | `/mkt seo-audit` |
| Create email campaign | `/mkt email-sequence "product, audience, price"` |
| Build a brand | `/brand identity-system "description"` |
| Financial model | `/fin financial-model "details"` |
| Validate SaaS idea | `/saas validate-idea "description"` |
| Write landing page | `/landing copy-framework "product, price, audience"` |
| Create viral content | `/content hook-write "topic, platform, audience"` |
| Plan a sprint | `/pm sprint-plan "epic, team size, duration"` |
| Set OKRs | `/lead okr-set "team, goals, company context"` |
| GDPR check | `/ops gdpr-compliance` |
| Research a topic | `/kb research "topic"` |
| Analyze strategy | `/strat blue-ocean "market"` |
