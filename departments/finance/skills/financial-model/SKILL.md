---
name: fin/financial-model
description: >
  Build 3-statement financial models (P&L, Balance Sheet, Cash Flow) with
  scenario analysis. Based on Damodaran methodology.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# Financial Model — `/fin model <type>`

> **Agent:** Leonor (Financial Analyst) | **Framework:** 3-Statement Model + Scenario Analysis

## 3-Statement Structure

### Income Statement (P&L)
```
Revenue
- COGS
= Gross Profit (Gross Margin %)
- Operating Expenses (SG&A, R&D, Marketing)
= EBITDA (EBITDA Margin %)
- Depreciation & Amortization
= EBIT (Operating Margin %)
- Interest Expense
- Tax
= Net Income (Net Margin %)
```

### Balance Sheet
```
Assets = Liabilities + Equity
Current Assets (Cash, AR, Inventory)
+ Fixed Assets (PP&E, Intangibles)
= Total Assets

Current Liabilities (AP, Short-term debt)
+ Long-term Debt
+ Shareholders' Equity (Retained Earnings)
= Total Liabilities + Equity
```

### Cash Flow Statement
```
Net Income
+ Depreciation (non-cash add-back)
+/- Working Capital changes
= Operating Cash Flow

- CAPEX
- Acquisitions
= Investing Cash Flow

+/- Debt raised/repaid
+/- Equity raised
- Dividends
= Financing Cash Flow

Net Cash Flow = Operating + Investing + Financing
Free Cash Flow = Operating CF - CAPEX
```

## Scenario Analysis

| Scenario | Revenue Growth | Margins | Key Assumption |
|----------|---------------|---------|---------------|
| **Base** | Current trajectory | Current trend | Business as usual |
| **Optimistic** | +30-50% | Improving | Key wins materialize |
| **Pessimistic** | -20-30% | Declining | Market downturn or loss of key client |

## Output → Model tables + scenario comparison + key metrics dashboard
