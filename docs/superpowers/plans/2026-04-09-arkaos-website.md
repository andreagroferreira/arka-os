# ArkaOS Website Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the official ArkaOS website — marketing site with scroll storytelling, comprehensive auto-generated docs, community hub, and blog.

**Architecture:** Nuxt 4 with Nuxt UI v4 content-driven architecture. Marketing pages use a clean full-width layout; docs use a sidebar+TOC layout powered by `@nuxt/content` v3 with MDC. Documentation pages for departments, agents, and skills are auto-generated from ArkaOS source YAMLs at build time. i18n with EN (default) + PT.

**Tech Stack:** Nuxt 4, Nuxt UI v4, Tailwind CSS 4, @nuxt/content v3, @nuxtjs/i18n, @nuxtjs/seo, @nuxt/fonts, @nuxt/image, nuxt-plausible, Cloudflare Pages

**Spec:** `docs/superpowers/specs/2026-04-09-arkaos-website-design.md`

**Project path:** `~/Work/arkaos-site`

**ArkaOS source path:** `~/AIProjects/arka-os` (for auto-generation script)

---

## Task 1: Scaffold Project from Landing Template

**Files:**
- Clone: `https://github.com/nuxt-ui-templates/landing.git` → `~/Work/arkaos-site`
- Modify: `package.json`
- Modify: `nuxt.config.ts`
- Modify: `app/app.config.ts`
- Modify: `app/assets/css/main.css`
- Delete: `content/index.yml`, `content.config.ts`
- Delete: `app/components/TemplateMenu.vue`
- Delete: `public/images/`, `public/logos/`, `public/templates/`

- [ ] **Step 1: Clone template and reinitialize git**

```bash
cd ~/Work
git clone https://github.com/nuxt-ui-templates/landing.git arkaos-site
cd arkaos-site
rm -rf .git
git init
```

- [ ] **Step 2: Install dependencies**

```bash
pnpm install
```

- [ ] **Step 3: Add required modules**

```bash
pnpm add @nuxtjs/i18n @nuxtjs/seo @nuxt/fonts nuxt-plausible
pnpm add @iconify-json/lucide @iconify-json/simple-icons
```

- [ ] **Step 4: Update package.json name and metadata**

Update `package.json`:
```json
{
  "name": "arkaos-site",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node scripts/generate-docs.mjs && nuxt build",
    "dev": "nuxt dev",
    "generate": "node scripts/generate-docs.mjs && nuxt generate",
    "preview": "nuxt preview",
    "postinstall": "nuxt prepare",
    "lint": "eslint .",
    "typecheck": "nuxt typecheck",
    "generate-docs": "node scripts/generate-docs.mjs"
  }
}
```

- [ ] **Step 5: Configure nuxt.config.ts**

Replace `nuxt.config.ts` with:
```ts
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/image',
    '@nuxt/ui',
    '@nuxt/content',
    '@nuxt/fonts',
    '@nuxtjs/i18n',
    '@nuxtjs/seo',
    'nuxt-plausible'
  ],

  devtools: { enabled: true },

  css: ['~/assets/css/main.css'],

  compatibilityDate: '2025-01-15',

  colorMode: {
    preference: 'dark',
    fallback: 'dark'
  },

  ui: {
    theme: {
      colors: ['arka']
    }
  },

  fonts: {
    families: [
      { name: 'Inter', provider: 'google' },
      { name: 'JetBrains Mono', provider: 'google' }
    ]
  },

  i18n: {
    locales: [
      { code: 'en', language: 'en-US', name: 'English', file: 'en.json' },
      { code: 'pt', language: 'pt-PT', name: 'Portugues', file: 'pt.json' }
    ],
    defaultLocale: 'en',
    strategy: 'prefix_except_default',
    langDir: 'i18n/locales'
  },

  site: {
    url: 'https://arkaos.dev',
    name: 'ArkaOS',
    description: 'The Operating System for AI Agent Teams',
    defaultLocale: 'en'
  },

  plausible: {
    autoPageviews: true
  },

  content: {
    build: {
      markdown: {
        highlight: {
          noApiRoute: false,
          langs: ['bash', 'typescript', 'python', 'yaml', 'json', 'vue', 'css', 'php']
        }
      }
    }
  },

  nitro: {
    preset: 'cloudflare-pages',
    prerender: {
      crawlLinks: true,
      routes: ['/']
    }
  },

  image: {
    provider: 'none'
  },

  app: {
    head: {
      htmlAttrs: { class: 'dark' },
      meta: [{ name: 'theme-color', content: '#0A0A0A' }]
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  }
})
```

- [ ] **Step 6: Configure app.config.ts with ArkaOS brand**

Replace `app/app.config.ts`:
```ts
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'arka',
      neutral: 'zinc'
    }
  }
})
```

- [ ] **Step 7: Set up ArkaOS brand CSS**

Replace `app/assets/css/main.css`:
```css
@import "tailwindcss";
@import "@nuxt/ui";
@source "../../../content/**/*";

@theme static {
  --color-arka-50: #EDFFF5;
  --color-arka-100: #D0FFE6;
  --color-arka-200: #A3FFD0;
  --color-arka-300: #66FFB3;
  --color-arka-400: #00FF88;
  --color-arka-500: #00CC6A;
  --color-arka-600: #00A155;
  --color-arka-700: #007F45;
  --color-arka-800: #006538;
  --color-arka-900: #00532E;
  --color-arka-950: #002E19;

  --font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, 'Cascadia Code', monospace;

  --animate-fade-in-up: fade-in-up 0.6s ease-out both;
  --animate-glow-pulse: glow-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  --animate-float: float 6s ease-in-out infinite;
  --animate-typing: typing 3.5s steps(40, end);
  --animate-blink-caret: blink-caret 0.75s step-end infinite;
}

html {
  color-scheme: dark;
  scroll-behavior: smooth;
}

body {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--color-zinc-950); }
::-webkit-scrollbar-thumb { background: rgba(0, 255, 136, 0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0, 255, 136, 0.5); }
* { scrollbar-width: thin; scrollbar-color: rgba(0, 255, 136, 0.3) var(--color-zinc-950); }

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes glow-pulse {
  0%, 100% { filter: drop-shadow(0 0 20px rgba(0, 255, 136, 0.15)); }
  50% { filter: drop-shadow(0 0 40px rgba(0, 255, 136, 0.3)); }
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

@keyframes typing {
  from { width: 0; }
  to { width: 100%; }
}

@keyframes blink-caret {
  from, to { border-color: transparent; }
  50% { border-color: #00FF88; }
}

.scroll-animate {
  opacity: 0;
  transform: translateY(30px);
  transition: all 0.7s cubic-bezier(0.16, 1, 0.3, 1);
}
.scroll-animate.is-visible {
  opacity: 1;
  transform: translateY(0);
}

.glow-green {
  box-shadow: 0 0 8px rgba(0, 255, 136, 0.4), 0 0 24px rgba(0, 255, 136, 0.15);
}

.pattern-dot-grid {
  background-image: radial-gradient(circle, rgba(0, 255, 136, 0.12) 1px, transparent 1px);
  background-size: 24px 24px;
}
```

- [ ] **Step 8: Clean up template files**

```bash
rm -f content/index.yml content.config.ts
rm -f app/components/TemplateMenu.vue
rm -rf public/images public/logos public/templates
```

- [ ] **Step 9: Create directory structure**

```bash
mkdir -p app/layouts
mkdir -p app/pages/docs
mkdir -p app/pages/blog
mkdir -p app/components/home
mkdir -p app/components/docs
mkdir -p app/components/blog
mkdir -p app/composables
mkdir -p content/docs/1.getting-started
mkdir -p content/docs/2.concepts
mkdir -p content/docs/3.departments
mkdir -p content/docs/4.agents
mkdir -p content/docs/5.skills
mkdir -p content/docs/6.guides
mkdir -p content/docs/7.api
mkdir -p content/blog
mkdir -p i18n/locales
mkdir -p scripts
mkdir -p public/og
```

- [ ] **Step 10: Create i18n locale files (minimal)**

Create `i18n/locales/en.json`:
```json
{
  "nav": {
    "features": "Features",
    "departments": "Departments",
    "docs": "Documentation",
    "blog": "Blog",
    "community": "Community",
    "getStarted": "Get Started"
  },
  "hero": {
    "tagline": "Your AI Workforce",
    "headline": "One command. {count} specialists.",
    "description": "17 departments. From dev to finance, marketing to strategy. An operating system for AI agent teams.",
    "cta": "Get Started",
    "github": "Star on GitHub"
  },
  "footer": {
    "newsletter": "Stay updated",
    "newsletterPlaceholder": "Enter your email",
    "subscribe": "Subscribe",
    "product": "Product",
    "resources": "Resources",
    "company": "Company",
    "legal": "Legal",
    "copyright": "WizardingCode. All rights reserved."
  }
}
```

Create `i18n/locales/pt.json`:
```json
{
  "nav": {
    "features": "Funcionalidades",
    "departments": "Departamentos",
    "docs": "Documentacao",
    "blog": "Blog",
    "community": "Comunidade",
    "getStarted": "Comecar"
  },
  "hero": {
    "tagline": "A Tua Forca de Trabalho IA",
    "headline": "Um comando. {count} especialistas.",
    "description": "17 departamentos. De desenvolvimento a financas, marketing a estrategia. Um sistema operativo para equipas de agentes IA.",
    "cta": "Comecar",
    "github": "Star no GitHub"
  },
  "footer": {
    "newsletter": "Mantem-te atualizado",
    "newsletterPlaceholder": "O teu email",
    "subscribe": "Subscrever",
    "product": "Produto",
    "resources": "Recursos",
    "company": "Empresa",
    "legal": "Legal",
    "copyright": "WizardingCode. Todos os direitos reservados."
  }
}
```

