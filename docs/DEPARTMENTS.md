# ArkaOS Departments

17 departments. 65 agents. 244 skills. Every department has a lead, specialized agents, and framework-backed skills. The Quality Gate reviews everything before it reaches you.

## How Departments Work

When you send a request, ArkaOS routes it to a department. The department lead assigns the work to the right agent(s). Agents execute using validated enterprise frameworks. The Quality Gate reviews the output. You get the result.

```
Your request --> Synapse routing --> Department lead --> Agent(s) execute --> Quality Gate --> You
```

## Development (`/dev`)

**What it does.** Full-stack software development: features, APIs, architecture, security audits, CI/CD, database design, debugging, and deployment. Covers the entire software lifecycle from spec to production.

**Lead:** Paulo (Tech Lead) -- methodical, quality-driven, follows SOLID and clean code principles religiously. DISC profile: C+D (Analyst-Driver). Will push back if a spec is vague.

**Agents (10):** Marco (CTO), Gabriel (Architect), Andre (Senior Backend Dev), Mariana (Frontend Dev), Lucas (Research Analyst), Diogo (DBA), Nuno (DevOps Engineer), Tiago (QA Engineer), Rita (Security Engineer), Pedro (Research Assistant)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `feature` | 9-phase enterprise workflow: spec, research, architecture, implementation, testing, security audit, self-critique, quality gate, delivery | `/dev feature "multi-tenant billing with Stripe"` |
| `code-review` | Reviews code for quality, security, patterns, and test coverage | `/dev code-review` (analyzes your current changes) |
| `security-audit` | OWASP-based security scan with severity ratings and fix recommendations | `/dev security-audit` (scans entire project) |

**When to use this department:**
- Building any software feature from scratch
- Debugging a failing system
- Setting up infrastructure (CI/CD, monitoring, deployment)
- Reviewing code before a release
- Designing database schemas or APIs

**Example workflow -- "Add OAuth2 login":**
Paulo receives the request. Gabriel designs the architecture (ADR). Andre implements the backend (Laravel Socialite, migrations, service layer). Mariana builds the frontend (OAuth buttons, callback handling). Tiago writes feature tests. Rita runs a security audit on the token flow. Marta reviews everything. You get production-ready code with tests.

---

## Marketing (`/mkt`)

**What it does.** Growth marketing: SEO audits, email sequences, paid campaigns, growth loops, content calendars, programmatic SEO, competitor analysis, and marketing automation.

**Lead:** Luna (Marketing Lead) -- creative, data-driven, thinks in funnels and loops. DISC profile: I+D (Inspirer-Driver). Energized by campaigns that compound.

**Agents (4):** Luna (Marketing Lead), Sara (SEO Specialist), Joana (Email Marketing), Filipe (Growth Hacker)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `seo-audit` | Full on-page and technical SEO analysis with prioritized fix list | `/mkt seo-audit` |
| `email-sequence` | Creates multi-email sequences using Brunson/AIDA frameworks | `/mkt email-sequence "SaaS launch, $49/mo, developer audience"` |
| `growth-loop` | Designs self-reinforcing growth loops for your product | `/mkt growth-loop "marketplace for freelance developers"` |

**When to use this department:**
- Planning a product launch campaign
- Improving organic search rankings
- Creating email marketing sequences
- Running paid ads (Google, Meta, LinkedIn)
- Analyzing competitor marketing strategies

---

## Brand and Design (`/brand`)

**What it does.** Brand identity creation: naming, color palettes, archetypes, voice guides, design systems, UX audits, mockups, and positioning. Uses Primal Branding, StoryBrand, and Jungian Archetypes.

**Lead:** Valentina (Creative Director) -- bold, intuitive, obsessed with consistency. DISC profile: I+S (Inspirer-Supporter). Fights for brand coherence across every touchpoint.

**Agents (4):** Valentina (Creative Director), Mateus (Brand Strategist), Isabel (Visual Designer), Rafael (Motion Designer)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `identity-system` | Complete brand identity: positioning, archetype, colors, voice, visual direction | `/brand identity-system "sustainable fashion marketplace"` |
| `voice-guide` | Brand voice document with tone scales, do/don't examples, and sample copy | `/brand voice-guide "playful but credible fintech"` |
| `ux-audit` | Nielsen heuristics + Laws of UX evaluation with severity ratings | `/brand ux-audit` |

