# arka-fovory — integration

Referenced from SKILL.md. Read only when needed.

## Architecture

```
Suppliers (API + CSV)
    │
    ▼
fovory-supplier-sync (Laravel 13 + Vue 3)
    ├── Supplier Driver System (Foxway, Realtime, StockFirmati)
    ├── Product Normalizer (categories, colors, sizes)
    ├── Deduplicator (EAN-based)
    ├── AI Enrichment Pipeline (translations, SEO, GEO/AEO)
    ├── AI System (providers, agents, personas, triggers, budgets)
    ├── Bulk Import System (Excel, WebSocket progress)
    ├── Variant/Offer CRUD (cascade status, bulk generation)
    ├── E-commerce Settings (store config, branding, measurements)
    └── Shopify Pusher (GraphQL Bulk Operations)
           │
           ▼
    Fovory Shopify Store ──► Customers
           │
           ├── Marketing (Social, Ads, Email)
           ├── Analytics (GA4, Shopify, Meta Pixel)
           └── Operations (Stock sync, pricing, translations)
```

## Squad Roles (full matrix)

### Development Squad (fovory-supplier-sync)

| Role | Agent Type | Specialty |
|------|-----------|-----------|
| **Tech Lead** | `tech-lead` | Sprint planning, task breakdown, plan presentation, coordination |
| **Backend Developer** | `backend-dev` | Laravel 13, PHP 8.4, Actions pattern, Eloquent, Form Requests, Horizon |
| **Frontend Developer** | `frontend-dev` | Vue 3, Inertia.js 3, Nuxt UI 4, TypeScript, Tailwind CSS 4, TipTap, TanStack |
| **AI Specialist** | `research-analyst` | Laravel AI SDK, Claude/Anthropic, agents/personas/triggers, prompt engineering |
| **Security Engineer** | `security-eng` | OWASP, Sanctum, Fortify, import validation, API security |
| **QA Tester** | `qa-eng` | Pest 5 (1471 tests), Playwright E2E, factories, datasets |

### Operations & Marketing Squad (Shopify Store)

| Role | Agent Type | Specialty |
|------|-----------|-----------|
| **Operations Manager** | `coo` | Store operations, SOPs, daily tasks, automation |
| **E-Commerce Manager** | `ecom-director` | Store optimization, conversion, UX audits |
| **Product Manager** | `commerce-engineer` | Catalog management, CSV bulk ops, translations, stock |
| **Marketing Strategist** | `strategy-director` | Marketing strategy, campaign planning, market analysis |
| **Content Creator** | `content-marketer` | Social media posts, Reels scripts, blog articles |
| **Ads Specialist** | `paid-specialist` | Google Ads, Meta Ads, ad copy, creative strategy |
| **Email Marketing** | `content-marketer` | Email flows, campaigns, segmentation |
| **SEO Specialist** | `seo-specialist` | Product SEO, blog SEO, technical SEO |
| **Analytics Specialist** | `metrics-analyst` | GA4, Shopify analytics, conversion tracking |
| **Pricing Strategist** | `strategy-director` | Price optimization, competitor pricing, margins |

## Project Conventions (fovory-supplier-sync)

These are NON-NEGOTIABLE when doing code work:

| Convention | Rule |
|-----------|------|
| **Layout** | UDashboardPanel with #header/#body slots — never raw divs with max-w |
| **Forms** | UModal with fieldsets + legends + USeparator — never USlideover |
| **File uploads** | Drag & drop dropzone pattern — never native file inputs |
| **Build tool** | `bun run build` — never npm |
| **Lists/tables** | Always paginate — never load all records |
| **Testing** | Pest 5 for unit/feature + Playwright for E2E — both mandatory |
| **PHP formatting** | `vendor/bin/pint --dirty --format agent` after changes |
| **Business logic** | Action classes in app/Actions/ |
| **Validation** | Form Request classes |
| **Commits** | Conventional commits, no Co-Authored-By trailer |
| **Phases** | Execute one at a time, STOP and wait for user approval |
| **Spec-driven** | Full interactive spec with user before ANY code |
| **Browser QA** | Must verify in browser before claiming done |

## Tech Stack Reference

