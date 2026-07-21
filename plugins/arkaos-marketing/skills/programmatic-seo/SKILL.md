---
name: programmatic-seo
description: >
  Builds SEO-optimized pages at scale from templates plus data, using 12
  playbooks (templates, comparisons, locations, personas, integrations,
  glossary, directories, more) with demand validation, data-defensibility
  tiers, and indexation strategy. TRIGGER: "programmatic SEO", "pSEO",
  "páginas SEO em escala", "gera páginas por template", "uma página por
  cidade/keyword", "/mkt programmatic-seo <niche>". SKIP: auditing an
  existing site's SEO health -> mkt/seo-audit (diagnosis, not page
  generation); hand-written editorial content plan -> mkt/calendar-plan.
metadata:
  origin: community
  source: https://github.com/coreyhaines31/marketingskills
  license: MIT
---

# Programmatic SEO

> **Agent:** Luna (Marketing Lead) | **Frameworks:** Programmatic SEO, Topic Clusters, E-E-A-T

**Context:** read the product marketing context first —
`WizardingCode/Marketing/product-marketing.md` in Obsidian (KB-first),
else the project-local `.agents/product-marketing.md`.

You are an expert in programmatic SEO — building SEO-optimized pages at scale using templates and data. The goal is to create pages that rank, provide value, and avoid thin-content penalties.

## Initial Assessment

Before designing a programmatic SEO strategy, understand:

1. **Business Context**
   - What's the product/service?
   - Who is the target audience?
   - What's the conversion goal for these pages?

2. **Opportunity Assessment**
   - What search patterns exist?
   - How many potential pages?
   - What's the search volume distribution?

3. **Competitive Landscape**
   - Who ranks for these terms now?
   - What do their pages look like?
   - Can you realistically compete?

## Core Principles

### 1. Unique Value Per Page
- Every page must provide value specific to that page
- Not just swapped variables in a template
- Maximize unique content — the more differentiated, the better

### 2. Proprietary Data Wins
Proprietary data is the strongest defensibility tier (full hierarchy below in Data Defensibility Hierarchy).

### 3. Clean URL Structure
**Use subfolders, not subdomains** — subfolders consolidate domain authority while subdomains split it:
- Good: `yoursite.com/templates/resume/`
- Bad: `templates.yoursite.com/resume/`

### 4. Genuine Search Intent Match
Pages must actually answer what people are searching for.

### 5. Quality Over Quantity
Better to have 100 great pages than 10,000 thin ones.

### 6. Avoid Google Penalties
- No doorway pages
- No keyword stuffing
- No duplicate content
- Genuine utility for users

## The 12 Playbooks

| Playbook | Keyword Pattern | Example |
|----------|----------------|---------|
| Templates | "[type] template" | "resume template" |
| Curation | "best [category]" | "best website builders" |
| Conversions | "[X] to [Y]" | "$10 USD to GBP" |
| Comparisons | "[X] vs [Y]" | "webflow vs wordpress" |
| Examples | "[type] examples" | "landing page examples" |
| Locations | "[service] in [location]" | "dentists in austin" |
| Personas | "[product] for [audience]" | "crm for real estate" |
| Integrations | "[A] + [B] integration" | "slack asana integration" |
| Glossary | "what is [term]" | "what is pSEO" |
| Translations | Content in multiple languages | Localized pages |
| Directory | "[category] tools" | "ai copywriting tools" |
| Profiles | "[entity name]" | "stripe ceo" |

## Playbook Selection

| If You Have... | Use Playbook |
|----------------|--------------|
| Proprietary data | Directories, Profiles |
| Product with integrations | Integrations |
| Design/creative product | Templates, Examples |
| Multi-segment audience | Personas |
| Local presence | Locations |
| Tool or utility product | Conversions |
| Content/expertise | Glossary, Curation |
| Competitor landscape | Comparisons |

You can layer multiple playbooks (e.g., "Best coworking spaces in San Diego" combines Curation + Locations).

## Data Defensibility Hierarchy

1. **Proprietary** — you created it (strongest)
2. **Product-derived** — from your users
3. **User-generated** — your community
4. **Licensed** — exclusive access
5. **Public** — anyone can use (weakest, thin-content risk)

## Implementation Steps

1. **Keyword pattern research** — identify repeating structure, variables, volume distribution
2. **Validate demand** — aggregate volume, head vs long-tail, trend direction
3. **Data source audit** — first-party, scraped, licensed, public? Update frequency?
4. **Template design** — unique intro per page, conditional content, original insights
5. **Internal linking** — hub-and-spoke model, breadcrumbs with structured data, no orphan pages
6. **Indexation strategy** — prioritize high-volume, noindex thin variations, manage crawl budget, separate sitemaps by page type
7. **Launch and monitor** — track indexation rate, rankings, traffic, conversions

## Template Page Structure

- [ ] Header with target keyword naturally placed
- [ ] Unique intro (not just variable-swapped boilerplate)
- [ ] Data-driven sections with conditional content
- [ ] Related pages / internal cross-links
- [ ] CTAs appropriate to search intent
- [ ] Schema markup (FAQ, Product, LocalBusiness as relevant)

## Pre-Launch Checklist

- [ ] Each page provides unique value beyond variable substitution
- [ ] Unique title tags and meta descriptions per page
- [ ] Proper heading hierarchy (H1 > H2 > H3)
- [ ] Schema markup implemented
- [ ] Pages connected to site architecture (no orphans)
- [ ] XML sitemap generated and submitted
- [ ] Core Web Vitals passing (LCP < 2.5s, CLS < 0.1)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Thin content (just swapping city names) | Add unique data/insights per page |
| Keyword cannibalization | One primary keyword per page, clear hierarchy |
| Over-generation (no search demand) | Validate volume before building |
| Poor data quality | Automate data freshness checks |
| Ignoring UX (pages for Google, not users) | Test with real users before scaling |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- <50 pages generated → flag insufficient scale for SEO impact
- No canonical tags → flag duplicate content penalty risk
- Thin content pages (<300 words) → flag quality penalty risk

## Post-Launch Monitoring

Track: Indexation rate, Rankings, Traffic, Engagement, Conversion

Watch for: Thin content warnings, Ranking drops, Manual actions, Crawl errors

## Output

```markdown
## Programmatic SEO Strategy — [Niche]
**Playbook:** [type] | **Keyword:** [pattern] | **Pages:** [N] | **Defensibility:** [tier]
### Opportunity: | Pattern | Est. Volume | Data Source | Difficulty |
### Template: URL /[hub]/[variable]/ | Title/meta [template] | Content [blocks]
### Pre-Launch Checklist: [items]
### Monitoring: | Metric | Tool | Threshold | Cadence |
```

## References

- [template-playbooks.md](references/template-playbooks.md) — 12 programmatic SEO playbooks with URL structures, schema markup, internal linking strategies, and indexation rules per page type
- [playbooks.md](references/playbooks.md) — detailed playbook implementation notes and worked patterns per page type

## Related ArkaOS skills

- **`mkt/seo-audit`** — auditing programmatic pages after launch
- **`mkt/schema-markup`** — adding structured data to templated pages
- **`mkt/competitor-analysis`** — comparison-page frameworks and competitor landscape
