---
name: research
description: >
  Dev-scoped technical research (Lucas, Analyst): library evaluation,
  framework/package selection, code pattern comparison, and engineering
  best-practice discovery across three sources — Context7 for the
  documented contract, gh-grep for how public repos really implement it,
  and web research — ending in a trade-off report with a recommendation.
  TRIGGER: user types "/dev research", "avalia a biblioteca", "que
  lib/framework usamos", "compara X vs Y" for code dependencies,
  "library evaluation", "which package/ORM/framework should we use",
  "best practice" questions about implementation choices — load BEFORE
  adding a new dependency or committing to an architecture-relevant
  library.
  SKIP: general, market, or knowledge-base research whose deliverable
  is an Obsidian KB note, including "best practices for" a non-code
  topic — arka-research (/arka research, 5-source fan-out) wins;
  requirements definition — arka-dev-spec wins.
---

# Research

> **Agent:** Lucas (Analyst) | **Framework:** Context7 + gh-grep + Web Research

## What It Does

Research a technical topic: library evaluation, pattern comparison, best practice discovery.

## Three sources, three questions

Run all three before writing a recommendation. Each answers something the
others cannot, and a report built on one of them is a report with a blind spot.

| Source | Question it answers |
| --- | --- |
| Obsidian + Graphify | what WE already decided, and what it cost us |
| `mcp__context7__query-docs` | what the maintainer documents — the contract |
| `mcp__gh-grep__searchGitHub` | what N teams actually shipped — the practice |

The gap between the last two is often the finding itself: an API that is
documented one way and used another way in every real repo is telling you
where the sharp edge is.

### Querying gh-grep

It is literal grep with regex over public repos, not semantic search. Query
with **code tokens**; a sentence returns noise.

Evaluating a library — is this API actually used the way the README shows?

```
query: "unstable_cache(" · language: TypeScript
→ read the call-sites: which options do people really pass, what do they
  wrap, and what do they never do
```

Comparing two options — which one shows up in serious codebases?

```
query: "from pydantic import BaseSettings" · language: Python
query: "from pydantic_settings import BaseSettings" · language: Python
→ the ratio, and the migration commits between them, answer the version
  question faster than any changelog
```

Cite what you find with the repo path, and mark it as practice, not
contract. Where docs and practice disagree, the docs win in the
recommendation and the divergence goes in the risks section.

## Output

Research report with options, trade-offs, and recommendation
