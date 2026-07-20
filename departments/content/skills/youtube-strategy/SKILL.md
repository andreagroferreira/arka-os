---
name: content/youtube-strategy
description: >
  Full YouTube channel strategy in 7 deliverables: channel positioning, 10
  title-thumbnail pairs, hook architecture, retention-mapped script
  structure, SEO metadata stack, 90-day publishing cadence, and
  cross-platform derivative spec. TRIGGER: "estratégia para o YouTube", "grow
  my YouTube channel", "lançar canal de YouTube", "YouTube SEO", "CTR e
  retenção", "/content youtube". SKIP: one video's packaging only ->
  content/thumbnail-package; one video's script only ->
  content/script-structure; Shorts-only content -> content/short-form
  (vertical short-form, not channel strategy).
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` (and
> `mcp__graphify__query_graph` when configured) and cite `[[wikilinks]]`
> or graph nodes — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# YouTube Strategy — `/content youtube <topic>`

> **Lead:** Rafael (Content Strategist) | **Cross-dept:** Isabel (Visual Designer) + Teresa (Copy) + Luna (Marketing) | **Frameworks:** MrBeast Title × Thumbnail Method + Algorithm-Aware Retention Design

## What ships

A production YouTube strategy in 7 deliverables:

1. **Channel positioning** with competing-channel analysis
2. **10 title × thumbnail pairs** with CTR patterns named
3. **Hook architecture** + retention curve plan per video
4. **Script structure** with retention drops mapped
5. **SEO metadata + playlist hierarchy**
6. **Publishing cadence** with view + subscriber targets
7. **Cross-platform derivative spec** (Shorts, threads, newsletter)

## The CTR-Retention Math (why packaging matters)

The YouTube algorithm rewards two metrics in tight loop:

- **CTR (click-through rate)** — % of impressions that click. Median is 4-6%; top performers 10-15%.
- **AVD (average view duration)** — minutes watched per view. Algorithm normalizes by video length but rewards higher absolute AVD.

CTR depends on **title × thumbnail × topic** working together. AVD depends on **hook + retention curve + payoff**. If CTR is high but AVD is low, the algorithm interprets the video as clickbait and demotes it. If CTR is low but AVD is high, the video starves of impressions.

Target floor: CTR ≥ 6%, AVD ≥ 40% of length, retention curve no sharp drops in first 30 seconds.

## Title × Thumbnail Patterns (CTR levers)

Each title × thumbnail pair uses one of these named patterns. Mixing patterns randomly produces noise; picking a primary pattern per channel produces compounding.

| Pattern | Title shape | Thumbnail shape | Use case |
|---|---|---|---|
| **Curiosity Gap** | "What happens when [unexpected]" | One element + question mark + face surprised | Investigation, experiment videos |
| **Transformation** | "From X to Y in Z time" | Before / After split | Tutorial, journey, case study |
| **Specific Claim** | "I [verb] [specific number] [specific subject]" | Numbers visible + product / outcome | Stunt, achievement, deep-dive |
| **Loss Aversion** | "Don't [common mistake]" | Red X + warning icon + face concerned | Warning, education |
| **Authority + Specific** | "How [expert title] [does specific thing]" | Person + tool / artifact + clean type | Expert content, behind-the-scenes |
| **Comparison** | "X vs Y: Which actually [outcome]" | Split with both items + clear winner cue | Review, head-to-head |
| **Contrarian** | "Why everyone is wrong about X" | Strikethrough on common belief + face defiant | Opinion, takedown, education |

Thumbnail design rules (visual hierarchy):
- **One focal point** — eye lands on a single element first
- **Face if relevant** — human face drives 30-40% CTR lift on most topics
- **Contrast** — high-saturation focal vs muted background
- **Type ≤ 4 words** — readable on mobile at 320px width
- **No clickbait that breaks promise** — title and thumbnail must accurately preview the payoff

## Hook Architecture (first 30 seconds)

The first 30 seconds determines whether the viewer stays. The hook structure that consistently retains:

```
0-3s   PATTERN INTERRUPT — visual + audio shock or unexpected statement
3-10s  PROMISE — name the transformation / outcome the viewer gets
10-20s STAKES — why this matters, what they'll lose by leaving
20-30s PREVIEW — quick montage of the 3 best moments coming up
```

Pattern interrupts that work: starting mid-action, a contradictory statement, an unexpected location, an unexpected visual element. Pattern interrupts that don't work: long intro animations, founder face talking to camera with no visual.

## Script Structure (full video)

Default structure for a 10-12 minute video (the optimal range for monetisation + retention):

```
0:00 - 0:30   Hook (see Hook Architecture)
0:30 - 2:00   Setup — name the problem, stakes, why now
2:00 - 4:00   Reframe — show the prevailing wrong answer + your alternative frame
4:00 - 8:00   Content blocks (2-3 blocks) — each with a mini-hook, a payoff, a transition
8:00 - 10:00  Payoff — the promised transformation / answer delivered concretely
10:00 - 11:00 Recap + CTA — quick recap + subscribe / next video / link in description
11:00 - 12:00 Outro + end screen — pattern-interrupt sting + related video CTA
```

Retention drops happen at predictable moments: 1:00 (initial commitment), 4:00 (mid-video boredom), 8:00 (sense of completion). Insert a mini-hook 10 seconds before each predicted drop to retain viewers through it.

## SEO Metadata Stack

For each video, fill the metadata stack:

```yaml
title:
  primary_keyword: "<2-3 word keyword>"
  full_title: "<title with keyword + pattern + emotional anchor>"
  variants_for_testing: 3-5 alternates

