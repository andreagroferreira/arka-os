# ARKA OS — Departments Guide

ARKA OS is organized into 7 departments, each with specialized AI team members. This guide explains what each department does, who's on the team, and what you can accomplish.

All agents follow the [CONSTITUTION.md](../CONSTITUTION.md) — a formal governance document with 3 enforcement levels (NON-NEGOTIABLE, MUST, SHOULD).

### Agent Tier Hierarchy

Every agent has a tier that defines their authority level:

| Tier | Role | Agents |
|------|------|--------|
| 0 (Chief) | Veto power, final decisions | CTO Marco, CFO Helena, COO Sofia |
| 1 (Lead) | Orchestrate, design, recommend | Tech Lead Paulo, Architect Gabriel, Luna, Ricardo, Tomas, Clara |
| 2 (Specialist) | Implement within boundaries | Andre, Diana, Bruno, Carlos |
| 3 (Support) | Validate, research, document | QA Rita, Analyst Lucas |

Key authority rules:
- Only **Carlos (DevOps)** can push to remote and deploy
- Only **Tier 0 agents** (Marco, Helena, Sofia) can veto decisions
- Only **Bruno (Security)** and **Rita (QA)** can block releases

### Agent Memory

Each agent has persistent memory at `~/.claude/agent-memory/arka-<name>/MEMORY.md` that survives across sessions. Agents record key decisions, recurring patterns, gotchas, and learned preferences. Memory files are never overwritten during updates.

---

## System — `/arka`

### What This Department Does

