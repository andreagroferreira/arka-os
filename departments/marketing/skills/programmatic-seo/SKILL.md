---
name: mkt/programmatic-seo
description: >
  Build SEO-optimized pages at scale using templates and data.
  12 playbooks: Templates, Curation, Conversions, Comparisons, Examples,
  Locations, Personas, Integrations, Glossary, Translations, Directory, Profiles.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# Programmatic SEO — `/mkt programmatic-seo <niche>`

> **Agent:** Luna (Marketing Lead) | **Frameworks:** Programmatic SEO, Topic Clusters, E-E-A-T

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
5. **Internal linking** — hub-and-spoke model, breadcrumbs, no orphan pages
6. **Indexation strategy** — prioritize high-volume, noindex thin variations, separate sitemaps
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