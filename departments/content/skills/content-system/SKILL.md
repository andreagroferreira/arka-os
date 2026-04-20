---
name: content/content-system
description: >
  Set up a Content Operating System: pillar content strategy, batching workflow,
  1-to-30+ repurposing pipeline, calendar, and analytics tracking.
allowed-tools: [Read, Write, Edit, Agent, WebFetch]
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

# Content Operating System — `/content system`

> **Agent:** Rafael (Content Strategist) + Nuno (Repurpose)
> **Framework:** GaryVee Pillar Model + Justin Welsh Content OS

## Content OS Architecture

```
PILLAR CONTENT (1x/week)
  Long-form: YouTube video, blog post, podcast episode, or newsletter
  ↓
ATOMIZE (Nuno's 1→30+ pipeline)
  ↓
├── 3-5 Short-form clips (TikTok, Reels, Shorts)
├── 5-10 Social posts (LinkedIn, X, Instagram)
├── 1-2 Newsletter sections
├── 3-5 Quote graphics
├── 1 Thread (X or LinkedIn)
├── 1 Carousel (Instagram, LinkedIn)
├── 3-5 Stories snippets
└── SEO blog post derivative
```

## Weekly Batching Workflow

| Day | Activity | Output |
|-----|----------|--------|
| Monday | Ideation + hook writing | 5 topic ideas with hooks scored |
| Tuesday | Pillar content creation | 1 long-form piece (video/blog/podcast) |
| Wednesday | Repurposing | 30+ platform-native pieces |
| Thursday | Scheduling + optimization | Content queued for the week |
| Friday | Analytics review + iteration | Performance report, next week adjustments |

## Content Calendar Template

```markdown
## Week of [date]

### Pillar: [Topic]
- Platform: YouTube / Blog / Podcast
- Hook: [selected hook]
- STEPPS score: X/12

### Derivatives:
- [ ] TikTok 1: [angle]
- [ ] TikTok 2: [angle]
- [ ] Reel 1: [angle]
- [ ] LinkedIn post: [angle]
- [ ] X thread: [angle]
- [ ] Newsletter section: [angle]
- [ ] Carousel: [angle]
- [ ] Quote graphics x3: [quotes]
```

## Metrics to Track

| Metric | Platform | Target |
|--------|----------|--------|
| Views/Impressions | All | Growing MoM |
| Engagement Rate | All | > 3% |
| Save/Bookmark Rate | Instagram, TikTok | > 2% |
| Shares | All | Growing (viral signal) |
| Follower Growth | All | Consistent weekly |
| CTR to link | Bio link, Stories | > 1% |
| Revenue attributed | All | Track via UTMs |

## Output → Obsidian: `WizardingCode/Content/System/CONTENT-OS-<project>.md`
