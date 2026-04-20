---
name: mkt/seo-audit
description: >
  Full SEO audit covering technical SEO, on-page, content gaps, and link profile.
  Uses Pillar-Cluster model, E-E-A-T, and Core Web Vitals.
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

# SEO Audit — `/mkt seo audit <url>`

> **Agent:** Ana (SEO Specialist) | **Frameworks:** Pillar-Cluster, E-E-A-T, CWV

## Audit Sections

### 1. Technical SEO
- [ ] Core Web Vitals (LCP < 2.5s, INP < 200ms, CLS < 0.1)
- [ ] Mobile-first responsive
- [ ] XML sitemap present and submitted
- [ ] robots.txt correctly configured
- [ ] HTTPS everywhere (no mixed content)
- [ ] Canonical tags on all pages
- [ ] Structured data (Schema.org) on key pages
- [ ] No broken links (404s)
- [ ] Crawl budget efficient (no infinite pagination, no duplicate)

### 2. On-Page SEO
- [ ] Title tags: unique, under 60 chars, keyword in first half
- [ ] Meta descriptions: unique, under 160 chars, includes CTA
- [ ] H1: one per page, includes primary keyword
- [ ] H2-H6: logical hierarchy, includes secondary keywords
- [ ] Internal linking: 3-5 relevant internal links per page
- [ ] Image alt text: descriptive, includes keyword where natural
- [ ] URL structure: short, descriptive, kebab-case

### 3. Content Strategy
- [ ] Pillar pages identified for core topics
- [ ] Cluster content links back to pillar
- [ ] Content gaps: keywords competitors rank for but we don't
- [ ] Content freshness: key pages updated in last 6 months
- [ ] E-E-A-T: Experience, Expertise, Authoritativeness, Trustworthiness signals

### 4. Link Profile
- [ ] Domain authority/rating baseline
- [ ] Top referring domains quality
- [ ] Toxic backlink identification
- [ ] Link building opportunities (Skyscraper candidates)

## Output → Obsidian: `WizardingCode/Marketing/SEO/AUDIT-<domain>-<date>.md`
