# 06 · Cognitive Layer

← [Home](Home.md)

The Cognitive Layer is ArkaOS's institutional memory system. It captures what
the system learns in every session, reflects on that work each night, and
surfaces relevant intelligence each morning — so every day of use compounds on
the last.

It was introduced in v2.10 and runs automatically after install. No manual
configuration is required for the defaults.

---

## Overview

Three components form the Cognitive Layer:

| Component | When it runs | What it does |
|---|---|---|
| **Institutional Memory** | Continuously | Dual-writes every session's decisions and deliverables to Obsidian and the vector DB |
| **Dreaming** | 02:00 daily | Self-critique, pattern detection, anti-pattern flagging, strategic reflection |
| **Research** | 05:00 daily | Stack-aware, domain-aware, business-aware morning intelligence briefing |

All three are orchestrated by the cross-platform scheduler.

---

## Institutional Memory

Every solution, decision, and deliverable produced in an approved session is
captured and indexed. The write is dual:

- **Obsidian** — a human-readable note at a vault path chosen by the
  cataloger, with frontmatter, tags, and bidirectional wikilinks. You can open
  it, edit it, and link it to other notes like any other Obsidian note.
- **Vector DB** — the same content chunked and embedded for semantic search.
  Future sessions retrieve it via Synapse L2.5 before the model starts
  planning.

This pairing matters: Obsidian keeps knowledge legible and navigable by a
human; the vector DB makes it retrievable by the system at prompt time without
any manual recall step.

### Cross-project retention

Knowledge is not siloed per project. A pattern validated in one client project
is available to all others. Patterns confirmed across three or more sessions
are promoted to "validated" status and carry higher retrieval weight.

### Confidence scoring

| Status | Condition |
|---|---|
| Provisional | Appeared in 1–2 sessions |
| Validated | Confirmed 3+ times, promoted by Dreaming |
| Anti-pattern | Flagged by Dreaming for repeated failure |

---

## Dreaming (02:00)

Dreaming is an autonomous nightly review. It reads the day's session records
and runs four passes:

| Pass | What it asks |
|---|---|
| **Self-critique** | Was this the best approach? Was there a simpler path? |
| **Pattern detection** | Is this solution recurring? Promote it to a validated pattern. |
| **Anti-pattern detection** | Is this mistake recurring? Flag it for active avoidance. |
| **Strategic reflection** | Does this serve the business, or only the developer's immediate task? |

The output is a set of actionable reflections attached to the relevant project.
The next time you open that project ArkaOS surfaces them before you ask:

```
Pending reflections from Dreaming:

1. [business] Offer model — rethink
   The offers table doesn't consider volume pricing tiers.
   Shopify B2B uses min_qty + tier_price for 23% higher conversion.

2. [technical] Sync retry — improve
   Fixed backoff can cause thundering herd. Use exponential
   backoff with jitter (validated pattern from ClientRetail).

Want me to elaborate?
```

Dreaming does not block your session. Reflections are advisory; you decide
whether to act on them.

---

## Research (05:00)

Research runs before you start work and produces an intelligence briefing
scoped to your active projects. The system infers your profile from
`.arkaos.json` files — no manual configuration needed.

Three awareness lenses:

| Lens | What it covers |
|---|---|
| **Stack-aware** | Security patches, migration guides, releases relevant to your frameworks |
| **Domain-aware** | Industry news and trends for the domains your projects operate in |
| **Business-aware** | Competitor moves, market shifts, funding trends |

A briefing looks like this:

```
Intelligence Briefing — 2026-04-10

ACTION REQUIRED:
- Laravel 12.1.3 security patch — SQL injection in whereHas.
  Affects: two active projects. Fix: composer update laravel/framework.

OPPORTUNITIES:
- Shopify Winter '26 bulk product API — sync could be 10x faster.
- Nuxt 4 RC2 migration guide published — start preparing.

COMPETITOR WATCH:
- CrewAI v3 launched memory layer — similar to our Cognitive Layer
  but without dual-write. ArkaOS is ahead.
```

Items marked ACTION REQUIRED surface first; the rest are informational. The
briefing is written to the vault so it accumulates as a searchable record.

---

## Cross-Platform Scheduler

The scheduler installs during `npx arkaos install` and creates the appropriate
system job for your platform (launchd on macOS, cron on Linux, Task Scheduler
on Windows).

```bash
arkaos scheduler status         # Check whether Dreaming and Research are registered
arkaos scheduler run dreaming   # Trigger Dreaming manually (useful after a heavy day)
arkaos scheduler run research   # Trigger Research manually
arkaos scheduler logs           # View execution logs
```

Manual triggering is useful when you want an immediate reflection after a long
session, or when you want a briefing mid-day after pulling in a new project.

---

## What the system writes, and where

The Cognitive Layer stores material in two places:

| Store | Path | Format |
|---|---|---|
| Obsidian vault | Varies by note type — see [Knowledge Base](09-Knowledge-Base.md) | Markdown with frontmatter |
| Vector DB | `~/.arkaos/knowledge/` (sqlite-vss) | Embedded chunks |

The vault paths are determined by the cataloger according to the note type
taxonomy. See [09 · Knowledge Base](09-Knowledge-Base.md) for the full
taxonomy table.

---

## Relationship to the Intelligence Loop

The Cognitive Layer provides the **memory** half of the system. The
[Intelligence Loop](07-Intelligence-Loop.md) provides the **retrieval and
write-back** wiring that makes memory useful at prompt time. They are
complementary: the Cognitive Layer decides *what to remember* and *when to
reflect*; the Intelligence Loop decides *when to inject* and *how to write
back*.

---

Related: [07 · Intelligence Loop](07-Intelligence-Loop.md), [09 · Knowledge Base](09-Knowledge-Base.md), [Home](Home.md)
