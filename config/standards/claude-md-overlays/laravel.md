## Laravel Stack Conventions

- Services + Repositories pattern; no logic in controllers.
- Form Requests for all input validation.
- API Resources for response shaping.
- Feature Tests with RefreshDatabase trait.
- Eloquent relationships over raw joins.
- Conventional commits: `feat(scope): ...`, `fix(scope): ...`.
