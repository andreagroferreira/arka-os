---
name: mkt/cold-email
description: >
  Write and iterate B2B cold email sequences that get replies.
  First-touch emails, multi-email sequences, and performance iteration.
  Uses AIDA framework and peer-level voice calibration.
allowed-tools: [Read, Write, Edit, Agent]
---

# Cold Email Outreach — `/mkt cold-email <mode>`

> **Agent:** Luna (Marketing Lead) | **Frameworks:** Cold Email Outreach, AIDA, PAS

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

## Voice Calibration by Audience

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

## Subject Line Rules

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

## What to Avoid

| Pattern | Why It Fails |
|---------|-------------|
| "I hope this email finds you well" | Instant template signal |
| Feature dump in email 1 | No trust built yet |
| HTML templates with logos | Looks like marketing, spam-filtered |
| "Just checking in" follow-ups | Zero value added |
| Opening with "My name is X" | Start with something interesting |
| Passive CTA ("let me know") | Weak; ask a direct question instead |

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

## Output

```markdown
## Cold Email — [Prospect Segment]
**Mode:** [write/sequence/iterate] | **Sender:** [role] at [company]
**Prospect:** [title] at [company type] | **Goal:** [book call / get reply]
### Email 1: **Subject:** [line] | **Body:** [copy]
### Subject Lines: 1. [variant] 2. [variant] 3. [variant]
### Rationale: [why this structure and tone were chosen]
```
