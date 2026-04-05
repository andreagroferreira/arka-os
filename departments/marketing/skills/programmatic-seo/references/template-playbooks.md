# Programmatic SEO Template Playbooks — Deep Reference

> Companion to `programmatic-seo/SKILL.md`. 12 playbooks with URL structures, schema markup, and internal linking strategies.

## Playbook Index

| # | Playbook | Keyword Pattern | Pages Potential | Difficulty |
|---|----------|----------------|:---------------:|:----------:|
| 1 | Location Pages | `[service] in [city]` | 100-10K | Low |
| 2 | Comparison Pages | `[X] vs [Y]` | 50-500 | Medium |
| 3 | Alternative Pages | `[product] alternatives` | 20-200 | Medium |
| 4 | Tool/Calculator Pages | `[type] calculator` | 10-100 | Low |
| 5 | Glossary Pages | `what is [term]` | 100-1K | Low |
| 6 | Statistics Pages | `[industry] statistics` | 20-200 | Medium |
| 7 | Template Pages | `[type] template` | 50-500 | Low |
| 8 | Directory Pages | `best [category] tools` | 20-200 | High |
| 9 | Integration Pages | `[A] + [B] integration` | 50-500 | Low |
| 10 | Persona Pages | `[product] for [audience]` | 20-200 | Medium |
| 11 | Examples/Gallery Pages | `[type] examples` | 50-500 | Low |
| 12 | Profile Pages | `[entity] [attribute]` | 100-10K | Medium |

---

## 1. Location Pages

**Pattern:** `[service] in [city/state/country]`
**Example:** "dentists in austin", "coworking spaces in lisbon"

| Element | Specification |
|---------|--------------|
| URL | `/[service]/[city-slug]/` |
| Title | `Best [Service] in [City] - [Year] Guide \| [Brand]` |
| H1 | `[Service] in [City]` |
| Unique content | Local data, pricing, reviews, neighborhood info |
| Schema | `LocalBusiness`, `Service`, `AggregateRating` |
| Internal links | Parent city hub, nearby cities, related services |

**Data sources:** Google Business API, Yelp, government records, own data.
**Thin content risk:** High. Must add unique local insights per page, not just city name swaps.

## 2. Comparison Pages

**Pattern:** `[X] vs [Y]`
**Example:** "webflow vs wordpress", "notion vs confluence"

| Element | Specification |
|---------|--------------|
| URL | `/compare/[x]-vs-[y]/` |
| Title | `[X] vs [Y]: Honest Comparison ([Year]) \| [Brand]` |
| H1 | `[X] vs [Y]` |
| Unique content | Feature matrix, pricing table, use case recommendations |
| Schema | `FAQPage`, `Table` |
| Internal links | Individual product pages, related comparisons, category hub |

**Content structure:**
1. Quick verdict (above fold)
2. Side-by-side feature comparison table
3. Pricing comparison
4. Best for [use case A] vs best for [use case B]
5. FAQ section

**Linking strategy:** Create a comparison hub (`/compare/`) linking all pairs. Link bidirectionally: X-vs-Y and Y-vs-X redirect to canonical.

## 3. Alternative Pages

**Pattern:** `[product] alternatives`
**Example:** "mailchimp alternatives", "figma alternatives"

| Element | Specification |
|---------|--------------|
| URL | `/alternatives/[product-slug]/` |
| Title | `Top [N] [Product] Alternatives ([Year]) \| [Brand]` |
| H1 | `Best [Product] Alternatives` |
| Unique content | Why switch, ranked alternatives with pros/cons, migration tips |
| Schema | `ItemList`, `FAQPage` |
| Internal links | Comparison pages for each alternative pair, product reviews |

**Ranking criteria to include:** Price, feature overlap, migration difficulty, best for [use case].

## 4. Tool/Calculator Pages

**Pattern:** `[type] calculator`, `[unit] converter`
**Example:** "mortgage calculator", "px to rem converter"