The System department is the control center of ARKA OS. It gives you an overview of everything happening across your business — projects, tasks, meetings, and system health. Think of it as your daily briefing.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/arka help` | See every command across all departments |
| `/arka standup` | Get a daily summary of what's going on — active projects, pending tasks, upcoming meetings, unread emails, and tech updates |
| `/arka status` | Check system health — your version, active departments, team members, integrations, and installed skills |
| `/arka monitor` | Scan your tech stack for updates and get recommendations |
| `/arka onboard <project>` | Initialize a new project with context files and an Obsidian page |

### Real-World Examples

**Morning routine:**
```
/arka standup
```
Start your day with a full picture: what projects need attention, what tasks are due, and what meetings are coming up.

**After installing a new skill:**
```
/arka status
```
Verify everything is working and see your updated setup.

### Where Results Are Saved

System reports are saved to `WizardingCode/Operations/` in your Obsidian vault.

---

## Development — `/dev`

### What This Department Does

The Development department is an enterprise-grade team of 9 specialized agents that handles everything related to building software — planning architecture, researching libraries, creating projects, writing features with mandatory security audits and self-critique, reviewing code, running tests, and deploying. It follows a structured multi-phase workflow with TODO tracking and always reads your project context before making changes.

### The Team

**Marco — CTO** `Tier 0`
15 years of experience building SaaS products and APIs. Marco is the final technical authority — he makes architecture decisions, reviews code, and has veto power on any design. His priority order: security, scalability, maintainability, then speed. Authority: `veto`, `approve_architecture`, `approve_tech_stack`, `block_release`.

**Paulo — Tech Lead (Orchestrator)** `Tier 1`
12 years leading engineering teams. Paulo doesn't write code — he orchestrates. He creates TODO lists before any work begins, manages workflow phases, coordinates the team, and writes final reports. Nothing starts without Paulo's plan. Authority: `orchestrate`, `assign_tasks`.

**Gabriel — Software Architect** `Tier 1`
12 years designing systems. Gabriel designs before anyone builds — data flows, API contracts, component hierarchies, schema changes. He writes Architecture Decision Records (ADRs) to Obsidian and gets Marco's approval before implementation starts. Authority: `design_architecture`, `create_adr`.

**Andre — Senior Backend Developer** `Tier 2`
10 years building web applications. Andre is the backend builder — Laravel, PHP, PostgreSQL, API design. He reads existing code patterns before writing anything new, follows the implementation order (Migration → Model → Service → Controller → FormRequest → Resource → Routes), and always reads 2-3 similar files first. Authority: `implement`.

**Diana — Senior Frontend Developer** `Tier 2`
8 years building user interfaces. Diana handles Vue 3, Nuxt 3, React, and Next.js. She thinks in components, demands pixel-perfect UIs, and never ships without loading states, error states, empty states, and accessibility (ARIA, keyboard nav). Authority: `implement`.

**Bruno — Security Engineer** `Tier 2`
10 years in application security. Bruno runs OWASP Top 10 checks on every feature before it ships. He's professionally paranoid — every input is malicious until proven otherwise. Critical issues block shipping, period. Authority: `block_release`, `security_audit`.

**Rita — QA Lead** `Tier 3`
Rita breaks things — on purpose — and defines the quality bar. She designs test strategies, writes feature/unit/component tests, enforces quality gates (≥80% coverage, all tests green), and blocks shipping when criteria aren't met. Authority: `block_release`, `validate`.

**Carlos — DevOps Lead** `Tier 2`
9 years automating infrastructure. Carlos handles CI/CD pipelines, Docker, zero-downtime deployments, monitoring (Sentry), and environment management. If it can be automated, it will be. Authority: `push`, `deploy`, `manage_ci`. (Only agent with push/deploy permissions.)

**Lucas — Technical Analyst** `Tier 3`
7 years in technical research. Lucas fetches up-to-date framework docs via Context7 MCP, searches the Obsidian KB for existing patterns, evaluates libraries, and documents everything. Every development session starts with his research. Authority: `research`, `recommend`.

### Enterprise Workflow

Features and APIs follow an 10-phase enterprise workflow:

1. **Orchestration** — Paulo creates TODO list, creates feature branch, detects stack
2. **Research** — Lucas fetches docs (Context7), searches KB, checks codebase
3. **Architecture** — Gabriel designs, writes ADR. Marco reviews and approves.
4. **Implementation** — Andre (backend) + Diana (frontend) build in parallel
5. **Self-Critique** — Each developer reviews their own work against checklists
6. **Security Audit** — Bruno runs OWASP Top 10 against new code
7. **QA** — Rita writes tests, runs suite, enforces quality gate
8. **Documentation** — Lucas saves patterns to KB, Paulo writes final report

Simpler commands (debug, refactor, db) use a focused 3-4 phase workflow. Read-only commands (review, test, deploy, docs, research) use 1-2 phases.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/dev do <description>` | Describe what you need in plain language — Paulo interprets, asks questions if needed, and routes to the right workflow automatically |
| `/dev scaffold <type> <name>` | Create a complete project from a starter template with dependencies installed and integrations configured |
| `/dev feature <description>` | Implement a new feature with full 10-phase enterprise workflow |
| `/dev api <spec>` | Generate API endpoints with full 10-phase enterprise workflow |
| `/dev plan <description>` | Architecture planning only — Gabriel designs, no code changes |
| `/dev debug <issue>` | Diagnose and fix a bug with triage, fix, and regression test |
| `/dev refactor <target>` | Refactor code with quality gates — tests must pass before and after |
| `/dev review` | Code review from Marco (CTO) + Bruno (Security) |
| `/dev test` | Run your test suite and get a quality report from Rita |
| `/dev deploy <environment>` | Deploy to staging or production |
| `/dev db <description>` | Create database migrations and update models |
| `/dev docs` | Generate technical documentation |
| `/dev stack-check` | Check for dependency updates |
| `/dev security-audit` | Standalone OWASP security audit of your codebase |
| `/dev research <topic>` | Research a library, framework, or integration with Context7 docs |
| `/dev mcp apply <profile>` | Configure integrations for a project |
| `/dev skill install <url>` | Install a community skill |

### Branch Isolation (Automatic)

Commands that modify code — `/dev feature`, `/dev api`, `/dev debug`, `/dev refactor`, `/dev db` — automatically run on a **dedicated feature branch**. This means:

- A new branch is created from `dev` (e.g., `feature/user-auth`, `fix/login-crash`, `refactor/controllers`)
- All code changes happen on this isolated branch
- Your main and dev branches stay clean and untouched
- After the work is done, you can review it and create a Merge Request to `dev`

You don't need to do anything — the branch is created automatically when you run the command.

### Real-World Examples

**Just describe what you need:**
```
/dev do "quero adicionar autenticação com social login Google e GitHub"
```
Paulo reads the project context, classifies the request as a Feature, asks if you want backend-only or full-stack, then routes to `/dev feature` with the full 10-phase enterprise workflow. You don't need to remember which command to use.

