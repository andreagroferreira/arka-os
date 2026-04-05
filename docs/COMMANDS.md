# ArkaOS Commands

Complete reference for every CLI command and department prefix, with real usage examples.

## CLI Commands

### Install and Setup

```bash
# Install ArkaOS (auto-detects your AI runtime)
npx arkaos install

# Install for a specific runtime
npx arkaos install --runtime claude-code
npx arkaos install --runtime codex
npx arkaos install --runtime gemini
npx arkaos install --runtime cursor

# Initialize ArkaOS in a project directory
cd my-laravel-app
npx arkaos init
# Output: Created .arkaos.json (detected: Laravel 11.x, PHP 8.3)

# Run health checks
npx arkaos doctor
# Output: 9/9 checks passed

# Update to latest version
npx arkaos update

# Migrate from v1
npx arkaos migrate

# Uninstall
npx arkaos uninstall
```

### Dashboard and Knowledge

```bash
# Start the monitoring dashboard (localhost:3333)
npx arkaos dashboard

# Index your Obsidian vault for semantic search
npx arkaos index
# Output: Indexed 847 notes, 12,340 chunks, 4.2MB vector DB

# Search your indexed knowledge
npx arkaos search "authentication patterns laravel"
# Output: 5 results ranked by relevance with snippets

# Manage API keys (stored encrypted)
npx arkaos keys set OPENAI_API_KEY sk-proj-...
npx arkaos keys set ANTHROPIC_API_KEY sk-ant-...
npx arkaos keys list
```

## Department Commands

Every department has a prefix. You can use the prefix with a skill name, or just describe what you need in plain language and ArkaOS routes it automatically.

### `/dev` -- Development (41 skills, 10 agents)

Led by Paulo (Tech Lead). Full-stack development from architecture to deployment.

```bash
# Build a complete feature with 9-phase enterprise workflow
/dev feature "user authentication with OAuth2"

# Review code for quality, security, and patterns
/dev code-review

# Design an API with OpenAPI spec generation
/dev api-design "REST API for order management"

# Run a security audit on your codebase
/dev security-audit

# Scaffold a new project (Laravel, Nuxt, Next.js, React)
/dev scaffold laravel "my-new-app"

# Analyze tech debt and get a prioritized fix plan
/dev tech-debt

# Set up CI/CD pipeline
/dev ci-cd-pipeline

# Design database schema with migrations
/dev db-design "multi-tenant SaaS with teams"

# Create architecture decision record
/dev architecture-design "microservices vs monolith"

# Debug a failing feature with structured root cause analysis
/dev debug "payments failing after Stripe webhook"
```

### `/mkt` -- Marketing (14 skills, 4 agents)

Led by Luna (Marketing Lead). Growth strategies, SEO, email, and paid campaigns.

```bash
# Full SEO audit with actionable fix list
/mkt seo-audit

# Create a 6-email launch sequence
/mkt email-sequence "B2B SaaS launching to CTOs, $299/mo"

# Design growth loops for your product
/mkt growth-loop "freemium developer tool"

# Plan a paid ad campaign (Google, Meta, LinkedIn)
/mkt paid-campaign "LinkedIn ads targeting CFOs, $5K budget"

# Generate a content calendar for the quarter
/mkt calendar-plan "Q3 2026, developer audience, weekly cadence"

# Analyze competitor marketing strategies
/mkt competitor-analysis "Notion vs Coda vs Slite"

# Build a programmatic SEO strategy
/mkt programmatic-seo "template pages for 500 city landing pages"

# Design A/B test for landing page
/mkt ab-test "pricing page hero section"
```

### `/brand` -- Brand and Design (12 skills, 4 agents)

Led by Valentina (Creative Director). Full brand identity from strategy to visual design.

```bash
# Create complete brand identity (colors, voice, positioning)
/brand identity-system "fintech startup for Gen Z"

# Generate color palette with accessibility checks
/brand colors "premium, trustworthy, modern"

# Find your brand archetype (Jungian framework)
/brand archetype-finder

# Create brand voice guide with examples
/brand voice-guide "professional but approachable"

# Generate logo brief for designers
/brand logo-brief "AI-powered fitness app"

# Run UX audit on your product
/brand ux-audit

# Design system creation (tokens, components, patterns)
/brand design-system "React component library"
```

### `/fin` -- Finance (8 skills, 3 agents)

Led by Helena (CFO). Financial modeling, valuation, and investment analysis.