| Element | Specification |
|---------|--------------|
| URL | `/tools/[tool-slug]/` |
| Title | `Free [Type] Calculator \| [Brand]` |
| H1 | `[Type] Calculator` |
| Unique content | Interactive tool, formula explanation, related examples |
| Schema | `WebApplication`, `FAQPage` |
| Internal links | Related tools, glossary terms, guides using this calculation |

**Key success factors:** Tool must work without JavaScript for basic Googlebot rendering. Include text content below the tool for crawlability.

## 5. Glossary Pages

**Pattern:** `what is [term]`, `[term] definition`
**Example:** "what is pSEO", "what is ARR"

| Element | Specification |
|---------|--------------|
| URL | `/glossary/[term-slug]/` |
| Title | `What is [Term]? Definition & Examples \| [Brand]` |
| H1 | `What is [Term]?` |
| Unique content | Clear definition, examples, related terms, visual aids |
| Schema | `DefinedTerm`, `FAQPage` |
| Internal links | Related glossary terms, in-depth guides, parent topic hub |

**Content template:**
1. One-sentence definition (target featured snippet)
2. Expanded explanation (2-3 paragraphs)
3. Real-world examples
4. Common misconceptions
5. Related terms (linked)

## 6. Statistics Pages

**Pattern:** `[industry/topic] statistics [year]`
**Example:** "saas churn statistics 2025", "remote work statistics"

| Element | Specification |
|---------|--------------|
| URL | `/statistics/[topic-slug]/` |
| Title | `[N]+ [Topic] Statistics ([Year]) \| [Brand]` |
| H1 | `[Topic] Statistics for [Year]` |
| Unique content | Curated statistics with sources, charts, trend analysis |
| Schema | `Article`, `Dataset` |
| Internal links | Related statistics pages, guides citing these stats, glossary |

**Defensibility:** High if you aggregate and visualize. Update annually for evergreen traffic. Always cite primary sources.

## 7. Template Pages

**Pattern:** `[type] template`, `[type] example`
**Example:** "business plan template", "invoice template"

| Element | Specification |
|---------|--------------|
| URL | `/templates/[type-slug]/` |
| Title | `Free [Type] Template ([Year]) - Download Now \| [Brand]` |
| H1 | `[Type] Template` |
| Unique content | Preview, download, customization guide, use cases |
| Schema | `CreativeWork`, `HowTo` |
| Internal links | Related templates, guides on the topic, tool pages |

**Conversion strategy:** Free preview, email gate for download, premium templates for paid users.

## 8. Directory/Listicle Pages

**Pattern:** `best [category] tools`, `top [N] [category]`
**Example:** "best project management tools", "top 10 CRM software"

| Element | Specification |
|---------|--------------|
| URL | `/best/[category-slug]/` |
| Title | `[N] Best [Category] Tools ([Year]) \| [Brand]` |
| H1 | `Best [Category] Tools` |
| Unique content | Ranked list with scoring criteria, screenshots, pricing |
| Schema | `ItemList`, `Review`, `FAQPage` |
| Internal links | Individual reviews, comparison pages, alternative pages |

**Scoring framework:** Define clear criteria (features, pricing, ease of use, support). Show scores transparently.

## 9. Integration Pages

**Pattern:** `[A] + [B] integration`, `connect [A] to [B]`
**Example:** "slack asana integration", "zapier hubspot"

| Element | Specification |
|---------|--------------|
| URL | `/integrations/[a-slug]-[b-slug]/` |
| Title | `[A] + [B] Integration: How to Connect \| [Brand]` |
| H1 | `Connect [A] to [B]` |
| Unique content | Setup steps, use cases, limitations, alternatives |
| Schema | `HowTo`, `SoftwareApplication` |
| Internal links | Both product pages, related integrations, comparison pages |

**Scale strategy:** If you have N integrations, you can generate N*(N-1)/2 combination pages. Only create pages with verified search volume.

## 10. Persona Pages

**Pattern:** `[product] for [audience]`
**Example:** "crm for real estate", "accounting software for freelancers"

