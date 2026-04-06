---
name: dev/tdd-cycle
description: >
  Test-Driven Development using Kent Beck's Red-Green-Refactor cycle.
  Write failing test first, minimal code to pass, then refactor.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# TDD Cycle — `/dev test <scope>`

> **Agent:** Rita (QA) + Andre/Diana (implementation)
> **Framework:** TDD Red-Green-Refactor (Kent Beck)

## The Cycle

```
RED → Write a test that fails (defines desired behavior)
  ↓
GREEN → Write the MINIMUM code to make the test pass
  ↓
REFACTOR → Improve the code while keeping tests green
  ↓
REPEAT
```

## Rules (NON-NEGOTIABLE)

1. Never write production code without a failing test
2. Write only enough test to fail (one assertion)
3. Write only enough code to pass the failing test
4. Refactor only when all tests are green

## Testing Pyramid

| Level | Proportion | Speed | What to test |
|-------|-----------|-------|-------------|
| Unit | 70% | Fast | Pure functions, business logic, calculations |
| Integration | 20% | Medium | API endpoints, DB queries, service interactions |
| E2E | 10% | Slow | Critical user journeys only |

## Test Quality Criteria

- **Coverage:** >= 80% (measured, not guessed)
- **FIRST:** Fast, Independent, Repeatable, Self-validating, Timely
- **No mocking of what you own** — Mock external services, not your own classes
- **Test behavior, not implementation** — Tests should survive refactoring

## Stack-Specific

| Stack | Framework | Command |
|-------|-----------|---------|
| Laravel | PHPUnit + Pest | `php artisan test` |
| Vue/Nuxt | Vitest | `npx vitest` |
| React/Next | Jest | `npx jest` |
| Python | pytest | `python -m pytest` |
| E2E | Playwright | `npx playwright test` |

## Browser Steps

Follow the [Browser Integration Pattern](/arka) for availability checking.

- [BROWSER] After tests pass, if web app: open localhost in browser and verify the feature works visually
- [BROWSER] Check console for runtime errors that tests might not catch

## Computer Use Steps

Follow the [Computer Use Availability Check](/arka) for availability checking.

- [COMPUTER] If native/mobile app: build, launch, and verify feature in the running app or iOS Simulator
