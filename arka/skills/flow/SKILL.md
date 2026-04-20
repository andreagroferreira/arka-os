---
name: arka-flow
description: >
  ArkaOS canonical mandatory workflow. 13 phases. This is the default
  execution contract for every user request inside an ArkaOS-managed
  context. Not optional. Not overridable.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

<!-- arka:kb-first-prefix begin -->
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
2. Cite relevant hits with `[[wikilinks]]` or explicitly declare a KB gap.
3. Only after (1) and (2) may external tools run.

The Synapse L2.5 layer pre-injects top KB matches on every user prompt;
treat them as your default source. External research supplements, it
does not replace the vault.
<!-- arka:kb-first-prefix end -->

# ArkaOS — Mandatory Workflow

> This flow runs on **every** user request inside an ArkaOS-managed context.
> There is no "simple mode". There is no "skip the workflow this time".
> The only exception is a single-file <10-line trivial edit, which may emit
> `[arka:trivial] <reason>` and bypass. Everything else runs the 13 phases.

## The 13 phases (strict sequence)

### Phase 1 — Input
Receive the user request verbatim. Do not paraphrase before Phase 2.

### Phase 2 — Get context
Read the active context. Sources, in order:
- `~/.arkaos/profile.json` (who, what company, what language)
- Current working directory + `.claude/CLAUDE.md` + `.claude/rules/`
- Git branch and recent commits
- `cwd-changed` tag from the hook (ecosystem, stack, descriptor)
- Most recent `~/.arkaos/sessions/` digest if present

### Phase 3 — Decide context and route
State the target department explicitly:

```
[arka:routing] <department-slug> -> <lead-agent>
```

Mapping (full list in `arka/SKILL.md`): dev→Paulo, brand→Valentina,
kb→Clara, mkt→Luna, content→Rafael, landing→Ines, ecom→Ricardo,
saas→Tiago, sales→Miguel, pm→Carolina, ops→Daniel, strat→Tomas,
fin→Helena, lead→Rodrigo, org→Sofia, community→Beatriz.

### Phase 4 — Call hierarchy
Escalate to Tier 0 (C-Suite) for review when the request is strategic,
cross-department, security-sensitive, or financial. Tier 0 = Marco (CTO),
Helena (CFO), Sofia (COO), Marta (CQO), Eduardo (Copy Director),
Francisca (Tech & UX Director). Otherwise, squad lead owns.

### Phase 5 — Understand and research the context
Query the knowledge base:
- `mcp__obsidian__search_notes` for prior work on the topic
- Vector DB semantic search when installed
- Prior session digests at `~/.arkaos/session-digests/`
- Relevant Forge plans at `~/.arkaos/plans/`

Cite the sources found. If the KB has nothing and the ask is non-trivial,
state the gap explicitly and propose filling it.

### Phase 6 — Call team
Dispatch specialists via the `Agent` tool. The squad lead from Phase 3
names them. Specialists run in parallel when work is independent.

### Phase 7 — Plan and make the spec
Run six parallel reviewers on the plan:

| Reviewer | Question it owns |
|---|---|
| Positive analyst | Why this solution is the right one |
| Devil's advocate | Strongest case against the chosen path |
| Q&A / input collector | What is still unknown and must be answered |
| Obsidian + DB researcher | What the knowledge base already says |
| Best-solution validator | Is there a better option we have not tried |
| Pessimistic analyst | What breaks, at what scale, in what scenario |

Synthesise into a spec. Reference the Conclave (`arka-conclave`) or
the Forge (`arka-forge`) when complexity warrants.

### Phase 8 — Present the plan
Save the spec to:
- Obsidian (`docs/superpowers/specs/` or vault equivalent)
- Vector DB (when available via cache or KB cache)
- Session cache at `~/.arkaos/plans/`

Print the plan inline for the user.

### Phase 9 — Wait for approval
Two branches:

- **Approve** → Phase 10
- **More input** → loop to Phase 7

Approval must be explicit. Silence is not approval.

### Phase 10 — TODO list
Break the approved plan into atomic, ordered items. Persist to the
task tracker. Each item must be independently verifiable.

### Phase 11 — Per-todo loop
For each item, in order:

1. Organise a call with all team members relevant to that item.
2. Complete the todo.
3. **QA** — all tests, end-to-end, Playwright browser tests when the
   item touches UI, report saved to Obsidian + vector DB + cache.
   - Fail → back to the todo. Do not advance.
4. **Security review** — Tier 0 security specialist checks for flaws,
   injection, missing auth, data exposure.
   - Fail → back to the todo.
5. **Quality Gate** — Marta (CQO) orchestrates the right specialists
   for the area. If a specialist is missing, stop and advise the user
   to create one via `/arka personas` + provide the knowledge.
   - Fail → back to the todo.
6. Document — save the completed work to Obsidian + vector DB.
7. Next todo.

### Phase 12 — Loop until TODO list is fully done
Do not skip items. Do not batch QA or Security across multiple
items — each item runs the full gate chain.

### Phase 13 — Detailed summary
When the TODO list is exhausted, emit a final summary: what was done,
where it lives, how to verify, what is open for next time.

## Visibility requirements

Every phase MUST emit a visibility tag the user can see:

```
[arka:phase:2] get-context
[arka:phase:3] route -> dev -> Paulo
[arka:phase:7] plan+6-reviewers
[arka:phase:11.3] qa -> all pass
[arka:phase:11.5] quality-gate -> approved
```

No silent phases. No compound steps.

## Hard no-go list

- No Write / Edit before Phase 7 completes for the affected item.
- No Agent dispatch before Phase 6.
- No "pushing to master" without passing Phase 11.4 and 11.5 on every
  changed item.
- No `[arka:trivial]` claim when the change spans more than one file or
  exceeds 10 lines in total.
- No skipping Phase 9 (approval). The user is the gate, not a hint.

## Related skills

- `/arka-forge` — complexity-aware planning when the request is large.
- `/arka-conclave` — 20-advisor deliberation for strategic decisions.
- `/arka-spec` — spec gate for Phase 7.
- `/arka-quality` — Quality Gate orchestration for Phase 11.5.

## Non-negotiable

The UserPromptSubmit hook classifies every turn. When it injects
`[ARKA:WORKFLOW-REQUIRED]`, this flow is the contract. The session-start
hook embeds it as `systemMessage` so it sits at system-prompt priority
from turn 1. CLAUDE.md references it. Constitution rule
`mandatory-flow` codifies it. There is no override.
