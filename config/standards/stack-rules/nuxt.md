---
paths:
  - "**/*.vue"
  - "composables/**"
  - "pages/**"
  - "layouts/**"
  - "server/**"
  - "nuxt.config.*"
---

## Nuxt Stack Conventions

- Composition API only; no Options API.
- TypeScript everywhere; no plain JS Vue files.
- `composables/` for shared reactive logic.
- `useFetch`/`useAsyncData` for server-side data.
- `~` alias for project root imports.
- Server routes in `server/api/`; never fetch third parties from components.
- Tailwind for styling; avoid scoped styles unless necessary.
