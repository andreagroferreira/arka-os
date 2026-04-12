# arka-rothbard100 — squad

Referenced from SKILL.md. Read only when needed.

## Architecture

```
Visitors --> rothbard100-landing (Nuxt 4, SSG via Nitro)
                   |
                   +-- @nuxtjs/i18n (5 locales: pt default, en, fr, es, de)
                   +-- @nuxt/image v2 (optimized images)
                   +-- @nuxt/ui v4.5.1 (component library)
                   +-- Iconify (lucide + simple-icons)
                   +-- Supabase (registration form submissions)
                   +-- Google Tag Manager + Microsoft Clarity (analytics)
                   +-- JSON-LD structured data + llms.txt (SEO/GEO/AEO)
                   +-- Cloudflare Pages (hosting, auto-deploy from main)
```

## Squad Roles (Full)

When processing any `/rothbard100` request, assign work to the appropriate squad members:

| Role | Agent Type | Specialty |
|------|-----------|-----------|
| **Project Manager** | `tech-lead` | Sprint planning, task breakdown, plan presentation |
| **Frontend Developer** | `frontend-dev` | Nuxt 4, Vue 3, TypeScript, Tailwind CSS 4, Nuxt UI 4, animations |
| **Content Creator** | `content-marketer` | Copy, messaging, event storytelling, persuasive writing |
| **SEO/Marketing** | `cro-specialist` | Landing page optimization, conversion, meta tags, performance |
| **Security Engineer** | `security-eng` | XSS, CSP, form validation, data protection |
| **QA Tester** | `qa-eng` | Vitest, Playwright, responsive testing, performance audits |
| **DevOps** | `devops-eng` | Cloudflare Pages deployment, CI/CD, CDN, domain setup |

## Key Architectural Notes

- **Single page app**: `app/pages/index.vue` composed by 17 section components
- **i18n-driven copy**: All text in `i18n/locales/*.json` — never in components
- **i18n strategy**: `prefix_except_default` (pt has no URL prefix)
- **Pre-rendered routes**: `/`, `/en`, `/fr`, `/es`, `/de`
- **Speaker/sponsor data**: Lives in component `<script setup>` arrays
- **Composables**: useCountdown, useScrollAnimate, useStructuredData, useSupabase
- **Plugins**: gtm.client.ts (Google Tag Manager), clarity.client.ts (Microsoft Clarity)
- **Public SEO files**: llms.txt, llms-full.txt, robots.txt, sitemap.xml
- **Backend**: Supabase for registration form submissions only. No auth.

## Components

| Component | Section |
|-----------|---------|
| AppHeader | Navigation + language switcher + scroll spy |
| LandingHero | Hero + countdown timer (27 Jun 2026) |
| LandingAbout | About Murray Rothbard |
| LandingAudience | Target audience |
| LandingHighlights | Event highlights |
| LandingBooks | Rothbard bibliography |
| LandingBookLaunch | Book launch section |
| LandingSchedule | Program/agenda |
| LandingSpeakers | Speaker cards |
| LandingTickets | Registration dialog + donation tiers |
| LandingVideos | Video content |
| LandingLocation | Venue / event location |
| LandingObjections | Objections/FAQ |
| LandingFaq | FAQ accordion |
| LandingSponsors | Organizers + supporters logos |
| LandingCta | Final call-to-action |
| AppFooter | Footer |

## Tech Stack Reference

### rothbard100-landing
- Nuxt 4.4.2, Vue 3, TypeScript (strict), Tailwind CSS 4, Nuxt UI v4.5.1
- @nuxtjs/i18n — 5 locales (pt default, en, fr, es, de)
- @nuxt/image v2
- @nuxt/eslint (Code quality)
- @supabase/supabase-js (registration form)
- Iconify: @iconify-json/lucide + @iconify-json/simple-icons
- Analytics: Google Tag Manager + Microsoft Clarity
- SEO: JSON-LD structured data (Event, VideoObject, Organization, BreadcrumbList), OG image, llms.txt (GEO/AEO)
- Package manager: pnpm
- Build: SSG (Static Site Generation) via Nitro prerender
- Hosting: Cloudflare Pages (auto-deploy from main branch)
- ESLint: Stylistic config (commaDangle: never, braceStyle: 1tbs)

### Key Conventions
- TypeScript strict mode
- Composition API (`<script setup lang="ts">`)
- Light mode only (forced via colorMode)
- Font: Inter (400–900)
- CSS classes: `section-light`, `section-divider`, `scroll-animate`, `btn-gold`, `pulse-gold`
- i18n strategy: `prefix_except_default`
- Performance-first (target Lighthouse 95+)

## Obsidian Output

All documentation: `/Users/andreagroferreira/Documents/Personal/Projects/Rothbard100/`

Structure:
```
Projects/Rothbard100/
├── Home.md                    ← Ecosystem overview
├── Landing Page.md            ← Landing page project docs
├── Architecture/
│   ├── System Architecture.md ← Architecture documentation
│   └── Brand Guide.md         ← Brand colors, typography, style
├── Content/
│   ├── Copy Guide.md          ← Event messaging and copy standards
│   └── Speaker Bios.md        ← Speaker information
├── Squad/
│   └── Workflows.md           ← Squad workflows and processes
└── Decisions/                 ← Architecture Decision Records
```
