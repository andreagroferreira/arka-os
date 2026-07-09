---
name: saas/voc-loop
description: >
  Voice of Customer loop — collect signal (NPS, CSAT, CES, tickets, churn
  reasons), close the loop with the customer, cluster themes, and run PDCA;
  only 1 in 26 unhappy customers complains, so closing the loop beats
  collecting more. Owned by the RevOps squad. TRIGGER: "voice of customer",
  "VoC", "feedback dos clientes", "fecha o loop com o cliente",
  "NPS/CSAT/CES program", "/saas voc-loop". SKIP: quantitative churn
  cohorts and retention curves -> saas/churn-analysis (numbers, not
  voice); acting on
  one account's feedback -> saas/customer-success (account playbook, not
  theme clustering).
allowed-tools: [Read, Write, Edit, Agent]
---

# Voice of Customer Loop — `/saas voc-loop`

> **Agent:** Rita S. (SaaS Metrics & VoC Analyst) · **Framework:** Voice of Customer + CX metrics
> KB: [[Processo Voice of Customer (VoC)]] · [[8 Métricas de CX (Nardon-Siqueira)]]

A continuous loop, not a one-off survey. For every 26 dissatisfied customers, only 1 complains — so the signal is scarce and closing the loop matters more than collecting.

## The loop (continuous)
1. **Collect** across sources: NPS, CSAT (interaction), CES (friction), support tickets, churn reasons, sales-lost reasons.
2. **Close the loop** with the customer who gave the signal — respond, acknowledge, tell them what changed. (This is the step most teams skip and where the value is.)
3. **Cluster** signals into themes before acting (don't react to single anecdotes).
4. **PDCA:** Plan a fix for the top theme → Do (ship) → Check (did the metric move?) → Act (standardise or revert).

## Metric distinctions (don't conflate)
- **NPS** = macro loyalty (would you recommend?)
- **CSAT** = immediate interaction satisfaction
- **CES** = effort/friction (96% of high-effort customers become less loyal)

## Output
A VoC theme report (clustered, ranked) + closed-loop log + the PDCA experiment status, in Obsidian. Feed themes to the Activate/Retain missions and to Product (Carolina) for discovery.
