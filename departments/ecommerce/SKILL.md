---
name: ecom
description: >
  E-commerce department. Store management, product optimization, pricing, launches.
  Integrates with Shopify MCP. Use when user says "ecom", "store", "product", "shop".
allowed-tools: Read, Grep, Glob, Bash, WebFetch, Write
---

# E-commerce Department — ARKA OS

Store management, product optimization, and e-commerce growth.

## Commands

| Command | Description |
|---------|-------------|
| `/ecom audit <url>` | Full store audit (5 agents) |
| `/ecom product <description>` | Create optimized product listing |
| `/ecom pricing <product>` | Pricing strategy analysis |
| `/ecom launch <store>` | New store launch plan |
| `/ecom ads <product>` | E-commerce ad campaigns |
| `/ecom competitors <url>` | Competitive e-commerce analysis |
| `/ecom seo <url>` | E-commerce SEO audit |
| `/ecom email <type>` | E-commerce email flows (cart, post-purchase, win-back) |
| `/ecom report <store>` | Store performance report |

## Obsidian Output

All e-commerce output goes to the Obsidian vault at `/Users/andreagroferreira/Documents/Personal/`:

| Content Type | Vault Path |
|-------------|-----------|
| Store audits | `WizardingCode/Ecommerce/Audits/<date> <store>.md` |
| Product analyses | `WizardingCode/Ecommerce/Products/<name>.md` |
| Competitor research | `WizardingCode/Ecommerce/Competitors/<date> <name>.md` |
| Launch plans | `WizardingCode/Ecommerce/Launches/<store>.md` |
| Performance reports | `WizardingCode/Ecommerce/Reports/<date> <store>.md` |

**Obsidian format:**
```markdown
---
type: report
department: ecommerce
title: "<title>"
date_created: <YYYY-MM-DD>
tags:
  - "report"
  - "ecommerce"
  - "<specific-tag>"
---
```

All files use wikilinks `[[]]` for cross-references and kebab-case tags.

## Workflows

### /ecom audit <url>

**Step 1: Fetch Store Data**
- Use WebFetch to crawl the store URL
- Capture homepage, key product pages, cart, checkout flow

**Step 2: Run 5 Parallel Audit Agents**

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

**Step 3: Synthesize Results**
- Combine all 5 agent reports
- Prioritize findings by impact (high/medium/low)
- Create actionable recommendations with estimated effort

**Step 4: Save to Obsidian**

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

**Step 5: Report**
```
═══ ARKA ECOM — Store Audit Complete ═══
Store:       <store>
URL:         <url>
Issues:      <count> (High: X, Medium: Y, Low: Z)
Top action:  <highest impact recommendation>
Obsidian:    WizardingCode/Ecommerce/Audits/<date> <store>.md
═════════════════════════════════════════
```

### /ecom product <description>

**Step 1: Research**
- Understand the product from the description
- If URL provided, use WebFetch to analyze the current listing
- If Shopify MCP available, pull existing product data

**Step 2: Optimize Product Listing**
- Title: SEO-optimized, keyword-rich, clear benefit
- Description: Problem → Solution → Benefits → Features → CTA
- Bullet points: Feature → Benefit format
- SEO tags: Primary keyword, long-tail variants, related terms
- Meta description: 155 chars, keyword-included, click-worthy

**Step 3: Generate Variants**
- 3 title options (SEO vs. emotional vs. benefit-led)
- Short description (50 words) and long description (200+ words)
- Suggested collections/categories
- Cross-sell and upsell suggestions

**Step 4: Save to Obsidian**

**File:** `WizardingCode/Ecommerce/Products/<name>.md`
```markdown
---
type: product
department: ecommerce
title: "<product name>"
date_created: <YYYY-MM-DD>
tags:
  - "product"
  - "ecommerce"
---

# <product name>

## Optimized Listing
### Title Options
1. [SEO-focused]
2. [Emotion-focused]
3. [Benefit-focused]

### Description
[Optimized product description]

### Bullet Points
- [Feature → Benefit]

### SEO
- Primary keyword: [keyword]
- Tags: [list]
- Meta description: [155 chars]

### Upsell/Cross-sell
- [Suggestions]

---
*Part of the [[WizardingCode MOC]]*
```

**Step 5: Apply via Shopify MCP**
- If Shopify MCP is available and user confirms, push the optimized listing directly

### /ecom pricing <product>

**Step 1: Gather Product Data**
- Current price (if exists)
- Cost of goods / margin
- Product category and positioning

**Step 2: Competitor Analysis**
- Use WebFetch to research 3-5 competitor prices for similar products
- Map price range: budget → mid-range → premium

**Step 3: Pricing Strategy**
- Calculate margin at different price points
- Apply psychological pricing (charm pricing, anchoring, decoy)
- Consider bundling opportunities
- Evaluate penetration vs. skimming strategy

**Step 4: Generate Recommendation**

**File:** `WizardingCode/Ecommerce/Products/<product>-pricing.md`
```markdown
---
type: pricing-analysis
department: ecommerce
title: "<product> — Pricing Strategy"
date_created: <YYYY-MM-DD>
tags:
  - "pricing"
  - "ecommerce"
---

# <product> — Pricing Strategy

## Competitor Landscape
| Competitor | Product | Price | Positioning |
|-----------|---------|-------|-------------|
| [name] | [product] | [price] | [budget/mid/premium] |

## Margin Analysis
| Price Point | Margin | Margin % | Notes |
|------------|--------|----------|-------|
| [price] | [margin] | [%] | [note] |

## Recommendation
- **Recommended price:** [price]
- **Strategy:** [penetration/skimming/competitive]
- **Rationale:** [why this price wins]

## Psychological Pricing
- [Techniques to apply]

## Bundle Opportunities
- [Bundle suggestions with margin impact]

---
*Part of the [[WizardingCode MOC]]*
```

## MCP Integration

Uses Shopify MCP when available for:
- Product management (get-products, get-collections)
- Order management (get-orders, get-order)
- Customer management (get-customers, tag-customer)
- Discount creation (create-discount)
- Store info (get-shop-details)

---
*All output: `WizardingCode/Ecommerce/` — Part of the [[WizardingCode MOC]]*
