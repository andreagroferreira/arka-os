# arka-ecommerce — Audit Flow (5 Parallel Agents)

Referenced from SKILL.md. Read only when needed.

## /ecom audit <url>

### Step 1: Fetch Store Data
- Use WebFetch to crawl the store URL
- Capture homepage, key product pages, cart, checkout flow

### Step 2: Run 5 Parallel Audit Agents

Launch these agents simultaneously:

**Agent 1: UX Auditor**
- Navigation and information architecture
- Mobile responsiveness
- Page load perception
- Cart and checkout friction
- Search and filtering usability

**Agent 2: SEO Auditor**
- Title tags, meta descriptions, heading structure
- Product page SEO (schema markup, alt text, URLs)
- Internal linking and site structure
- Collection/category page optimization
- Technical SEO (canonical URLs, sitemap, robots.txt)

**Agent 3: Performance Auditor**
- Page load speed indicators
- Image optimization assessment
- Third-party script overhead
- Core Web Vitals estimation
- Mobile performance

**Agent 4: Content Auditor**
- Product descriptions (quality, length, persuasion)
- Product photography assessment
- Trust signals (reviews, badges, guarantees)
- Brand consistency across pages
- Copy effectiveness (headlines, CTAs)

**Agent 5: Conversion Auditor**
- Call-to-action clarity and placement
- Social proof visibility
- Urgency/scarcity elements
- Upsell and cross-sell opportunities
- Abandoned cart recovery signals
- Email capture strategy

### Step 3: Synthesize Results
- Combine all 5 agent reports
- Prioritize findings by impact (high/medium/low)
- Create actionable recommendations with estimated effort

### Step 4: Save to Obsidian

**File:** `WizardingCode/Ecommerce/Audits/<YYYY-MM-DD> <store>.md`
```markdown
---
type: audit
department: ecommerce
title: "<store> — E-commerce Audit"
url: "<url>"
date_created: <YYYY-MM-DD>
tags:
  - "audit"
  - "ecommerce"
---

# <store> — E-commerce Audit

## Executive Summary
[Top 3-5 findings and overall score]

## UX Analysis
[Agent 1 findings]

## SEO Analysis
[Agent 2 findings]

## Performance Analysis
[Agent 3 findings]

## Content Analysis
[Agent 4 findings]

## Conversion Analysis
[Agent 5 findings]

## Priority Actions
| # | Action | Impact | Effort | Category |
|---|--------|--------|--------|----------|
| 1 | [action] | High | [effort] | [category] |

---
*Part of the [[WizardingCode MOC]]*
```

### Step 5: Report
```
═══ ARKA ECOM — Store Audit Complete ═══
Store:       <store>
URL:         <url>
Issues:      <count> (High: X, Medium: Y, Low: Z)
Top action:  <highest impact recommendation>
Obsidian:    WizardingCode/Ecommerce/Audits/<date> <store>.md
═════════════════════════════════════════
```
