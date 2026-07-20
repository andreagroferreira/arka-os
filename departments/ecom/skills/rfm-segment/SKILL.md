---
name: ecom/rfm-segment
description: >
  RFM customer segmentation (Recency, Frequency, Monetary — Drew Sanocki):
  scores customers 1-5 per dimension, identifies Champions, Loyal, At-Risk,
  and Hibernating segments, applies the whale curve, and delivers an RFM
  matrix with segment counts and an action plan plus automated flow per
  segment. TRIGGER: "segmenta os clientes", "quem são os meus melhores
  clientes", "RFM analysis", "clientes em risco", "/ecom rfm". SKIP:
  demographic audience building for campaigns -> marketing/audience-segment
  (targeting, not purchase-behaviour scoring); mapping the experience per
  stage -> ecom/customer-journey; executing win-back emails -> ecom/cart-recovery.
allowed-tools: [Read, Write, Edit, Agent, WebFetch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# RFM Segmentation — `/ecom rfm`

> **Agent:** Catarina (Retention Manager) | **Framework:** RFM Analysis (Drew Sanocki)

## RFM Dimensions

| Dimension | Question | Score 1 (worst) → 5 (best) |
|-----------|----------|---------------------------|
| **R**ecency | When was the last purchase? | Long ago → Very recent |
| **F**requency | How often do they buy? | Rarely → Very often |
| **M**onetary | How much have they spent? | Low → High |

## Key Segments

| Segment | RFM | Action |
|---------|-----|--------|
| **Champions** | R5 F5 M5 | VIP program, early access, referral ask |
| **Loyal** | R4-5 F4-5 M3-5 | Cross-sell, loyalty rewards |
| **Potential Loyal** | R4-5 F2-3 M2-3 | Nurture series, incentivize 2nd/3rd purchase |
| **New** | R5 F1 M1-2 | Welcome flow, first-purchase experience |
| **At Risk** | R2-3 F3-5 M3-5 | Win-back campaign, special discount |
| **Can't Lose** | R1-2 F4-5 M4-5 | Personal outreach, strong discount |
| **Hibernating** | R1-2 F1-2 M1-2 | Re-engagement or accept churn |

## Whale Curve
- Top 20% customers = 80%+ of profit
- Bottom 20% often = LOSS
- Action: Protect top 20%, reduce cost of bottom 20%

## Automated Flows per Segment
- Champions → VIP early access + referral program
- New → Welcome series (5 emails, 14 days)
- At Risk → Win-back (3 emails, escalating discount)
- Cart Abandonment → 3 emails (1h, 24h, 72h)

## Output → RFM matrix + segment counts + action plan per segment
