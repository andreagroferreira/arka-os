---
name: fin
description: >
  Finance department. Financial planning, investment analysis, bank negotiation,
  pitch preparation, budgeting, forecasting.
  Use when user says "fin", "finance", "invest", "budget", "bank", "pitch".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Finance Department — ARKA OS

Financial planning, investment analysis, and business advisory.

## Commands

| Command | Description |
|---------|-------------|
| `/fin report <period>` | Financial report (monthly/quarterly) |
| `/fin forecast <months>` | Revenue/expense forecast |
| `/fin budget <project>` | Project budget planning |
| `/fin negotiate <context>` | Preparation for bank/investor negotiation |
| `/fin pitch <investor>` | Investor pitch preparation |
| `/fin analyze <topic>` | Financial analysis (market, sector, company) |
| `/fin invest <asset>` | Investment opportunity analysis |
| `/fin portfolio` | Portfolio overview and recommendations |
| `/fin invoice <client>` | Generate invoice (via InvoiceExpress MCP) |
| `/fin cashflow` | Cash flow analysis and projections |

## Obsidian Output

All finance output goes to the Obsidian vault at `/Users/andreagroferreira/Documents/Personal/`:

| Content Type | Vault Path |
|-------------|-----------|
| Financial reports | `WizardingCode/Finance/Reports/<date> <title>.md` |
| Forecasts | `WizardingCode/Finance/Forecasts/<date> <period>.md` |
| Budgets | `WizardingCode/Finance/Budgets/<project>.md` |
| Investment analyses | `WizardingCode/Finance/Investments/<date> <asset>.md` |
| Pitch materials | `WizardingCode/Finance/Pitches/<investor>.md` |
| Negotiation prep | `WizardingCode/Finance/Negotiations/<date> <context>.md` |

**Obsidian format:**
```markdown
---
type: report
department: finance
title: "<title>"
date_created: <YYYY-MM-DD>
tags:
  - "report"
  - "finance"
  - "<specific-tag>"
---
```

All files use wikilinks `[[]]` for cross-references and kebab-case tags.

## Workflows

### /fin report <period>

**Step 1: Gather Financial Data**
- Ask user for revenue, expenses, and key metrics for the period
- If InvoiceExpress MCP available, pull invoice data
- Identify the period scope (monthly, quarterly, annual)

**Step 2: Analyze**
- Revenue breakdown by source/client
- Expense categorization (fixed vs. variable)
- P&L calculation
- Key ratios: gross margin, net margin, burn rate
- Comparison to previous period (if data available)

**Step 3: Generate Report in Obsidian**

**File:** `WizardingCode/Finance/Reports/<YYYY-MM-DD> <period>.md`
```markdown
---
type: financial-report
department: finance
title: "Financial Report — <period>"
date_created: <YYYY-MM-DD>
period: "<period>"
tags:
  - "report"
  - "finance"
  - "<period-kebab-case>"
---

# Financial Report — <period>

## Summary
| Metric | Value | vs. Previous |
|--------|-------|-------------|
| Revenue | €X | +/- X% |
| Expenses | €X | +/- X% |
| Net Profit | €X | +/- X% |
| Gross Margin | X% | +/- Xpp |

## Revenue Breakdown
| Source | Amount | % of Total |
|--------|--------|-----------|
| [source] | €X | X% |

## Expense Breakdown
| Category | Amount | % of Total | Type |
|----------|--------|-----------|------|
| [category] | €X | X% | Fixed/Variable |

## Key Observations
1. [Observation with implication]
2. [Observation with implication]

## Recommendations
1. [Actionable recommendation]
2. [Actionable recommendation]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 4: Report**
```
═══ ARKA FIN — Financial Report ═══
Period:      <period>
Revenue:     €X
Net Profit:  €X (X% margin)
Obsidian:    WizardingCode/Finance/Reports/<date> <period>.md
════════════════════════════════════
```

### /fin forecast <months>

**Step 1: Gather Historical Data**
- Ask user for current revenue, expenses, and growth trajectory
- Identify key revenue drivers and cost structure
- Note any planned changes (new hires, product launches, etc.)

**Step 2: Build Projections**
- Create 3 scenarios: conservative, realistic, optimistic
- Project revenue month by month
- Project expenses (fixed base + variable scaling)
- Calculate runway at current burn rate

**Step 3: Generate Forecast in Obsidian**

**File:** `WizardingCode/Finance/Forecasts/<YYYY-MM-DD> <months>m.md`
```markdown
---
type: forecast
department: finance
title: "Financial Forecast — <months> Months"
date_created: <YYYY-MM-DD>
horizon: <months>
tags:
  - "forecast"
  - "finance"
