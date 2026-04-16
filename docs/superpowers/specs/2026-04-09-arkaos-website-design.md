# ArkaOS Website — Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Owner:** Andre Groferreira / WizardingCode
**Scope:** Marketing site + Documentation hub + Community + Blog

---

## 1. Overview

The official ArkaOS website: a high-performance Nuxt 4 site that serves as the primary touchpoint for the ArkaOS product. Combines a marketing site with scroll storytelling, comprehensive documentation auto-generated from the ArkaOS source, a community hub, and a blog.

**Design principles:**
- Terminal-first hero with live demo feel (Cursor)
- Scroll storytelling with fluid animations (Linear)
- Clean docs with DX-first navigation (Vercel)
- Technical depth with inline code examples (Stripe)
- ArkaOS Dark Cockpit brand identity throughout

**Target audience:** Universal — developers, founders/CTOs, agencies. Messaging adapts per persona.

**Not in scope (future):** Pricing page, dashboard/auth, Pro plans.

---

## 2. Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | Nuxt 4 (SSG + SSR hybrid) |
| UI Library | Nuxt UI v4 (dark cockpit theme, color `arka`) |
| Content | `@nuxt/content` v3 with MDC (Vue components in markdown) |
| i18n | `@nuxtjs/i18n` (EN default + PT, prefix strategy) |
| SEO | `@nuxtjs/seo` (sitemap, robots, og-image, schema.org) |
| Fonts | `@nuxt/fonts` (Inter + JetBrains Mono) |
| Icons | `@iconify-json/lucide` + `@iconify-json/simple-icons` |
| Images | `@nuxt/image` v2 |
| Analytics | `nuxt-plausible` (privacy-first) |
| Deploy | Cloudflare Pages (SSG prerender) |
| Package Manager | pnpm |

**Starter kit:** `https://github.com/nuxt-ui-templates/landing.git`

