---
name: ecom/product-launch
description: >
  E-commerce product launch plan — positioning + pricing ladder + content
  assets + channel mix + ad creative + day-by-day launch sequence + post-
  launch optimisation triggers.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
> **KB-first:** query `mcp__obsidian__search_notes` and cite
> `[[wikilinks]]` — or declare the gap — BEFORE any external research.
> Full doctrine: `arka/SKILL.md` (KB-First Research).
<!-- arka:kb-first-prefix end -->

# Product Launch — `/ecom launch <product>`

> **Lead:** Ricardo (E-Commerce Director) | **Cross-dept:** Mateus (Brand) + Helena (CFO) + Luna (Marketing) + Pedro (Paid) + Isabel (Visual) + Eduardo (Copy) | **Framework:** GTM × Launch Sequence + Inventory-Aware Demand Curve

## What ships

A production launch package in 7 deliverables:

1. **Positioning** — competitive set + onlyness frame + price tier
2. **Pricing ladder** — anchor + main + promo + bundle with margin math per tier
3. **Content assets** — product page + photo brief + video brief + email + social copy
4. **Channel mix** — owned + marketplace + paid + organic + partnerships per priority
5. **Ad creative plan** — static + video + UGC + retargeting per channel
6. **Day-by-day launch sequence** — soft launch through post-launch optimisation
7. **Executive summary** — 1-page printable with sales target + kill-switch criterion

## Positioning Frame (e-commerce specific)

Position the SKU on three axes simultaneously:

1. **Competitive set** — name 3-5 directly competing SKUs across price tiers
2. **Differentiation angle** — what's the one thing this SKU does that the competitive set doesn't
3. **Price tier** — entry / mid / premium / luxury with explicit anchor comparison

Format:
```yaml
positioning:
  category: <product category>
  competitive_set: [<SKU 1>, <SKU 2>, <SKU 3>]
  onlyness: "The only <category> that <unique mechanism> for <customer> who want <outcome>"
  price_tier: entry | mid | premium | luxury
  anchor_competitor: <SKU we benchmark against>
  anchor_price: <competitor price>
  our_price: <price + delta vs anchor + rationale>
```

## Pricing Ladder

Every launch ships with a 4-tier pricing ladder, not a single price:

| Tier | Use | Margin floor | When to show |
|---|---|---|---|
| **Anchor** | Shown crossed-out to anchor perception | n/a (decorative) | First view |
| **Main** | Default offer | Gross margin ≥ category benchmark | Default state |
| **Promo** | Limited-time deal (launch week, holiday) | Gross margin ≥ 60% of main | Launch week + scarcity moments |
| **Bundle** | Multi-SKU or main + accessory | Combined margin ≥ main × 1.3 | Cart upsell |

Margin math must close at every tier. Promo prices that don't cover variable costs are not promos — they're losses.

## Content Asset Inventory

Required assets per launch:

```yaml
content_assets:
  product_page:
    - hero_image: 1
    - lifestyle_images: 3-5
    - detail_shots: 3-5
    - video: 15-30s
    - bullets: 5-7
    - long_description: 200-400 words
    - faq: 5-8 questions

  email:
    - launch_announcement: 1
    - reminder_24h_before: 1
    - launch_day: 1
    - day_3_social_proof: 1
    - day_7_last_chance: 1

  social:
    - announcement_post: 3-5 platforms × 1 format
    - launch_day_post: 3-5 platforms × 1 format
    - countdown_stories: 3-7 days

  ad_creative:
    - static_image: 5-10 variants
    - video_15s: 3-5 variants
    - video_30s: 2-3 variants
    - ugc_request_brief: 1
```

## Channel Mix Priority

Channel ramp follows a deliberate sequence. Day-0 is not "everywhere at once" — it's a controlled wedge.

| Priority | Day 0 | Week 1 | Month 1 | Why this order |
|---|---|---|---|---|
| 1 | Email list (warm) | Email + retargeting | Email + retargeting + organic | Warmest audience first, validates demand signal |
| 2 | Direct traffic + organic | Direct + organic + meta paid | Add marketplace listing | Earned reach before paid |
| 3 | Marketplace listing | Paid scale-up | TikTok / influencer | Paid only after CR validated |
| 4 | Influencer outreach | Influencer publishes | Affiliate program | Third-party signal once core demand proven |

Skipping the warm-audience-first step burns paid spend on uninformed buyers and produces unstable CR baselines.

## Day-by-Day Launch Sequence Template

```
T-30  Inventory commit + content brief signed off
T-21  Photo + video shoot
T-14  Product page in staging
T-7   Email warm-up (#1 sent — "something's coming")
T-3   Email reminder (#2 sent — date + sneak peek)
T-0   LAUNCH:
        06:00 — Product page live
        08:00 — Email blast to full list
        10:00 — Social announcement (all platforms)
        12:00 — First-hour analytics check (CR, AOV, traffic)
        14:00 — Retargeting ads live (only if signal positive)
        16:00 — Live-stream / Q&A if applicable
        20:00 — End-of-day metrics review + decision: continue ramp or pause
T+1   Day-2 email + paid ramp decision
T+3   Social proof email (real customer reactions)
T+7   "Last chance for launch pricing" email
T+8   Move to evergreen pricing
T+14  Post-launch retrospective + decision (scale / iterate / kill)
```

Each step has a named owner and a success criterion. The "decision: continue ramp or pause" gate at T+0 evening is the load-bearing one — preventing wasted paid spend on a dud.

## Inventory-Aware Demand Curve

Match channel ramp to inventory levels:

```yaml
inventory_demand_curve:
  units_in_stock: <N>
  base_sales_velocity: <units per day at baseline>
  launch_uplift_factor: 5-15x baseline typical
  days_of_stock_at_launch_velocity: <calculated>

  scenarios:
    sold_out_before_day_3:
      action: "Throttle paid spend immediately, switch promo to 'next batch' positioning"
      pre_emptive: "Set inventory alert at 30% stock; cap ad spend automatically"
    sold_out_between_day_3_and_day_7:
      action: "Pause paid Day 4, reactivate when restock confirmed"
      pre_emptive: "Pre-order option live by Day 3 if velocity > 2x projection"
    sells_through_below_projection:
      action: "Switch to discovery-mode messaging, increase retargeting frequency"
      pre_emptive: "Have 'discovery angle 2' copy variant pre-approved for fast swap"
```

Launches that ignore inventory produce either backorder customer-experience disasters or markdown-spiral losses.

## Kill-Switch Criteria (named upfront)

Every launch ships with explicit kill criteria — if any fires, stop spending paid budget:

- Day-0 CR < 50% of category benchmark
- Day-3 cumulative AOV < 80% of projected
- Day-7 return rate > 2× category baseline
- Day-7 negative-review-to-purchase ratio > category baseline

Kill-switch criteria stated upfront prevent the "let's just spend more to make it work" trap.

## Common Failure Modes

1. **Single-price launch** — no ladder, leaves margin on the table and removes promo lever
2. **Channel-everywhere day-0** — burns paid spend before CR signal is validated
3. **Inventory-blind ramp** — sells out at peak demand or markdowns at post-peak slump
4. **No kill-switch** — bad launches drag on consuming budget without falsification path
5. **Asset shortage** — running launch with incomplete photo/video set produces below-benchmark CR

## Output → Obsidian: `WizardingCode/Ecom/Launches/<product>-<date>/`

Delivers: positioning + pricing ladder (margin math per tier) + content asset inventory + channel mix priority + day-by-day launch sequence + ad creative plan + inventory-aware demand curve + kill-switch criteria + 1-page executive summary.
