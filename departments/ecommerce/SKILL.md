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

## MCP Integration

Uses Shopify MCP when available for:
- Product management (get-products, get-collections)
- Order management (get-orders, get-order)
- Customer management (get-customers, tag-customer)
- Discount creation (create-discount)
- Store info (get-shop-details)

---
*All output: `WizardingCode/Ecommerce/` — Part of the [[WizardingCode MOC]]*