```bash
# Build a DCF valuation model
/fin valuation-model "SaaS company, $2M ARR, 40% growth"

# Create project budget with scenarios
/fin budget-plan "mobile app development, 6-month timeline"

# Calculate unit economics
/fin unit-economics "CAC $120, LTV $840, payback 4 months"

# Build financial model for investor pitch
/fin financial-model "Series A, $5M raise, 18-month runway"

# Cash flow forecast with 3 scenarios
/fin cashflow-forecast "next 12 months, base/bull/bear"

# Prepare pitch deck financial slides
/fin pitch-deck "seed round, pre-revenue, AI healthcare"
```

### `/strat` -- Strategy (9 skills, 3 agents)

Led by Tomas (Strategy Director). Market analysis and strategic planning.

```bash
# Blue Ocean strategy analysis
/strat blue-ocean "AI writing tools market"

# Porter's Five Forces analysis
/strat five-forces "food delivery industry in Portugal"

# Business Model Canvas
/strat bmc "marketplace connecting freelance designers with startups"

# Structured brainstorm with 5 perspectives
/strat brainstorm "how to differentiate in crowded CRM market"

# Competitive intelligence deep-dive
/strat competitor-intelligence "Shopify vs WooCommerce vs BigCommerce"
```

### `/ecom` -- E-Commerce (12 skills, 4 agents)

Led by Ricardo (E-Commerce Lead). Store optimization, CRO, and pricing.

```bash
# Full store audit (UX, SEO, performance, content, conversion)
/ecom store-audit "https://mystore.com"

# Pricing strategy analysis
/ecom pricing-strategy "subscription boxes, $29-89 range"

# Product listing optimization
/ecom product-listing "running shoes, targeting marathon runners"

# RFM customer segmentation
/ecom rfm-analysis
```

### `/kb` -- Knowledge (12 skills, 4 agents)

Led by Clara (Knowledge Lead). Research, learning, and knowledge management.

```bash
# Deep research on a topic with source citations
/kb research "state of AI agents in 2026"

# Build a persona from knowledge sources
/kb persona-build "Alex Hormozi" --sources youtube,books

# Learn from a YouTube video (download, transcribe, analyze)
/kb learn "https://youtube.com/watch?v=..."

# Create a Zettelkasten note structure
/kb zettelkasten "machine learning fundamentals"
```

### `/ops` -- Operations (15 skills, 3 agents)

Led by Daniel (Ops Lead). Process automation, compliance, and risk management.

```bash
# Create a Standard Operating Procedure
/ops sop-create "employee onboarding process"

# GDPR compliance check
/ops gdpr-compliance

# ISO 27001 readiness assessment
/ops iso27001

# SOC 2 preparation guide
/ops soc2-readiness

# Risk assessment matrix
/ops risk-assessment "cloud migration project"

# Process automation recommendation
/ops automate "invoice processing workflow"
```

### `/pm` -- Project Management (13 skills, 3 agents)

Led by Carolina (PM Director). Agile planning, discovery, and delivery.

```bash
# Sprint planning with story generation
/pm sprint-plan "authentication epic, 2-week sprint"

# Build product roadmap
/pm roadmap-build "Q3-Q4 2026, 3 themes"

# Write user stories with acceptance criteria
/pm story-write "as a user, I want to export data as CSV"

# Continuous discovery framework
/pm discovery "customer interview insights from last 10 calls"

# Shape Up pitch document
/pm shape-up "redesign the billing page"
```

### `/saas` -- SaaS (15 skills, 4 agents)

Led by Tiago (SaaS Strategist). Validation, metrics, and growth for SaaS products.

```bash
# Validate a SaaS idea with structured analysis
/saas validate-idea "AI meeting summarizer, $15/mo"

# Build metrics dashboard spec
/saas metrics-dashboard

# Design PLG (Product-Led Growth) strategy
/saas plg-setup "developer tool with free tier"

# Analyze churn patterns and recommend fixes
/saas churn-analysis

# Go-to-market strategy
/saas gtm-strategy "B2B SaaS for HR teams, $99/mo"

# Scaffold a micro-SaaS project
/saas saas-scaffold "Nuxt 4 + Supabase + Stripe"
```

### `/landing` -- Landing Pages (15 skills, 4 agents)

Led by Ines (Landing Lead). High-converting copy, funnels, and page generation.

```bash
# Generate landing page copy with multiple frameworks
/landing copy-framework "developer productivity tool, $19/mo"

# Design a complete sales funnel
/landing funnel-design "webinar funnel for B2B SaaS"

# Create a Grand Slam Offer (Hormozi framework)
/landing grand-slam-offer "fitness coaching program"

# Write a VSL (Video Sales Letter) script
/landing vsl-script "online course, $497"

# Optimize existing landing page
/landing page-optimize "current conversion rate 2.1%"
```

### `/content` -- Content (14 skills, 4 agents)

Led by Rafael (Content Strategist). Viral content, hooks, scripts, and repurposing.

