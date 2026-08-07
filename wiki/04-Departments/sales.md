# Sales

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/sales` · **Lead:** Miguel (Tier 1) · **Agents:** 4 · **Skills:** 14

The Sales department handles the full revenue cycle from first contact to signed deal. Miguel leads with a consultative, qualification-first approach grounded in SPIN Selling and the Challenger Sale — both of which emphasise understanding the customer's situation before positioning any solution. The squad covers prospecting, deal qualification, proposal writing, objection handling, negotiation, and pipeline forecasting.

This is not a broadcast-and-hope department. Every engagement starts with rigorous ICP fit scoring, every deal is tracked through a structured pipeline with velocity metrics, and every negotiation is prepared with a defined BATNA before the first counter-offer is made.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 13 | 14 | 4 |

**Commands** (13 via `/sales`):

| Command | What it does |
| --- | --- |
| `/sales challenger <context>` | Challenger sale approach |
| `/sales discovery <prospect>` | Discovery call preparation (SPIN questions) |
| `/sales forecast` | Revenue forecast |
| `/sales negotiate <deal>` | Negotiation strategy (BATNA) |
| `/sales objection <objection>` | Objection handling playbook |
| `/sales pipeline` | Pipeline analysis and recommendations |
| `/sales pricing <product>` | Pricing negotiation strategy |
| `/sales proposal <client>` | Sales proposal writing |
| `/sales prospecting` | Find, qualify, and build a prospect list |
| `/sales qualify <deal>` | Deal qualification (BANT/MEDDIC) |
| `/sales revops` | Lead lifecycle, scoring, routing, pipeline ops |
| `/sales sales-enablement` | Decks, one-pagers, battlecards, demo scripts |
| ... | 1 more — full list in [docs/COMMANDS.md](../../docs/COMMANDS.md) |

**Skills** (14 — 13 sub-skills plus the `/sales` hub):

| Skill | What it does |
| --- | --- |
| `challenger-sell` | Prepares a Challenger Sale approach (Dixon/Adamson): commercial insight to teach, message tailoring per sta... |
| `deal-qualify` | Qualifies a deal with MEDDIC/BANT — Metrics, Economic Buyer, Decision Criteria, Decision Process, Champion... |
| `discovery-call` | Prepares a discovery call end to end: prospect research, SPIN question bank, call goals, and agenda. TRIGGE... |
| `forecast-revenue` | Builds a revenue forecast from probability-weighted pipeline, historical stage conversion, and confidence i... |
| `negotiate-plan` | Plans a negotiation with the BATNA framework: BATNA and walk-away point, ZOPA mapping, anchoring strategy,... |
| `objection-handle` | Builds an objection-handling playbook for a specific sales objection: acknowledge, clarify, respond with ev... |
| `pipeline-manage` | Analyses pipeline health with the Pipeline Velocity formula: velocity, conversion by stage, deal aging, bot... |
| `pricing-negotiate` | Prepares a value-based pricing negotiation: anchor on value and ROI, respond to price objections, and prote... |
| `proposal-write` | Writes an outcome-focused sales proposal (max 5-7 pages): executive summary, client challenge, solution wit... |
| `prospecting` | Find, qualify, and score prospect lists across four motions — B2B SaaS, general B2B, local SMB, and early-s... |
| `revops` | Design the systems that connect marketing, sales, and customer success into one revenue engine — lead lifec... |
| `sales-hub` | Sales & Negotiation department. Pipeline management, proposals, discovery calls, deal qualification, negoti... |
| `sales-enablement` | Create sales collateral reps actually use — pitch decks, one-pagers, objection-handling docs, ROI calculato... |
| `spin-sell` | Prepares SPIN Selling questions (Neil Rackham): Situation, Problem, Implication, and Need-Payoff banks cust... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Miguel | Sales Director | 1 |
| Ines S. | Sales Operations Analyst | 2 |
| Martim | SDR / Pre-Sales | 2 |
| Joao | Sales Closer | 2 |

## Frameworks

- **SPIN Selling (Rackham)** — four question types (Situation, Problem, Implication, Need-payoff) that surface genuine need before any pitch
- **Challenger Sale (Dixon/Adamson)** — teach, tailor, take control; reframe the customer's thinking rather than just respond to it
- **MEDDIC qualification** — Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion; every deal rated against all six
- **Predictable Revenue / Cold Calling 2.0 (Ross)** — outbound process with MQL-to-SQL SLA and separation of prospecting from closing
- **BATNA negotiation** — every negotiation prepared with a walk-away position, ZOPA mapping, and anchoring strategy
- **Pipeline Velocity Formula** — tracks number of deals, average deal size, win rate, and sales cycle length to forecast with confidence intervals
- **Sandler Selling System** — used situationally for complex, multi-stakeholder deals where upfront contracts reduce late-stage surprises

## What you can ask for

- "Prepare my SPIN questions for a call with a mid-market SaaS prospect" → `/sales spin-sell`
- "Qualify this deal against MEDDIC — here is the context" → `/sales deal-qualify`
- "Run a Challenger teaching sequence for our enterprise pitch" → `/sales challenger-sell`
- "Write a proposal focused on outcomes, not features" → `/sales proposal-write`
- "Prepare a negotiation plan with BATNA and concession strategy" → `/sales negotiate-plan`
- "Handle the objection: your price is too high" → `/sales objection-handle`
- "Prepare a pricing negotiation — protect margin without losing the deal" → `/sales pricing-negotiate`
- "Give me a pipeline health report with velocity and aging by stage" → `/sales pipeline-manage`
- "Build a revenue forecast with weighted pipeline and confidence intervals" → `/sales forecast-revenue`
- "Script and structure a discovery call for this prospect" → `/sales discovery-call`

## When to use it

Use the Sales department any time you need to move a prospect toward a decision: qualifying inbound leads, structuring outbound sequences, preparing for a live sales call, writing a proposal, negotiating a contract, or diagnosing pipeline stall. It also covers operational work — CRM hygiene, stage conversion analysis, and quarterly forecasting.

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