description:
  first_140_chars: "<keyword-loaded summary that appears in search>"
  full_description:
    - paragraph 1: hook + value prop (250 chars)
    - paragraph 2: timestamps with keyword variants
    - paragraph 3: links + CTAs
    - paragraph 4: hashtags (3-5 max, mixed broad + niche)
  pinned_comment: "<first comment author posts with related links>"

tags:
  primary: ["<broad topic>", "<specific topic>"]
  long_tail: ["<specific phrase>", "<question phrase>"]
  branded: ["<channel name>", "<series name>"]

end_screen:
  best_for_viewer: <related video by same channel>
  subscribe_cta: <button position>

playlists:
  series_playlist: <series name if applicable>
  topic_playlist: <topic cluster>
```

## Publishing Cadence Math

Sustainability beats burst. The cadence math:

- **Long-form video** anchor — 1 per week typical floor for growth channels, 1 per 2 weeks for high-production
- **Shorts derivatives** — 3-5 per long-form video, posted on rolling schedule
- **Community posts** — 2-3 per week to keep algorithm engagement signal
- **Live / Premiere** — optional monthly cadence for community deepening

First 90 days targets:
- Week 1-4: 4 long-forms, 16-20 shorts. Target: identify which pattern resonates.
- Week 5-8: Double down on winning pattern. Target: first video to 10k views.
- Week 9-12: Optimise + scale. Target: first 1000 subs OR 100k cumulative views, whichever ships first.

## Cross-Platform Derivatives (per long-form video)

Each long-form video should produce:
- **3-5 YouTube Shorts** (vertical, 30-60s, hook-led clips)
- **1 Twitter/X thread** (10-15 tweets summarising the video with embedded clips)
- **1 LinkedIn post** (professional framing for B2B audiences)
- **1 newsletter section** (long-form summary with personal context)
- **1 Podcast adaptation** (audio extraction if relevant)

Derivative production should be templated — derivatives are not new content, they are repackaging.

## Output → Obsidian: `WizardingCode/Content/YouTube/<topic>-<date>/`

Delivers: channel positioning + 10 title × thumbnail pairs + hook architecture + script structure for 3-5 videos + SEO metadata stack per video + 90-day cadence + cross-platform derivative spec + 1-page executive summary.
