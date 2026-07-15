---
name: pr-test-analyzer
description: >
  Judges whether a PR's tests would catch the change breaking — maps
  changed code to its tests, finds untested paths and edge cases, flags
  assertion-free and flaky tests, and ranks the gaps by blast radius.
  TRIGGER: "/dev pr-test-analyzer", "test coverage of this PR", "are these
  tests enough", "behavioural coverage", "test gaps", "os testes cobrem
  isto?", "isto está bem testado?"; run on a diff before approving its
  merge. SKIP: general code review -> dev/code-review wins; writing the
  missing tests -> dev/tdd-cycle wins; error-handling review ->
  dev/silent-failure-hunter wins.
metadata:
  origin: arkaos
---

# PR Test Analyzer

> **Agent:** Rita (QA Engineer) | **Framework:** Behavioural coverage, test-quality over line-coverage

Coverage is a measure of which lines ran, and it is routinely mistaken for
a measure of whether the change is safe. A PR can add a feature, run every
new line through one happy-path test that asserts almost nothing, and post
a green 100%. This lens reads the diff and its tests side by side and holds
them to the only standard that matters at merge time: if the change were
wrong, would a test go red?

## Analysis

### 1. Map changed code to tests
- List the functions, classes, and branches the diff added or altered.
- Locate the tests that exercise each. Name the changed paths with **no** test.

### 2. Behavioural coverage
- Does each new behaviour have a test that would fail if the behaviour broke?
- Are the edge cases covered — empty input, boundary values, the error path, not just the success path?
- Are the integrations the change touches (db, queue, external call) exercised, or only mocked away?

### 3. Test quality
- Flag tests that assert nothing beyond "it did not throw" — a green test that proves nothing.
- Flag flaky patterns: time/order dependence, shared mutable state, sleeps.
- Check that test names describe the behaviour, so a failure reads as a spec.

### 4. Rank the gaps
Rate each gap by the blast radius of the bug it would let ship:
critical (data loss, auth, money), important (a real feature path),
nice-to-have (a defensive branch unlikely to trigger).

## Proactive Triggers

Surface these WITHOUT being asked:

- a changed function with no test at all → critical or important by its blast radius; name it
- a new test with no assertion (or only `assert not raises`) → it proves nothing; say what it should assert
- an error/exception path added in the diff with only the happy path tested → the failure that ships untested

## Output

```markdown
## PR Test Report

**Diff:** {files / functions changed}
**Verdict:** {tests adequate to merge? yes / gaps below}

### Coverage summary
{what is covered well, in one or two lines}

### Critical gaps
- {file}:{func} — {the behaviour with no failing test} → {the test to add}

### Test-quality issues
- {file}:{test} — {assertion-free / flaky} → {fix}

### Positive
{what the tests do genuinely well}
```
