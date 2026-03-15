---
name: mkt
description: >
  Marketing department. Social media content, affiliate marketing, email campaigns,
  ad copy, landing pages, content strategy. Uses knowledge base personas for style.
  Use when user says "mkt", "social", "content", "affiliate", "ads", "email", "post".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# Marketing Department — ARKA OS

Content creation, social media management, affiliate marketing, and advertising.

## Commands

| Command | Description |
|---------|-------------|
| `/mkt social <topic>` | Generate social media posts (multi-platform) |
| `/mkt calendar <period>` | Content calendar (week/month) |
| `/mkt reels <topic>` | Scripts for Reels/TikTok/Shorts |
| `/mkt stories <topic>` | Instagram/Facebook stories sequence |
| `/mkt email <type> <topic>` | Email sequence (welcome, nurture, launch, cart) |
| `/mkt landing <product>` | Landing page copy (can use KB personas) |
| `/mkt ads <product>` | Ad copy for multiple platforms |
| `/mkt affiliate <product-url>` | Affiliate marketing analysis + content |
| `/mkt blog <topic>` | SEO-optimized blog article |
| `/mkt copy <url>` | Analyze and improve existing copy |
| `/mkt brand <url>` | Brand voice analysis and guidelines |
| `/mkt audit <url>` | Full marketing audit (5 parallel agents) |

## Obsidian Output

All marketing output goes to the Obsidian vault at `/Users/andreagroferreira/Documents/Personal/`:

| Content Type | Vault Path |
|-------------|-----------|
| Social calendars | `WizardingCode/Marketing/Calendars/<date> <title>.md` |
| Campaign plans | `WizardingCode/Marketing/Campaigns/<name>.md` |
| Audit reports | `WizardingCode/Marketing/Audits/<date> <target>.md` |
| Brand guidelines | `WizardingCode/Marketing/Brand/<name>.md` |
| Ad copy | `WizardingCode/Marketing/Ads/<date> <product>.md` |
| Blog drafts | `WizardingCode/Marketing/Blog/<title>.md` |

**Obsidian format:**
```markdown
---
type: report
department: marketing
title: "<title>"
date_created: <YYYY-MM-DD>
tags:
  - "report"
  - "marketing"
  - "<specific-tag>"
---
```

All files use wikilinks `[[]]` for cross-references and kebab-case tags.

## Knowledge Base Integration

When generating content, ALWAYS check:
1. Does a relevant persona exist in `Personas/` in the Obsidian vault?
2. If yes, use their frameworks and style as reference
3. If `--persona "Name"` is specified, adopt that persona's voice completely

Example:
```
/mkt landing "fitness course" --persona "Sabri Suby"
→ Uses Sabri's PHSO formula, his direct tone, his CTA patterns
```

## Affiliate Marketing

`/mkt affiliate <product-url>`:
1. Analyze the product (WebFetch the URL)
2. Identify target audience and pain points
3. Generate: review article, comparison post, email sequence, social posts
4. Optimize for affiliate conversion (not just traffic)
5. Include disclosure/compliance notes

## Workflows

### /mkt social <topic>

**Step 1: Persona Check**
- If `--persona "Name"` specified, read `Personas/<Name>.md` from Obsidian vault
- Adopt their voice, frameworks, and content patterns
- If no persona specified, use Luna's default style

**Step 2: Generate Platform-Specific Content**

Create separate, native content for each platform:

**Instagram:**
- Caption (hook + story + CTA, max 2200 chars)
- Hashtag set (10-15, mix of broad + niche)
- Visual direction (image/carousel/reel concept)
- Best posting time suggestion

**LinkedIn:**
- Text post (hook + insight + question, max 3000 chars)
- Professional framing of the topic
- Engagement question at the end

**X/Twitter:**
- Tweet (max 280 chars, punchy hook)
- Thread option (5-7 tweets for depth)
- Quote-tweet worthy standalone lines

**TikTok/Reels:**
- Script (hook in first 3 seconds, 30-60 sec total)
- Visual cues and transitions
- Trending audio suggestion (describe the vibe)

**Step 3: Save to Obsidian**

