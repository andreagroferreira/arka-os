---
name: landing/affiliate-bridge
description: >
  Affiliate bridge page spec that pre-sells a third-party offer: review or
  comparison angle, page copy, trust elements, and affiliate tracking setup
  before sending traffic to the vendor. TRIGGER: "bridge page", "página de
  afiliado", "pré-venda de afiliado", "affiliate pre-sell", "review page
  para oferta de afiliado", "/landing affiliate". SKIP: designing a
  multi-step funnel around your OWN product -> landing/funnel-design
  (bridge pages only front someone else's offer).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
metadata:
  origin: community
  source: https://github.com/coreyhaines31/marketingskills
  license: MIT
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Affiliate Bridge — `/landing affiliate <product>`

> **Agent:** Sergio (Affiliate Manager) | **Framework:** Affiliate Bridge Funnel + Referral & Affiliate Programs

**Context:** read the product marketing context first —
`WizardingCode/Marketing/product-marketing.md` in Obsidian (KB-first),
else the project-local `.agents/product-marketing.md`.

## Two Modes

This skill covers both sides of partner-driven growth. Pick the mode from
the request.

| Mode | You are... | Deliverable |
|------|-----------|-------------|
| **A — Bridge page** | The affiliate pre-selling someone else's offer | Bridge page spec that warms traffic before the vendor's checkout |
| **B — Program** | The vendor recruiting others to sell for you | Referral or affiliate program design that turns customers and partners into a growth engine |

Bridge-page work fronts a third-party offer; program work builds the
incentive system behind your own product.

---

## Mode A — Bridge Page

A bridge page sits between an ad (or a piece of content) and a third-party
offer. It pre-sells with a review, comparison, or personal-angle framing so
the visitor arrives at the vendor warm instead of cold.

Build it with:

- **Angle** — review, comparison ("X vs Y"), or story/use-case that earns the click honestly.
- **Copy** — restate the visitor's problem, show the offer as the path, set expectations for what happens after the click.
- **Trust elements** — disclosure of the affiliate relationship, real experience, proof, honest pros and cons.
- **Tracking** — affiliate link with correct attribution parameters, click tracking, and, where the program allows, post-conversion reporting.

Output: a bridge page spec with copy, trust elements, and tracking setup,
ready to hand to `landing/copy-framework` and `landing/landing-gen`.

---

## Mode B — Referral & Affiliate Programs

Design and optimize programs that turn customers and partners into growth
engines.

### Program Inputs (ask if not provided)

**Program type:**
- Customer referral program, affiliate program, or both?
- B2B or B2C?
- Average customer LTV?
- Current CAC from other channels?

**Current state:**
- Existing referral/affiliate program?
- Current referral rate (% who refer)?
- What incentives have you tried?

**Product fit:**
- Is the product shareable?
- Does it have network effects?
- Do customers naturally talk about it?

**Resources:**
- Tools/platforms in use or under consideration?
- Budget for referral incentives?

---

### Referral vs. Affiliate

#### Customer referral programs

**Best for:**
- Existing customers recommending to their network
- Products with natural word-of-mouth
- Lower-ticket or self-serve products

**Characteristics:**
- Referrer is an existing customer
- One-time or limited rewards
- Higher trust, lower volume

#### Affiliate programs

**Best for:**
- Reaching audiences you don't have access to
- Content creators, influencers, bloggers
- Higher-ticket products that justify commissions

**Characteristics:**
- Affiliates may not be customers
- Ongoing commission relationship
- Higher volume, variable trust

---

### Referral Program Design

#### The referral loop

```
Trigger Moment → Share Action → Convert Referred → Reward → (Loop)
```

#### Step 1: Identify trigger moments

**High-intent moments:**
- Right after the first "aha" moment
- After achieving a milestone
- After exceptional support
- After renewing or upgrading

#### Step 2: Design the share mechanism

**Ranked by effectiveness:**
1. In-product sharing (highest conversion)
2. Personalized link
3. Email invitation
4. Social sharing
5. Referral code (works offline)

#### Step 3: Choose the incentive structure

**Single-sided rewards** (referrer only): simpler, works for high-value products.

**Double-sided rewards** (both parties): higher conversion, win-win framing.

**Tiered rewards**: gamifies the referral process, increases engagement.

**For examples and incentive sizing**: See [references/program-examples.md](references/program-examples.md)

---

### Program Optimization

#### Improving the referral rate

**If few customers are referring:**
- Ask at better moments
- Simplify the sharing process
- Test different incentive types
- Make the referral prompt prominent in-product

**If referrals aren't converting:**
- Improve the landing experience for referred users
- Strengthen the incentive for new users
- Ensure the referrer's endorsement is visible

#### A/B tests to run

**Incentive tests:** amount, type, single vs. double-sided, timing.

**Messaging tests:** program description, CTA copy, landing page copy.

**Placement tests:** where and when the referral prompt appears.

#### Common problems and fixes

| Problem | Fix |
|---------|-----|
| Low awareness | Add prominent in-app prompts |
| Low share rate | Simplify to one click |
| Low conversion | Optimize the referred-user experience |
| Fraud/abuse | Add verification, limits |
| One-time referrers | Add tiered/gamified rewards |

---

### Measuring Success

#### Key metrics

**Program health:**
- Active referrers (referred someone in the last 30 days)
- Referral conversion rate
- Rewards earned/paid

**Business impact:**
- % of new customers from referrals
- CAC via referral vs. other channels
- LTV of referred customers
- Referral program ROI

#### Typical findings

- Referred customers have 16-25% higher LTV
- Referred customers have 18-37% lower churn
- Referred customers refer others at 2-3x the rate

---

### Launch Checklist

**Before launch:**
- [ ] Define program goals and success metrics
- [ ] Design the incentive structure
- [ ] Build or configure the referral tool
- [ ] Create the referral landing page
- [ ] Set up tracking and attribution
- [ ] Define fraud-prevention rules
- [ ] Create terms and conditions
- [ ] Test the complete referral flow

**Launch:**
- [ ] Announce to existing customers
- [ ] Add in-app referral prompts
- [ ] Update the website with program details
- [ ] Brief the support team

**Post-launch (first 30 days):**
- [ ] Review the conversion funnel
- [ ] Identify top referrers
- [ ] Gather feedback
- [ ] Fix friction points
- [ ] Send reminder emails to non-referrers

---

### Email Sequences

**Referral program launch:**

```
Subject: You can now earn [reward] for sharing [Product]

We just launched our referral program!

Share [Product] with friends and earn [reward] for each signup.
They get [their reward] too.

[Unique referral link]

1. Share your link
2. Friend signs up
3. You both get [reward]
```

**Referral nurture sequence:**

- Day 7: remind about the referral program
- Day 30: "Know anyone who'd benefit?"
- Day 60: success story + referral prompt
- After a milestone: "You achieved [X] — know others who'd want this?"

---

### Affiliate Programs

**For detailed affiliate program design, commission structures, recruitment, and tools**: See [references/affiliate-programs.md](references/affiliate-programs.md)

---

### Task-Specific Questions

1. What type of program (referral, affiliate, or both)?
2. What's your customer LTV and current CAC?
3. Existing program or starting from scratch?
4. What tools/platforms are you considering?
5. What's your budget for rewards/commissions?
6. Is your product naturally shareable?

---

### Tool Integrations

For implementation, see the [tools registry](../../../marketing/tools/REGISTRY.md). Key tools for referral programs:

| Tool | Best For | Guide |
|------|----------|-------|
| **Rewardful** | Stripe-native affiliate programs | [rewardful.md](../../../marketing/tools/integrations/rewardful.md) |
| **Tolt** | SaaS affiliate programs | [tolt.md](../../../marketing/tools/integrations/tolt.md) |
| **Mention Me** | Enterprise referral programs | [mention-me.md](../../../marketing/tools/integrations/mention-me.md) |
| **Dub.co** | Link tracking and attribution | [dub-co.md](../../../marketing/tools/integrations/dub-co.md) |
| **Stripe** | Payment processing (for commission tracking) | [stripe.md](../../../marketing/tools/integrations/stripe.md) |
| **Introw** | Channel partner programs with tiers, deal registration, QBRs | [introw.md](../../../marketing/tools/integrations/introw.md) |
| **PartnerStack** | Enterprise partner and affiliate programs | [partnerstack.md](../../../marketing/tools/integrations/partnerstack.md) |

---

## Related ArkaOS skills

- **`saas/launch-execute`** — launching the referral/affiliate program
- **`landing/email-sequence`** — referral nurture campaigns
- **`landing/persuasion-apply`** — the psychology behind why people refer
- **`landing/offer-create`** — the incentive/offer that powers the program
- **`landing/funnel-design`** — a multi-step funnel around your own product

## Output → Obsidian

- **Bridge mode:** bridge page spec (copy, trust elements, tracking) → `WizardingCode/Landing-Pages/Affiliate/BRIDGE-<slug>.md`
- **Program mode:** referral/affiliate program design (loop, incentives, launch checklist, metrics) → `WizardingCode/Landing-Pages/Affiliate/PROGRAM-<slug>.md`
