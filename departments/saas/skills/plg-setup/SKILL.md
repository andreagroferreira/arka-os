---
name: saas/plg-setup
description: >
  Product-Led Growth setup: freemium/trial model selection, activation metrics,
  onboarding flow, PQL definition. Framework: Wes Bush PLG Flywheel.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

# PLG Setup — `/saas plg <product>`

> **Agent:** Tiago + Andre S. (Growth Engineer) | **Framework:** PLG (Wes Bush)

## PLG Model Selection

| Model | Best For | Conversion Target |
|-------|----------|-------------------|
| Freemium | High volume, low marginal cost, network effects | Free→Paid: 3-5% |
| Free Trial (14 day) | Need full experience to see value | Trial→Paid: 15-25% |
| Reverse Trial | Show premium, then downgrade to free | Reverse→Paid: 8-15% |
| Open Core | Dev tools, open-source community | Community→Enterprise: 1-3% |

## PLG Flywheel Design

```
User signs up (self-serve)
  → Onboarding (time-to-value < 5 min)
    → Activation (aha moment)
      → Engagement (habit formation)
        → Expansion (invite team, upgrade)
          → Advocacy (refer others)
            → New users sign up → REPEAT
```

## Key Metrics to Define

| Metric | Definition | Target |
|--------|-----------|--------|
| Time to Value (TTV) | Signup → first value | < 5 minutes |
| Activation Rate | Users who reach aha moment / total signups | > 40% in 7 days |
| PQL (Product Qualified Lead) | User behavior that predicts conversion | Define threshold |
| Free-to-Paid Conversion | Free users who upgrade | 3-5% (freemium) |
| NRR | Net Revenue Retention | > 110% |
| Natural Rate of Growth | Organic + viral (no paid) | Track monthly |

## Onboarding Flow Design
1. **Welcome screen** — One sentence: what you'll accomplish
2. **Setup steps** — Maximum 3 steps to first value
3. **Aha moment trigger** — The specific action that hooks the user
4. **Empty states** — Show what success looks like, not blank screens
5. **Progress indicator** — Show how far along they are
6. **Celebration** — Acknowledge when they complete activation

## Output → Obsidian: `WizardingCode/SaaS/PLG/PLG-<slug>.md`
