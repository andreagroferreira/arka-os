---
name: mkt/growth-loop
description: >
  Mechanistic design of ONE self-reinforcing growth loop (viral, paid,
  content, product, community) that compounds: spec + math +
  instrumentation + 30-day experiment plan. Replaces linear funnels.
  TRIGGER: "growth loop", "loop de crescimento", "viralidade",
  "K-factor", "AARRR", "referral loop", "flywheel de aquisição",
  "compounding acquisition", "substituir o funil", "make growth
  self-sustaining", CAC-payback/reinvest-ratio loop math.
  SKIP: a full stage-by-stage product roadmap (PMF, T2D3, team,
  channels) -> saas/growth-plan wins; community member growth (1000
  True Fans, membership) -> community/growth-plan wins; choosing the
  growth DIRECTION (new market, Ansoff, adjacency, moats) ->
  strat/growth-strategy wins.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Growth Loop Design — `/mkt growth-loop`

> **Lead:** Luna (Marketing Director) | **Cross-dept:** Pedro (Paid Specialist) + Tomas (Strategy) + Helena (CFO) | **Framework:** Growth Loops (Andrew Chen / Reforge)

## Why Loops > Funnels

Funnels are linear: input stops → output stops. Every new customer requires fresh top-of-funnel work. CAC stays flat or rises.

Loops are circular: **output feeds the next cycle's input**. The system gets stronger with use. CAC trends toward zero on the marginal customer.

A growing business is the sum of working loops, not the sum of funnels.

## Loop Type Decision Matrix

Pick the primary loop based on product DNA, retention shape, and unit economics. Mixing loop types without committing to a primary produces zero compounding.

| Loop type | Default product DNA | Min retention | Min unit econ | Compounding rate | Typical payback |
|---|---|---|---|---|---|
| **Viral** | UGC, communication, multiplayer | D30 ≥ 25% | Free or freemium | K-factor (target > 0.5) | Weeks |
| **Paid** | Clear LTV signal, AOV ≥ CAC × 3 | D30 ≥ 30% | LTV/CAC ≥ 3 | Reinvest ratio | 6-12 months |
| **Content** | Searchable problem space, repeat searcher | Brand recall | Long-tail compound | Page-month growth | 3-12 months |
| **Product** | Multi-user by design (invite, share, embed) | D30 ≥ 40% | Free trial / freemium | Natural rate of growth | Months |
| **Community** | Identity-driven adoption, practitioner audience | D90 ≥ 50% | LTV scales with engagement | Member-second-order growth | Quarters |

If you don't pass any minimum, **fix retention first**. Loops on broken retention amplify churn.

## The 5 Loop Types Fully Spec'd

### 1. Viral Loop (User-Generated)

```
User creates content → Content indexed/shared → New user discovers → Signs up → Creates content → REPEAT
```

Worked example: Pinterest, YouTube, Notion templates, Figma community files.

Key metric: **K-factor** = invites sent × conversion rate. K > 1 = exponential. K = 0.5 means each new user brings 0.5 more (sub-viral but compounds with paid).

Failure modes: K declines as audience saturates → loop dies. Invite incentives without product value → users opt out. Content production without index → SEO doesn't pick up.

Instrumentation needed: sign-up event with source (viral_invite vs organic), invite-sent event with recipient_id, conversion event from invite landing.

### 2. Paid Loop (Revenue-Funded)

```
User pays → Revenue reinvested in ads → New user acquired → Pays → REPEAT
```

Worked example: DTC brands with strong AOV, SaaS with efficient paid (Notion, Webflow at scale), pure-play e-commerce.

Required unit economics: **LTV/CAC ≥ 3, CAC payback < 12 months**. Below those, the loop runs negative against runway.

Failure modes: Channel saturation drives CAC up faster than LTV improves. Single-channel concentration (90% Meta) collapses on platform changes. Attribution opacity prevents real ROI measurement → you reinvest into losing channels.

Instrumentation needed: per-channel CAC tracking, cohort LTV (D30/D90/D365), payback cohort analysis, attribution model (last-touch + multi-touch comparison).

### 3. Content Loop (Search-Driven)

```
User searches problem → Lands on content → Converts to lead/customer → Content earns links → Ranks higher → More searchers find it → REPEAT
```

Worked example: Ahrefs, HubSpot, Investopedia, Wirecutter.

Key metric: **Page-month growth rate** + **Domain Authority compounding**. New page-months publish faster than old page-months decay.

