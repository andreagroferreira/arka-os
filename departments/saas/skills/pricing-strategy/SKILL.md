---
name: saas/pricing-strategy
description: >
  SaaS pricing strategy using value-based pricing (Patrick Campbell), Van Westendorp
  sensitivity analysis, and competitive positioning. Outputs pricing page structure.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

# SaaS Pricing Strategy — `/saas pricing <product>`

> **Agent:** Tiago (SaaS Strategist) | **Framework:** Value-Based Pricing (Campbell)

## Pricing Process

### Step 1: Value Metric Identification
- What unit of value does the customer pay for?
- Good value metrics: users, transactions, storage, API calls
- Bad value metrics: flat fee per company (no expansion), features only

### Step 2: Willingness to Pay (Van Westendorp)
4 questions to ask target customers:
1. At what price is this too expensive? (won't consider)
2. At what price is this expensive but worth it? (would consider)
3. At what price is this a bargain? (great deal)
4. At what price is this too cheap? (suspect quality)

### Step 3: Competitive Positioning
| Position | Strategy | When |
|----------|----------|------|
| Premium | 2-3x market price | Superior features, brand, support |
| Competitive | Market average | Similar features, compete on UX |
| Penetration | Below market | New entrant, grab share fast |
| Freemium | Free core + paid premium | PLG, high volume, low marginal cost |

### Step 4: Tier Structure
Standard 3-tier model:
- **Free/Starter:** Hook users, demonstrate value, capture leads
- **Pro:** Most popular, solves the full problem, best value
- **Business/Enterprise:** Team features, SSO, SLA, priority support

### Step 5: Pricing Page Rules
- Highlight the recommended plan (usually middle)
- Annual pricing default (show monthly savings)
- Feature comparison table with clear differentiators
- Social proof on pricing page (logos, testimonials)
- FAQ section addressing common objections

## Output → Obsidian: `WizardingCode/SaaS/Pricing/PRICING-<slug>.md`