- [ ] **Step 11: Verify dev server starts**

```bash
pnpm dev
```

Expected: Nuxt dev server starts on `http://localhost:3000` with dark theme and ArkaOS green color.

- [ ] **Step 12: Initial commit**

```bash
git add -A
git commit -m "feat: scaffold ArkaOS site from Nuxt UI landing template

- Nuxt 4 + Nuxt UI v4 + Tailwind CSS 4
- ArkaOS brand identity (arka green #00FF88, dark cockpit)
- Modules: content, i18n, seo, fonts, plausible
- EN + PT locale files
- Directory structure for pages, docs, blog, components"
```

---

## Task 2: Layouts and Core Components

**Files:**
- Create: `app/layouts/default.vue`
- Create: `app/layouts/docs.vue`
- Modify: `app/app.vue`
- Modify: `app/components/AppHeader.vue`
- Modify: `app/components/AppFooter.vue`
- Modify: `app/components/AppLogo.vue`
- Delete: `app/components/StarsBg.vue` (replaced later with custom hero)

- [ ] **Step 1: Create AppLogo component with The Levitation**

Replace `app/components/AppLogo.vue`:
```vue
<script setup lang="ts">
defineProps<{
  class?: string
}>()
</script>

<template>
  <NuxtLink to="/" class="flex items-center gap-2">
    <svg
      :class="['h-7 w-auto', $props.class]"
      viewBox="0 0 1000 1000"
      fill="none"
      aria-label="ArkaOS"
      role="img"
    >
      <path d="M400 100H475L475 610L370 920H140Z" class="fill-primary" />
      <path d="M525 100H600L860 920H630L525 610Z" class="fill-primary" />
      <rect x="275" y="645" width="450" height="44" class="fill-primary" />
    </svg>
    <span class="font-bold text-lg text-default">
      <span class="text-primary">Arka</span>OS
    </span>
  </NuxtLink>
</template>
```

- [ ] **Step 2: Create AppHeader with i18n navigation**

Replace `app/components/AppHeader.vue`:
```vue
<script setup lang="ts">
const { t } = useI18n()

const links = computed(() => [
  { label: t('nav.features'), to: '/features' },
  { label: t('nav.departments'), to: '/departments' },
  { label: t('nav.docs'), to: '/docs' },
  { label: t('nav.blog'), to: '/blog' },
  { label: t('nav.community'), to: '/community' }
])
</script>

<template>
  <UHeader>
    <template #left>
      <AppLogo />
    </template>

    <UNavigationMenu :items="links" />

    <template #right>
      <UButton
        :label="t('nav.getStarted')"
        color="primary"
        to="/docs"
        size="sm"
      />
    </template>
  </UHeader>
</template>
```

- [ ] **Step 3: Create AppFooter with i18n**

Replace `app/components/AppFooter.vue`:
```vue
<script setup lang="ts">
const { t } = useI18n()

const columns = computed(() => [
  {
    label: t('footer.product'),
    children: [
      { label: t('nav.features'), to: '/features' },
      { label: t('nav.departments'), to: '/departments' },
      { label: 'Agents', to: '/agents' },
      { label: 'Changelog', to: '/changelog' }
    ]
  },
  {
    label: t('footer.resources'),
    children: [
      { label: t('nav.docs'), to: '/docs' },
      { label: t('nav.blog'), to: '/blog' },
      { label: t('nav.community'), to: '/community' },
      { label: 'GitHub', to: 'https://github.com/andreagroferreira/arka-os', target: '_blank' }
    ]
  },
  {
    label: t('footer.company'),
    children: [
      { label: 'About', to: '/about' },
      { label: 'WizardingCode', to: 'https://wizardingcode.com', target: '_blank' }
    ]
  }
])
</script>

<template>
  <UFooter>
    <UFooterColumns :columns="columns" />

    <USeparator />

    <UContainer>
      <div class="flex items-center justify-between py-4">
        <AppLogo />
        <p class="text-sm text-muted">
          &copy; {{ new Date().getFullYear() }} {{ t('footer.copyright') }}
        </p>
      </div>
    </UContainer>
  </UFooter>
</template>
```

- [ ] **Step 4: Create default layout (marketing)**

Create `app/layouts/default.vue`:
```vue
<template>
  <div>
    <AppHeader />
    <UMain>
      <slot />
    </UMain>
    <AppFooter />
  </div>
</template>
```

- [ ] **Step 5: Create docs layout (sidebar + TOC)**

Create `app/layouts/docs.vue`:
```vue
<script setup lang="ts">
const { data: navigation } = await useAsyncData('docs-navigation', () => {
  return queryCollectionNavigation('docs')
})
</script>

<template>
  <div>
    <AppHeader />
    <UMain>
      <UContainer>
        <div class="flex gap-8 py-8">
          <aside class="hidden lg:block w-64 shrink-0">
            <UNavigationTree
              :links="navigation || []"
              default-open
            />
          </aside>

          <div class="flex-1 min-w-0">
            <slot />
          </div>

          <aside class="hidden xl:block w-48 shrink-0">
            <UContentToc />
          </aside>
        </div>
      </UContainer>
    </UMain>
    <AppFooter />
  </div>
</template>
```

- [ ] **Step 6: Update app.vue to use layouts**

Replace `app/app.vue`:
```vue
<script setup lang="ts">
const colorMode = useColorMode()
colorMode.preference = 'dark'

useSeoMeta({
  titleTemplate: '%s - ArkaOS',
  ogSiteName: 'ArkaOS',
  twitterCard: 'summary_large_image'
})

useHead({
  htmlAttrs: { class: 'dark' },
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ]
})
</script>

<template>
  <UApp>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
```

- [ ] **Step 7: Verify layouts render correctly**

```bash
pnpm dev
```

Visit `http://localhost:3000` — should see header with ArkaOS logo, nav links, green CTA button, and footer.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add layouts, header, footer, and ArkaOS logo

- Default layout (marketing: clean, full-width)
- Docs layout (sidebar navigation + table of contents)
- AppHeader with i18n navigation
- AppFooter with columns and copyright
- AppLogo with The Levitation SVG mark"
```

---

## Task 3: Homepage Hero with Animated Terminal

**Files:**
- Create: `app/components/home/HomeHero.vue`
- Create: `app/components/home/TerminalAnimation.vue`
- Modify: `app/pages/index.vue`
- Delete: `app/components/HeroBackground.vue`

- [ ] **Step 1: Create TerminalAnimation component**

Create `app/components/home/TerminalAnimation.vue`:
```vue
<script setup lang="ts">
const lines = ref<{ text: string; type: 'command' | 'output' | 'success' | 'route' }[]>([])
const currentLine = ref(0)
const isTyping = ref(false)

const script = [
  { text: '$ npx arkaos install', type: 'command' as const, delay: 80 },
  { text: 'Installing ArkaOS v2.10.1...', type: 'output' as const, delay: 30 },
  { text: '\u2713 17 departments configured', type: 'output' as const, delay: 30 },
  { text: '\u2713 65 agents activated', type: 'output' as const, delay: 30 },
  { text: '\u2713 244 skills loaded', type: 'output' as const, delay: 30 },
  { text: 'Ready. Your AI workforce is online.', type: 'success' as const, delay: 30 },
  { text: '', type: 'output' as const, delay: 0 },
  { text: '$ /do "create a brand for my startup"', type: 'command' as const, delay: 60 },
  { text: '\u2192 Routing to Brand Department...', type: 'route' as const, delay: 30 },
  { text: '\u2192 Valentina (Creative Director) assigned', type: 'output' as const, delay: 30 },
  { text: '\u2192 Mateus (Brand Strategist) assigned', type: 'output' as const, delay: 30 },
  { text: '\u2192 Isabel (Visual Designer) assigned', type: 'output' as const, delay: 30 },
  { text: '\u2713 Brand identity delivered in 3 minutes', type: 'success' as const, delay: 30 }
]

async function typeText(text: string, charDelay: number): Promise<string> {
  let result = ''
  for (const char of text) {
    result += char
    await new Promise(r => setTimeout(r, charDelay))
  }
  return result
}

async function runAnimation() {
  for (const step of script) {
    isTyping.value = step.type === 'command'
    const text = step.delay > 0 ? await typeText(step.text, step.delay) : step.text
    lines.value.push({ text, type: step.type })
    isTyping.value = false
    await new Promise(r => setTimeout(r, step.type === 'command' ? 500 : 200))
  }
}

onMounted(() => {
  setTimeout(runAnimation, 1000)
})
</script>

<template>
  <div class="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-2xl shadow-primary/5">
    <!-- Title bar -->
    <div class="flex items-center gap-2 px-4 py-3 bg-zinc-900/50 border-b border-zinc-800">
      <div class="flex gap-1.5">
        <div class="size-3 rounded-full bg-zinc-700" />
        <div class="size-3 rounded-full bg-zinc-700" />
        <div class="size-3 rounded-full bg-zinc-700" />
      </div>
      <span class="font-mono text-xs text-zinc-500 ml-2">arkaos</span>
    </div>

    <!-- Terminal body -->
    <div class="p-5 font-mono text-sm leading-relaxed min-h-[320px]">
      <div
        v-for="(line, i) in lines"
        :key="i"
        :class="{
          'text-zinc-200': line.type === 'command',
          'text-zinc-500': line.type === 'output',
          'text-primary': line.type === 'success',
          'text-arka-300': line.type === 'route'
        }"
      >
        {{ line.text }}
      </div>
      <div v-if="isTyping" class="inline-block w-2 h-4 bg-primary animate-pulse" />
      <div v-else-if="lines.length > 0" class="text-zinc-600">
        $<span class="inline-block w-2 h-4 bg-zinc-600 ml-1 animate-pulse" />
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create HomeHero component**