**When to use this department:**
- Starting a new company or product and need a brand
- Redesigning visual identity
- Creating a design system for your product
- Auditing user experience
- Ensuring brand consistency across channels

---

## Finance (`/fin`)

**What it does.** Financial modeling, DCF valuation, budgets, unit economics, cash flow forecasting, pitch deck financials, and CISO advisory. Uses Damodaran DCF methodology, COSO ERM, and standard SaaS metrics.

**Lead:** Helena (CFO) -- precise, risk-aware, speaks in numbers. DISC profile: C+S (Analyst-Supporter). Will not approve a budget without three scenarios.

**Agents (3):** Helena (CFO), Vasco (Financial Analyst), Catarina (Investment Analyst)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `valuation-model` | DCF valuation with sensitivity analysis and comparable company multiples | `/fin valuation-model "SaaS, $3M ARR, 35% growth, 70% margins"` |
| `unit-economics` | Full unit economics breakdown with LTV/CAC ratios and payback period | `/fin unit-economics "CAC $200, ARPU $50/mo, churn 3%/mo"` |
| `financial-model` | 3-year financial model with revenue, expenses, and fundraising scenarios | `/fin financial-model "Series A prep, $8M target"` |

**When to use this department:**
- Preparing for a fundraise
- Building financial projections
- Analyzing whether a project is worth the investment
- Planning annual or quarterly budgets
- Understanding unit economics of your business

---

## Strategy (`/strat`)

**What it does.** Strategic analysis: Blue Ocean, Porter's Five Forces, Business Model Canvas, Wardley Mapping, competitive intelligence, and structured brainstorming with 5 perspective agents.

**Lead:** Tomas (Strategy Director) -- analytical, long-term thinker, connects dots others miss. DISC profile: C+D (Analyst-Driver). Obsessed with finding asymmetric advantages.

**Agents (3):** Tomas (Strategy Director), Ana (Market Analyst), Bruno (Innovation Specialist)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `blue-ocean` | Blue Ocean strategy with value curve, eliminate-reduce-raise-create grid | `/strat blue-ocean "project management tools for agencies"` |
| `brainstorm` | 5 agents debate: Visionary, Pragmatist, Devil's Advocate, Customer Voice, Analyst | `/strat brainstorm "should we pivot from B2C to B2B?"` |
| `bmc` | Business Model Canvas with all 9 blocks filled and validated | `/strat bmc "on-demand tutoring platform"` |

**When to use this department:**
- Evaluating a market before entering
- Making a major strategic decision (pivot, expansion, partnership)
- Analyzing competitive landscape
- Designing or redesigning your business model

---

## E-Commerce (`/ecom`)

**What it does.** Store optimization: full audits (UX, SEO, performance, content, conversion), pricing strategies, product listings, RFM segmentation, and CRO. Uses ResearchXL, Baymard Institute guidelines, and MACH architecture.

**Lead:** Ricardo (E-Commerce Lead) -- conversion-obsessed, data-first, A/B tests everything. DISC profile: D+C (Driver-Analyst).

**Agents (4):** Ricardo (E-Commerce Lead), Ines (CRO Specialist), Sofia (Product Manager), Pedro (Analytics Engineer)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `store-audit` | 5-agent parallel audit: UX, SEO, performance, content, conversion | `/ecom store-audit "https://myshop.com"` |
| `pricing-strategy` | Price elasticity analysis with tiering recommendations | `/ecom pricing-strategy "subscription box, competitors at $25-45"` |
| `rfm-analysis` | RFM customer segmentation with targeted retention strategies | `/ecom rfm-analysis` |

**When to use this department:**
- Launching or optimizing an online store
- Improving conversion rates
- Setting pricing for products or subscriptions
- Segmenting customers for targeted campaigns

---

## Knowledge (`/kb`)

**What it does.** Research, learning, and knowledge management. Deep research with citations, YouTube video analysis, persona building from sources, Zettelkasten note creation, and Obsidian vault management.

**Lead:** Clara (Knowledge Lead) -- methodical researcher, connects ideas across domains. DISC profile: S+C (Supporter-Analyst).

