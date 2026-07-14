---
name: clean-code-review
description: >
  Focused Clean Code (Uncle Bob) + SOLID sweep of a file or PR — naming,
  function size, nesting depth, dead code, god classes, dependency
  direction — reported as BLOCKER/WARNING/NOTE with scores. TRIGGER:
  "/dev clean-review", "clean code", "SOLID", "code smells", "god class",
  "naming review", "refactor review", "está limpo?", "verifica SOLID",
  "revê a qualidade do código", "isto viola SRP?". SKIP: full review that
  must also weigh tests, security, and a merge verdict -> dev/code-review wins;
  hunting bugs, race conditions, or attack vectors -> dev/adversarial-review wins;
  anything visual (UI, layout, brand compliance) -> brand/design-review wins.
---

# Clean Code Review

> **Agent:** Paulo (Tech Lead) | **Framework:** Clean Code + SOLID (Robert C. Martin)

## What It Does

Reviews a file or PR against Clean Code and SOLID principles. Returns a structured
report with issues categorized as BLOCKER, WARNING, or NOTE.

## Checklist

### Clean Code Checks
- [ ] **Meaningful names** — Variables, functions, classes reveal intent
- [ ] **Small functions** — Under 30 lines, one responsibility each
- [ ] **Max 3 nesting levels** — No arrow code
- [ ] **Max 3 parameters** — Use objects for more
- [ ] **No dead code** — Remove commented-out code, unused imports
- [ ] **No magic numbers** — Named constants instead
- [ ] **Command-Query Separation** — Functions either do something or return something
- [ ] **DRY** — No duplicated logic (3+ lines repeated = extract)
- [ ] **Self-documenting** — Code readable without comments explaining the "what"

### SOLID Checks
- [ ] **SRP** — Each class has one reason to change
- [ ] **OCP** — Extend via interfaces/abstractions, not modification
- [ ] **LSP** — Subtypes are substitutable for their base types
- [ ] **ISP** — No client depends on methods it doesn't use
- [ ] **DIP** — High-level modules depend on abstractions, not details

### Architecture Checks
- [ ] **Dependency Rule** — Dependencies point inward (domain doesn't import framework)
- [ ] **No business logic in controllers** — Controllers delegate to services
- [ ] **Repository pattern** — Data access abstracted from business logic

## Output Format

```markdown
## Clean Code Review: <file>

### BLOCKERS (must fix)
- [B1] `ClassName:lineN` — God class with 15 methods and 4 responsibilities
  Fix: Split into UserService, AuthService, NotificationService

### WARNINGS (should fix)
- [W1] `functionName:lineN` — Function is 45 lines (max: 30)
  Fix: Extract validation logic into validateInput()

### NOTES (nice to have)
- [N1] `variableName:lineN` — Name could be more descriptive
  Suggest: `userAccountBalance` instead of `bal`

### Summary
- SOLID score: 4/5 (ISP violation in UserInterface)
- Clean Code score: 7/10
- Nesting max: 2 (good)
- Longest function: 45 lines (needs split)
```
