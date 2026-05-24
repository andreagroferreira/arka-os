---
name: landing/webinar-funnel
description: >
  Webinar funnel design — registration page, reminder sequence, live pitch
  script structure, replay/cart sequence, conversion targets.
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

# Webinar Funnel — `/landing webinar <topic>`

> **Lead:** Ines (Conversion Strategist) | **Copy:** Teresa (Sales Copywriter) | **Framework:** Russell Brunson Perfect Webinar + False Belief Patterns

## What ships

A production webinar funnel in 6 deliverables:

1. **Registration page** with hook + promise + agenda + host + social proof + CTA
2. **Reminder email sequence** (5 emails, registration → live)
3. **Live pitch script** with timing markers, false-belief teardown, offer stack
4. **Replay + cart sequence** (5-7 emails post-webinar)
5. **Conversion targets** with funnel math (registration → show-up → buy)
6. **Tracking spec** with pixel events and attribution windows

## The Perfect Webinar Frame (Brunson)

A converting webinar follows a strict structure. Deviating from any element measurably drops conversion.

```
TIMING               BLOCK            PURPOSE
─────────────────────────────────────────────────────────────────────
0:00 - 0:05          Open             Hook, agenda, attendance proof
0:05 - 0:15          Origin Story     Builder credibility, stakes
0:15 - 0:45          Content (3 secrets) Teardown of 3 false beliefs
0:45 - 0:55          Transition       "Here's what to do next"
0:55 - 1:25          Offer Stack      Itemized value, anchored price
1:25 - 1:35          Urgency + FAQ    Scarcity reason, top objections
1:35 - 1:50          Close + Q&A      Repeated CTA, live Q&A
```

The 90-minute structure is the floor. Live webinars can run 120-180; auto-webinars compress to 60-75.

## False Belief Patterns (the content middle)

The middle of the webinar exists to teardown 3 false beliefs the audience holds — about the **vehicle** (what method), the **internal** (their own capability), and the **external** (their environment / circumstances). Each teardown follows the same shape:

```
1. State the false belief plainly ("Most people think X")
2. Tell the origin of that belief (where it came from, why it's plausible)
3. Tell the story of when YOU believed it (vulnerability anchor)
4. Reveal the cost of that belief (specific consequence)
5. Introduce the new belief (what actually works)
6. Prove the new belief with evidence + story
```

Pick the 3 most load-bearing false beliefs your offer needs to dismantle. Pick more than 3 and the webinar bloats. Pick fewer and conversion drops.

## Registration Page Anatomy

Above the fold:
- **Headline** — the hook (curiosity-led specific outcome)
- **Sub-headline** — the timeframe + named mechanism
- **Date / time / format** — specific, with timezone
- **CTA button** — register, not "submit"

Below the fold:
- **Agenda** — 3-4 bullets teasing the 3 content blocks
- **Host bio** — one paragraph + photo + 3 credibility markers
- **Social proof** — 2-3 testimonials or registrant count
- **Reminder consent** — "We'll send a reminder by email/SMS"
- **FAQ block** — duration, replay availability, recording disclosure

Conversion target: **30-45%** registration rate from warm traffic, **8-15%** from cold ads.

## Reminder Sequence Template (5 emails)

| # | When | Subject style | Purpose |
|---|---|---|---|
| 1 | Immediately | Confirmation + calendar link | Confirm registration, add to calendar |
| 2 | 24h before | Value-prime story | Story-led pre-sell of the secrets to be revealed |
| 3 | 1h before | "Starting soon" + login link | Drive show-up |
| 4 | 10 min before | "We're live in 10" | Last show-up push |
| 5 | At start | "We're live now" | Catch the last-minute attendees |

Conversion target: **35-55%** show-up rate from registration. Auto-webinar shows higher (60-70%) because re-watching is built in.

## Live Pitch Script Structure (core deliverable)

The script template has fixed sections. Filling each section is the work; structure is not optional.

```markdown
# Webinar — [TOPIC]

## 0:00 — Open (5 min)
Hook line: [ONE SENTENCE WITH SPECIFIC NUMBER + TIMEFRAME]
Agenda: [3 BULLETS — THE 3 SECRETS]
Attendance proof: [WHO'S HERE / WHERE FROM]

## 0:05 — Origin Story (10 min)
- The moment everything changed
- What was at stake (concrete)
- The cost of NOT solving it
- The breakthrough insight

## 0:15 — Secret #1 [VEHICLE FALSE BELIEF] (10 min)
- False belief: [plain sentence]
- Origin of the belief: [story]
- When YOU believed it: [vulnerability anchor]
- Cost of the belief: [specific consequence]
- New belief: [plain sentence]
- Proof: [story + evidence]

## 0:25 — Secret #2 [INTERNAL FALSE BELIEF] (10 min)
(same structure)

## 0:35 — Secret #3 [EXTERNAL FALSE BELIEF] (10 min)
(same structure)

## 0:45 — Transition (10 min)
"You're now wondering: how do I actually DO this?"
- Three options: (1) figure it out alone (slow), (2) hire someone (expensive), (3) follow a proven system (the offer)
- Introduce the offer name

## 0:55 — Offer Stack (30 min)
- Component 1: [name + dream outcome + value $X]
- Component 2: [name + dream outcome + value $X]
- Component 3: [name + dream outcome + value $X]
- Bonus 1: [name + scarcity reason]
- Bonus 2: [name + scarcity reason]
- Total value: $X
- Today's price: $Y (anchored vs total)

## 1:25 — Urgency + FAQ (10 min)
Urgency reason: [scarcity / deadline / cohort cap / price increase]
Top objections answered: [3-5 with prepared scripts]

## 1:35 — Close + Live Q&A (15 min)
Repeat CTA + URL
Live Q&A with prepared questions
Final close at 1:50
```

## Replay + Cart Sequence (post-webinar)

| # | When | Subject style | Purpose |
|---|---|---|---|
| 1 | 1h after | "Did you miss it?" + replay | Catch no-shows |
| 2 | 24h | "Quick recap" + replay + CTA | Re-engage, soft pitch |
| 3 | 48h | Case study | Social proof, momentum |
| 4 | 72h | FAQ + objection-handling | De-risk |
| 5 | Cart-close - 24h | "Closing tomorrow" + scarcity | Urgency |
| 6 | Cart-close - 6h | "Closing in 6h" | Final push |
| 7 | Cart-close - 1h | "Closing in 1h" | Last-call |

Conversion target: **3-8%** of registrants buy (cold list), **8-20%** (warm list). Replay attribution is 30-50% of total revenue — don't skip it.

## Tracking Spec

Pixel events required:
- `Registration` — fires on registration form submit
- `WebinarOpen` — fires on live broadcast page load (50%+ attendance signal)
- `WebinarComplete` — fires at 75% watched
- `PitchOpen` — fires when offer URL loads from webinar
- `Purchase` — fires on order confirmation
- `ReplayOpen` — fires on replay page load
- `ReplayPurchase` — fires on order from replay-attributed link

Attribution window: 14 days, last-click weighted toward the live broadcast event.

## Output → Obsidian: `WizardingCode/Webinars/<topic>-<date>/`

Delivers: hook variants + registration page + 5-email reminder sequence + full pitch script + 5-7 email replay/cart sequence + conversion targets + tracking spec.