**Build a feature (full enterprise workflow):**
```
/dev feature "add user registration with email verification"
```
Paulo creates a TODO list, creates a feature branch (`feature/user-registration`). Lucas researches Laravel auth docs. Gabriel designs the data flow and writes an ADR. Andre implements the backend (migration, model, service, controller). Diana builds the frontend (composable, component, page). Both self-critique their work. Bruno runs a security audit. Rita writes tests and enforces quality gates. Lucas saves patterns to the KB. Paulo writes the final report.

**Plan before building:**
```
/dev plan "payment system with Stripe"
```
Lucas researches Stripe integration options (Context7 + KB). Gabriel designs the architecture and writes an ADR. Paulo presents the plan with estimates. No code is written — run `/dev feature` afterward to implement.

**Run a security audit:**
```
/dev security-audit
```
Bruno runs OWASP Top 10 against your codebase. Lucas researches any CVEs found. You get a detailed report with severity, location, and fixes.

**Research before deciding:**
```
/dev research "payment gateways"
```
Lucas fetches docs, evaluates options (Stripe vs Paddle vs Cashier), checks your KB for prior decisions, and delivers a comparison report.

### Where Results Are Saved

- **Architecture decisions:** `Projects/<name>/Architecture/ADR-<NNN>.md`
- **Security audits:** `Projects/<name>/Architecture/Security-Audit-<date>.md`
- **Technical docs:** `Projects/<name>/Docs/`
- **Research:** `Projects/<name>/Docs/Research-<topic>.md`

---

## Marketing — `/mkt`

### What This Department Does

The Marketing department creates content for every platform — social media, email, blogs, ads, and landing pages. It adapts to each platform's style and can write in the voice of any persona in your knowledge base.

### The Team

**Luna — Content Creator** `Tier 1`
Luna is a trend-aware content machine. She knows that Instagram is visual-first, LinkedIn is professional, TikTok needs to be raw and authentic, and X/Twitter demands brevity. She uses proven content frameworks — Hook-Story-Offer, Problem-Agitate-Solve, Before-After-Bridge — and adapts to whatever voice your brand needs. Authority: `create_content`, `manage_campaigns`.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/mkt social <platform> <topic>` | Get platform-specific social media posts with captions, hashtags, and formatting |
| `/mkt calendar <period>` | Get a full content calendar with themes, post ideas, and scheduling |
| `/mkt reels <topic>` | Get scripts for Reels, TikTok, or YouTube Shorts with hooks and visual cues |
| `/mkt email <type> <topic>` | Get email sequences — welcome series, nurture, sales, re-engagement |
| `/mkt landing <product>` | Get landing page copy with headlines, benefits, social proof sections, and CTAs |
| `/mkt ads <platform> <product>` | Get ad copy optimized for Facebook, Google, Instagram, or any platform |
| `/mkt affiliate <analysis>` | Get an analysis of affiliate marketing opportunities |
| `/mkt blog <topic>` | Get a full blog article, SEO-optimized and ready to publish |
| `/mkt copy-analysis <url>` | Get a teardown of existing copy with specific improvement suggestions |
| `/mkt brand-guide` | Get comprehensive brand guidelines |
| `/mkt audit` | Get a complete marketing audit across all channels |

### Real-World Examples

**Create Instagram content for a product launch:**
```
/mkt social instagram "We're launching a new project management tool for freelancers"
```
Luna creates multiple post variations with captions, hashtags, visual direction, and posting times.

**Plan a month of content:**
```
/mkt calendar "April 2026"
```
Get a day-by-day calendar with themes, content types, platform assignments, and topic ideas.

**Write a sales email sequence:**
```
/mkt email sales "SaaS free trial ending"
```
Get a multi-email sequence designed to convert free trial users to paying customers.

### Where Results Are Saved

All marketing content goes to `WizardingCode/Marketing/` in your Obsidian vault.

---

## E-commerce — `/ecom`

### What This Department Does

The E-commerce department helps you run and grow online stores. It can audit your store from every angle, optimize product listings, analyze pricing, study competitors, and plan product launches.

### The Team

**Ricardo — E-commerce Manager** `Tier 1`
8 years scaling online stores to 7 figures. Ricardo is conversion-obsessed and data-driven. He analyzes stores by following the customer journey: traffic source, funnel steps, product pages, pricing, email flows, SEO, and customer lifetime value. Every recommendation comes with expected impact. Authority: `manage_store`, `pricing_decisions`.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/ecom audit <store-url>` | Five AI analysts audit your store simultaneously — UX, SEO, performance, content, and conversion — then deliver a combined report |
| `/ecom product <listing>` | Optimize a product listing — title, description, images, keywords, and SEO |
| `/ecom pricing <product>` | Analyze your pricing versus competitors and recommend a strategy |
| `/ecom competitors <niche>` | Deep competitive analysis — who's winning, why, and where their gaps are |
| `/ecom launch <product>` | Complete launch plan with timeline, marketing, email sequences, and ad strategy |
| `/ecom ads <product>` | Ad campaigns designed for e-commerce conversion |
| `/ecom email-flows` | Automated email sequences — welcome, abandoned cart, post-purchase, win-back |
| `/ecom report` | Performance report with metrics, trends, and action items |