Create `app/components/home/HomeHero.vue`:
```vue
<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <section class="relative overflow-hidden">
    <!-- Background glow -->
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[150px]" />

    <UContainer class="relative py-20 lg:py-32">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
        <!-- Left: Copy -->
        <div class="space-y-6">
          <p class="font-mono text-sm text-primary tracking-widest uppercase">
            {{ t('hero.tagline') }}
          </p>
          <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-default leading-tight">
            One command.<br />
            <span class="text-primary">65 specialists.</span>
          </h1>
          <p class="text-lg text-muted max-w-lg">
            {{ t('hero.description') }}
          </p>
          <div class="flex flex-wrap gap-4 pt-2">
            <UButton
              :label="t('hero.cta')"
              color="primary"
              size="xl"
              to="/docs"
              icon="i-lucide-terminal"
            />
            <UButton
              :label="t('hero.github')"
              color="neutral"
              variant="outline"
              size="xl"
              to="https://github.com/andreagroferreira/arka-os"
              target="_blank"
              icon="i-simple-icons-github"
            />
          </div>
        </div>

        <!-- Right: Terminal -->
        <div class="lg:pl-8">
          <TerminalAnimation />
        </div>
      </div>
    </UContainer>
  </section>
</template>
```

- [ ] **Step 3: Create initial homepage**

Replace `app/pages/index.vue`:
```vue
<script setup lang="ts">
useSeoMeta({
  title: 'ArkaOS - The Operating System for AI Agent Teams',
  ogTitle: 'ArkaOS - Your AI Workforce',
  description: '65 agents. 17 departments. One command. An operating system for AI agent teams.',
  ogDescription: '65 agents. 17 departments. One command. An operating system for AI agent teams.'
})
</script>

<template>
  <div>
    <HomeHero />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <!-- Sections 2-9 added in Tasks 4 & 5 -->
  </div>
</template>
```

- [ ] **Step 4: Remove old template components**

```bash
rm -f app/components/HeroBackground.vue app/components/StarsBg.vue
```

- [ ] **Step 5: Verify hero renders with animation**

```bash
pnpm dev
```

Visit `http://localhost:3000` — should see the terminal-first hero with typing animation on the right and ArkaOS copy on the left.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add homepage hero with animated terminal

- Terminal typing animation showing install + routing demo
- Split layout: headline left, terminal right
- Brand glow background effect
- i18n-ready copy"
```

---

## Task 4: Homepage Sections 2-5 (Problem, Solution, How it Works, Departments)

**Files:**
- Create: `app/components/home/HomeProblem.vue`
- Create: `app/components/home/HomeSolution.vue`
- Create: `app/components/home/HomeHowItWorks.vue`
- Create: `app/components/home/HomeDepartments.vue`
- Create: `app/composables/useScrollReveal.ts`
- Modify: `app/pages/index.vue`

- [ ] **Step 1: Create scroll reveal composable**

Create `app/composables/useScrollReveal.ts`:
```ts
export function useScrollReveal() {
  onMounted(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
          }
        })
      },
      { threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
    )

    document.querySelectorAll('.scroll-animate').forEach((el) => {
      observer.observe(el)
    })

    onUnmounted(() => observer.disconnect())
  })
}
```

- [ ] **Step 2: Create HomeProblem section**

Create `app/components/home/HomeProblem.vue`:
```vue
<template>
  <UPageSection class="scroll-animate">
    <template #title>
      You're running a <span class="text-primary">business</span>,
      not just writing code
    </template>
    <template #description>
      Development is one department. What about brand, strategy, finance, marketing, operations, e-commerce? You're juggling ChatGPT, Cursor, Notion, and 15 other tools — none of them talk to each other.
    </template>

    <UContainer>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div
          v-for="tool in ['ChatGPT', 'Cursor', 'Notion', 'Figma', 'Slack', 'Linear', 'Stripe', 'Analytics']"
          :key="tool"
          class="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 text-center"
        >
          <span class="text-sm text-zinc-500 line-through">{{ tool }}</span>
        </div>
      </div>
      <div class="text-center mt-8">
        <p class="font-mono text-sm text-zinc-500">
          8 tools. 8 contexts. 0 coordination.
        </p>
      </div>
    </UContainer>
  </UPageSection>
</template>
```

- [ ] **Step 3: Create HomeSolution section**

Create `app/components/home/HomeSolution.vue`:
```vue
<template>
  <UPageSection class="scroll-animate">
    <template #title>
      One OS. <span class="text-primary">17 departments.</span>
    </template>
    <template #description>
      ArkaOS replaces the tool sprawl with a unified operating system. Each department has specialized agents, workflows, and frameworks — coordinated by a single command interface.
    </template>

    <UContainer>
      <div class="relative max-w-3xl mx-auto">
        <!-- Central node -->
        <div class="flex justify-center mb-8">
          <div class="bg-zinc-900 border-2 border-primary rounded-xl px-6 py-3 glow-green">
            <span class="font-mono text-primary font-bold">/do</span>
            <span class="text-zinc-400 text-sm ml-2">Universal Orchestrator</span>
          </div>
        </div>

        <!-- Department grid -->
        <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
          <div
            v-for="dept in ['Dev', 'Brand', 'Marketing', 'Finance', 'Strategy', 'E-Commerce', 'Knowledge', 'Operations', 'Project Mgmt', 'SaaS', 'Landing', 'Content', 'Community', 'Sales', 'Leadership', 'Organization', 'Quality']"
            :key="dept"
            class="bg-zinc-900/50 border border-zinc-800 hover:border-primary/30 rounded-lg p-2 text-center transition-colors"
          >
            <span class="text-xs text-zinc-400">{{ dept }}</span>
          </div>
        </div>
      </div>
    </UContainer>
  </UPageSection>
</template>
```

- [ ] **Step 4: Create HomeHowItWorks section**

Create `app/components/home/HomeHowItWorks.vue`:
```vue
<template>
  <UPageSection class="scroll-animate">
    <template #title>
      Three steps to <span class="text-primary">your AI workforce</span>
    </template>

    <UContainer>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div
          v-for="(step, i) in steps"
          :key="step.title"
          class="relative"
        >
          <div class="flex items-center gap-3 mb-4">
            <div class="flex items-center justify-center size-10 rounded-full bg-primary/10 border border-primary/20">
              <span class="font-mono text-primary font-bold">{{ i + 1 }}</span>
            </div>
            <h3 class="text-lg font-bold text-default">{{ step.title }}</h3>
          </div>
          <div class="bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-sm">
            <div v-for="line in step.code" :key="line.text" :class="line.class">
              {{ line.text }}
            </div>
          </div>
          <p class="text-sm text-muted mt-3">{{ step.description }}</p>
        </div>
      </div>
    </UContainer>
  </UPageSection>
</template>

<script setup lang="ts">
const steps = [
  {
    title: 'Install',
    description: 'One command. Works with Claude Code, Codex, Gemini, and Cursor.',
    code: [
      { text: '$ npx arkaos install', class: 'text-zinc-200' },
      { text: '\u2713 ArkaOS v2.10.1 ready', class: 'text-primary' }
    ]
  },
  {
    title: 'Command',
    description: 'Describe what you need in natural language. ArkaOS routes to the right department.',
    code: [
      { text: '$ /do "audit my e-commerce"', class: 'text-zinc-200' },
      { text: '\u2192 E-Commerce Department', class: 'text-arka-300' },
      { text: '\u2192 5 agents assigned', class: 'text-zinc-500' }
    ]
  },
  {
    title: 'Deliver',
    description: 'Specialized agents execute with enterprise workflows, quality gates, and documentation.',
    code: [
      { text: '\u2713 UX audit complete', class: 'text-zinc-500' },
      { text: '\u2713 SEO audit complete', class: 'text-zinc-500' },
      { text: '\u2713 Quality Gate: APPROVED', class: 'text-primary' }
    ]
  }
]
</script>
```

- [ ] **Step 5: Create HomeDepartments section**

Create `app/components/home/HomeDepartments.vue`:
```vue
<script setup lang="ts">
const departments = [
  { prefix: '/dev', name: 'Development', agents: 9, lead: 'Paulo', icon: 'i-lucide-code-2' },
  { prefix: '/brand', name: 'Brand & Design', agents: 4, lead: 'Valentina', icon: 'i-lucide-palette' },
  { prefix: '/mkt', name: 'Marketing', agents: 4, lead: 'Luna', icon: 'i-lucide-megaphone' },
  { prefix: '/fin', name: 'Finance', agents: 3, lead: 'Helena', icon: 'i-lucide-landmark' },
  { prefix: '/strat', name: 'Strategy', agents: 3, lead: 'Tomas', icon: 'i-lucide-target' },
  { prefix: '/ecom', name: 'E-Commerce', agents: 4, lead: 'Ricardo', icon: 'i-lucide-shopping-cart' },
  { prefix: '/kb', name: 'Knowledge', agents: 3, lead: 'Clara', icon: 'i-lucide-book-open' },
  { prefix: '/ops', name: 'Operations', agents: 2, lead: 'Daniel', icon: 'i-lucide-settings' },
  { prefix: '/pm', name: 'Project Mgmt', agents: 3, lead: 'Carolina', icon: 'i-lucide-kanban' },
  { prefix: '/saas', name: 'SaaS', agents: 3, lead: 'Tiago', icon: 'i-lucide-cloud' },
  { prefix: '/landing', name: 'Landing Pages', agents: 4, lead: 'Ines', icon: 'i-lucide-layout' },
  { prefix: '/content', name: 'Content', agents: 4, lead: 'Rafael', icon: 'i-lucide-pen-tool' },
  { prefix: '/community', name: 'Communities', agents: 2, lead: 'Beatriz', icon: 'i-lucide-users' },
  { prefix: '/sales', name: 'Sales', agents: 2, lead: 'Miguel', icon: 'i-lucide-handshake' },
  { prefix: '/lead', name: 'Leadership', agents: 2, lead: 'Rodrigo', icon: 'i-lucide-crown' },
  { prefix: '/org', name: 'Organization', agents: 1, lead: 'Sofia', icon: 'i-lucide-network' },
  { prefix: '/quality', name: 'Quality', agents: 3, lead: 'Marta', icon: 'i-lucide-shield-check' }
]