**Brand identity** (from `arkaos-brand` project):
- Primary color: `arka` (#00FF88 scale, defined with `@theme static`)
- Neutral: `zinc`
- Dark mode only (forced via `colorMode.preference: 'dark'`)
- Fonts: Inter (sans) + JetBrains Mono (mono)
- Logo: "The Levitation" deconstructed A with floating crossbar
- Animations: `fade-in-up`, `glow-pulse`, `float`

---

## 3. Layouts

### Marketing Layout (clean, no sidebar)
- Header: logo + nav links (Features, Departments, Docs, Blog, Community) + CTA button + locale switcher
- Full-width content area
- Footer: links grid, newsletter signup, social links, legal

### Docs Layout (sidebar + TOC)
- Header: same as marketing but with docs-specific nav
- Left sidebar: auto-generated navigation tree from `@nuxt/content` directory structure
- Main content: markdown rendered with MDC components
- Right sidebar: table of contents (on-page headings)
- Prev/Next navigation between pages
- "Edit on GitHub" link per page

---

## 4. Page Structure

### Marketing Pages

| Route | Content |
|-------|---------|
| `/` | Homepage — terminal hero + 9-section scroll storytelling |
| `/features` | Detailed features with inline code examples |
| `/departments` | Interactive grid of 17 departments with expand/detail |
| `/agents` | Catalog of 65 agents with behavioral DNA profiles |
| `/blog` | Articles listing — tutorials, case studies, changelogs |
| `/blog/:slug` | Individual article |
| `/changelog` | Release notes |
| `/community` | Discord, GitHub, contributors, newsletter |
| `/about` | WizardingCode, mission, team |

### Documentation Pages

| Route | Content |
|-------|---------|
| `/docs` | Getting started — install in 60 seconds |
| `/docs/concepts` | Architecture, Synapse, workflows, constitution |
| `/docs/departments/:dept` | Per department: agents, commands, workflows (auto-generated) |
| `/docs/agents/:agent` | Agent detail: DNA, role, capabilities (auto-generated) |
| `/docs/skills/:skill` | Skill reference: commands, usage (auto-generated) |
| `/docs/api` | Core API reference (Python) |
| `/docs/runtimes` | Claude Code, Codex, Gemini, Cursor setup |
| `/docs/guides/*` | How-to guides |

---

## 5. Homepage — Scroll Storytelling

9 sections with scroll-triggered animations:

| # | Section | Content | Animation |
|---|---------|---------|-----------|
| 1 | **Hero** | Animated terminal: `npx arkaos install` then `/do` routing demo | Typing effect, line-by-line output |
| 2 | **Problem** | "You're running a business, not just writing code" — fragmented tools | Fade-in on scroll |
| 3 | **Solution** | "One OS. 17 departments." — system overview visual | Scale-up reveal |
| 4 | **How it works** | 3 steps: Install, Command, Deliver — with code snippets | Step-by-step on scroll |
| 5 | **Departments** | Interactive grid of 17 departments — hover shows agents & commands | Staggered grid entrance |
| 6 | **4-Layer Diff** | Comparison table: ArkaOS vs ChatGPT vs Cursor vs Devin | Slide-in columns |
| 7 | **Numbers** | 65 agents, 244+ skills, 542 tests, 17 depts, open source | Counter animation |
| 8 | **Community** | Discord widget, GitHub stars, newsletter form | Fade-in |
| 9 | **Final CTA** | "Ready? One command." — terminal + Get Started / Star on GitHub | Glow pulse |

Animations use brand identity keyframes (`fade-in-up`, `glow-pulse`, `float`) combined with `IntersectionObserver` scroll triggers.

---

## 6. Documentation Content Structure

```
content/docs/
  1.getting-started/
    1.installation.md
    2.quick-start.md
    3.configuration.md
    4.runtimes.md
  2.concepts/
    1.architecture.md
    2.synapse.md
    3.workflows.md
    4.squads.md
    5.constitution.md
    6.behavioral-dna.md
  3.departments/
    [auto-generated from departments/*/agents/*.yaml — 17 pages]
  4.agents/
    [auto-generated from departments/*/agents/*.yaml — 65 pages]
  5.skills/
    [auto-generated from ~/.claude/skills/arka-*/SKILL.md]
  6.guides/
    create-agent.md
    create-skill.md
    create-workflow.md
    ecosystem-setup.md
    contributing.md
  7.api/
    core.md
    cli.md
    hooks.md
```

**Auto-generation:** A Node.js build-time script converts ArkaOS source YAML/MD into content markdown:
- `departments/*/agents/*.yaml` to `content/docs/4.agents/*.md`
- `departments/` structure to `content/docs/3.departments/*.md`
- `~/.claude/skills/arka-*/SKILL.md` to `content/docs/5.skills/*.md`

**Doc features:**
- Auto-generated sidebar from directory structure
- Table of contents (right sidebar)
- Code blocks with syntax highlighting + copy button
- MDC components: `::callout`, `::code-group`, `::terminal`
- Full-text search via `@nuxt/content` built-in
- Prev/Next page navigation
- "Edit on GitHub" link per page

---

## 7. SEO / GEO / AEO Strategy

| Pillar | Implementation |
|--------|---------------|
| Technical SEO | `@nuxtjs/seo` (auto sitemap, robots.txt, canonical URLs), SSG prerender, semantic HTML, JSON-LD structured data |
| On-page SEO | Meta titles/descriptions per page, auto-generated OG images with `nuxt-og-image`, heading hierarchy H1-H6 |
| GEO (Generative Engine) | Schema.org (`SoftwareApplication`, `FAQPage`, `HowTo`), direct answers in docs, content optimized for LLM extraction |
| AEO (Answer Engine) | FAQ sections with schema markup, "What is ArkaOS?" snippets, clear definitions at top of each doc page |
| i18n SEO | `hreflang` tags EN/PT, URL prefix strategy (`/pt/docs/...`), sitemap per locale |
| Performance | Cloudflare Pages edge, `@nuxt/image` optimization, font subsetting, automatic code splitting |
| Social | Branded OG cards (dark cockpit + logo), Twitter cards, LinkedIn previews |

**AI-readiness:**
- `llms.txt` and `llms-full.txt` at site root for AI crawlers
- Each doc page starts with a 1-2 sentence definition (optimized for AI extraction)
- FAQ schema on key pages (homepage, features, getting started)
- Blog posts with `Article` + `author` structured data
- RSS feed at `/feed.xml`

---

## 8. Community & Blog

### Community Page (`/community`)
- Discord invite widget with live member count
- GitHub stats: stars, forks, contributors (fetched at build time via GitHub API)
- Newsletter signup form (provider: Resend, Loops, or Buttondown — TBD)
- "Built with ArkaOS" showcase gallery
- Contributors grid with GitHub avatars

### Blog (`/blog`)
- Powered by `@nuxt/content` v3 (markdown + MDC)
- Categories: Tutorials, Changelog, Case Studies, Announcements
- Tag system for cross-referencing
- Estimated reading time
- Auto-generated OG image per post
- RSS feed (`/feed.xml`)
- Author cards

---

## 9. i18n Strategy

- EN as default locale (no prefix)
- PT as secondary locale (prefix: `/pt/`)
- `@nuxtjs/i18n` with `prefix_except_default` strategy
- Translation files in `i18n/locales/en.json` and `i18n/locales/pt.json`
- Marketing UI strings via JSON locale files; doc content via separate `content/pt/docs/` directory (PT content written manually, not auto-translated)
- `hreflang` tags auto-generated
- Locale switcher in header

---

## 10. Project Path & Deployment

- **Project path:** `~/Work/arkaos-site`
- **Repository:** `andreagroferreira/arkaos-site` (GitHub)
- **Deploy:** Cloudflare Pages with automatic deploys from `main` branch
- **Domain:** TBD (arkaos.dev, arkaos.ai, or similar)
- **Preview:** Cloudflare Pages preview URLs per PR
