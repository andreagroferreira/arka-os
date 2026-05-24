---
name: strat/growth-strategy
description: >
  Growth strategy using Ansoff Matrix + adjacency framework + Greiner growth
  phases. Picks the next growth vector with risk-adjusted feasibility and a
  12-month execution roadmap.
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

# Growth Strategy — `/strat growth <business>`

> **Lead:** Tomas (Chief Strategist) | **Cross-dept:** Helena (CFO) + Rita (Market Analyst) | **Frameworks:** Ansoff Matrix + Chris Zook Adjacencies + Greiner Growth Phases

## What ships

A production growth strategy in 6 deliverables:

1. **Greiner phase diagnosis** — current phase + impending crisis prediction
2. **Ansoff Matrix mapping** — concrete options per quadrant with market sizing
3. **Adjacency analysis** — ranked adjacencies by distance × capability × attractiveness
4. **Growth vector selection** — primary + assist with explicit trade-off rationale
5. **Risk profile** — pre-mortem with top 5 risks + early warning signals + mitigations
6. **12-month execution roadmap** — quarter-by-quarter milestones with named owners

## Greiner Growth Phases (where are you in the curve?)

Larry Greiner's model says companies grow through 6 evolutionary phases, each ending in a predictable crisis. Knowing the phase predicts the crisis.

| # | Phase | Driver | Predictable Crisis | Resolution |
|---|---|---|---|---|
| 1 | **Creativity** | Founder vision + product-market fit | Leadership Crisis (founder can't manage operations) | Hire professional management |
| 2 | **Direction** | Top-down management + functional structure | Autonomy Crisis (middle managers blocked by HQ) | Delegate authority downward |
| 3 | **Delegation** | Decentralised operating units | Control Crisis (HQ loses visibility into BUs) | Build coordination systems |
| 4 | **Coordination** | Formal systems, planning, ROI gates | Red Tape Crisis (bureaucracy strangles decisions) | Collaboration via teams |
| 5 | **Collaboration** | Cross-functional teams, matrix structure | Growth Crisis (internal saturation, need new sources) | External alliances / M&A |
| 6 | **Alliances** | Partnerships, joint ventures, ecosystems | Identity Crisis (who are we?) | Reinvention / spin-out |

Diagnose by symptoms, not org-chart vibes. Each phase has specific decision-making patterns and pain points.

## The Ansoff Matrix (4 growth quadrants)

The 2×2 matrix on Products (existing / new) × Markets (existing / new). Each quadrant has a different risk profile.

```
                    EXISTING PRODUCTS         NEW PRODUCTS
EXISTING MARKETS    Market Penetration        Product Development
                    (lowest risk)             (medium-high risk)
                    - Cross-sell              - Adjacent product
                    - Up-sell                 - Same customer expansion
                    - Win share from competitor

NEW MARKETS         Market Development        Diversification
                    (medium risk)             (highest risk)
                    - New geo                 - New product + new market
                    - New segment             - True new business
                    - New channel             - Acquisition often required
```

Default risk-adjusted sequencing: start with **Market Penetration** until the law of diminishing returns hits (typically 70-80% market share in a defined segment). Then choose between Market Development and Product Development based on capability fit. Diversification only when first three quadrants are exhausted or a structural opportunity is undeniable.

## Chris Zook Adjacency Framework

For each candidate growth move, score on three dimensions:

1. **Distance from core** (1-10): How far is this from your repeatable model? 1 = same customer + same product + tweaks. 10 = different customer + different product + different capability.
2. **Capability fit** (1-10): Does it use your existing strengths? 10 = leverages your core competence. 1 = requires building all-new capability.
3. **Market attractiveness** (1-10): Size × growth × profitability of the target market.

Zook's empirical finding: **adjacency success rate drops 50% with every step away from core**. So the math:

```
expected_success_rate = 0.27 × (0.5 ^ distance_from_core_steps) × capability_fit_factor × market_factor
```

Adjacencies more than 2 steps from core have <10% historical success rate. Pick the closest viable adjacency, not the most attractive one.

## Growth Vector Decision Tree

```
Is current retention healthy (D30 > category norm)?
  NO  → Fix retention. No growth vector survives broken retention.
  YES → Continue.

Have you saturated current market segment (>70% share or stalled)?
  NO  → Market Penetration is the default. Cross-sell, up-sell, win share.
  YES → Continue.

Do you have unique capability that transfers?
  YES → Product Development (new product to existing customers) OR
        Market Development (existing product to new segment / geo).
        Choose by capability fit score.
  NO  → Acquisition or partnership required. Diversification.
```

## Risk Profile Template

Every growth vector ships with a pre-mortem. Format:

```yaml
top_5_risks:
  - name: <specific risk>
    probability: low | medium | high
    impact: low | medium | high | terminal
    early_warning_signal: <observable signal in first 90 days>
    mitigation: <named action if signal fires>
    owner: <named human>
```

Risks must be specific. "Market might shift" is vibes; "if our top 3 partners renegotiate pricing in Q2 our gross margin drops below the cost floor" is a risk.

## 12-Month Roadmap Template

```
Q1: Foundation
  Milestone: [specific outcome, not activity]
  Owner: [named human]
  Success metric: [measurable number]

Q2: First Proof
  Milestone: [first measurable signal that vector is working]
  Owner: [named]
  Decision gate: [continue / pivot criteria]

Q3: Scale or Pivot
  Decision: [scale signal observed? Y/N]
  If scale: doubling milestone
  If pivot: alternate vector selected

Q4: Compound
  Milestone: [vector now self-sustaining or absorbed into ops]
  Owner: [named]
  Year-end metric: [measurable target tied to original brief]
```

Every quarter has a decision gate, not just a milestone. Roadmaps without decision gates become wish lists.

## Common Failure Modes

1. **Skipping retention check** — chasing growth on broken retention amplifies churn
2. **Ansoff diagonal-jumping** — jumping straight to Diversification without proving Market Penetration is exhausted
3. **Capability vanity** — picking the most attractive adjacency instead of the highest-fit one
4. **Greiner phase denial** — refusing to acknowledge the next crisis (e.g., founder won't delegate, stays in Direction phase past breakeven)
5. **Roadmap without decision gates** — quarterly milestones without "continue / pivot" criteria become marketing for the existing strategy

## Output → Obsidian: `WizardingCode/Strategy/Growth/<business>-<date>/`

Delivers: Greiner phase diagnosis + Ansoff Matrix mapping + adjacency analysis + vector selection rationale + risk profile (5 risks with mitigations) + 12-month roadmap with decision gates + 1-page executive summary.
