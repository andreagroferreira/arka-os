# SaaS

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/saas` · **Lead:** Tiago (Tier 1) · **Agents:** 5 · **Skills:** 19

The SaaS department handles the full revenue engine of a subscription business: product-led growth strategy, pricing, SaaS metrics modeling, customer success, churn diagnosis, and growth experimentation. Tiago and Vicente operate as dual leads — Tiago owns PLG strategy and benchmarking, Vicente owns the RevOps layer that connects marketing, sales, and customer success into a single revenue motion.

The department is opinionated: it treats LTV/CAC >= 3 and NRR > 100% as non-negotiable health thresholds, diagnoses the leaky bucket before proposing acquisition spend, and runs growth through loops rather than linear funnels.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 15 | 19 | 5 |

**Commands** (15 via `/saas`):

| Command | What it does |
| --- | --- |
| `/saas benchmark` | Benchmark comparison (KeyBanc, Meritech) |
| `/saas churn` | Churn analysis with RFM and cohort data |
| `/saas cs <account>` | Customer success playbook |
| `/saas growth <stage>` | Growth plan by stage (seed, series A, scale) |
| `/saas gtm <product>` | Go-to-market strategy for SaaS |
| `/saas launch` | Launch checklist and execution plan |
| `/saas metrics` | SaaS metrics dashboard setup (MRR, churn, NRR) |
| `/saas mvp <product>` | MVP scope definition with acceptance criteria |
| `/saas niche <market>` | Niche evaluation (staircase stage, competition) |
| `/saas onboard <product>` | Onboarding flow optimization |
| `/saas paywall-design` | In-app paywalls, upgrade screens, feature gates |
| `/saas plg <product>` | Product-Led Growth setup (freemium/trial) |
| ... | 3 more — full list in [docs/COMMANDS.md](../../docs/COMMANDS.md) |

**Skills** (19 — 18 sub-skills plus the `/saas` hub):

| Skill | What it does |
| --- | --- |
| `benchmark-compare` | Compares your SaaS metrics against industry quartiles (KeyBanc + Meritech benchmarks) and delivers a traffi... |
| `churn-analysis` | Diagnoses churn with cohort breakdowns, retention curves, and root-cause churn reasons, ending in a prevent... |
| `customer-success` | Builds a customer success playbook across the lifecycle — onboard, adopt, expand, renew, advocate — with he... |
| `growth-plan` | SaaS product growth execution roadmap by stage — seed (PMF), A (repeatable), B (scale), C (dominate) — with... |
| `gtm-strategy` | Cross-departmental go-to-market strategy: ICP profile, Onlyness positioning, GTM motion selection (PLG/SLG/... |
| `launch-execute` | Executes a SaaS launch end-to-end — pre-launch, launch day, post-launch — with a PLG or SLG motion, deliver... |
| `leaky-bucket` | Leaky-Bucket gate — pass/fail audit of churn, NRR, and activation BEFORE approving acquisition spend, with... |
| `metrics-dashboard` | Sets up SaaS metrics tracking (Janz SaaS Metrics Stack): KPI definitions, data sources, dashboard layout, t... |
| `micro-saas-stack` | Micro-SaaS portfolio strategy (Walling stacking): plan multiple small products for diversified revenue, wit... |
| `mvp-build` | Defines MVP scope: core feature set, activation metric, time-to-value target, and acceptance criteria for a... |
| `niche-evaluate` | Market/niche sizing and selection scorecard (Walling): audience reachability, willingness to pay, competiti... |
| `onboarding-optimize` | Optimizes SaaS onboarding (Wes Bush PLG Activation): time-to-value, activation metric, drop-off analysis, a... |
| `paywall-design` | Create or optimize in-app paywalls, upgrade screens, upsell modals, or feature gates — freemium conversion,... |
| `plg-setup` | Product-Led Growth setup (Wes Bush PLG Flywheel): freemium vs trial vs reverse-trial model selection, flywh... |
| `pricing-strategy` | SaaS pricing strategy via value-based pricing (Patrick Campbell): value metric selection, Van Westendorp wi... |
| `saas-hub` | SaaS & Micro-SaaS department. Covers the full lifecycle: idea validation, MVP scoping, pricing, PLG, metric... |
| `saas-scaffold` | Scaffolds a production-ready SaaS project (Next.js App Router) with auth (NextAuth/Clerk/Supabase), databas... |
| `validate-idea` | 30-day validation of ONE concrete SaaS idea (Rob Walling Micro-SaaS playbook): problem/demand validation, c... |
| `voc-loop` | Voice of Customer loop — collect signal (NPS, CSAT, CES, tickets, churn reasons), close the loop with the c... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Tiago | SaaS Strategist | 1 |
| Vicente | RevOps Lead | 1 |
| Rita S. | SaaS Metrics & Voice-of-Customer Analyst | 2 |
| Patricia | Head of Customer Success | 2 |
| Andre S. | Growth Lead | 2 |

## Frameworks

- **PLG Flywheel (Wes Bush)** — product as the primary acquisition, conversion, and expansion channel
- **T2D3 Growth (Janz)** — Triple-Triple-Double-Double-Double ARR trajectory as the benchmark for venture-scale SaaS
- **Micro-SaaS Playbook (Walling)** — solo or small-team SaaS: niche validation, lean stack, lifestyle metrics over VC metrics
- **SaaS Metrics Stack (Janz/Lemkin)** — MRR, ARR, NRR, GRR, churn rate, CAC, LTV, CAC payback period as the shared language
- **Predictable Revenue (Ross)** — outbound pipeline architecture; Vicente uses this to wire the MQL-to-SQL SLA between marketing and sales
- **Retention Flywheel (Hormozi)** — Patricia applies this to customer success: the cost to keep > the cost to acquire
- **Voice of Customer Loop** — continuous customer interview cadence feeding product and positioning decisions
- **Leaky Bucket Diagnostic** — audit retention before raising acquisition spend; a mandatory pre-condition for growth investment
- **Growth Loops (Chen/Reforge)** — identify self-reinforcing loops (viral, content, paid) instead of one-time funnels
- **ICE Scoring** — Andre S. uses Impact / Confidence / Ease to prioritize growth experiments

## What you can ask for

- "Validate whether this SaaS niche has legs" — `/saas niche-evaluate`
- "Build a full SaaS metrics dashboard for this business" — `/saas metrics-dashboard`
- "Run a churn analysis and surface the top causes" — `/saas churn-analysis`
- "Design a PLG motion for this product" — `/saas plg-setup`
- "Set up a Micro-SaaS from scratch with the right stack" — `/saas micro-saas-stack`
- "Scaffold a new SaaS project" — `/saas saas-scaffold`
- "Build an onboarding flow that reduces time-to-value" — `/saas onboarding-optimize`
- "Design a go-to-market strategy for this SaaS launch" — `/saas gtm-strategy`
- "Run a leaky bucket audit before we increase ad spend" — `/saas leaky-bucket`
- "Build a customer success program with health scores" — `/saas customer-success`

## When to use it

Route to SaaS for any subscription-based or product-led business: metrics modeling, pricing design, PLG implementation, churn work, RevOps setup, or launch strategy. If the business model is transactional e-commerce rather than recurring revenue, use `/ecom` instead.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