| Element | Specification |
|---------|--------------|
| URL | `/for/[audience-slug]/` |
| Title | `[Product] for [Audience]: Features & Pricing \| [Brand]` |
| H1 | `[Product] for [Audience]` |
| Unique content | Audience-specific features, testimonials, use cases, pricing |
| Schema | `Product`, `FAQPage` |
| Internal links | Main product page, related persona pages, case studies |

**Content differentiation:** Each persona page must highlight different features, different testimonials, and different use cases. Not just audience name swaps.

## 11. Examples/Gallery Pages

**Pattern:** `[type] examples`, `[type] inspiration`
**Example:** "landing page examples", "portfolio website examples"

| Element | Specification |
|---------|--------------|
| URL | `/examples/[type-slug]/` |
| Title | `[N] [Type] Examples for Inspiration ([Year]) \| [Brand]` |
| H1 | `[Type] Examples` |
| Unique content | Curated examples with screenshots, analysis, what works and why |
| Schema | `ItemList`, `ImageObject` |
| Internal links | Template pages, related examples, how-to guides |

**Image optimization:** Compress screenshots, use descriptive alt text, implement lazy loading. Images are the content here.

## 12. Profile/Entity Pages

**Pattern:** `[entity name] [attribute]`
**Example:** "stripe ceo", "shopify revenue", "notion pricing"

| Element | Specification |
|---------|--------------|
| URL | `/companies/[entity-slug]/` or `/people/[entity-slug]/` |
| Title | `[Entity]: [Key Attribute] & Overview \| [Brand]` |
| H1 | `[Entity]` |
| Unique content | Structured data about the entity, timeline, key facts |
| Schema | `Organization`, `Person`, `Article` |
| Internal links | Related entities, industry pages, comparison pages |

**Data defensibility:** Strongest when using proprietary data. Public data pages compete with Wikipedia and Crunchbase.

---

## Universal Internal Linking Strategy

### Hub-and-Spoke Model

```
                    [Category Hub]
                   /    |    |    \
            [Page A] [Page B] [Page C] [Page D]
              |         |         |         |
           [Sub A1]  [Sub B1]  [Sub C1]  [Sub D1]
```

### Cross-Linking Rules

| Rule | Implementation |
|------|---------------|
| Every page links to its parent hub | Breadcrumb + in-content link |
| Hub links to all children | Paginated list or directory |
| Siblings link to each other | "Related" section (3-5 links) |
| Cross-type linking | Glossary term links to comparison, comparison links to alternatives |
| No orphan pages | Every page reachable within 3 clicks from homepage |

## Universal Schema Markup Checklist

- [ ] `BreadcrumbList` on every page (navigation path)
- [ ] Primary schema type matching page intent (see per-playbook above)
- [ ] `FAQPage` where genuine questions are answered
- [ ] `Organization` on the homepage
- [ ] `SiteNavigationElement` in header/footer
- [ ] Test with Google Rich Results Test before launch
- [ ] Monitor Search Console for schema errors weekly

## Indexation Strategy for Scale

| Page Count | Strategy |
|------------|---------|
| < 100 pages | Index all, single sitemap |
| 100-1K pages | Index all with quality threshold, segmented sitemaps |
| 1K-10K pages | noindex thin pages (<300 words), priority in sitemap |
| 10K+ pages | Aggressive quality gating, separate sitemap per type, crawl budget management |

### Sitemap Segmentation

```xml
sitemap-index.xml
  sitemap-locations.xml      (location pages)
  sitemap-comparisons.xml    (comparison pages)
  sitemap-glossary.xml       (glossary pages)
  sitemap-tools.xml          (tool/calculator pages)
```

### Quality Gate Before Indexing

| Check | Threshold | Action if Below |
|-------|-----------|----------------|
| Word count | > 300 words | noindex or add content |
| Unique content ratio | > 60% unique vs template | noindex or rewrite |
| Search volume for target keyword | > 10/month | noindex or consolidate |
| Internal links pointing to page | >= 2 | Add links or orphan alert |
