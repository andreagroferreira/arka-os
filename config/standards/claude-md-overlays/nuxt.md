## Nuxt / Vue Stack Conventions

- Composition API only; no Options API.
- TypeScript everywhere; no plain JS Vue files.
- `composables/` for shared reactive logic.
- `useFetch`/`useAsyncData` for server-side data.
- `~` alias for project root imports.
- Tailwind for styling; avoid scoped styles unless necessary.