```bash
# Write viral hooks for short-form video
/content hook-write "productivity tips for developers"

# Design viral content strategy
/content viral-design "tech startup brand on TikTok"

# Write a YouTube script with retention markers
/content youtube-script "10 Laravel tips most developers don't know"

# Repurpose a long video into multiple formats
/content repurpose "1-hour podcast episode"

# Create content operating system
/content content-os "weekly publishing cadence, 3 platforms"
```

### `/community` -- Communities (14 skills, 3 agents)

Led by Beatriz (Community Strategist). Groups, membership, and engagement.

```bash
# Plan community platform setup
/community platform-setup "Discord community for 500 developers"

# Growth strategy for community
/community growth-plan "paid membership, target 1000 members by Q4"

# Design gamification system
/community gamification "points, badges, leaderboard for learning platform"

# Membership model design
/community membership-model "3-tier, $29/$99/$299"
```

### `/sales` -- Sales (10 skills, 3 agents)

Led by Miguel (Sales Director). Pipeline management and selling frameworks.

```bash
# Manage sales pipeline
/sales pipeline-manage

# SPIN selling framework for a deal
/sales spin-sell "enterprise SaaS deal, $50K ACV"

# Negotiation preparation
/sales negotiate-prep "contract renewal, client wants 30% discount"

# Cold outreach sequence
/sales cold-outreach "targeting VP Engineering at Series B startups"
```

### `/lead` -- Leadership (10 skills, 3 agents)

Led by Rodrigo (Leadership Lead). Team health, OKRs, and culture building.

```bash
# Set OKRs with cascade structure
/lead okr-set "company-level growth OKRs for Q3"

# Run team health assessment
/lead team-health

# Design hiring plan
/lead hiring-plan "engineering team, 5 hires in 6 months"

# Build team culture playbook
/lead culture-playbook "remote-first startup, 20 people"
```

### `/org` -- Organization (10 skills, 3 agents)

Led by Sofia (COO). Organizational design and team structure.

```bash
# Design org structure
/org design "scaling from 20 to 50 people"

# Team topology analysis
/org team-topology "platform team vs stream-aligned teams"

# Compensation framework
/org compensation "engineering levels and bands"
```

## Python CLI Tools

Standalone analysis tools that run locally. All support `--json` for machine-readable output and `--help` for usage info.

```bash
# Score a headline for engagement (0-100)
python scripts/tools/headline_scorer.py "10 Laravel Tips That Will Save You Hours"
# Output: Score: 78/100 | Power words: 2 | Emotional: medium | Length: optimal

# Run on-page SEO audit
python scripts/tools/seo_checker.py index.html
# Output: Score: 64/100 | Missing: meta description, alt tags (3), h1 duplicate

# Prioritize features using RICE framework
python scripts/tools/rice_prioritizer.py features.json
# Output: Ranked list with Reach, Impact, Confidence, Effort scores

# Calculate DCF valuation
python scripts/tools/dcf_calculator.py --revenue 2000000 --growth 30 --margin 20
# Output: Enterprise value: $8.4M | Equity value: $7.9M | Per-share: $15.80

# Analyze SaaS health metrics
python scripts/tools/saas_metrics.py --new-mrr 50000 --churned-mrr 5000 --expansion-mrr 8000
# Output: Net MRR: $53K | Quick ratio: 11.6 | Net revenue retention: 106%

# Scan codebase for tech debt
python scripts/tools/tech_debt_analyzer.py src/
# Output: Debt score: 34/100 | Hotspots: 12 files | Est. fix time: 40h

# Analyze brand voice consistency
python scripts/tools/brand_voice_analyzer.py marketing-copy.txt
# Output: Consistency: 72% | Tone: professional | Issues: passive voice (14x)

# Generate OKR cascade from a theme
python scripts/tools/okr_cascade.py growth
# Output: 3 objectives, 9 key results, aligned to company-level growth theme
```

## Natural Language Routing

You do not need to memorize commands. Just describe what you need:

```
"fix the checkout bug"                  --> /dev debug
"create a brand for my fintech"         --> /brand identity-system
"plan the Q3 budget"                    --> /fin budget-plan
"validate my saas idea"                 --> /saas validate-idea
"write viral hooks for TikTok"          --> /content hook-write
"are we GDPR compliant?"               --> /ops gdpr-compliance
"plan the next sprint"                  --> /pm sprint-plan
"analyze our churn rate"                --> /saas churn-analysis
"design the landing page copy"          --> /landing copy-framework
"set up the Discord community"          --> /community platform-setup
```

The Synapse engine detects your intent (L1 keyword detection + L5 command hints) and routes to the correct department automatically.
