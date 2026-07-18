---
paths:
  - "app/**/*.php"
  - "routes/**/*.php"
  - "database/**/*.php"
  - "config/**/*.php"
  - "tests/**/*.php"
---

## Laravel Stack Conventions

- Services + Repositories pattern; no logic in controllers.
- Form Requests for all input validation.
- API Resources for response shaping.
- Feature Tests with RefreshDatabase trait.
- Eloquent relationships over raw joins.
- Policies for authorization; never inline ability checks.
- Queued jobs for slow work; never block the request cycle.
- Conventional commits: `feat(scope): ...`, `fix(scope): ...`.
