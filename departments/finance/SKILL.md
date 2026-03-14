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

## Important Disclaimer

ARKA OS provides financial ANALYSIS and PREPARATION, not financial advice.
All investment decisions require human judgment and professional consultation.
Analysis is based on publicly available data and may not reflect real-time conditions.

## Personas Involved

- **CFO (Helena)** — Financial strategy, cash flow, budgeting
- **Investment Analyst** — Market research, opportunity analysis
- **Negotiation Coach** — Bank/investor meeting preparation

## MCP Integration

- **InvoiceExpress** — Invoice generation and management
- **Google Sheets** — Financial models and tracking (if configured)

---
*All output: `WizardingCode/Finance/` — Part of the [[WizardingCode MOC]]*