### fovory-supplier-sync
- **Backend**: PHP 8.4, Laravel 13, Inertia.js 3, Laravel Horizon, Laravel Reverb (WebSocket)
- **Frontend**: Vue 3.5, TypeScript, Tailwind CSS 4, Nuxt UI 4, TipTap 3, TanStack Table, Unovis charts
- **Database**: PostgreSQL, Redis, SQLite (dev)
- **AI**: Laravel AI SDK (`laravel/ai`), Claude/Anthropic providers, agents/personas/triggers
- **Import**: Maatwebsite Excel, WebSocket progress tracking
- **Auth**: Laravel Fortify, Laravel Pennant (feature flags)
- **Testing**: Pest 5, Playwright, Larastan, Rector, Pint
- **Build**: Bun, Vite

### Codebase Stats (2026-04-11)
- **45 models** — Products, Variants, Offers, Suppliers, AI (agents/personas/triggers/providers), Enrichment (jobs/batches), Imports, E-commerce Settings
- **74 actions** — Business logic layer
- **43 controllers** — HTTP layer
- **45 Vue pages** — Products, Brands, Categories, Segments, Collections, Attributes, AI, Imports, Settings, Auth
- **77 migrations** — Full schema
- **1471 tests** (4159 assertions) — Pest 5

### Key Modules
- **Supplier Driver System** — Plugin-based architecture (Foxway, RealtimeData, StockFirmati), DriverManager, config registry, dynamic forms
- **Product Management** — CRUD, variants, offers, images (drag & drop), translations (multi-locale)
- **AI System** — Providers (OpenRouter, Anthropic, OpenAI), agents (Copywriter, Translator, AttributeMapper), personas, triggers, budgets, competitive analysis
- **AI Enrichment Pipeline** — Auto-enrich entities with translations, SEO metadata, GEO/AEO content; 4-phase pipeline with smart skip, graceful degradation, WebSocket progress tracking
- **Import System** — Excel bulk import, template download, WebSocket progress, row-level error reporting
- **E-commerce Settings** — General info, branding (logo, favicon, OG image with dropzone), measurements (weight/dimension units)

## Shopify Integration

### Via Shopify MCP (`shopify-dev`)
- Product CRUD (create, read, update, delete)
- Order management
- Customer data
- Inventory/stock management
- Collection management
- Discount/promotion management

### CSV Bulk Operations
For millions of products, use CSV workflows:
1. Export current catalog from Shopify
2. Process CSV with transformations (pricing, translations, stock)
3. Import updated CSV back to Shopify
4. Verify changes

### Supported Operations
- **Bulk price updates** (margin calculations, competitor matching, min 35% margin)
- **Bulk translations** (pt, en, fr, de — via AI agents)
- **Stock management** (threshold alerts, reorder recommendations, 5% buffer)
- **Category/tag optimization** (SEO-driven)
- **Image optimization** (alt texts, descriptions)
- **Meta descriptions** (SEO-optimized product descriptions)

## Marketing Channels

### Social Media
- **Instagram** — Posts, Reels, Stories sequences
- **TikTok** — Short-form video scripts
- **LinkedIn** — Professional brand content
- **X/Twitter** — Engagement posts
- **Pinterest** — Product pins, lookbooks

### Advertising
- **Google Ads** — Search, Shopping, Display campaigns
- **Meta Ads** — Facebook/Instagram ads
- **Google Shopping** — Product feed optimization

### Email Marketing
- **Welcome sequences** — Onboarding new customers
- **Cart abandonment** — Recovery flows
- **Post-purchase** — Upsell, review requests
- **Win-back** — Re-engagement campaigns
- **Newsletter** — Regular content

## Analytics & Tracking

| Platform | Purpose |
|----------|---------|
| Google Analytics 4 | Traffic, conversions, behavior |
| Google Ads | Ad performance, ROAS |
| Shopify Analytics | Revenue, orders, products |
| Meta Pixel | Facebook/Instagram conversion tracking |
| Google Search Console | Organic search performance |

## Knowledge Base Integration

Fovory feeds from and contributes to the global knowledge base:
- **Personas**: Use learned personas (from `/kb learn`) for authentic content voice
- **Market research**: Feed competitor analysis back into KB
- **Content patterns**: Learn from successful content for future generation
- **Price intelligence**: Store pricing data for strategic decisions

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/Fovory/`

```
Projects/Fovory/
├── Home.md                    — Ecosystem overview
├── Architecture/              — System architecture, data flow
├── Strategy/                  — Pricing, market, competition
├── Marketing/                 — Content calendars, campaigns, ads
│   ├── Social/               — Social media content
│   ├── Email/                — Email campaigns
│   └── Ads/                  — Ad campaigns and creatives
├── Operations/               — SOPs, product management logs
├── Analytics/                — Performance reports
└── Decisions/                — Architecture Decision Records
```
