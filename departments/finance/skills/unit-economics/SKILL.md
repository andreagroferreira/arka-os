---
name: fin/unit-economics
description: >
  Unit economics analysis: CAC, LTV, payback, Rule of 40, NRR.
  With SaaS benchmarks from KeyBanc and Meritech.
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

# Unit Economics — `/fin unit-economics`

> **Agent:** Leonor (Financial Analyst) | **Framework:** SaaS Metrics + Unit Economics

## Core Metrics

| Metric | Formula | Target | Source |
|--------|---------|--------|--------|
| **CAC** | Total S&M / New Customers | Decreasing QoQ | |
| **LTV** | ARPU x Gross Margin x Lifetime | > 3x CAC | |
| **LTV:CAC** | LTV / CAC | > 3:1 (top: 4.2:1) | KeyBanc 2024 |
| **Payback** | CAC / (Monthly ARPU x Gross Margin) | < 12 months | |
| **Rule of 40** | Revenue Growth % + Profit Margin % | > 40% (median: 34%) | Brad Feld |
| **NRR** | (Start MRR + Expansion - Churn) / Start MRR | > 110% (top: 130%+) | |
| **Gross Margin** | (Revenue - COGS) / Revenue | > 70% for SaaS | |
| **Burn Multiple** | Net Burn / Net New ARR | < 2x (top: < 1x) | |
| **Magic Number** | Net New ARR / S&M Spend (prev Q) | > 0.75 | |

## Analysis Steps

1. **Collect data** — Revenue, customers, S&M spend, COGS, churn
2. **Calculate metrics** — All formulas above with actuals
3. **Benchmark** — Compare against KeyBanc/Meritech by stage and ACV
4. **Diagnose** — Which metrics are below benchmark? Why?
5. **Recommend** — Specific actions to improve weak metrics

## Benchmark Ranges (Private SaaS, KeyBanc 2024)

| Metric | Bottom Quartile | Median | Top Quartile |
|--------|----------------|--------|-------------|
| LTV:CAC | < 2:1 | 3:1 | > 4.2:1 |
| Payback | > 24 months | 13 months | < 6 months |
| NRR | < 100% | 107% | > 120% |
| Gross Margin | < 65% | 73% | > 80% |

## Output → Unit economics dashboard with traffic light indicators (green/yellow/red)