const expanded = ref<string | null>(null)
</script>

<template>
  <UPageSection class="scroll-animate">
    <template #title>
      <span class="text-primary">17 departments</span> at your command
    </template>
    <template #description>
      Each department has specialized agents, workflows, and enterprise frameworks. Click to explore.
    </template>

    <UContainer>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        <button
          v-for="dept in departments"
          :key="dept.prefix"
          class="text-left bg-zinc-900/50 border rounded-lg p-4 transition-all hover:border-primary/30"
          :class="expanded === dept.prefix ? 'border-primary/50 bg-zinc-900' : 'border-zinc-800'"
          @click="expanded = expanded === dept.prefix ? null : dept.prefix"
        >
          <div class="flex items-center gap-2 mb-2">
            <UIcon :name="dept.icon" class="size-4 text-primary" />
            <span class="font-mono text-xs text-primary">{{ dept.prefix }}</span>
          </div>
          <h3 class="text-sm font-semibold text-default">{{ dept.name }}</h3>
          <p class="text-xs text-muted mt-1">{{ dept.agents }} agents &middot; Lead: {{ dept.lead }}</p>
        </button>
      </div>
    </UContainer>
  </UPageSection>
</template>
```

- [ ] **Step 6: Add sections 2-5 to homepage**

Update `app/pages/index.vue`:
```vue
<script setup lang="ts">
import { useScrollReveal } from '~/composables/useScrollReveal'

useScrollReveal()

useSeoMeta({
  title: 'ArkaOS - The Operating System for AI Agent Teams',
  ogTitle: 'ArkaOS - Your AI Workforce',
  description: '65 agents. 17 departments. One command. An operating system for AI agent teams.',
  ogDescription: '65 agents. 17 departments. One command. An operating system for AI agent teams.'
})
</script>

<template>
  <div>
    <HomeHero />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeProblem />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeSolution />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeHowItWorks />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeDepartments />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <!-- Sections 6-9 added in Task 5 -->
  </div>
</template>
```

- [ ] **Step 7: Verify all 5 sections render with scroll animations**

```bash
pnpm dev
```

Scroll through `http://localhost:3000` — each section should fade in as it enters the viewport.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add homepage sections 2-5

- Problem section: fragmented tools visualization
- Solution section: /do orchestrator + department grid
- How it Works: 3-step install/command/deliver
- Departments: interactive grid of 17 departments
- Scroll reveal composable with IntersectionObserver"
```

---

## Task 5: Homepage Sections 6-9 (Comparison, Numbers, Community CTA, Final CTA)

**Files:**
- Create: `app/components/home/HomeComparison.vue`
- Create: `app/components/home/HomeNumbers.vue`
- Create: `app/components/home/HomeCommunity.vue`
- Create: `app/components/home/HomeFinalCTA.vue`
- Create: `app/composables/useCountUp.ts`
- Modify: `app/pages/index.vue`

- [ ] **Step 1: Create counter animation composable**

Create `app/composables/useCountUp.ts`:
```ts
export function useCountUp(target: number, duration: number = 2000) {
  const count = ref(0)
  const el = ref<HTMLElement | null>(null)
  let animated = false

  onMounted(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !animated) {
          animated = true
          const start = performance.now()
          function step(now: number) {
            const progress = Math.min((now - start) / duration, 1)
            count.value = Math.floor(progress * target)
            if (progress < 1) requestAnimationFrame(step)
          }
          requestAnimationFrame(step)
        }
      },
      { threshold: 0.5 }
    )

    if (el.value) observer.observe(el.value)
    onUnmounted(() => observer.disconnect())
  })

  return { count, el }
}
```

- [ ] **Step 2: Create HomeComparison section**

Create `app/components/home/HomeComparison.vue`:
```vue
<script setup lang="ts">
const layers = [
  { name: 'Spec Framework', arkaos: true, chatgpt: false, cursor: false, devin: false },
  { name: 'Planning System', arkaos: true, chatgpt: false, cursor: false, devin: true },
  { name: 'Multi-Domain Agents', arkaos: true, chatgpt: false, cursor: false, devin: false },
  { name: 'Runtime Engine', arkaos: true, chatgpt: false, cursor: true, devin: true },
  { name: 'Quality Gates', arkaos: true, chatgpt: false, cursor: false, devin: false },
  { name: 'Enterprise Workflows', arkaos: true, chatgpt: false, cursor: false, devin: false },
  { name: 'Behavioral DNA', arkaos: true, chatgpt: false, cursor: false, devin: false },
  { name: 'Open Source', arkaos: true, chatgpt: false, cursor: false, devin: false }
]
</script>

<template>
  <UPageSection class="scroll-animate">
    <template #title>
      No one else covers <span class="text-primary">all 4 layers</span>
    </template>
    <template #description>
      Specs, Planning, Execution, and Runtime — ArkaOS is the only framework that covers the full stack across multiple business domains.
    </template>

    <UContainer>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-zinc-800">
              <th class="text-left py-3 pr-4 text-muted font-medium">Capability</th>
              <th class="py-3 px-4 text-primary font-bold">ArkaOS</th>
              <th class="py-3 px-4 text-zinc-400 font-medium">ChatGPT</th>
              <th class="py-3 px-4 text-zinc-400 font-medium">Cursor</th>
              <th class="py-3 px-4 text-zinc-400 font-medium">Devin</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="layer in layers"
              :key="layer.name"
              class="border-b border-zinc-800/50"
            >
              <td class="py-3 pr-4 text-zinc-300">{{ layer.name }}</td>
              <td class="py-3 px-4 text-center">
                <UIcon name="i-lucide-check" class="size-5 text-primary" />
              </td>
              <td class="py-3 px-4 text-center">
                <UIcon v-if="layer.chatgpt" name="i-lucide-check" class="size-5 text-zinc-500" />
                <UIcon v-else name="i-lucide-minus" class="size-5 text-zinc-700" />
              </td>
              <td class="py-3 px-4 text-center">
                <UIcon v-if="layer.cursor" name="i-lucide-check" class="size-5 text-zinc-500" />
                <UIcon v-else name="i-lucide-minus" class="size-5 text-zinc-700" />
              </td>
              <td class="py-3 px-4 text-center">
                <UIcon v-if="layer.devin" name="i-lucide-check" class="size-5 text-zinc-500" />
                <UIcon v-else name="i-lucide-minus" class="size-5 text-zinc-700" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </UContainer>
  </UPageSection>
</template>
```

- [ ] **Step 3: Create HomeNumbers section**

Create `app/components/home/HomeNumbers.vue`:
```vue
<script setup lang="ts">
import { useCountUp } from '~/composables/useCountUp'

const stats = [
  { label: 'Agents', value: 65, suffix: '' },
  { label: 'Skills', value: 244, suffix: '+' },
  { label: 'Departments', value: 17, suffix: '' },
  { label: 'Tests', value: 542, suffix: '+' }
]
</script>

<template>
  <UPageSection class="scroll-animate">
    <UContainer>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
        <div v-for="stat in stats" :key="stat.label">
          <HomeNumberCounter :target="stat.value" :suffix="stat.suffix" />
          <p class="text-sm text-muted mt-2 font-mono uppercase tracking-wider">{{ stat.label }}</p>
        </div>
      </div>
      <div class="text-center mt-8">
        <UBadge label="100% Open Source" color="primary" variant="subtle" size="lg" />
      </div>
    </UContainer>
  </UPageSection>
</template>
```

Create `app/components/home/HomeNumberCounter.vue`:
```vue
<script setup lang="ts">
import { useCountUp } from '~/composables/useCountUp'

const props = defineProps<{
  target: number
  suffix?: string
}>()

const { count, el } = useCountUp(props.target)
</script>

<template>
  <div ref="el" class="text-5xl font-extrabold text-primary tabular-nums">
    {{ count }}{{ suffix }}
  </div>
