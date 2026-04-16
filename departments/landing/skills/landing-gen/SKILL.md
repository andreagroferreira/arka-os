---
name: landing/landing-gen
description: >
  Generate high-converting landing pages as complete TSX components.
  Hero, features, pricing, FAQ, testimonials, CTA sections with
  proven copy frameworks (PAS, AIDA, BAB) and SEO optimization.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Landing Page Generator — `/landing gen <product>`

> **Agent:** Ines (Landing Lead) | **Frameworks:** AIDA, PAS, Grand Slam Offer, Core Web Vitals

## Input

| Field | Required | Example |
|-------|----------|---------|
| Product | yes | "TaskFlow" |
| Tagline | yes | "Ship faster. Break less." |
| Target audience | yes | "Engineering teams at startups" |
| Key pain point | yes | "Manual deployments waste hours" |
| Key benefit | yes | "Zero-config instant rollbacks" |
| Pricing tiers | yes | "Free / Pro $29 / Enterprise" |
| Design style | no | dark-saas, clean-minimal, bold-startup, enterprise |
| Copy framework | no | PAS, AIDA, BAB |

## Design Styles

| Style | Background | Accent | CTA Button |
|-------|-----------|--------|------------|
| Dark SaaS | `bg-gray-950 text-white` | violet-500 | `bg-violet-600 hover:bg-violet-500` |
| Clean Minimal | `bg-white text-gray-900` | blue-600 | `bg-blue-600 hover:bg-blue-700` |
| Bold Startup | `bg-white text-gray-900` | orange-500 | `bg-orange-500 hover:bg-orange-600` |
| Enterprise | `bg-slate-50 text-slate-900` | slate-700 | `bg-slate-900 hover:bg-slate-800` |

## Copy Frameworks

| Framework | H1 | Subheadline | CTA |
|-----------|----|----|-----|
| **PAS** | Painful state they are in | What happens if they do not fix it | What you offer |
| **AIDA** | Bold attention-grabbing statement | Interesting fact or benefit | Clear action |
| **BAB** | "[Before] to [After]" | "Here is how [product] bridges the gap" | Try it now |

## Generation Workflow

1. Gather inputs (ask only for missing fields)
2. Select design style (infer from brand voice if not specified)
3. Apply copy framework to all headline and body copy
4. Generate sections in order: Hero > Features > Pricing > FAQ > Testimonials > CTA > Footer
5. Validate against SEO checklist
6. Output complete TSX + Tailwind components

## Section Inventory

| Section | Variants | Key Pattern |
|---------|----------|-------------|
| Hero | centered, split, gradient, video-bg, minimal | Badge + H1 + subhead + 2 CTAs |
| Features | grid, alternating, icon cards | Map over features array |
| Pricing | 2-4 tiers with toggle | Highlighted plan with ring + border |
| FAQ | accordion with schema | FAQPage JSON-LD + shadcn Accordion |
| Testimonials | grid, carousel, single-quote | Avatar + name + role + quote |
| CTA | banner, full-page, inline | Headline + subhead + trust signals |
| Footer | simple, mega, minimal | Logo + nav columns + social + legal |

## SEO Checklist

- [ ] `<title>`: primary keyword + brand (50-60 chars)
- [ ] Meta description: benefit + CTA (150-160 chars)
- [ ] OG image: 1200x630px with product name
- [ ] H1: one per page, includes primary keyword
- [ ] Structured data: FAQPage, Product, or Organization
- [ ] Canonical URL set
- [ ] Image alt text on all `<Image>` components
- [ ] Core Web Vitals: LCP < 1s, CLS < 0.1, FID < 100ms

## Performance Targets

| Metric | Target | Technique |
|--------|--------|-----------|
| LCP | < 1s | Preload hero image, `priority` on Next/Image |
| CLS | < 0.1 | Explicit width/height on all images |
| FID/INP | < 100ms | Defer non-critical JS, `loading="lazy"` |
| TTFB | < 200ms | ISR or static generation |
| Bundle | < 100KB JS | Audit with `@next/bundle-analyzer` |

## Common Pitfalls

| Problem | Fix |
|---------|-----|
| Hero image not preloaded | Add `priority` prop to first `<Image>` |
| No mobile CTA above fold | Ensure button visible without scrolling on 375px |
| Vague CTA copy | "Start free trial" beats "Learn more" |
| Missing trust signals near pricing | Add guarantee + testimonials near CTA |
| No FAQ schema markup | Inject FAQPage JSON-LD via `dangerouslySetInnerHTML` |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- No mobile responsive design → flag 60%+ traffic loss
- CTA below the fold → flag conversion rate risk
- No loading speed optimization → flag Core Web Vitals penalty

## Output

```markdown
## Landing Page — [Product Name]
**Style:** [style] | **Framework:** [copy framework]
**Sections:** [list of generated sections]
### Files: components/hero.tsx, features.tsx, pricing.tsx, faq.tsx, cta.tsx, footer.tsx, app/page.tsx, app/layout.tsx
### SEO Checklist: [validated items]
```