**Agents (4):** Clara (Knowledge Lead), Miguel (Research Analyst), Teresa (Librarian), Antonio (Curator)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `research` | Deep research with source citations and structured findings | `/kb research "state of AI code generation in 2026"` |
| `learn` | Ingest YouTube, PDF, or web content into your knowledge base | `/kb learn "https://youtube.com/watch?v=..."` |
| `persona-build` | Build a persona from multiple knowledge sources | `/kb persona-build "Naval Ravikant" --sources youtube,podcasts,books` |

**When to use this department:**
- Researching a new topic before making decisions
- Building a knowledge base from videos, books, and articles
- Creating personas from public figures for writing or strategy
- Organizing research into actionable notes

---

## Operations (`/ops`)

**What it does.** Process automation, compliance, risk management, SOP creation, and audit preparation. Covers GDPR, ISO 27001, SOC 2, and general operational excellence using Lean and Theory of Constraints.

**Lead:** Daniel (Ops Lead) -- process-oriented, risk-aware, automates everything possible. DISC profile: C+S (Analyst-Supporter).

**Agents (3):** Daniel (Ops Lead), Carla (Compliance Officer), Hugo (Automation Engineer)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `sop-create` | Standard Operating Procedure with steps, checklists, and responsibilities | `/ops sop-create "customer support escalation process"` |
| `gdpr-compliance` | GDPR readiness assessment with gap analysis and remediation plan | `/ops gdpr-compliance` |
| `automate` | Identify automation opportunities in a workflow with ROI estimates | `/ops automate "monthly invoice generation and sending"` |

**When to use this department:**
- Preparing for compliance audits
- Documenting business processes
- Automating repetitive workflows
- Assessing operational risks

---

## Project Management (`/pm`)

**What it does.** Agile planning: sprint planning, roadmap building, user story writing, continuous discovery, Shape Up pitches, and backlog grooming. Supports Scrum, Kanban, and Shape Up.

**Lead:** Carolina (PM Director) -- organized, outcome-focused, writes clear acceptance criteria. DISC profile: D+S (Driver-Supporter).

**Agents (3):** Carolina (PM Director), Pedro (Scrum Master), Diana (Product Owner)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `sprint-plan` | Sprint plan with stories, points, capacity, and sprint goal | `/pm sprint-plan "payments epic, team of 4, 2-week sprint"` |
| `roadmap-build` | Quarterly roadmap with themes, milestones, and dependencies | `/pm roadmap-build "2026 H2 product roadmap"` |
| `story-write` | User stories with acceptance criteria, technical notes, and test scenarios | `/pm story-write "export dashboard data to PDF"` |

**When to use this department:**
- Planning sprints or quarters
- Writing clear user stories and specs
- Building a product roadmap
- Running discovery on customer needs

---

## SaaS (`/saas`)

**What it does.** SaaS-specific strategy: idea validation, metrics dashboards, PLG design, churn analysis, go-to-market, pricing, and micro-SaaS scaffolding. Uses T2D3, PLG frameworks, and the Micro-SaaS Playbook.

**Lead:** Tiago (SaaS Strategist) -- metrics-obsessed, validates before building. DISC profile: C+D (Analyst-Driver).

**Agents (4):** Tiago (SaaS Strategist), Ana (Growth Analyst), Rui (Product Engineer), Marta (Customer Success)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `validate-idea` | 5-point validation: market size, competitors, unit economics, feasibility, GTM fit | `/saas validate-idea "AI resume builder, $12/mo"` |
| `metrics-dashboard` | Design metrics dashboard with KPIs, alerts, and visualization spec | `/saas metrics-dashboard` |
| `plg-setup` | PLG strategy: free tier design, activation metrics, conversion triggers | `/saas plg-setup "API monitoring tool with free tier"` |

**When to use this department:**
- Validating a SaaS idea before building
- Designing pricing and packaging
- Reducing churn
- Planning go-to-market strategy
- Building a micro-SaaS from scratch

---

## Landing Pages (`/landing`)

**What it does.** High-converting copy and funnel design: AIDA/PAS copy frameworks, Grand Slam Offers (Hormozi), VSL scripts, funnel architecture, and page optimization. Uses Value Ladder and offer stack design.

