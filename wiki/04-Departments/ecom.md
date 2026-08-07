# E-Commerce

← [Departments index](README.md) · [Home](../Home.md)

> **Prefix:** `/ecom` · **Lead:** Ricardo (Tier 1) · **Agents:** 4 · **Skills:** 15

The E-Commerce department owns the full commercial lifecycle of a store: from store audit and product page conversion to checkout engineering, RFM lifecycle management, and marketplace operations. Ricardo coordinates all four agents under a single revenue objective — every decision is anchored to CAC, LTV, AOV, and ROAS before any opinion enters the room.

The department operates within a matrix structure: Alice (CRO Specialist) is shared with the Landing Pages department, allowing conversion work to draw on both e-commerce data and funnel copywriting context without duplicating the role.

## Command surface

| Commands | Skills | Agents |
| --- | --- | --- |
| 18 | 15 | 4 |

**Commands** (18 via `/ecom`):

| Command | What it does |
| --- | --- |
| `/ecom ads <product>` | E-commerce ad campaigns |
| `/ecom analytics` | E-commerce analytics dashboard |
| `/ecom audit` | Full store audit (UX, SEO, performance, content, conversion) |
| `/ecom cart-recovery` | Cart abandonment email sequence |
| `/ecom competitors <url>` | Competitive e-commerce analysis |
| `/ecom cro <page>` | CRO optimization with ResearchXL |
| `/ecom email <type>` | Email flows (cart, post-purchase, win-back) |
| `/ecom fulfillment` | Fulfillment strategy (3PL, dropship, FBA) |
| `/ecom journey <segment>` | Customer journey mapping |
| `/ecom launch <product>` | Product launch plan |
| `/ecom marketplace <action>` | Marketplace operations (Mirakl, multi-vendor) |
| `/ecom pricing <product>` | Pricing strategy (value-based, dynamic, psychological) |
| ... | 6 more — full list in [docs/COMMANDS.md](../../docs/COMMANDS.md) |

**Skills** (15 — 14 sub-skills plus the `/ecom` hub):

| Skill | What it does |
| --- | --- |
| `analytics` | E-commerce metrics analysis — AOV, conversion rate, CLV, ROAS, and cart abandonment — delivered as a dashbo... |
| `browse-competitor` | Navigates a competitor's e-commerce site with browser integration and extracts structured intelligence — pr... |
| `cart-recovery` | Designs a cart abandonment recovery email sequence — 3 emails at 1h, 24h, and 72h with urgency escalation —... |
| `cro-optimize` | Conversion Rate Optimization using CXL's ResearchXL framework — 6 research phases (heuristic, technical, an... |
| `customer-journey` | Maps the e-commerce customer journey across discovery, consideration, purchase, delivery, and loyalty stage... |
| `ecom-hub` | E-Commerce department. Store optimization, CRO, RFM segmentation, pricing, marketplace operations, fulfillm... |
| `ecommerce` | E-commerce department orchestrator (Ricardo's squad, 7-phase workflow with mandatory Quality Gate) routing... |
| `fulfillment-plan` | Fulfillment strategy design — compares 3PL, FBA, and dropshipping models, plans logistics, returns handling... |
| `marketplace-manage` | Marketplace operations (Marketplace Flywheel + Mirakl framework) — seller onboarding, commission model desi... |
| `pricing-strategy` | E-commerce pricing strategy — value-based analysis, psychological pricing, dynamic pricing, and competitor... |
| `product-launch` | End-to-end e-commerce product launch package — positioning frame, 4-tier pricing ladder with margin math, c... |
| `rfm-segment` | RFM customer segmentation (Recency, Frequency, Monetary — Drew Sanocki): scores customers 1-5 per dimension... |
| `social-commerce` | Social commerce strategy (TikTok Shop + Instagram Shopping) — platform selection, product feed setup, and l... |
| `store-audit` | Full store audit with 5 parallel agents — UX, SEO, performance, content, and conversion — including live br... |
| `subscription-model` | Designs commerce subscription models (Subscription Economy — Tien Tzuo) — replenishment, curation, access,... |

## The squad

| Agent | Role | Tier |
|---|---|---|
| Ricardo | E-Commerce Director | 1 |
| Alice | CRO Specialist (shared with Landing Pages) | 2 |
| David | Commerce Engineer | 2 |
| Catarina | Lifecycle & Retention Manager | 2 |

## Frameworks

- **ResearchXL (Peep Laja / CXL)** — evidence-based CRO methodology: heuristic analysis, technical audit, digital analytics, mouse tracking, qualitative surveys, user testing
- **RFM Segmentation (Sanocki)** — Recency / Frequency / Monetary scoring to drive lifecycle and re-engagement campaigns
- **Baymard UX Guidelines** — checkout and product page UX standards backed by large-scale usability research
- **MACH Architecture** — Microservices, API-first, Cloud-native, Headless; guides technical commerce stack decisions
- **Marketplace Flywheel (Bezos)** — selection drives traffic drives sellers drives selection; applied to marketplace strategy
- **E-Commerce Metrics Stack** — CAC / LTV / AOV / ROAS as the shared decision language across all squad work
- **Lifecycle Flywheel** — onboarding → repeat purchase → winback sequences; Catarina applies this across email and SMS flows
- **PIE/ICE Prioritization** — used by Alice to rank A/B test candidates before committing engineering time

## What you can ask for

- "Run a full conversion audit on this product page" — `/ecom store-audit`
- "Design an RFM segmentation model for this customer list" — `/ecom rfm-segment`
- "Build a cart abandonment email sequence" — `/ecom cart-recovery`
- "Set up a subscription model for this product" — `/ecom subscription-model`
- "Analyze this marketplace and design an expansion strategy" — `/ecom marketplace-manage`
- "Create a social commerce strategy for Instagram and TikTok Shop" — `/ecom social-commerce`
- "Optimize checkout flow and reduce drop-off" — `/ecom cro-optimize`
- "Build a fulfillment and logistics plan" — `/ecom fulfillment-plan`
- "Audit competitor stores and surface opportunities" — `/ecom browse-competitor`
- "Model a pricing strategy for this product line" — `/ecom pricing-strategy`

## When to use it

Route to E-Commerce when the work involves a physical or digital store: conversion rate work, Shopify development, email/SMS lifecycle flows, marketplace operations, pricing, or any request that starts from a product SKU and ends at revenue. For pure landing page copy or affiliate funnels with no store component, prefer `/landing`.

---

Related: [Core Concepts](../02-Core-Concepts.md) · [The Evidence Flow (4 Gates)](../03-The-13-Phase-Flow.md) · [Quality Gate](../10-Quality-Gate.md)