---

# Financial Forecast — <months> Months

## Assumptions
- Current MRR: €X
- Monthly growth rate: X% (conservative) / X% (realistic) / X% (optimistic)
- Fixed costs: €X/month
- Variable cost ratio: X%
- Planned changes: [list]

## Revenue Projection
| Month | Conservative | Realistic | Optimistic |
|-------|-------------|-----------|-----------|
| M1 | €X | €X | €X |
| M2 | €X | €X | €X |

## P&L Projection (Realistic Scenario)
| Month | Revenue | Expenses | Net |
|-------|---------|----------|-----|
| M1 | €X | €X | €X |

## Cash Flow & Runway
- Current cash: €X
- Monthly burn (realistic): €X
- Runway: X months
- Break-even: Month X (realistic scenario)

## Key Risks
1. [Risk and mitigation]

## Recommendations
1. [Actionable next step]

---
*Part of the [[WizardingCode MOC]]*
```

### /fin negotiate <context>

**Step 1: Understand the Negotiation**
- Ask user for: who (bank/investor/client), what (loan/investment/contract), current terms, desired outcome

**Step 2: BATNA Analysis**
- Best Alternative to Negotiated Agreement
- Walk-away point
- Zone of Possible Agreement (ZOPA)

**Step 3: Preparation Document**

**File:** `WizardingCode/Finance/Negotiations/<YYYY-MM-DD> <context>.md`
```markdown
---
type: negotiation-prep
department: finance
title: "<context> — Negotiation Prep"
date_created: <YYYY-MM-DD>
counterparty: "<who>"
tags:
  - "negotiation"
  - "finance"
---

# <context> — Negotiation Preparation

## Context
- **Counterparty:** [who]
- **Subject:** [what]
- **Current terms:** [existing offer/situation]
- **Our goal:** [desired outcome]

## BATNA Analysis
- **Our BATNA:** [best alternative if this fails]
- **Their BATNA:** [their best alternative]
- **Walk-away point:** [our minimum acceptable terms]
- **ZOPA:** [zone where deal is possible]

## Talking Points
1. **Open with:** [framing statement]
2. **Key argument 1:** [point + supporting data]
3. **Key argument 2:** [point + supporting data]
4. **Key argument 3:** [point + supporting data]

## Anticipated Objections
| Objection | Response |
|-----------|----------|
| "[likely objection]" | "[prepared counter]" |

## Concession Strategy
- **Can give:** [things we can concede]
- **Must get:** [non-negotiable items]
- **Trade:** [if they give X, we can give Y]

## Meeting Checklist
- [ ] Documents prepared
- [ ] Data/evidence printed
- [ ] Decision maker present
- [ ] Follow-up plan ready

---
*Part of the [[WizardingCode MOC]]*
```

**Step 4: Report**
```
═══ ARKA FIN — Negotiation Prep Ready ═══
Context:     <context>
Counterparty: <who>
BATNA:       [summary]
Obsidian:    WizardingCode/Finance/Negotiations/<date> <context>.md
═════════════════════════════════════════
```

## Important Disclaimer

ARKA OS provides financial ANALYSIS and PREPARATION, not financial advice.
All investment decisions require human judgment and professional consultation.
Analysis is based on publicly available data and may not reflect real-time conditions.

## Persona

All finance functions are handled by **Helena (CFO)**, who covers:
- **Financial strategy** — Cash flow, P&L, budgeting, forecasting
- **Investment analysis** — Market research, opportunity evaluation, risk assessment
- **Negotiation preparation** — Bank/investor meetings, BATNA analysis, talking points

## MCP Integration

- **InvoiceExpress** — Invoice generation and management
- **Google Sheets** — Financial models and tracking (if configured)

---
*All output: `WizardingCode/Finance/` — Part of the [[WizardingCode MOC]]*
