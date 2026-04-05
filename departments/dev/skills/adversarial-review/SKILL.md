---
name: dev/adversarial-review
description: >
  Adversarial code review with 3 hostile personas: Saboteur, New Hire,
  Security Auditor. Finds edge cases, race conditions, and abuse vectors.
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Adversarial Review — `/dev adversarial-review`

> **Agent:** Bruno (Security Engineer) | **Framework:** Adversarial Testing, Threat Modeling, OWASP

## The 3 Personas

### Persona 1: The Saboteur
**Mindset:** "I am trying to break this code in production."

| Check | Question |
|-------|---------|
| Input | What is the worst input I could send this? |
| External calls | What if this fails, times out, or returns garbage? |
| State mutation | What if this runs twice? Concurrently? Never? |
| Conditionals | What if neither branch is correct? |
| Resources | File handles, connections, listeners leaking? |
| Boundaries | Off-by-one? Integer overflow? Null dereference? |

### Persona 2: The New Hire
**Mindset:** "I just joined. I must understand and modify this in 6 months."

| Check | Question |
|-------|---------|
| Naming | Does the name communicate intent? What does `data` mean? |
| Complexity | How many files do I need to read to understand this? |
| Magic values | Unexplained constants, magic numbers or strings? |
| SRP | Does this function do more than one thing? |
| Types | Missing type info that forces call-chain tracing? |
| Conventions | Inconsistent with surrounding code style? |
| Tests | Testing implementation details instead of behavior? |

### Persona 3: The Security Auditor
**Mindset:** "This code will be attacked."

| Category | What to Look For |
|----------|-----------------|
| Injection | SQL, NoSQL, OS command -- user input in query/command? |
| Auth | Hardcoded credentials? Missing auth on endpoints? |
| Data exposure | Sensitive data in logs, errors, API responses? |
| Insecure defaults | Debug mode on? Permissive CORS? Wildcard permissions? |
| Access control | IDOR? Missing role checks? Privilege escalation? |
| Dependencies | New deps with known CVEs? Unnecessary transitive deps? |
| Secrets | API keys, tokens, passwords in code or config? |

## Severity Classification

| Severity | Definition | Action |
|----------|-----------|--------|
| CRITICAL | Data loss, security breach, or production outage | Block merge |
| WARNING | Edge case bugs, performance issues, maintainability | Fix or accept with justification |
| NOTE | Style, minor improvement, documentation gap | Author's discretion |

**Promotion rule:** Finding flagged by 2+ personas is promoted one severity level.

## Review Workflow

| Step | Action |
|------|--------|
| 1 | Gather changes (git diff or specified files) |
| 2 | Read full file context (not just changed lines) |
| 3 | Run all 3 personas sequentially (each MUST find >= 1 issue) |
| 4 | Deduplicate findings; promote cross-persona matches |
| 5 | Produce verdict: BLOCK / CONCERNS / CLEAN |

## Self-Review Trap Breakers

- [ ] Read code bottom-up (last function first)
- [ ] State each function's contract BEFORE reading body
- [ ] Assume every variable could be null/undefined
- [ ] Assume every external call will fail
- [ ] Ask: "If I deleted this change, what would break?"

## Verdicts

| Verdict | Condition | Merge? |
|---------|-----------|--------|
| BLOCK | 1+ CRITICAL findings | No -- resolve first |
| CONCERNS | 0 critical, 2+ warnings | At your own risk |
| CLEAN | Only notes | Safe to merge |

## Proactive Triggers

Surface these issues WITHOUT being asked:

- Race condition in concurrent operations → flag data corruption risk
- Unbounded input without limits → flag DoS vector
- Error messages exposing internals → flag information leakage

## Output

```markdown
## Adversarial Review: <scope>

**Scope:** [files reviewed, lines changed, change type]
**Verdict:** BLOCK / CONCERNS / CLEAN

### Critical Findings
- [C1] [Persona] <file>:<line> -- <issue>
  Fix: <recommendation>

### Warnings
- [W1] [Persona] <file>:<line> -- <issue>

### Notes
- [N1] [Persona] <issue>

### Summary
[2-3 sentences: risk profile + single most important fix]
```
