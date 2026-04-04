---
name: ecom/rfm-segment
description: >
  RFM customer segmentation: Recency, Frequency, Monetary analysis.
  Identify Champions, At-Risk, and Hibernating customers with action plans.
allowed-tools: [Read, Write, Edit, Agent, WebFetch]
---

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