</template>
```

- [ ] **Step 4: Create HomeCommunity section**

Create `app/components/home/HomeCommunity.vue`:
```vue
<template>
  <UPageSection class="scroll-animate">
    <template #title>
      Join the <span class="text-primary">community</span>
    </template>
    <template #description>
      ArkaOS is built in the open. Contribute, learn, and grow with us.
    </template>

    <UContainer>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <UCard variant="outline" :ui="{ root: 'hover:border-primary/30 transition-colors' }">
          <div class="flex items-center gap-3 mb-3">
            <UIcon name="i-simple-icons-discord" class="size-6 text-primary" />
            <h3 class="font-bold text-default">Discord</h3>
          </div>
          <p class="text-sm text-muted mb-4">Chat with the team, get help, share what you're building.</p>
          <UButton label="Join Discord" variant="outline" color="primary" size="sm" to="#" target="_blank" />
        </UCard>

        <UCard variant="outline" :ui="{ root: 'hover:border-primary/30 transition-colors' }">
          <div class="flex items-center gap-3 mb-3">
            <UIcon name="i-simple-icons-github" class="size-6 text-primary" />
            <h3 class="font-bold text-default">GitHub</h3>
          </div>
          <p class="text-sm text-muted mb-4">Star the repo, report issues, submit PRs. All contributions welcome.</p>
          <UButton label="View on GitHub" variant="outline" color="primary" size="sm" to="https://github.com/andreagroferreira/arka-os" target="_blank" />
        </UCard>

        <UCard variant="outline" :ui="{ root: 'hover:border-primary/30 transition-colors' }">
          <div class="flex items-center gap-3 mb-3">
            <UIcon name="i-lucide-mail" class="size-6 text-primary" />
            <h3 class="font-bold text-default">Newsletter</h3>
          </div>
          <p class="text-sm text-muted mb-4">Monthly updates on new departments, agents, and features.</p>
          <div class="flex gap-2">
            <UInput placeholder="Email" size="sm" class="flex-1" />
            <UButton label="Subscribe" color="primary" size="sm" />
          </div>
        </UCard>
      </div>
    </UContainer>
  </UPageSection>
</template>
```

- [ ] **Step 5: Create HomeFinalCTA section**

Create `app/components/home/HomeFinalCTA.vue`:
```vue
<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <section class="relative overflow-hidden py-24">
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-primary/5 rounded-full blur-[120px]" />

    <UContainer class="relative text-center space-y-8">
      <h2 class="text-4xl sm:text-5xl font-extrabold text-default">
        Ready? <span class="text-primary">One command.</span>
      </h2>

      <div class="max-w-md mx-auto">
        <div class="bg-zinc-950 border border-zinc-800 rounded-xl p-5 font-mono text-sm glow-green">
          <span class="text-zinc-500">$</span>
          <span class="text-primary ml-1">npx</span>
          <span class="text-zinc-200 ml-1">arkaos install</span>
        </div>
      </div>

      <div class="flex flex-wrap justify-center gap-4">
        <UButton
          :label="t('hero.cta')"
          color="primary"
          size="xl"
          to="/docs"
          icon="i-lucide-terminal"
        />
        <UButton
          :label="t('hero.github')"
          color="neutral"
          variant="outline"
          size="xl"
          to="https://github.com/andreagroferreira/arka-os"
          target="_blank"
          icon="i-simple-icons-github"
        />
      </div>
    </UContainer>
  </section>
</template>
```

- [ ] **Step 6: Complete homepage with all 9 sections**

Update `app/pages/index.vue`:
```vue
<script setup lang="ts">
import { useScrollReveal } from '~/composables/useScrollReveal'

useScrollReveal()

useSeoMeta({
  title: 'ArkaOS - The Operating System for AI Agent Teams',
  ogTitle: 'ArkaOS - Your AI Workforce',
  description: '65 agents. 17 departments. One command. An operating system for AI agent teams.',
  ogDescription: '65 agents. 17 departments. One command. An operating system for AI agent teams.'
})
</script>

<template>
  <div>
    <HomeHero />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeProblem />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeSolution />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeHowItWorks />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeDepartments />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeComparison />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeNumbers />
    <USeparator :ui="{ border: 'border-primary/20' }" />
    <HomeCommunity />
    <HomeFinalCTA />
  </div>
</template>
```

- [ ] **Step 7: Verify complete homepage scroll experience**

```bash
pnpm dev
```

Scroll through all 9 sections. Each should animate on scroll entry.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: complete homepage with all 9 scroll storytelling sections

- Comparison table: ArkaOS vs ChatGPT vs Cursor vs Devin
- Numbers section with animated counters
- Community CTA: Discord, GitHub, Newsletter
- Final CTA with glowing terminal install command
- Counter animation composable with IntersectionObserver"
```

---

## Task 6: Documentation Infrastructure

**Files:**
- Create: `content/docs/1.getting-started/1.installation.md`
- Create: `content/docs/1.getting-started/2.quick-start.md`
- Create: `content/docs/2.concepts/1.architecture.md`
- Create: `app/pages/docs/[...slug].vue`
- Modify: `app/layouts/docs.vue` (if adjustments needed)

- [ ] **Step 1: Create docs catch-all page**

Create `app/pages/docs/[...slug].vue`:
```vue
<script setup lang="ts">
definePageMeta({
  layout: 'docs'
})

const route = useRoute()
const path = computed(() => {
  const slug = route.params.slug
  if (Array.isArray(slug)) return slug.join('/')
  return slug || ''
})

const { data: page } = await useAsyncData(`docs-${path.value}`, () => {
  return queryCollection('docs').path(`/docs/${path.value}`).first()
})

if (!page.value) {
  throw createError({ statusCode: 404, statusMessage: 'Page not found' })
}

useSeoMeta({
  title: page.value.title,
  description: page.value.description
})
</script>

<template>
  <div>
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-default mb-2">{{ page?.title }}</h1>
      <p v-if="page?.description" class="text-lg text-muted">{{ page.description }}</p>
    </div>

    <ContentRenderer v-if="page" :value="page" class="prose prose-invert max-w-none" />

    <div class="flex items-center justify-between mt-12 pt-8 border-t border-zinc-800">
      <UButton
        v-if="page?.prev"
        :label="page.prev.title"
        :to="page.prev._path"
        variant="ghost"
        icon="i-lucide-arrow-left"
      />
      <div />
      <UButton
        v-if="page?.next"
        :label="page.next.title"
        :to="page.next._path"
        variant="ghost"
        trailing-icon="i-lucide-arrow-right"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 2: Create installation doc**

Create `content/docs/1.getting-started/1.installation.md`:
```markdown
---
title: Installation
description: Install ArkaOS in 60 seconds with a single command.
---

ArkaOS installs as a layer on top of your AI coding assistant. It works with Claude Code, Codex CLI, Gemini CLI, and Cursor.

## Prerequisites

- **Node.js** 18+ (for the installer)
- **Python** 3.10+ (for the core engine)
- One of the supported runtimes: Claude Code, Codex CLI, Gemini CLI, or Cursor

## Quick Install

::code-group

```bash [Claude Code]
npx arkaos install
```

```bash [Codex CLI]
npx arkaos install --runtime codex
```

```bash [Gemini CLI]
npx arkaos install --runtime gemini
```

::

The installer will:
1. Detect your runtime automatically
2. Install the Python core engine
3. Configure 17 departments with 65 agents
4. Set up hooks for your runtime
5. Load 244+ skills

## Verify Installation

```bash
/arka status
```

You should see your ArkaOS version, department count, and agent count.

## Update

```bash
npx arkaos@latest update
```

Then inside your AI assistant:

```bash
/arka update
```

## Next Steps

- [Quick Start](/docs/getting-started/quick-start) — Your first command
- [Configuration](/docs/getting-started/configuration) — Customize ArkaOS
- [Runtimes](/docs/getting-started/runtimes) — Runtime-specific setup
```

- [ ] **Step 3: Create quick start doc**

Create `content/docs/1.getting-started/2.quick-start.md`:
```markdown
---
title: Quick Start
description: Run your first ArkaOS command and see your AI workforce in action.
---

After installation, ArkaOS is ready to use. Every interaction routes through the department system — you never talk to a generic AI assistant.

## Your First Command

The simplest way to use ArkaOS is with the universal orchestrator:

```bash
/do "describe what you need"
```

ArkaOS analyzes your request and routes it to the right department automatically.

## Examples

### Development

```bash
/do "add user authentication with OAuth"
# Routes to: Dev Department (Paulo, Tech Lead)
# Workflow: 10-phase enterprise (spec → research → architecture → implement → QA → quality gate)
```

### Brand & Design

```bash
/do "create a brand identity for my SaaS"
# Routes to: Brand Department (Valentina, Creative Director)
# Workflow: 7-phase brand (discovery → strategy → visual → expression → quality gate)
```

### Strategy

```bash
/do "analyze the market for AI developer tools"
# Routes to: Strategy Department (Tomas, Strategy Director)
# Workflow: Research → frameworks → analysis → recommendations
```

## Direct Commands

If you know the department, use the prefix directly:

```bash
/dev feature "user dashboard"
/brand identity "my startup"
/fin budget Q3
/ecom audit
/strat market-analysis "AI tools"
```

## Next Steps

- [Departments](/docs/departments) — Explore all 17 departments
- [Agents](/docs/agents) — Meet the 65 specialized agents
- [Workflows](/docs/concepts/workflows) — Understand the execution model
```

- [ ] **Step 4: Create architecture concepts doc**

Create `content/docs/2.concepts/1.architecture.md`:
```markdown
---
title: Architecture
description: How ArkaOS organizes 65 agents across 17 departments with enterprise workflows.
---

ArkaOS is structured as a 4-layer operating system for AI agent teams. No other framework covers all 4 layers with multi-domain support.

## The 4 Layers

