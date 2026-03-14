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

## Knowledge Base Integration

When generating content, ALWAYS check:
1. Does a relevant persona exist in `knowledge/personas/`?
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

## Content Personas

Available personas for content creation:
- Check `knowledge/personas/` for learned personas
- Each persona brings frameworks, voice, and strategies
- Can blend multiple personas for unique content
