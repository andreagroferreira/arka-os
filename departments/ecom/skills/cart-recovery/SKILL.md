---
name: ecom/cart-recovery
description: >
  Designs a cart abandonment recovery email sequence — 3 emails at 1h, 24h,
  and 72h with urgency escalation — delivering subject lines, body copy,
  timing, and incentive strategy. TRIGGER: "carrinho abandonado", "recupera
  carrinhos abandonados", "abandoned cart emails", "sequência de recuperação
  de carrinho", "/ecom cart-recovery". SKIP: broader nurture or promotional
  email flows -> landing/email-sequence (persuasion sequences beyond cart
  abandonment); deciding WHICH customers to target by value first
  -> ecom/rfm-segment (segmentation precedes the flow).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Cart Recovery — `/ecom cart-recovery`

> **Agent:** Catarina (Retention Manager) | **Framework:** Email Flow Architecture + RFM

## What It Does

Cart abandonment email sequence: 3 emails (1h, 24h, 72h) with urgency escalation.

## Output

Cart recovery sequence with subject lines, body copy, timing, and incentive strategy