### Real-World Examples

**Audit your store:**
```
/ecom audit "https://myshopifystore.com"
```
Five specialists analyze your store at once. You get a detailed report covering UX issues, SEO gaps, slow pages, content problems, and conversion killers — with prioritized fixes.

**Optimize a product listing:**
```
/ecom product "Premium Wireless Headphones - Model X Pro"
```
Ricardo rewrites your title, description, and bullet points to maximize conversions and search visibility.

**Plan a product launch:**
```
/ecom launch "summer sunglasses collection"
```
Get a complete launch plan: pre-launch buzz, launch day strategy, email sequences, social media plan, ad campaigns, and post-launch follow-up.

### Where Results Are Saved

E-commerce reports and analyses go to `WizardingCode/Ecommerce/` in your Obsidian vault.

---

## Finance — `/fin`

### What This Department Does

The Finance department handles everything money-related — financial reports, budgets, forecasts, investment analysis, negotiation prep, and investor pitches. It provides analysis and preparation, not financial advice.

### The Team

**Helena — CFO** `Tier 0`
12 years of experience taking startups from seed to scale. Helena is conservative with money, obsessive about data, and speaks in clear numbers — no vague projections. She covers three roles: financial planning (budgets, cash flow, P&L), investment analysis (opportunity evaluation, portfolio review), and negotiation coaching (strategy, BATNA analysis, talking points). Authority: `veto`, `approve_budget`, `financial_decisions`.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/fin report <type>` | Financial reports — monthly, quarterly, or annual — with metrics, trends, and highlights |
| `/fin forecast <period>` | Revenue and expense projections with scenarios (optimistic, realistic, conservative) |
| `/fin budget <project>` | Detailed budget breakdown for a project or the whole company |
| `/fin negotiate <context>` | Negotiation preparation — strategy, best alternative, key arguments, and red lines |
| `/fin pitch <context>` | Investor pitch preparation with financial models and key metrics |
| `/fin analysis <topic>` | Financial analysis on any business decision |
| `/fin investment <opportunity>` | Evaluate an investment opportunity with risk assessment |
| `/fin portfolio` | Portfolio review with allocation analysis and recommendations |
| `/fin invoice <client>` | Generate a professional invoice |

### Real-World Examples

**Prepare for a salary negotiation:**
```
/fin negotiate "salary review - I want a 20% raise"
```
Helena prepares your BATNA (best alternative), supporting arguments, potential objections with counter-arguments, and walk-away point.

**Evaluate a business decision:**
```
/fin analysis "should we move from AWS to Google Cloud?"
```
Get a full cost comparison, migration costs, risk analysis, and recommendation.

**Prepare an investor pitch:**
```
/fin pitch "raising 500K for our SaaS platform"
```
Helena builds your financial model, key metrics, use of funds, and the financial slides for your pitch deck.

### Where Results Are Saved

Financial reports and analyses go to `WizardingCode/Finance/` in your Obsidian vault.

---

## Operations — `/ops`

### What This Department Does

The Operations department runs the day-to-day business — task management, email communication, calendar, meetings, client onboarding, process automation, and multi-platform messaging. It connects to ClickUp, Gmail, Google Calendar, and messaging platforms.

### The Team

**Sofia — COO** `Tier 0`
10 years of operational excellence. Sofia is process-obsessed and calm under pressure. Her mantra: checklists over memory, templates over blanks, async over sync. She documents everything, automates what she can, and creates systems that run themselves. Authority: `veto`, `approve_operations`, `cross_department`.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/ops tasks` | View and manage your tasks in ClickUp |
| `/ops email <type>` | Draft professional emails — follow-ups, proposals, introductions, apologies |
| `/ops calendar` | View upcoming events and meetings |
| `/ops meeting <topic>` | Prepare meeting agenda with talking points and background materials |
| `/ops standup` | Run a daily standup — what happened yesterday, what's planned today, any blockers |
| `/ops invoice <client>` | Generate and track client invoices |
| `/ops automate <process>` | Design process automations with step-by-step workflows |
| `/ops report` | Generate operational reports |
| `/ops onboard <client>` | Create a client onboarding checklist and workflow |
| `/ops channel add <platform> <id>` | Connect a messaging channel (Slack, Discord, WhatsApp, Teams) |
| `/ops channel list` | See all connected messaging channels |
| `/ops channel remove <platform>` | Disconnect a messaging channel |
| `/ops notify <message>` | Send a message to your default channel |
| `/ops broadcast <message>` | Send a message to all connected channels |

