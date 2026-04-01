---
name: ecom
description: >
  E-commerce department. Full store audits with 5 parallel agents (UX, SEO, performance,
  content, conversion), product listing optimization, pricing strategy analysis, store launch
  plans, e-commerce ad campaigns, competitor analysis, e-commerce SEO audits, automated email
  flows (cart abandonment, post-purchase, win-back), and store performance reports. Integrates
  with Shopify MCP for direct product/order/customer management. All output saved to Obsidian.
  Use when user says "ecom", "store", "product", "shop", "shopify", "ecommerce", "e-commerce",
  "sales", "conversion", "pricing", "catalog", "inventory", "cart", "checkout", "listing",
  or any online store task.
---

# E-commerce Department — ARKA OS

Store management, product optimization, and e-commerce growth.

## Universal Workflow (7-Phase — NON-NEGOTIABLE)

Every e-commerce command follows this workflow. No exceptions. No shortcuts.

### Phase 0: BRIEF (Ricardo)
- Clarify the request: store data, objective, current metrics, constraints
- Load store context via Shopify MCP or WebFetch
- Save brief to Obsidian: `WizardingCode/Ecommerce/Briefs/BRIEF-<slug>.md`
- **Gate:** Brief confirmed by user before proceeding

### Phase 1: CHALLENGE & RESEARCH (Tomas — Strategy + Helena — CFO)
- Tomas: market positioning, competitor analysis, strategic angle
- Helena: financial viability, margin impact, ROI projection
- Challenge assumptions: "Data shows X, are you sure about Y?"
- Research benchmarks and competitor pricing
- Present findings and alternatives to user
- **Gate:** User approves the approach

### Phase 2: PLANNING (Ricardo)
- Define strategy with supporting data
- Create TODO list with `TaskCreate` (one task per deliverable)
- For pricing: define 3 scenarios (conservative, realistic, aggressive)
- For products: define optimization priorities

### Phase 3: EXECUTION (Ricardo)
- Execute the approved plan
- Product optimization: copy, SEO, variants, attributes
- Pricing: competitor-informed, margin-validated
- Tasks executed ONE AT A TIME, each validated before the next

### Phase 4: SELF-CRITIQUE (Ricardo)
- Do the data support the recommendations?
- Are all product attributes correct for the category? (NO WiFi on shoes)
- Are margins positive in all scenarios?
- Does the copy follow human-writing standards?

### Phase 5: SUPERVISION (Helena — CFO)
- Financial impact review: margins, ROI, cash flow impact
- Data validation: are the numbers correct and consistent?
- **Gate:** Helena approves or sends back to Phase 3

### Phase 6: QUALITY GATE (Marta — CQO)
- Marta dispatches Eduardo (copy review) + Francisca (data/technical review)
- Eduardo: product copy quality, descriptions, email campaigns
- Francisca: data integrity (attributes match category), Shopify push validation, pricing consistency
- Marta aggregates verdict:
  - **APPROVED** → Proceed to Phase 7
  - **REJECTED** → Exact issue list, return to Phase 3
- **NO OUTPUT REACHES THE USER WITHOUT MARTA'S APPROVAL**

### Phase 7: DELIVERY (Ricardo)
- Apply via Shopify MCP (only if user approved push)
- Save to Obsidian: `WizardingCode/Ecommerce/<type>/`
- Report with before/after metrics where applicable
- Report what was delivered vs. what was in the brief

### Visibility (NON-NEGOTIABLE)
Every phase transition is announced to the user:
- "📋 Phase 0: Loading store context and creating brief..."
- "🔍 Phase 1: Tomas and Helena challenging the approach..."
- "💰 Phase 5: Helena reviewing financial impact..."
- "🔒 Phase 6: Quality Gate — Eduardo + Francisca reviewing..."
- "✅ Phase 6: APPROVED by Marta. Proceeding to delivery."

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

All e-commerce output goes to the Obsidian vault at `{{OBSIDIAN_VAULT}}`:

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