| Layer | Purpose | ArkaOS Component |
|-------|---------|-----------------|
| **Spec Framework** | Define what to build before building it | Living Specs with bidirectional sync |
| **Planning System** | Coordinate multi-step work | YAML workflow engine with phases and gates |
| **Execution Agents** | Do the actual work | 65 agents across 17 domains |
| **Runtime Engine** | Run on any AI coding tool | Claude Code, Codex, Gemini, Cursor adapters |

## Core Systems

### Synapse — Context Engine

8-layer context injection system that gives every agent the right information at the right time. Sub-millisecond with caching.

### Workflow Engine

Declarative YAML workflows with phases, quality gates, and parallel execution. Three tiers:
- **Enterprise** (7-10 phases) — for features, APIs
- **Focused** (3-4 phases) — for debug, refactor
- **Specialist** (1-2 phases) — for review, research

### Squad Framework

Agents belong to department squads but can be borrowed into ad-hoc project squads. Matrix structure inspired by SpaceX (flat, mission-driven) and Google (matrix).

### Governance

Constitution with 4 enforcement levels: NON-NEGOTIABLE (14 rules), QUALITY GATE (mandatory review), MUST (6 rules), SHOULD (4 rules).

## Agent Hierarchy

| Tier | Role | Count | Authority |
|------|------|-------|-----------|
| 0 | C-Suite | 6 | Veto power |
| 1 | Squad Leads | 16 | Orchestrate |
| 2 | Specialists | 40 | Execute |
| 3 | Support | 3 | Research |
```

- [ ] **Step 5: Create docs index page**

Create `content/docs/index.md`:
```markdown
---
title: Documentation
description: Everything you need to know about ArkaOS — from installation to advanced workflows.
navigation: false
---

Welcome to the ArkaOS documentation. Start with installation, explore the concepts, then dive into departments and agents.

## Getting Started

::card-group
  ::card{title="Installation" icon="i-lucide-download" to="/docs/getting-started/installation"}
  Install ArkaOS in 60 seconds with a single command.
  ::

  ::card{title="Quick Start" icon="i-lucide-zap" to="/docs/getting-started/quick-start"}
  Run your first command and see your AI workforce in action.
  ::
::
```

- [ ] **Step 6: Verify docs render with sidebar and navigation**

```bash
pnpm dev
```

Visit `http://localhost:3000/docs` — should see docs index. Visit `/docs/getting-started/installation` — should see sidebar navigation, content, and TOC.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add documentation infrastructure with @nuxt/content

- Docs catch-all page with sidebar layout
- Installation guide with multi-runtime code groups
- Quick start guide with command examples
- Architecture concepts overview
- Docs index with card navigation
- Prev/Next page navigation"
```

---

## Task 7: Auto-Generation Script (YAML to Markdown)

**Files:**
- Create: `scripts/generate-docs.mjs`

- [ ] **Step 1: Create the auto-generation script**

Create `scripts/generate-docs.mjs`:
```js
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync, statSync } from 'fs'
import { join, basename, dirname } from 'path'
import { parse } from 'yaml'

const ARKAOS_PATH = process.env.ARKAOS_PATH || join(process.env.HOME, 'AIProjects', 'arka-os')
const CONTENT_PATH = join(process.cwd(), 'content', 'docs')

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
}

function generateDepartmentDocs() {
  const deptDir = join(ARKAOS_PATH, 'departments')
  if (!existsSync(deptDir)) {
    console.warn('Warning: departments directory not found at', deptDir)
    return
  }

  const outputDir = join(CONTENT_PATH, '3.departments')
  ensureDir(outputDir)

  const departments = readdirSync(deptDir).filter(d => {
    return statSync(join(deptDir, d)).isDirectory() && d !== 'quality'
  })

  departments.sort()

  departments.forEach((dept, index) => {
    const agentsDir = join(deptDir, dept, 'agents')
    let agents = []

    if (existsSync(agentsDir)) {
      agents = readdirSync(agentsDir)
        .filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))
        .map(f => {
          try {
            const content = readFileSync(join(agentsDir, f), 'utf8')
            const data = parse(content)
            return {
              name: data.name || basename(f, '.yaml'),
              role: data.role || 'Agent',
              tier: data.tier || 2,
              file: f
            }
          } catch {
            return { name: basename(f, '.yaml'), role: 'Agent', tier: 2, file: f }
          }
        })
    }

    const deptName = dept.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
    const md = `---
title: ${deptName}
description: ${deptName} department — ${agents.length} specialized agents.
---

# ${deptName} Department

${agents.length} specialized agents working together with enterprise workflows.

## Agents

| Agent | Role | Tier |
|-------|------|------|
${agents.map(a => `| ${a.name} | ${a.role} | ${a.tier} |`).join('\n')}

## Usage

\`\`\`bash
/${dept === 'marketing' ? 'mkt' : dept.slice(0, dept.length > 5 ? 4 : dept.length)} do "describe your task"
\`\`\`

:read-more{to="/docs/agents" title="View all agents"}
`

    writeFileSync(join(outputDir, `${index + 1}.${dept}.md`), md)
    console.log(`Generated: 3.departments/${index + 1}.${dept}.md (${agents.length} agents)`)
  })
}

function generateAgentDocs() {
  const deptDir = join(ARKAOS_PATH, 'departments')
  if (!existsSync(deptDir)) return

  const outputDir = join(CONTENT_PATH, '4.agents')
  ensureDir(outputDir)

  let agentIndex = 0
  const departments = readdirSync(deptDir).filter(d => {
    return statSync(join(deptDir, d)).isDirectory()
  }).sort()

  for (const dept of departments) {
    const agentsDir = join(deptDir, dept, 'agents')
    if (!existsSync(agentsDir)) continue

    const files = readdirSync(agentsDir).filter(f => f.endsWith('.yaml') || f.endsWith('.yml'))

    for (const file of files) {
      try {
        const content = readFileSync(join(agentsDir, file), 'utf8')
        const data = parse(content)
        agentIndex++

        const name = data.name || basename(file, '.yaml')
        const deptName = dept.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())

        let md = `---
title: "${name}"
description: "${name} — ${data.role || 'Agent'} in the ${deptName} department."
---

# ${name}

**Role:** ${data.role || 'Agent'}
**Department:** ${deptName}
**Tier:** ${data.tier || 2}
`

        if (data.disc) {
          md += `
## Behavioral DNA

### DISC Profile
- **Type:** ${data.disc.type || 'N/A'}
- **Style:** ${data.disc.style || 'N/A'}
`
        }

        if (data.enneagram) {
          md += `
### Enneagram
- **Type:** ${data.enneagram.type || 'N/A'}
- **Core motivation:** ${data.enneagram.core_motivation || 'N/A'}
`
        }

        writeFileSync(join(outputDir, `${agentIndex}.${basename(file, '.yaml')}.md`), md)
      } catch (err) {
        console.warn(`Warning: Failed to parse ${file}:`, err.message)
      }
    }
  }

  console.log(`Generated: ${agentIndex} agent docs`)
}

console.log('ArkaOS Docs Generator')
console.log('Source:', ARKAOS_PATH)
console.log('Output:', CONTENT_PATH)
console.log('')

generateDepartmentDocs()
generateAgentDocs()

console.log('\nDone.')
```

- [ ] **Step 2: Add yaml dependency**

```bash
pnpm add -D yaml
```

- [ ] **Step 3: Run the generator and verify output**

```bash
node scripts/generate-docs.mjs
```

Expected: markdown files created in `content/docs/3.departments/` and `content/docs/4.agents/`.

- [ ] **Step 4: Verify generated docs render in the site**

```bash
pnpm dev
```

Visit `http://localhost:3000/docs/departments/dev` — should show the Development department page with its agents table.

- [ ] **Step 5: Add generated content to .gitignore**

Add to `.gitignore`:
```
content/docs/3.departments/
content/docs/4.agents/
content/docs/5.skills/
.superpowers/
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add docs auto-generation script from ArkaOS YAMLs

- Node.js script converts department/agent YAMLs to markdown
- Generates 17 department pages with agent tables
- Generates 65 agent pages with behavioral DNA profiles
- Runs at build time via generate-docs script
- Generated content gitignored (built from source)"
```

---

## Task 8: Blog Infrastructure

**Files:**
- Create: `app/pages/blog/index.vue`
- Create: `app/pages/blog/[slug].vue`
- Create: `content/blog/hello-world.md` (sample post)

- [ ] **Step 1: Create blog listing page**

Create `app/pages/blog/index.vue`:
```vue
<script setup lang="ts">
useSeoMeta({
  title: 'Blog',
  description: 'Tutorials, changelogs, case studies, and announcements from the ArkaOS team.'
})

const { data: posts } = await useAsyncData('blog-posts', () => {
  return queryCollection('blog')
    .order('date', 'DESC')
    .all()
})
</script>

<template>
  <div>
    <UPageHero>
      <template #title>
        <span class="text-primary">Blog</span>
      </template>
      <template #description>
        Tutorials, changelogs, and updates from the ArkaOS team.
      </template>
    </UPageHero>

    <UContainer class="py-12">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <NuxtLink
          v-for="post in posts"
          :key="post._path"
          :to="post._path"
          class="group"
        >
          <UCard variant="outline" :ui="{ root: 'hover:border-primary/30 transition-colors h-full' }">
            <div class="space-y-3">
              <div class="flex items-center gap-2">
                <UBadge v-if="post.category" :label="post.category" color="primary" variant="subtle" size="xs" />
                <span class="text-xs text-muted">{{ post.date }}</span>
              </div>
              <h2 class="text-lg font-bold text-default group-hover:text-primary transition-colors">
                {{ post.title }}
              </h2>
              <p class="text-sm text-muted line-clamp-3">{{ post.description }}</p>
            </div>
          </UCard>
        </NuxtLink>
      </div>
    </UContainer>
  </div>
</template>
```