### Real-World Examples

**Prepare for a client meeting:**
```
/ops meeting "quarterly review with Acme Corp"
```
Sofia creates an agenda, prepares talking points, pulls relevant project data, and suggests follow-up actions.

**Set up messaging:**
```
/ops channel add slack C0123456789
/ops channel add discord 987654321
```
Now you can send updates to both platforms:
```
/ops broadcast "Version 2.0 is live!"
```

**Create a client onboarding process:**
```
/ops onboard "New Client Ltd"
```
Get a complete onboarding checklist: welcome email, kickoff meeting agenda, access setup, project setup, and milestone planning.

### Where Results Are Saved

Operational documents go to `WizardingCode/Operations/` in your Obsidian vault.

---

## Strategy — `/strat`

### What This Department Does

The Strategy department helps you think bigger — market analysis, brainstorming, competitive intelligence, and strategic planning. Every analysis uses proven business frameworks and ends with concrete action items.

### The Team

**Tomas — Chief Strategist** `Tier 1`
Ex-management consultant who thinks in frameworks — Porter's Five Forces, Blue Ocean Strategy, Jobs-to-be-Done. Tomas blends data with intuition, plays devil's advocate, and spots connections others miss. During brainstorms, he argues from 5 different perspectives (visionary, pragmatist, skeptic, customer, analyst) and then synthesizes everything into a clear recommendation. Authority: `strategic_planning`, `market_analysis`.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/strat brainstorm <topic>` | Structured brainstorm with 5 simultaneous perspectives, then a synthesis with a clear recommendation |
| `/strat market <industry>` | Full market analysis — total addressable market, serviceable market, competitive landscape, entry barriers |
| `/strat prospect <criteria>` | Find and profile potential clients or partners |
| `/strat compete <competitor>` | Deep competitive intelligence — strengths, weaknesses, strategy, and where to attack |
| `/strat swot <business>` | Classic SWOT analysis with prioritized actions for each quadrant |
| `/strat evaluate <idea>` | Score a business idea on market size, feasibility, competition, and timing |
| `/strat pivot <context>` | Analyze strategic pivot options with risk and reward for each path |
| `/strat roadmap <product>` | Create a product or business roadmap with milestones and dependencies |
| `/strat trends <industry>` | Analyze emerging trends and predict where things are heading |

### Real-World Examples

**Brainstorm a new direction:**
```
/strat brainstorm "should we add a marketplace to our SaaS?"
```
Five perspectives argue simultaneously:
- **Visionary:** "The platform play is where the money is..."
- **Pragmatist:** "We need 1,000 active users before a marketplace makes sense..."
- **Devil's Advocate:** "Every SaaS that became a marketplace lost focus..."
- **Customer Voice:** "Users want integrations, not a marketplace..."
- **Analyst:** "The data shows marketplace SaaS has 3x higher retention..."

Then Tomas synthesizes it all into a clear recommendation.

**Analyze a market:**
```
/strat market "AI tools for real estate agents in Europe"
```
Get market sizing (TAM/SAM/SOM), key players, entry barriers, customer segments, and a go-to-market recommendation.

**Evaluate a competitor:**
```
/strat compete "Notion"
```
Get a full profile — their strengths, weaknesses, pricing strategy, target market, recent moves, and specific opportunities where you can differentiate.

### Where Results Are Saved

Strategy documents go to `WizardingCode/Strategy/` in your Obsidian vault.

---

## Knowledge Base — `/kb`

### What This Department Does

The Knowledge Base department turns content into usable expertise. Feed it a YouTube video, article, or any text, and it extracts strategies, frameworks, voice patterns, philosophy, and key quotes. Over time, you build a library of expert personas you can reference and generate content from.

### The Team

**Clara — Knowledge Curator** `Tier 1`
Former research librarian turned AI knowledge architect. Clara is analytical, systematic, and quality-obsessed. She doesn't just summarize — she decomposes content into actionable frameworks, identifies voice patterns, and builds connections between different sources. Her rule: everything must be attributed, nothing is deleted (only merged), and contradictions between sources are valuable. Authority: `manage_knowledge`, `create_personas`.

### What You Can Do

| Command | What Happens |
|---------|-------------|
| `/kb learn <source>` | Learn from a YouTube video, article, or text — extracts expertise and builds a persona profile |
| `/kb search <query>` | Search across your entire knowledge base |
| `/kb persona list` | See all expert personas you've built |
| `/kb persona <name>` | View a persona's full profile — their strategies, frameworks, voice, and quotes |
| `/kb topic <name>` | View or create a topic page that links related knowledge |
| `/kb generate <persona> <topic>` | Generate new content written in a persona's authentic voice and style |

### Real-World Examples

**Learn from a YouTube video:**
```
/kb learn "https://youtube.com/watch?v=abc123"
```
Clara downloads the video, transcribes it, and runs 5 specialized analyses at the same time — extracting strategies, frameworks, voice patterns, philosophy, and key quotes. The result is a rich persona profile in your Obsidian vault.

**Generate content in a persona's style:**
```
/kb generate "Alex Hormozi" "pricing strategies for digital products"
```
Clara writes about pricing in Alex Hormozi's authentic voice, using his frameworks, examples, and communication style.

**Build expertise over time:**
```
/kb learn "https://youtube.com/watch?v=video1"
/kb learn "https://youtube.com/watch?v=video2"
/kb learn "https://youtube.com/watch?v=video3"
```
Each time you learn from the same person, their persona profile gets richer and more nuanced. The knowledge compounds.

### Where Results Are Saved

- Persona profiles → `Personas/` in your Obsidian vault
- Video sources → `Sources/Videos/`
- Article sources → `Sources/Articles/`
- Topic pages → `Topics/`
- Frameworks → `🧠 Knowledge Base/Frameworks/`
- Raw transcripts → `🧠 Knowledge Base/Raw Transcripts/`

---

## Working Across Departments

Departments aren't isolated — they share context and can reference each other's work. Some examples:

- **Marketing + Knowledge:** Luna can write content in any persona's voice after Clara has analyzed their content
- **Strategy + Finance:** Tomas can pull Helena's financial data into strategic analyses
- **Development + Operations:** Carlos can automate deployment notifications through Sofia's messaging channels
- **E-commerce + Marketing:** Ricardo and Luna can collaborate on product launch content

Everything flows through your Obsidian vault, so context is always available across departments.

---

## Constitution & Governance

All departments are governed by `CONSTITUTION.md` — a formal set of rules with 3 enforcement levels:

- **NON-NEGOTIABLE** (13 rules) — Branch isolation, Obsidian output, authority boundaries, security gate, context-first, SOLID + clean code, spec-driven, human writing, squad routing, full visibility, sequential validation, mandatory QA, ARKA supremacy. Plus mandatory Quality Gate (Marta, Eduardo, Francisca). These cannot be bypassed.
- **MUST** — Conventional commits, test coverage, pattern matching, actionable output, memory persistence. Violations are flagged.
- **SHOULD** — Research before building, self-critique, KB contribution, complexity assessment. Best practices.

---

## Contextual Intelligence

ARKA OS automatically injects context into every prompt via hooks:

1. **Constitution rules** — Compressed governance rules are included in every interaction
2. **Department detection** — Your prompt is analyzed to detect which department is relevant
3. **Agent memory** — If an agent is mentioned, their relevant gotchas are surfaced
4. **Project context** — If you're in a known project directory, project info is injected
5. **Branch awareness** — Active git feature branch is detected
6. **Error patterns** — Recurring errors for the detected department are surfaced
7. **Time context** — Morning, afternoon, or evening

This happens automatically via the `UserPromptSubmit` hook in under 200ms.

---

## Error Tracking

ARKA OS tracks recurring errors across all departments via the `PostToolUse` hook:

- Every tool error (non-zero exit code, error patterns in output) is captured
- Errors are normalized, categorized (laravel, frontend, git, database, permissions, testing), and stored
- The top errors are surfaced in the context injection so agents can avoid known pitfalls
- View tracked errors with `arka gotchas` in the terminal
