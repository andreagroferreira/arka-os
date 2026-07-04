# 10 · The Quality Gate

← [Departments](04-Departments/) · [Home](Home.md)

Nothing reaches you without passing the Quality Gate. It is a NON-NEGOTIABLE
constitutional rule (`mandatory-qa`) and runs as Gate 4 (REVIEW) of the
evidence flow, with no exceptions. The verdict derives from executable
checks — linter, type-checker, test run, coverage report, security grep —
not from narrated approval.

---

## Who is on the gate

Three Tier-0 agents, all running on the **Opus** model (this is mandatory and
non-negotiable — quality review never runs on a cheaper model):

| Agent | Role | Reviews |
|---|---|---|
| **Marta** | CQO — Chief Quality Officer | Orchestrates the gate, issues the final verdict |
| **Eduardo** | Copy & Language Director | All text: spelling, grammar, tone, accents, zero AI clichés, cultural fit |
| **Francisca** | Technical & UX Director | All technical output: code, tests, UX/UI, data integrity, performance, security, API contracts |

Marta dispatches Eduardo and Francisca, collects their verdicts, and returns a
single binary result.

## The verdict

The gate is binary: **APPROVED** or **REJECTED**. There is no "approved with
minor issues that ship anyway". A REJECTED verdict sends the work back into the
loop — it does not advance to delivery.

```
Marta (CQO) orchestrating review of: <deliverable>
  ├─ Eduardo (Copy)      -> APPROVED | REJECTED + findings
  └─ Francisca (Tech/UX) -> APPROVED | REJECTED + findings

Verdict: APPROVED  ✔  (or REJECTED — back to the loop)
```

## What each reviewer enforces

### Eduardo — copy and language

- Correct spelling and grammar in the target language
- European Portuguese (pt-PT) when writing Portuguese — never Brazilian
- Full orthographic correctness — accents and diacritics never stripped
- Zero AI clichés ("delve", "in today's fast-paced world", "it's worth noting…")
- Consistent tone aligned to the brand voice
- A sycophancy detector flags pure-agreement openers and missing pushback

### Francisca — technical and UX

- SOLID and Clean Code (functions under 30 lines, max 3 nesting levels,
  self-documenting names, no dead code)
- Tests present and passing — the **entire** suite, never a subset
- Security reviewed (OWASP Top 10 where relevant)
- UX/UI quality, data integrity, performance, API contracts
- Zero tolerance for workarounds, hacks, or partial implementations

## Why it's structural, not optional

A single AI assistant reviews its own work only when it remembers to. ArkaOS
makes review a separate, adversarial step performed by different agents with
veto power. The author and the reviewer are never the same — which is exactly
how serious engineering organizations operate.

This is the same discipline used to build this very wiki: the foundation
(the canonical stats counter and benchmark suite) was reviewed by the Quality
Gate before anything was written on top of it.

## How it shows up in a response

Substantive turns end with a transparency line that includes the gate's
verdict:

```
[arka:meta] kb=3 research=none persona=Clara gap=none critic=passed
```

The `critic` field carries the self-critic verdict (`passed` / `failed` /
`skipped`); the full Quality Gate verdict is stated inline when a deliverable
is produced.

---

Related: [The Evidence Flow (4 Gates)](03-The-13-Phase-Flow.md) (the gate is Gate 4 REVIEW),
[Core Concepts](02-Core-Concepts.md) (the constitution and tiers).