Failure modes: Content quality below SERP threshold → no ranking. No internal linking → no topical authority. AI-flood post-2024 raised the quality floor; thin content doesn't rank.

Instrumentation needed: GSC clicks/impressions per page, organic conversion rate per page, time-to-first-rank, total indexable pages.

### 4. Product Loop (Built-in Virality)

```
User uses product → Product surface exposes to others → Others see it / receive output → Sign up / install → REPEAT
```

Worked example: Slack (invite team), Dropbox (share file), Calendly (send invite link), Figma (share design link), Loom (share recording).

Key metric: **Natural rate of growth** = % of new users from product surface (not paid, not virally invited).

Failure modes: Product output stays inside the team (no external exposure surface). Sharing requires extra steps (high friction). Output looks bad outside the product (no brand impression).

Instrumentation needed: source attribution on first session (product_share_url vs organic vs paid), share-link click-to-signup conversion, output-publish event tracking.

### 5. Community Loop (Identity-Driven)

```
Practitioner joins community → Status from contributing → Other practitioners notice → Join → Contribute → REPEAT
```

Worked example: Stack Overflow, Reddit communities, Substack networks, Slack practitioner groups, Discord servers.

Key metric: **Member-second-order growth** — for every new member, how many new members do they bring within 90 days?

Failure modes: Community grows but doesn't tie to product revenue (community-led ≠ revenue loop). Status hierarchy collapses → top contributors leave. Spam erodes signal → quality contributors disengage.

Instrumentation needed: cohort retention curves (D30/D90/D365), contribution distribution (Gini coefficient), second-order growth attribution.

## Loop Specification Format

Every loop spec must answer these 6 questions in the same shape:

```yaml
loop_name: <descriptive name>
loop_type: viral | paid | content | product | community

step_1_trigger:
  what_happens: <observable event>
  mechanism: <named mechanism, not vibes>
  metric: <measurable target>
  owner: <named human>

step_2_action:
  what_user_does: <observable user action>
  mechanism: <what makes this action likely>
  metric: <conversion rate target>
  owner: <named human>

step_3_output:
  what_gets_produced: <artifact, signal, content, money>
  visibility: <internal | shareable | indexed | broadcast>
  metric: <output volume target>
  owner: <named human>

step_4_reinput:
  how_output_becomes_input: <named mechanism>
  audience: <who sees the output>
  metric: <reinput conversion rate>
  owner: <named human>

cycle_time: <hours / days / weeks per full loop>
compounding_factor: <K-factor / reinvest ratio / page velocity / NRG / 2nd-order rate>
breakeven_threshold: <the number where loop self-sustains>
```

## Loop Design Checklist (pre-instrumentation)

Before instrumenting, the loop must pass these 8 checks. Failing any check means the loop is incoherent — fix the spec before tracking.

- [ ] **Output is observable** — the loop's output (artifact, signal, post, share) can be counted, not inferred
- [ ] **Re-input mechanism is named** — "users tell their friends" is vibes; "invite link with referral code on Day 7 prompt" is a mechanism
- [ ] **No infinite resource assumed** — the loop doesn't require infinite content production, infinite paid budget, or infinite founder time
- [ ] **Step ownership is human-named** — every step has a named owner, not "marketing team"
- [ ] **Cycle time is sub-quarterly** — at least one full loop completes within 90 days, otherwise feedback is too slow
- [ ] **Compounding factor is computable** — you can express the math: K-factor, reinvest ratio, NRG percentage
- [ ] **Breakeven threshold is named** — you know the number at which the loop self-sustains
- [ ] **Failure modes are listed** — the spec names 2-3 things that would kill the loop and the early signals

## Common Failure Modes Across All Loop Types

1. **Mistaking content for loop** — publishing content monthly isn't a loop unless each piece earns links/searches that bring new users
2. **No instrumentation** — without per-step tracking, you can't tell if the loop is working or if growth is from somewhere else
3. **Multiple half-loops** — running 3 loops at 0.3x compounding ≠ 1 loop at 1.0x. Pick a primary
4. **Loop without retention** — a loop on broken retention amplifies churn. Fix D30 first
5. **Loop ignores unit economics** — viral loops still need someone to pay eventually; product loops still need conversion rate

## Output → Obsidian: `WizardingCode/Marketing/GrowthLoops/<product>-<date>/`

Delivers: retention baseline + loop type selection rationale + full loop spec (all 4 steps with mechanism/metric/owner per step) + compounding math + unit economics check + instrumentation tracking spec + 30-day experiment plan + 1-page executive summary.
