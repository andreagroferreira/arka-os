---
name: pm/roadmap-build
description: >
  Outcome-driven product roadmap — North Star + outcome tree + 3-horizon
  map (Now/Next/Later) + bet selection + capacity allocation + audience-
  specific communication. Replaces feature-list roadmaps with measurable
  bets.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Roadmap Build — `/pm roadmap <product>`

> **Lead:** Carolina (Product Manager) | **Cross-dept:** Tomas (Strategy) + Francisca (Tech) + Eduardo (Copy) | **Frameworks:** Marty Cagan Outcome-Driven Roadmaps + Three Horizons + Bets vs Promises

## What ships

A production roadmap in 6 deliverables:

1. **North Star metric** — the one number the product team optimises
2. **Outcome tree** — 3-5 outcomes that decompose the North Star, each measurable
3. **Three-horizon map** — Now (committed) / Next (validating) / Later (exploring)
4. **Bet selection** — 1-3 bets per outcome with hypothesis + success criteria
5. **Capacity allocation** — team mapping with fixed-time vs fixed-scope policy
6. **Per-audience communication** — exec / engineering / sales / customer views

## North Star Metric (the math constraint)

The North Star is **one number**, not a dashboard. Properties of a valid North Star:

- **Lagging enough** — represents customer value, not just activity. "Active users" is leading; "Active users who completed the core action 3 times in 7 days" is closer to value.
- **Leading enough** — moves on quarterly cadence, not yearly. Revenue is too lagging for product team decisions.
- **Causal to revenue** — a working North Star explains revenue movement with 90-day lag.
- **Movable by product** — the team can affect it with shipped work, not just marketing or sales.

Examples that work: Airbnb's "Nights Booked", Slack's "Messages sent in active teams", Stripe's "Payment volume processed".

Examples that fail: NPS (too lagging, hard to move), "Number of users" (vanity), "Engineering velocity" (internal, not customer).

## Outcome Tree (decomposition)

Decompose the North Star into 3-5 outcomes. Each outcome is a number, not a description. The math should hold: if all outcomes move, the North Star moves.

```
NORTH STAR: Active teams using core feature 3+ times/week

  OUTCOME 1: Trial-to-paid conversion rate (currently 6%, target 12%)
    BET 1.1: Improve onboarding completion rate
    BET 1.2: Reduce time-to-first-value

  OUTCOME 2: Weekly active rate per paid team (currently 60%, target 80%)
    BET 2.1: Habit loop in core workflow
    BET 2.2: Notification system that drives return

  OUTCOME 3: Feature adoption depth (currently 1.4 features per active team, target 2.5)
    BET 3.1: Discoverability improvements
    BET 3.2: Cross-feature integration

  OUTCOME 4: Team-to-team expansion (currently 5% of paid teams expand, target 15%)
    BET 4.1: Multi-team workflow
    BET 4.2: Admin tools for organisations
```

Each outcome must answer: *if this number moves by X, does the North Star move by Y? Show the math.*

## Three Horizons (commitment-by-horizon)

| Horizon | Time | Commitment | Communication |
|---|---|---|---|
| **Now** | Current quarter | High — committed, in flight | Specific bets named, in-progress |
| **Next** | Following quarter | Medium — validating, scoped | Bets shaped, not yet started |
| **Later** | 2-4 quarters out | Low — exploring, hypothesis-stage | Directional only, "we believe X matters" |

The rule: **the further out, the lower the commitment**. Roadmaps that promise specific Q4 features at Q1 confidence lose all credibility when they slip.

## Bets vs Promises (Shape Up alignment)

A bet has:
- **Appetite** (time budget, fixed)
- **Hypothesis** (if we ship X, Y will change)
- **Success criteria** (Y moves by Z)
- **Failure criteria** (if Y doesn't move by Z by date W, we stop)

A promise has:
- Date
- Specific deliverable
- No falsification path

Roadmaps with promises are commitments to specific outputs. Roadmaps with bets are commitments to specific *learning*. Bets compound; promises break.

## Capacity Allocation Policy

Each bet has a policy on what's fixed vs variable:

- **Fixed time, variable scope** (Shape Up default) — appetite is the constraint. Scope is whatever fits.
- **Fixed scope, variable time** (legacy waterfall) — only use when externally constrained (regulatory, contractual).
- **Fixed both** — invalid. Pick one. Trying to fix both produces death marches.

Typical mix for a product team: 60% Fixed Time (Now horizon), 30% Discovery (Next horizon), 10% Exploration (Later horizon, hypothesis testing).

## Per-Audience Communication

The same roadmap presents differently to different audiences. Same data, different framing.

| Audience | What they see | What's redacted |
|---|---|---|
| **Exec / Board** | Outcomes + North Star projection + bet portfolio | Specific feature lists, internal team names |
| **Engineering** | Bets with appetite + technical context | Sales-speak, customer logo lists |
| **Sales / GTM** | What's shipping + when (Now horizon only) | Discovery hypotheses, failed bets |
| **Customer-facing** | Public-safe directional ("We're investing in X") | Specifics, dates, anything we might not ship |

The mistake: showing customers the same roadmap as engineering. Customers see dates and treat them as promises; engineering sees dates and treats them as appetite. Different commitment levels need different framings.

## Common Failure Modes

1. **Feature roadmap disguised as outcome roadmap** — list of features renamed "outcomes". The test: can you measure success without shipping a specific feature? If no, it's a feature roadmap.
2. **North Star that doesn't move** — picking a metric that takes 6+ months to respond. The team can't tell if work is working.
3. **Promising the Later horizon** — exposing speculative quarters as commitments. When they slip, the team loses credibility on the Now horizon too.
4. **No falsification on bets** — bets without failure criteria become marathons. Set the kill-switch date upfront.
5. **Same view for all audiences** — engineering sees customer-facing directional language and treats it as imprecision. Customers see engineering specificity and treat it as promise.

## Output → Obsidian: `WizardingCode/Product/Roadmap/<product>-<date>/`

Delivers: North Star definition + outcome tree (3-5 outcomes with metrics) + three-horizon map + bet definitions (hypothesis + success criteria + appetite per bet) + capacity allocation + per-audience roadmap views + 1-page executive summary.
