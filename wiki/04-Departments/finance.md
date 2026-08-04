# Finance

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/fin` · **Lead:** Helena (Tier 0 — CFO) · **Agents:** 3 · **Skills:** 9

The Finance department is led by Helena, who holds a dual role: she is both the squad lead for this department and the Chief Financial Officer at Tier 0, meaning she carries veto authority on financial decisions across the entire organization. The squad operates at the intersection of financial rigor and business strategy — covering everything from granular unit economics to full 3-statement models and investor-grade valuations.

The squad is deliberately lean. Three specialists handle the full financial stack: modeling, fundraising, and strategic oversight. Helena applies Margin of Safety thinking and scenario-first reasoning before any number leaves the department. Every output is grounded in methodology — no ballpark figures, no back-of-envelope projections passed off as models.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 10 | 9 | 3 |

**Commands** (10 via `/fin`):

| Command | What it does |
| --- | --- |
| `/fin budget <scope>` | Budget planning |
| `/fin cashflow <period>` | Cash flow forecast |
| `/fin expense-audit` | Expense audit and optimization |
| `/fin model <type>` | Financial model (3-statement, DCF, scenario) |
| `/fin pitch <stage>` | Investor pitch deck financials |
| `/fin report <type>` | Financial report (monthly, quarterly, annual) |
| `/fin revenue-model` | Revenue model design |
| `/fin scenario <context>` | Scenario analysis (base, bull, bear) |
| `/fin unit-economics` | Unit economics analysis (CAC, LTV, Rule of 40) |
| `/fin valuation` | Company valuation (DCF, comparables) |

**Skills** (9 — 8 sub-skills plus the `/finance` hub):

| Skill | What it does |
| --- | --- |
| `budget-plan` | Budget planning with Helena (CFO): revenue plan, cost structure, headcount and CAPEX by department using th... |
| `cashflow-forecast` | Cash flow forecasting across operating, investing and financing flows, with runway, burn rate and working-c... |
| `ciso-advisor` | CFO-side security economics: security budget justification via ALE risk quantification (SLE x ARO), complia... |
| `finance-hub` | Finance & Investment department. Financial modeling, valuation, unit economics, fundraising, risk managemen... |
| `financial-model` | Builds 3-statement financial models — P&L, Balance Sheet, Cash Flow — with base/optimistic/pessimistic scen... |
| `pitch-deck` | Investor pitch deck financials with Rui (Investment Strategist): market size, traction, unit economics, fun... |
| `scenario-analysis` | Financial scenario analysis: base, optimistic and pessimistic cases with key-variable sensitivity and proba... |
| `unit-economics` | Unit economics analysis: CAC, LTV, LTV:CAC, payback, Rule of 40, NRR, burn multiple and magic number, bench... |
| `valuation-model` | Company valuation: DCF with WACC (Damodaran), comparable company analysis and precedent transactions, produ... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Helena | Chief Financial Officer | 0 |
| Leonor | Financial Analyst | 2 |
| Rui | Investment & Fundraising Strategist | 2 |

## Frameworks

- Damodaran DCF — intrinsic valuation with WACC and terminal value
- 3-statement modeling — P&L, Balance Sheet, and Cash Flow fully linked
- Unit economics — CAC, LTV, payback period, Rule of 40, NRR with SaaS benchmarks
- COSO ERM — enterprise risk identification, treatment, and monitoring
- Scenario analysis — base, bull, and bear cases with sensitivity tables
- Margin of Safety (Graham/Buffett) — applied before any projection is finalized
- Throughput Accounting (Goldratt) — constraint-aware cost allocation
- Rule of 40 (Feld) — SaaS health metric guiding growth vs. profitability trade-offs

## What you can ask for

- "Build a 3-statement financial model for next fiscal year" — `/fin financial-model`
- "Run a DCF valuation with comparable company analysis" — `/fin valuation-model`
- "What are our unit economics and how do they benchmark?" — `/fin unit-economics`
- "Forecast cash flow and calculate runway" — `/fin cashflow-forecast`
- "Run base/bull/bear scenario analysis with sensitivity" — `/fin scenario-analysis`
- "Build an annual budget with department cost breakdown" — `/fin budget-plan`
- "Prepare the financials section of our investor pitch deck" — `/fin pitch-deck`
- "Justify the security budget to the board and map compliance ROI" — `finance/ciso-advisor`

## When to use it

Engage Finance whenever a decision carries monetary weight: fundraising prep, pricing changes, new market entry, headcount planning, or any time you need numbers that will be seen by investors, a board, or a CFO. Also use it before committing to a compliance spend — the ciso-advisor skill quantifies risk in financial terms, not just technical ones.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