- [ ] **Step 2: Create blog post page**

Create `app/pages/blog/[slug].vue`:
```vue
<script setup lang="ts">
const route = useRoute()

const { data: post } = await useAsyncData(`blog-${route.params.slug}`, () => {
  return queryCollection('blog').path(`/blog/${route.params.slug}`).first()
})

if (!post.value) {
  throw createError({ statusCode: 404, statusMessage: 'Post not found' })
}

useSeoMeta({
  title: post.value.title,
  description: post.value.description,
  ogType: 'article'
})
</script>

<template>
  <div>
    <UContainer class="py-12 max-w-3xl">
      <article>
        <header class="mb-8">
          <div class="flex items-center gap-3 mb-4">
            <UBadge v-if="post?.category" :label="post.category" color="primary" variant="subtle" />
            <span class="text-sm text-muted">{{ post?.date }}</span>
          </div>
          <h1 class="text-3xl sm:text-4xl font-extrabold text-default mb-3">{{ post?.title }}</h1>
          <p class="text-lg text-muted">{{ post?.description }}</p>
        </header>

        <ContentRenderer v-if="post" :value="post" class="prose prose-invert max-w-none" />
      </article>

      <div class="mt-12 pt-8 border-t border-zinc-800">
        <UButton label="Back to Blog" to="/blog" variant="ghost" icon="i-lucide-arrow-left" />
      </div>
    </UContainer>
  </div>
</template>
```

- [ ] **Step 3: Create sample blog post**

Create `content/blog/hello-world.md`:
```markdown
---
title: "Introducing ArkaOS v2.10"
description: "The Cognitive Layer release — Institutional Memory, Dreaming, and Research capabilities for your AI workforce."
date: "2026-04-09"
category: "Announcement"
---

ArkaOS v2.10 introduces the Cognitive Layer — a set of capabilities that give your AI workforce persistent memory, autonomous learning, and research intelligence.

## What's New

### Institutional Memory
Your agents now remember decisions, patterns, and context across sessions. No more re-explaining your architecture or coding conventions.

### Dreaming
ArkaOS analyzes your codebase overnight and surfaces insights, technical debt, and improvement opportunities every morning.

### Research
Automated research intelligence that monitors your ecosystem's dependencies, security advisories, and framework updates.

## Getting Started

Update to the latest version:

```bash
npx arkaos@latest update
```

Then sync your projects:

```bash
/arka update
```

The Cognitive Layer activates automatically after update.
```

- [ ] **Step 4: Verify blog renders**

```bash
pnpm dev
```

Visit `http://localhost:3000/blog` — should list the sample post. Click through to the full article.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add blog infrastructure with listing and post pages

- Blog listing page with card grid
- Blog post page with article layout
- Sample announcement post for v2.10
- Category badges and date display
- Prose styling for markdown content"
```

---

## Task 9: Marketing Pages (Features, Departments, Agents, Community, About)

**Files:**
- Create: `app/pages/features.vue`
- Create: `app/pages/departments.vue`
- Create: `app/pages/agents.vue`
- Create: `app/pages/community.vue`
- Create: `app/pages/about.vue`
- Create: `app/pages/changelog.vue`

- [ ] **Step 1: Create features page**

Create `app/pages/features.vue`:
```vue
<script setup lang="ts">
useSeoMeta({
  title: 'Features',
  description: 'ArkaOS features: 17 departments, 65 agents, enterprise workflows, multi-runtime, and more.'
})

const features = [
  {
    title: '17 Departments',
    description: 'Dev, Brand, Marketing, Finance, Strategy, E-Commerce, Knowledge, Operations, PM, SaaS, Landing, Content, Community, Sales, Leadership, Organization, Quality.',
    icon: 'i-lucide-building-2'
  },
  {
    title: '65 Specialized Agents',
    description: 'Each agent has a complete behavioral profile with DISC, Enneagram, Big Five, and MBTI frameworks. They act, think, and communicate consistently.',
    icon: 'i-lucide-users'
  },
  {
    title: 'Enterprise Workflows',
    description: 'YAML-defined workflows with phases, quality gates, and parallel execution. From 2-phase quick tasks to 10-phase enterprise features.',
    icon: 'i-lucide-git-branch'
  },
  {
    title: 'Multi-Runtime',
    description: 'Works with Claude Code, Codex CLI, Gemini CLI, and Cursor. One install, any runtime.',
    icon: 'i-lucide-monitor'
  },
  {
    title: 'Quality Gate',
    description: 'Nothing ships without CQO approval. Every output is reviewed by Copy Director and Tech Director before delivery.',
    icon: 'i-lucide-shield-check'
  },
  {
    title: 'Living Specs',
    description: 'Bidirectional spec/code sync. Specs evolve with the codebase, not in a dusty wiki.',
    icon: 'i-lucide-file-code'
  },
  {
    title: 'Synapse Context Engine',
    description: '8-layer context injection in sub-millisecond. Every agent gets the right information at the right time.',
    icon: 'i-lucide-brain'
  },
  {
    title: 'Knowledge Base',
    description: '16 areas of framework-backed knowledge. Porter, StoryBrand, SOLID, DORA, OWASP, and more.',
    icon: 'i-lucide-library'
  },
  {
    title: 'Open Source',
    description: '100% open source. MIT license. Community-driven. Star us on GitHub.',
    icon: 'i-lucide-heart'
  }
]
</script>

<template>
  <div>
    <UPageHero>
      <template #title>
        <span class="text-primary">Features</span>
      </template>
      <template #description>
        Everything ArkaOS brings to your workflow.
      </template>
    </UPageHero>

    <UContainer class="py-12">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <UCard
          v-for="feature in features"
          :key="feature.title"
          variant="outline"
        >
          <div class="space-y-3">
            <div class="p-3 rounded-lg bg-primary/10 w-fit">
              <UIcon :name="feature.icon" class="size-6 text-primary" />
            </div>
            <h3 class="text-lg font-bold text-default">{{ feature.title }}</h3>
            <p class="text-sm text-muted">{{ feature.description }}</p>
          </div>
        </UCard>
      </div>
    </UContainer>
  </div>
</template>
```

- [ ] **Step 2: Create departments page (reuses HomeDepartments data)**

Create `app/pages/departments.vue`:
```vue
<script setup lang="ts">
useSeoMeta({
  title: 'Departments',
  description: '17 specialized departments covering every business domain — from development to finance, marketing to strategy.'
})

const departments = [
  { prefix: '/dev', name: 'Development', agents: 9, lead: 'Paulo', commands: 16, icon: 'i-lucide-code-2', description: 'Full-stack development with 10-phase enterprise workflows. Laravel, Vue, React, Python.' },
  { prefix: '/brand', name: 'Brand & Design', agents: 4, lead: 'Valentina', commands: 12, icon: 'i-lucide-palette', description: 'Brand identity, design systems, mockups, logo creation, brandbooks.' },
  { prefix: '/mkt', name: 'Marketing & Growth', agents: 4, lead: 'Luna', commands: 12, icon: 'i-lucide-megaphone', description: 'Social media, ad campaigns, content calendars, email flows, growth hacking.' },
  { prefix: '/fin', name: 'Finance & Investment', agents: 3, lead: 'Helena', commands: 10, icon: 'i-lucide-landmark', description: 'Budgets, forecasts, investor materials, financial analysis, unit economics.' },
  { prefix: '/strat', name: 'Strategy & Innovation', agents: 3, lead: 'Tomas', commands: 10, icon: 'i-lucide-target', description: 'Market analysis, competitive intelligence, brainstorming, business models.' },
  { prefix: '/ecom', name: 'E-Commerce', agents: 4, lead: 'Ricardo', commands: 12, icon: 'i-lucide-shopping-cart', description: 'Store audits, product optimization, pricing strategy, conversion rate optimization.' },
  { prefix: '/kb', name: 'Knowledge Management', agents: 3, lead: 'Clara', commands: 12, icon: 'i-lucide-book-open', description: 'Knowledge ingestion, personas, vector search, YouTube analysis, PDF processing.' },
  { prefix: '/ops', name: 'Operations', agents: 2, lead: 'Daniel', commands: 10, icon: 'i-lucide-settings', description: 'Task management, email drafting, calendar, SOPs, process automation.' },
  { prefix: '/pm', name: 'Project Management', agents: 3, lead: 'Carolina', commands: 12, icon: 'i-lucide-kanban', description: 'Scrum, Kanban, sprint planning, retrospectives, continuous discovery.' },
  { prefix: '/saas', name: 'SaaS & Micro-SaaS', agents: 3, lead: 'Tiago', commands: 14, icon: 'i-lucide-cloud', description: 'SaaS validation, MVPs, metrics tracking, growth engineering, churn analysis.' },
  { prefix: '/landing', name: 'Landing Pages & Funnels', agents: 4, lead: 'Ines', commands: 14, icon: 'i-lucide-layout', description: 'Sales funnels, landing pages, A/B copy, conversion optimization, offers.' },
  { prefix: '/content', name: 'Content & Viralization', agents: 4, lead: 'Rafael', commands: 14, icon: 'i-lucide-pen-tool', description: 'Viral content, video scripts, content calendars, repurposing, distribution.' },
  { prefix: '/community', name: 'Communities & Groups', agents: 2, lead: 'Beatriz', commands: 14, icon: 'i-lucide-users', description: 'Discord/forum growth, engagement, events, ambassador programs.' },
  { prefix: '/sales', name: 'Sales & Negotiation', agents: 2, lead: 'Miguel', commands: 10, icon: 'i-lucide-handshake', description: 'Sales scripts, objection handling, proposal generation, pipeline management.' },
  { prefix: '/lead', name: 'Leadership & People', agents: 2, lead: 'Rodrigo', commands: 10, icon: 'i-lucide-crown', description: 'Team building, culture, coaching, performance reviews, OKRs.' },
  { prefix: '/org', name: 'Organization & Teams', agents: 1, lead: 'Sofia', commands: 10, icon: 'i-lucide-network', description: 'Org design, team topologies, workflow optimization, SOPs.' },
  { prefix: '/quality', name: 'Quality', agents: 3, lead: 'Marta', commands: 0, icon: 'i-lucide-shield-check', description: 'Cross-cutting quality gate. Every output reviewed before delivery.' }
]
</script>

