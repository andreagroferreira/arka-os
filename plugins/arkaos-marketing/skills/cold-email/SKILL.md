---
name: cold-email
description: >
  Writes and iterates B2B cold email: single first-touch emails, 5-6
  email sequences with cadence, and performance-driven revisions, using
  AIDA, peer-level voice calibration, and deliverability checks. TRIGGER:
  "cold email", "email frio", "escreve um cold email", "sequência de
  outreach", "prospecção por email", "/mkt cold-email <mode>". SKIP:
  lifecycle emails to existing subscribers (welcome, nurture, win-back)
  -> mkt/email-sequence (owned audiences, not cold prospects); the sales
  proposal after a reply -> sales/proposal-write.
metadata:
  origin: community
  source: https://github.com/coreyhaines31/marketingskills
  license: MIT
---

# Cold Email Outreach

> **Agent:** Luna (Marketing Lead) | **Frameworks:** Cold Email Outreach, AIDA, PAS

**Context:** read the product marketing context first —
`WizardingCode/Marketing/product-marketing.md` in Obsidian (KB-first),
else the project-local `.agents/product-marketing.md`.

## Modes

| Mode | When | Deliverable |
|------|------|-------------|
| `write` | Need a single first-touch email | Email + 3 subject lines + rationale |
| `sequence` | Need a 5-6 email sequence | Full sequence with cadence + angles |
| `iterate` | Have performance data to improve | Diagnosis + revised emails + test plan |

## Context Gathering

| Category | Questions |
|----------|-----------|
| Sender | Role? Product? Proof points? Individual or company? |
| Prospect | Title? Company type/size? Problem? Trigger to reach out now? |
| Ask | Goal of email 1? (book call, get reply, get referral) |

Research signals worth hunting: funding, hiring, leadership posts, company
news, tech-stack changes. One strong signal plus a clear value prop is
enough to write — don't block on missing inputs; use what you have and note
what would make it stronger.

## Voice Calibration by Audience

**Target voice:** a sharp colleague who noticed something relevant and is
sharing it — conversational but not sloppy, confident but not pushy.
Calibrate by audience:

| Audience | Length | Tone | What Works |
|----------|--------|------|------------|
| C-suite | 3-4 sentences | Ultra-brief, peer-level | Big problem + proof + one question |
| VP / Director | 5-7 sentences | Direct, metrics-conscious | Specific observation + business angle |
| Manager | 7-10 sentences | Practical, shows homework | Problem + practical value + easy CTA |
| Technical | 7-10 sentences | Precise, no fluff | Exact problem + precise solution + low-friction ask |

## Core Principles

1. **Write like a peer, not a vendor** — would a friend send this?
2. **Every sentence earns its place** — create curiosity, establish relevance, build credibility, or drive the ask
3. **Personalization connects to the problem** — not "I saw you went to MIT"
4. **Lead with their world** — opener about them, not you
5. **One ask per email** — pick one CTA, not three

Personalization runs on a 4-level system (from generic to signal-driven);
if you could remove the personalized opening and the email still made sense,
it isn't working. See [personalization.md](references/personalization.md)
for the levels and research signals.

## Message Structure & Frameworks

There's no single right structure. Pick a framework that fits the situation,
or write freeform when the email flows without one.

- **Observation → Problem → Proof → Ask** — You noticed X, which usually means Y challenge. We helped Z with that. Interested?
- **Question → Value → Ask** — Struggling with X? We do Y. Company Z saw [result]. Worth a look?
- **Trigger → Insight → Ask** — Congrats on X. That usually creates Y challenge. We've helped similar companies with that. Curious?
- **Story → Bridge → Ask** — [Similar company] had [problem]. They [solved it this way]. Relevant to you?

For the full catalog of frameworks with examples, see [frameworks.md](references/frameworks.md).

## Subject Line Rules

Short, boring, internal-looking. The subject line's only job is to get the
email opened — 2-4 words, lowercase, no punctuation tricks, no prospect's
first name.

| Works | Example | Why |
|-------|---------|-----|
| Two-three words | "quick question" | Looks like a colleague |
| Trigger + question | "your TechCrunch piece" | Specific, not spam |
| Shared context | "re: Series B" | Feels like follow-up |
| Observation | "your ATS setup" | Relevant, not salesy |

