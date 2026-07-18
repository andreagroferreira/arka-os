---
paths:
  - "**/*.tsx"
  - "**/*.jsx"
---

## React / Next.js Stack Conventions

- TypeScript everywhere; no plain JSX files.
- Server Components by default; `"use client"` only when interaction demands it.
- App Router (`app/`); no new Pages Router code.
- shadcn/ui + Tailwind for UI primitives.
- Hooks for shared logic; no HOC or render-prop patterns in new code.
- Co-locate component, styles, and test; PascalCase component files.