<template>
  <div>
    <UPageHero>
      <template #title>
        <span class="text-primary">17 Departments</span>
      </template>
      <template #description>
        Every business domain covered by specialized agents with enterprise workflows.
      </template>
    </UPageHero>

    <UContainer class="py-12">
      <div class="space-y-4">
        <UCard
          v-for="dept in departments"
          :key="dept.prefix"
          variant="outline"
          :ui="{ root: 'hover:border-primary/30 transition-colors' }"
        >
          <div class="flex items-start gap-4">
            <div class="p-3 rounded-lg bg-primary/10 shrink-0">
              <UIcon :name="dept.icon" class="size-6 text-primary" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-1">
                <h2 class="text-lg font-bold text-default">{{ dept.name }}</h2>
                <code class="font-mono text-xs text-primary bg-primary/10 px-2 py-0.5 rounded">{{ dept.prefix }}</code>
              </div>
              <p class="text-sm text-muted mb-3">{{ dept.description }}</p>
              <div class="flex gap-4 text-xs text-muted font-mono">
                <span>{{ dept.agents }} agents</span>
                <span>Lead: {{ dept.lead }}</span>
                <span v-if="dept.commands > 0">{{ dept.commands }} commands</span>
              </div>
            </div>
            <UButton label="Docs" variant="ghost" size="xs" :to="`/docs/departments/${dept.prefix.slice(1)}`" />
          </div>
        </UCard>
      </div>
    </UContainer>
  </div>
</template>
```

- [ ] **Step 3: Create community page**

Create `app/pages/community.vue`:
```vue
<script setup lang="ts">
useSeoMeta({
  title: 'Community',
  description: 'Join the ArkaOS community — Discord, GitHub, newsletter, and showcase.'
})
</script>

<template>
  <div>
    <UPageHero>
      <template #title>
        Join the <span class="text-primary">community</span>
      </template>
      <template #description>
        ArkaOS is built in the open. Contribute, learn, and grow with us.
      </template>
    </UPageHero>

    <UContainer class="py-12 space-y-12">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <UCard variant="outline">
          <div class="space-y-4">
            <UIcon name="i-simple-icons-discord" class="size-10 text-primary" />
            <h2 class="text-xl font-bold text-default">Discord</h2>
            <p class="text-muted">Real-time chat with the ArkaOS team and community. Get help, share what you're building, propose features.</p>
            <UButton label="Join Discord" color="primary" to="#" target="_blank" icon="i-simple-icons-discord" />
          </div>
        </UCard>

        <UCard variant="outline">
          <div class="space-y-4">
            <UIcon name="i-simple-icons-github" class="size-10 text-primary" />
            <h2 class="text-xl font-bold text-default">GitHub</h2>
            <p class="text-muted">Star the repo, report issues, submit pull requests. ArkaOS is 100% open source — every contribution matters.</p>
            <UButton label="View Repository" color="primary" to="https://github.com/andreagroferreira/arka-os" target="_blank" icon="i-simple-icons-github" />
          </div>
        </UCard>
      </div>

      <UCard variant="outline">
        <div class="text-center space-y-4 py-4">
          <UIcon name="i-lucide-mail" class="size-10 text-primary mx-auto" />
          <h2 class="text-xl font-bold text-default">Newsletter</h2>
          <p class="text-muted max-w-lg mx-auto">Monthly updates on new departments, agents, features, and community highlights.</p>
          <div class="flex gap-2 max-w-sm mx-auto">
            <UInput placeholder="you@email.com" size="lg" class="flex-1" />
            <UButton label="Subscribe" color="primary" size="lg" />
          </div>
        </div>
      </UCard>
    </UContainer>
  </div>
</template>
```

- [ ] **Step 4: Create about page**

Create `app/pages/about.vue`:
```vue
<script setup lang="ts">
useSeoMeta({
  title: 'About',
  description: 'ArkaOS is built by WizardingCode — an operating system for AI agent teams.'
})
</script>

<template>
  <div>
    <UPageHero>
      <template #title>
        About <span class="text-primary">ArkaOS</span>
      </template>
      <template #description>
        Built by WizardingCode. Powered by the community.
      </template>
    </UPageHero>

    <UContainer class="py-12 max-w-3xl space-y-8">
      <div class="prose prose-invert max-w-none">
        <h2>The Problem</h2>
        <p>AI coding assistants are powerful but limited to one domain: writing code. Running a business requires strategy, marketing, finance, operations, brand, content, and more. You end up juggling dozens of tools with zero coordination.</p>

        <h2>The Solution</h2>
        <p>ArkaOS organizes 65 specialized AI agents into 17 departments — each with enterprise workflows, quality gates, and framework-backed knowledge. One command interface routes your request to the right team.</p>

        <h2>WizardingCode</h2>
        <p>ArkaOS is the flagship product of WizardingCode, a software company based in Portugal. We build AI-powered tools for developers and businesses.</p>
      </div>
    </UContainer>
  </div>
</template>
```

- [ ] **Step 5: Verify all marketing pages render**

```bash
pnpm dev
```

Visit `/features`, `/departments`, `/community`, `/about` — all should render with the marketing layout.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add marketing pages — features, departments, community, about

- Features page with 9 capability cards
- Departments page with all 17 departments detailed
- Community page with Discord, GitHub, newsletter
- About page with mission and WizardingCode info"
```

---

## Task 10: SEO, llms.txt, and Schema.org

**Files:**
- Create: `public/llms.txt`
- Create: `public/llms-full.txt`
- Create: `public/robots.txt`

- [ ] **Step 1: Create llms.txt for AI crawlers**

Create `public/llms.txt`:
```
# ArkaOS — The Operating System for AI Agent Teams

> 65 agents. 17 departments. 244+ skills. Multi-runtime.

ArkaOS organizes specialized AI agents into business departments with enterprise workflows, quality gates, and framework-backed knowledge. Install with `npx arkaos install`.

## Documentation
- Getting Started: https://arkaos.dev/docs/getting-started/installation
- Architecture: https://arkaos.dev/docs/concepts/architecture
- Departments: https://arkaos.dev/docs/departments
- Agents: https://arkaos.dev/docs/agents

## Links
- Website: https://arkaos.dev
- GitHub: https://github.com/andreagroferreira/arka-os
- Full docs: https://arkaos.dev/llms-full.txt
```

- [ ] **Step 2: Create robots.txt**

Create `public/robots.txt`:
```
User-agent: *
Allow: /

Sitemap: https://arkaos.dev/sitemap.xml
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: add SEO assets — llms.txt, robots.txt

- llms.txt for AI crawler discoverability
- robots.txt with sitemap reference
- @nuxtjs/seo handles sitemap, og-image, schema.org"
```

---

## Task 11: Deployment Configuration

**Files:**
- Create: `wrangler.toml` (Cloudflare Pages config)
- Modify: `.gitignore`

- [ ] **Step 1: Finalize .gitignore**

Ensure `.gitignore` includes:
```
node_modules
.nuxt
.output
dist
.data
content/docs/3.departments/
content/docs/4.agents/
content/docs/5.skills/
.superpowers/
.env
```

- [ ] **Step 2: Create GitHub repository and push**

```bash
cd ~/Work/arkaos-site
gh repo create andreagroferreira/arkaos-site --public --source=. --push
```

- [ ] **Step 3: Verify build succeeds locally**

```bash
pnpm generate-docs && pnpm build
```

Expected: Build completes without errors. Output in `.output/`.

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "chore: add deployment config and finalize project

- Cloudflare Pages compatible Nitro preset
- .gitignore for generated docs and build output
- Build pipeline: generate-docs → nuxt build"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Scaffold + base config | `nuxt.config.ts`, `main.css`, `app.config.ts` |
| 2 | Layouts + core components | `layouts/`, `AppHeader`, `AppFooter`, `AppLogo` |
| 3 | Homepage hero + terminal | `HomeHero`, `TerminalAnimation` |
| 4 | Homepage sections 2-5 | Problem, Solution, HowItWorks, Departments |
| 5 | Homepage sections 6-9 | Comparison, Numbers, Community, FinalCTA |
| 6 | Docs infrastructure | `[...slug].vue`, initial docs, docs layout |
| 7 | Auto-generation script | `scripts/generate-docs.mjs` |
| 8 | Blog infrastructure | Blog listing, post page, sample post |
| 9 | Marketing pages | Features, Departments, Community, About |
| 10 | SEO assets | `llms.txt`, `robots.txt` |
| 11 | Deployment | GitHub repo, build verification |