**Lead:** Ines (Landing Lead) -- conversion-focused, writes copy that sells. DISC profile: I+D (Inspirer-Driver).

**Agents (4):** Ines (Landing Lead), Joao (Copywriter), Sara (Funnel Architect), Miguel (CRO Analyst)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `copy-framework` | Landing page copy using AIDA, PAS, or StoryBrand with multiple variants | `/landing copy-framework "online course teaching Python, $197"` |
| `funnel-design` | Complete funnel architecture: pages, emails, upsells, downsells | `/landing funnel-design "webinar funnel for coaching business"` |
| `grand-slam-offer` | Hormozi Grand Slam Offer with value stack, bonuses, and guarantee | `/landing grand-slam-offer "fitness transformation program, $997"` |

**When to use this department:**
- Launching a product and need a landing page
- Building a sales funnel
- Writing sales copy for any product
- Optimizing an underperforming landing page

---

## Content (`/content`)

**What it does.** Content creation and viralization: hook writing, viral content design, YouTube scripts, podcast planning, content repurposing, and content operating systems. Uses STEPPS (Berger), Hook Architecture, and Content OS frameworks.

**Lead:** Rafael (Content Strategist) -- creative, platform-native, understands algorithms. DISC profile: I+D (Inspirer-Driver).

**Agents (4):** Rafael (Content Strategist), Ana (Video Producer), Carlos (Copywriter), Lucia (Repurposing Specialist)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `hook-write` | 10 viral hooks for short-form video with retention analysis | `/content hook-write "JavaScript tips for beginners"` |
| `viral-design` | Content strategy using STEPPS framework for maximum shareability | `/content viral-design "developer personal brand on LinkedIn"` |
| `content-os` | Complete content operating system: cadence, platforms, repurposing pipeline | `/content content-os "weekly YouTube + daily Twitter/LinkedIn"` |

**When to use this department:**
- Building a content strategy from scratch
- Creating viral short-form video scripts
- Planning YouTube content with retention optimization
- Repurposing long content into multiple formats

---

## Communities (`/community`)

**What it does.** Community building: platform setup, growth plans, gamification, membership models, and engagement strategies. Uses SPACES framework, Membership Economy, and Platform Matrix.

**Lead:** Beatriz (Community Strategist) -- empathetic, community-first, builds belonging. DISC profile: S+I (Supporter-Inspirer).

**Agents (3):** Beatriz (Community Strategist), Carlos (Engagement Manager), Teresa (Membership Designer)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `platform-setup` | Community platform recommendation and setup guide | `/community platform-setup "paid developer community, 200 initial members"` |
| `growth-plan` | Community growth strategy with acquisition channels and milestones | `/community growth-plan "target 5000 members in 12 months"` |
| `gamification` | Points, badges, levels, and reward system design | `/community gamification "learning platform for designers"` |

**When to use this department:**
- Launching a community or membership
- Growing an existing community
- Adding gamification to increase engagement
- Designing membership tiers and pricing

---

## Sales (`/sales`)

**What it does.** Sales operations: pipeline management, SPIN selling, negotiation preparation, cold outreach, and deal strategy. Uses SPIN, Challenger Sale, and MEDDIC frameworks.

**Lead:** Miguel (Sales Director) -- assertive, relationship-builder, closes with confidence. DISC profile: D+I (Driver-Inspirer).

**Agents (3):** Miguel (Sales Director), Ricardo (Account Executive), Sofia (SDR)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `spin-sell` | SPIN selling framework applied to a specific deal | `/sales spin-sell "enterprise HR platform, $100K ACV"` |
| `pipeline-manage` | Pipeline review with deal health scores and next actions | `/sales pipeline-manage` |
| `cold-outreach` | Multi-touch outreach sequence (email + LinkedIn) | `/sales cold-outreach "VP Product at Series B SaaS companies"` |

**When to use this department:**
- Preparing for a sales meeting
- Building outreach sequences
- Managing your sales pipeline
- Preparing for a negotiation

---

## Leadership (`/lead`)

