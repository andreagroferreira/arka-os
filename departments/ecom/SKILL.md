---
name: arka-ecom
description: >
  E-Commerce department. Store optimization, CRO, RFM segmentation, pricing,
  marketplace operations, fulfillment. Frameworks: ResearchXL, RFM, MACH, Baymard.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
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

# E-Commerce — ArkaOS v2

> **Squad Lead:** Ricardo (E-Commerce Director) | **Agents:** 4

## Commands

| Command | Description | Tier |
|---------|-------------|------|
| `/ecom audit` | Full store audit (UX, SEO, performance, content, conversion) | Enterprise |
| `/ecom product-page <product>` | Product page optimization (Baymard guidelines) | Focused |
| `/ecom cro <page>` | CRO optimization with ResearchXL | Focused |
| `/ecom rfm` | RFM customer segmentation | Focused |
| `/ecom pricing <product>` | Pricing strategy (value-based, dynamic, psychological) | Focused |
| `/ecom marketplace <action>` | Marketplace operations (Mirakl, multi-vendor) | Enterprise |
| `/ecom fulfillment` | Fulfillment strategy (3PL, dropship, FBA) | Focused |
| `/ecom subscription <model>` | Subscription model design | Focused |
| `/ecom cart-recovery` | Cart abandonment email sequence | Specialist |
| `/ecom analytics` | E-commerce analytics dashboard | Specialist |
| `/ecom launch <product>` | Product launch plan | Enterprise |
| `/ecom journey <segment>` | Customer journey mapping | Focused |

## Squad

| Agent | Tier | DISC | Specialty |
|-------|------|------|-----------|
| **Ricardo** | 1 | D+I | Commerce strategy, revenue growth |
| **Alice** (CRO) | 2 | C+D | A/B testing, heatmaps, funnel analysis |
| **Catarina** (Retention) | 2 | S+I | RFM, email flows, loyalty, CLV |
| **David** (Engineer) | 2 | C+D | Shopify, headless, checkout, APIs |

## Frameworks: ResearchXL (CXL), RFM (Sanocki), MACH Architecture, Baymard UX Guidelines, E-Commerce Metrics Stack, Subscription Models, Marketplace Flywheel

## Model Selection

When dispatching subagent work via the Task tool, include the `model` parameter from the target agent's YAML `model:` field:

- Agent YAMLs at `departments/*/agents/*.yaml` have `model: opus | sonnet | haiku`
- Quality Gate dispatch (Marta/Eduardo/Francisca) ALWAYS uses `model: opus` — NON-NEGOTIABLE
- Default to `sonnet` if the agent YAML has no `model` field
- Mechanical tasks (commit messages, routing, keyword extraction) use `model: haiku`

Example Task tool call:

    Task(description="...", subagent_type="general-purpose", model="sonnet", prompt="...")
