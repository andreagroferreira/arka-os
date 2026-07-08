---
name: saas/gtm-strategy
description: >
  Cross-departmental go-to-market strategy: ICP, positioning, motion selection,
  channel mix, 90-day execution plan. Orchestrates SaaS + Strategy + Marketing
  + Sales + Landing.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# GTM Strategy — `/saas gtm <product>`

> **Lead:** Tiago (SaaS Strategist) | **Cross-dept:** Tomas (Strategy) + Mateus (Brand) + Luna (Marketing) + Miguel (Sales) + Ines (Landing) | **Framework:** MOVE (Sangram Vajre) + Onlyness + AARRR

## What ships

A production GTM package in 6 deliverables, each with a named owner and a measurable target:

1. **ICP profile** — firmographics + persona + pain triggers + buying signal
2. **Positioning statement** — Onlyness frame + competitive contrast table
3. **Motion selection** — primary + assist motion with feasibility math
4. **Channel mix** — budget allocation across channels with AARRR baseline
5. **90-day execution plan** — week-by-week with owners + checkpoints
6. **Executive summary** — 1-page printable to align stakeholders

## ICP Template (firmographic + persona + pain + signal)

Every ICP profile must carry these four blocks. Vagueness in any block invalidates the rest of the GTM stack.

### Firmographics (the company shape)
- Company size (employees, ARR range)
- Industry vertical (with NAICS / SIC code if relevant)
- Geo (countries, regulatory regions)
- Tech stack signal (what they already pay for that signals readiness)
- Funding stage (bootstrapped / seed / Series A+ / public)

### Persona (the human inside the company)
- Title and seniority
- Primary KPI they own
- Tools they use daily
- Information diet (newsletters, podcasts, communities)
- Decision authority (sole / committee / approval)

### Pain Triggers (the moment they realise they need this)
- The specific event that surfaces the pain (new hire, missed quarter, audit, regulation change)
- The cost of not solving it (revenue at risk, hours wasted, compliance exposure)
- The status quo workaround (Excel, agencies, internal builds)

### Buying Signal (how you find them in the wild)
- Observable behavior in the open web (job postings with specific keywords, tool reviews, talks at specific conferences)
- Account-level data signal (vendor footprint, hiring pattern, public infrastructure)
- Conversational signal (specific Slack/Discord communities, specific subreddits)

## Onlyness Statement (positioning frame)

The Onlyness frame forces a single defensible sentence:

> **We are the only [category] that [unique mechanism] for [ICP] who want [outcome].**

Worked example:
> "We are the only AI agent orchestration system that ships behavioral compliance telemetry baked into the runtime for technical founders who want measurable governance instead of vibes-based discipline."

The statement must pass three tests:
1. **Substitution test** — replace your name with a competitor's. Does the sentence still hold? If yes, the positioning isn't defensible.
2. **Customer-articulation test** — would a current customer say this sentence back unprompted in roughly these words?
3. **Mechanism test** — is "unique mechanism" a verifiable specific (a feature, a method, a metric) or marketing prose (an adjective, a vibe)?

## 6 GTM Motions (pick primary + assist)

Each motion has a default ICP shape and a default channel mix. Mixing motions without understanding the constraints below produces zero-momentum GTM.

| Motion | Default ICP | Default Channels | Velocity | Typical CAC payback |
|---|---|---|---|---|
| **Product-Led (PLG)** | High-volume, low-ticket, self-serve adoption pattern | SEO + integrations + viral loops + product itself | Fast (weeks to first value) | 6-12 months |
| **Sales-Led (SLG)** | Enterprise, committee buying, regulated industries | Outbound + content + events + partner channel | Slow (months to close) | 12-18 months |
| **Community-Led** | High-affinity practitioners, identity-driven adoption | Owned community + open source + advocate program | Medium (compounds quarterly) | Variable (community creates own loop) |
| **Partner-Led** | Vertical specialists, complex installs, system integrator channel | Channel partnerships + reseller program + co-marketing | Slow start, faster scale | 9-18 months |
| **Inbound** | Information-seeking buyers researching solutions | SEO + content marketing + comparison content + reviews | Medium (3-6 month ramp) | 6-12 months |
| **Outbound** | Identified buyer set, account-based targeting | Cold email + cold call + LinkedIn + ABM | Fast pipeline, slow trust | 12-24 months |

The MOVE framework (Sangram Vajre): **M**arkets (who you're selling into), **O**perations (your repeatable engine), **V**elocity (deal cycle + expansion math), **E**xpansion (NRR > 110% target).

## Channel-Motion Matrix

```
                  Content/SEO   Paid   Community   Partner   Event   Outbound
Product-Led          ✓✓✓         ✓✓     ✓✓✓          ✓        ✓       —
Sales-Led            ✓✓          ✓✓     ✓            ✓✓✓      ✓✓✓     ✓✓✓
Community-Led        ✓✓✓         —      ✓✓✓✓         ✓✓       ✓✓      —
Partner-Led          ✓           ✓      ✓            ✓✓✓✓     ✓✓✓     ✓✓
Inbound              ✓✓✓✓        ✓✓✓    ✓✓           ✓        ✓✓      —
Outbound             ✓✓          ✓      ✓            ✓✓       ✓✓      ✓✓✓✓
```

Pick exactly ONE primary channel that gets 50%+ of budget. Add at most TWO assist channels. More channels = no channel.

## 90-Day Execution Plan Template

Plan structure (every plan must follow this shape):

```
Week 1-2: Foundation
  - [Owner] ICP doc validated with 5 customer conversations
  - [Owner] Positioning statement live on homepage
  - [Owner] Tracking baseline measured (current AARRR rates)

Week 3-4: Channel Activation (primary)
  - [Owner] First 4 [channel-native content units] published
  - [Owner] Conversion tracking live, first signals captured
  - [Owner] Sales playbook v1 written for inbound responses

Week 5-8: Iteration
  - [Owner] Top-funnel CAC measured, channel ROI computed
  - [Owner] Pricing test A/B started
  - [Owner] First 10 customer interviews completed and tagged
  - [Owner] Assist channels activated based on primary signal

Week 9-12: Scale Decision
  - [Owner] Channel-mix review — double down or pivot
  - [Owner] First retention cohort analysis (D7, D30)
  - [Owner] Next-90-day plan written based on real data
```

Every line must have: owner name, measurable output, due date.

## Executive Summary (1-page, mandatory output)

The full GTM package is dense. The 1-page exec summary captures:

```
Product:             [name]
ICP:                 [one sentence: who, where, what pain]
Positioning:         [Onlyness sentence]
Primary Motion:      [name + why this one]
Primary Channel:     [name + 90-day budget]
North Star Metric:   [the one number that, if it moves, the strategy works]
Day-90 Target:       [specific number tied to North Star Metric]
Top Risk:            [what would invalidate this strategy + mitigation]
```

If the executive summary doesn't fit on one printable page, the strategy is overcomplicated.

## Output → Obsidian: `WizardingCode/GTM/<product>-<date>/`

Delivers: ICP profile + positioning statement + motion selection + channel mix + 90-day plan + executive summary. Plus the cross-departmental review trail (Strategy + Brand + Marketing + Sales + Landing signatures from each phase gate).