**What it does.** People leadership: OKR setting, team health checks, hiring plans, culture playbooks, 1-on-1 templates, and performance frameworks. Uses Lencioni's 5 Dysfunctions, Netflix Culture, and OKR methodology.

**Lead:** Rodrigo (Leadership Lead) -- empathetic, principled, develops people. DISC profile: S+D (Supporter-Driver).

**Agents (3):** Rodrigo (Leadership Lead), Ana (People Partner), Filipe (Talent Acquisition)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `okr-set` | OKR cascade from company to team to individual level | `/lead okr-set "Q3 company OKRs focused on expansion"` |
| `team-health` | Team health assessment using Lencioni's framework with action items | `/lead team-health` |
| `hiring-plan` | Hiring plan with roles, JDs, interview scorecards, and timeline | `/lead hiring-plan "3 engineers + 1 designer in 4 months"` |

**When to use this department:**
- Setting quarterly OKRs
- Diagnosing team issues
- Planning hires
- Building company culture documentation

---

## Organization (`/org`)

**What it does.** Organizational design: team structures, topology analysis, compensation frameworks, and scaling playbooks. Uses Team Topologies, Spotify Model insights, and compensation benchmarking.

**Lead:** Sofia (COO) -- systems thinker, designs for scale. DISC profile: C+D (Analyst-Driver). Tier 0 authority.

**Agents (3):** Sofia (COO), Pedro (Org Designer), Carla (Compensation Analyst)

**Top skills with examples:**

| Skill | What it does | Example |
|-------|-------------|---------|
| `design` | Org chart design with reporting lines, team sizes, and growth plan | `/org design "scaling from 15 to 50, engineering-heavy"` |
| `team-topology` | Team Topologies analysis: stream-aligned, platform, enabling, complicated-subsystem | `/org team-topology "current 4-team setup, adding 2 more"` |
| `compensation` | Compensation bands with levels, benchmarks, and equity guidelines | `/org compensation "engineering IC track, Lisbon market"` |

**When to use this department:**
- Designing or restructuring your organization
- Defining team boundaries and interactions
- Creating compensation frameworks
- Planning organizational growth

---

## Quality Gate (Automatic)

**What it does.** Mandatory review on every workflow output. Nothing reaches you without passing the Quality Gate. This is non-negotiable.

**Lead:** Marta (CQO) -- exacting, binary verdicts, no exceptions. DISC profile: C (pure Analyst). Tier 0 authority with absolute veto.

**Agents (3):**
- **Marta (CQO)** -- orchestrates the review, issues APPROVED or REJECTED
- **Eduardo (Copy Director)** -- reviews all text: spelling, grammar, tone, AI pattern detection
- **Francisca (Tech Director)** -- reviews all technical output: code quality, tests, UX, security

The verdict is binary. APPROVED means it ships. REJECTED means the responsible agent fixes the issues and resubmits. There is no "good enough."

---

## Agent Hierarchy

| Tier | Role | Count | Authority | Examples |
|------|------|-------|-----------|----------|
| 0 | C-Suite | 6 | Veto power, approve architecture and budgets, block releases | Marco (CTO), Helena (CFO), Sofia (COO), Marta (CQO) |
| 1 | Squad Leads | 16 | Orchestrate department, delegate to specialists, approve within scope | Paulo, Luna, Valentina, Tomas, all department leads |
| 2 | Specialists | 40 | Execute framework-backed work within their domain | Andre, Gabriel, Sara, Joana, all specialist agents |
| 3 | Support | 3 | Research, documentation, data collection | Research assistants |

## Behavioral DNA

Every agent has a complete personality profile from 4 psychological frameworks. This is not cosmetic -- it shapes how they communicate, what they prioritize, and how they handle pressure.

- **DISC** -- How they communicate. A C-type (Analyst) gives you detailed reports. A D-type (Driver) gives you action items.
- **Enneagram** -- What motivates them. A Type 1 (Reformer) pushes for correctness. A Type 3 (Achiever) pushes for results.
- **Big Five (OCEAN)** -- Personality trait intensities on a 0-100 scale. High Conscientiousness agents are detail-oriented. High Openness agents are creative.
- **MBTI** -- How they process information. An INTJ designs systems. An ENFP generates ideas.

You can browse every agent's full profile in the dashboard at **Agents** page.
