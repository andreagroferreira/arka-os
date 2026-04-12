# arka-ecommerce — Playbooks (Product, Pricing, RFM, Marketplace)

Referenced from SKILL.md. Read only when needed.

## /ecom product <description>

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

## /ecom pricing <product>

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

## RFM Segmentation

Recency, Frequency, Monetary analysis. Identify Champions, Loyal Customers, At-Risk, Hibernating, Lost. Map segments to lifecycle email flows and win-back offers.

## Marketplace Operations

Seller onboarding, commission models, quality control, dispute resolution, catalog governance, listing quality scores, marketplace-specific SEO (Amazon A9, eBay Cassini).

## MCP Integration

Shopify MCP when available:
- Product management (get-products, get-collections)
- Order management (get-orders, get-order)
- Customer management (get-customers, tag-customer)
- Discount creation (create-discount)
- Store info (get-shop-details)