**File:** `WizardingCode/Marketing/Campaigns/<YYYY-MM-DD> <topic>.md`
```markdown
---
type: social-content
department: marketing
title: "<topic> — Social Content"
date_created: <YYYY-MM-DD>
persona: "<persona or Luna>"
tags:
  - "social-media"
  - "marketing"
  - "<topic-kebab-case>"
---

# <topic> — Social Content

## Instagram
[Content]

## LinkedIn
[Content]

## X/Twitter
[Content]

## TikTok/Reels
[Script]

## Scheduling Notes
[Best times and cadence]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 4: Report**
```
═══ ARKA MKT — Social Content Ready ═══
Topic:       <topic>
Platforms:   Instagram, LinkedIn, X, TikTok
Persona:     <persona or Luna>
Obsidian:    WizardingCode/Marketing/Campaigns/<date> <topic>.md
═════════════════════════════════════════
```

### /mkt audit <url>

**Step 1: Fetch Site Data**
- Use WebFetch to crawl the target URL
- Capture homepage, key pages, social links

**Step 2: Run 5 Parallel Audit Agents**

**Agent 1: SEO Auditor**
- On-page SEO (titles, metas, headings, alt text)
- Content quality and keyword targeting
- Technical SEO indicators
- Backlink profile assessment (if data available)

**Agent 2: Social Media Auditor**
- Platform presence and consistency
- Content quality and posting frequency
- Engagement patterns
- Community management

**Agent 3: Content Auditor**
- Blog/content quality and relevance
- Content gaps and opportunities
- Voice consistency
- Content-to-conversion alignment

**Agent 4: UX Auditor**
- Navigation clarity
- Mobile experience
- Load speed perception
- Call-to-action effectiveness
- Trust signals

**Agent 5: Funnel Auditor**
- Awareness → Interest → Desire → Action mapping
- Lead capture mechanisms
- Email marketing indicators
- Retargeting signals
- Conversion path clarity

**Step 3: Synthesize & Prioritize**
- Combine all 5 reports
- Score each area (1-10)
- Prioritize by impact and effort

**Step 4: Save to Obsidian**

**File:** `WizardingCode/Marketing/Audits/<YYYY-MM-DD> <target>.md`
```markdown
---
type: marketing-audit
department: marketing
title: "<target> — Marketing Audit"
url: "<url>"
date_created: <YYYY-MM-DD>
tags:
  - "audit"
  - "marketing"
---

# <target> — Marketing Audit

## Scorecard
| Area | Score | Priority |
|------|-------|----------|
| SEO | X/10 | [high/med/low] |
| Social | X/10 | [high/med/low] |
| Content | X/10 | [high/med/low] |
| UX | X/10 | [high/med/low] |
| Funnel | X/10 | [high/med/low] |

## SEO Analysis
[Agent 1 findings]

## Social Media Analysis
[Agent 2 findings]

## Content Analysis
[Agent 3 findings]

## UX Analysis
[Agent 4 findings]

## Funnel Analysis
[Agent 5 findings]

## Priority Actions
| # | Action | Impact | Effort |
|---|--------|--------|--------|
| 1 | [action] | High | [effort] |

---
*Part of the [[WizardingCode MOC]]*
```

### /mkt calendar <period>

**Step 1: Define Period**
- Determine scope: week or month
- Check for holidays, events, or launches in the period

**Step 2: Plan Content Themes**
- Identify 3-4 themes for the period
- Map themes to business goals
- Balance content types: educational, promotional, engagement, behind-the-scenes

**Step 3: Build Calendar**
- Assign content to specific days
- Define platform and format per post
- Set cadence per platform (e.g., Instagram 5x/week, LinkedIn 3x/week)

**Step 4: Save to Obsidian**

**File:** `WizardingCode/Marketing/Calendars/<YYYY-MM-DD> <period>.md`
```markdown
---
type: content-calendar
department: marketing
title: "Content Calendar — <period>"
date_created: <YYYY-MM-DD>
period: "<start> to <end>"
tags:
  - "calendar"
  - "marketing"
  - "content-strategy"
---

# Content Calendar — <period>

## Themes
1. **[Theme]** — [business goal it serves]
2. **[Theme]** — [business goal it serves]

## Platform Cadence
| Platform | Posts/Week | Best Days | Best Times |
|----------|-----------|-----------|-----------|
| Instagram | 5 | Mon-Fri | 9am, 6pm |
| LinkedIn | 3 | Tue, Thu, Sat | 8am |
| X | Daily | Every day | 12pm, 5pm |

## Calendar
### Week 1
| Day | Platform | Content | Type | Theme |
|-----|----------|---------|------|-------|
| Mon | Instagram | [content idea] | Reel | [theme] |
| Mon | LinkedIn | [content idea] | Post | [theme] |

### Week 2
[...]

## Content Production Notes
- [Batch creation suggestions]
- [Assets needed]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 5: Report**
```
═══ ARKA MKT — Calendar Ready ═══
Period:      <period>
Themes:      <count> themes
Posts:        <total count> across <platforms>
Obsidian:    WizardingCode/Marketing/Calendars/<date> <period>.md
═════════════════════════════════════
```

## Content Personas

Available personas for content creation:
- Check `Personas/` in the Obsidian vault for learned personas
- Each persona brings frameworks, voice, and strategies
- Can blend multiple personas for unique content

---
*All output: `WizardingCode/Marketing/` — Part of the [[WizardingCode MOC]]*