| Kills Opens | Why |
|-------------|-----|
| ALL CAPS | Spam signal |
| Fake Re:/Fwd: | Deceptive, kills trust |
| Feature/benefit in subject | Looks like marketing |
| Company name in subject | Immediate vendor flag |

For the full data on what earns opens, see [subject-lines.md](references/subject-lines.md).

## Follow-Up Sequence Cadence

| Email | Day | Gap | Angle |
|-------|-----|-----|-------|
| 1 | Day 1 | -- | First touch: trigger + problem + ask |
| 2 | Day 4 | +3 | New evidence (case study, data point) |
| 3 | Day 9 | +5 | New angle on the problem |
| 4 | Day 16 | +7 | Related insight (industry, tech stack) |
| 5 | Day 25 | +9 | Direct question (plain clarity) |
| Breakup | Day 35 | +10 | Close the loop professionally |

## Follow-Up Rules

- [ ] Each follow-up has a NEW angle (never "just checking in")
- [ ] Each email stands alone (prospect does not remember previous ones)
- [ ] Breakup email signals finality (increases reply rate)
- [ ] Rotate: evidence, new angle, insight, direct question, reverse ask

For cadence, angle rotation, and breakup templates, see [follow-up-sequences.md](references/follow-up-sequences.md).

## What to Avoid

| Pattern | Why It Fails |
|---------|-------------|
| "I hope this email finds you well" | Instant template signal |
| Feature dump in email 1 | No trust built yet |
| HTML templates with logos | Looks like marketing, spam-filtered |
| "Just checking in" follow-ups | Zero value added |
| Opening with "My name is X" | Start with something interesting |
| Passive CTA ("let me know") | Weak; ask a direct question instead |
| Jargon: "synergy," "leverage," "best-in-class" | Reads as vendor boilerplate |

## Deliverability Basics

- [ ] Dedicated sending domain (not primary), SPF/DKIM/DMARC passing
- [ ] Domain warmup: 4-6 weeks, start 20/day, plain text emails
- [ ] Unsubscribe mechanism (CAN-SPAM, GDPR), under 200 emails/day
- [ ] Bounce rate under 5% (verify lists before sending)

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No unsubscribe link → flag CAN-SPAM violation
- Sending >50 emails/day from new domain → flag deliverability risk
- No domain warm-up plan → flag spam folder risk

## Quality Check

Before presenting, gut-check:

- Does it sound like a human wrote it? (Read it aloud.)
- Would YOU reply to this if you received it?
- Does every sentence serve the reader, not the sender?
- Is the personalization connected to the problem?
- Is there one clear, low-friction ask?

## Data & References

The references carry the performance data behind these choices — use them to
inform the writing, not as a checklist to satisfy:

- [benchmarks.md](references/benchmarks.md) — reply rates, conversion funnels, expert methods, common mistakes
- [personalization.md](references/personalization.md) — 4-level personalization system, research signals
- [subject-lines.md](references/subject-lines.md) — subject line data and optimization
- [follow-up-sequences.md](references/follow-up-sequences.md) — cadence, angles, breakup emails
- [frameworks.md](references/frameworks.md) — all copywriting frameworks with examples

## Related ArkaOS skills

- **`sales/prospecting`** — build and qualify the prospect list this skill writes outreach against (the upstream step)
- **`landing/copy-framework`** — landing pages and web copy
- **`mkt/email-sequence`** — lifecycle/nurture email sequences (not cold outreach)
- **`mkt/social-strategy`** — LinkedIn and social posts
- **`mkt/product-marketing`** — foundational positioning
- **`sales/revops`** — lead scoring, routing, and pipeline management

## Output

```markdown
## Cold Email — [Prospect Segment]
**Mode:** [write/sequence/iterate] | **Sender:** [role] at [company]
**Prospect:** [title] at [company type] | **Goal:** [book call / get reply]
### Email 1: **Subject:** [line] | **Body:** [copy]
### Subject Lines: 1. [variant] 2. [variant] 3. [variant]
### Rationale: [why this structure and tone were chosen]
```
