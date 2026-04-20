---
name: content/viral-design
description: >
  Design viral content using Jonah Berger's STEPPS framework. Score content
  against 6 viral triggers before publishing.
allowed-tools: [Read, Write, Edit, Agent, WebFetch, WebSearch]
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

# Viral Content Design — `/content viral <topic>`

> **Agent:** Rafael (Content Strategist) + Filipe (Viral Engineer)
> **Framework:** STEPPS (Jonah Berger, "Contagious")

## STEPPS Framework

Score each piece of content against all 6 triggers (minimum 3/6 to publish):

| Trigger | Question | Score 0-2 |
|---------|----------|-----------|
| **S**ocial Currency | Does sharing this make the person look good/smart/insider? | |
| **T**riggers | Is there something in daily life that reminds people of this? | |
| **E**motion | Does it provoke high-arousal emotion (awe, anger, anxiety, humor)? | |
| **P**ublic | Is the use/sharing visible to others? | |
| **P**ractical Value | Is it genuinely useful? Would people share to help others? | |
| **S**tories | Is there a narrative that carries the message? | |

**Scoring:** 0 = absent, 1 = present, 2 = strong
**Minimum:** 6/12 (50%) to publish. 9+ = high viral probability.

## Execution Steps

1. **Topic Selection** — Choose topic with inherent emotional charge
2. **STEPPS Audit** — Score the raw topic. If < 4/12, reframe or abandon
3. **Hook Design** — 5+ hook variants (Filipe, see hook-write skill)
4. **Script Structure** — Hook → Bridge → Body → CTA (Joana)
5. **Platform Adaptation** — Native formatting per platform
6. **STEPPS Re-Audit** — Score the final piece. Must hit 6+/12.

## High-Arousal Emotions (share more)
Awe, excitement, humor, anger, anxiety

## Low-Arousal Emotions (share less)
Sadness, contentment, relaxation

## Output → Obsidian: `WizardingCode/Content/Viral/` with STEPPS scorecard
