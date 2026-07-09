---
name: arka-dreams
description: >
  User-facing surface for Dreaming v2, the nightly cognitive
  consolidation engine — lists insights ArkaOS surfaced from recent vault
  activity and session digests, filters by day window, promotes an
  insight into a /pm backlog item, or triggers a Dreaming pass manually;
  read-only over the vault. TRIGGER: "/arka dreams" (--since, --all,
  promote, trigger), "o que descobriste esta noite", "insights de
  ontem", "what did ArkaOS notice last night", "run a dreaming pass
  now". SKIP: one-off research questions -> arka-research (same fan-out
  pattern, different primitive); spend of the Dreaming backend ->
  arka-costs (this skill surfaces insights, not costs).
allowed-tools: [Read, Bash, Agent]
---

# /arka dreams — what ArkaOS noticed last night

> The motor without an ignition is a research demo. This skill is the
> ignition: it reads what Dreaming v2 wrote to the vault and surfaces
> it so the user can act.

## Subcommands

| Command | What it does |
| --- | --- |
| `/arka dreams` | List insights surfaced today (UTC-day, generous tolerance). |
| `/arka dreams --since 7` | Last N days of insights, newest first. |
| `/arka dreams --all` | Every insight ever surfaced (since the vault was indexed). |
| `/arka dreams promote <id>` | Convert an insight into a sprint backlog item. Delegates to `/pm` (Carolina). |
| `/arka dreams trigger` | Manually run a Dreaming pass *right now* instead of waiting for 02:00. Useful for end-to-end smoke tests after an install or a model swap. |

## How it works

```
1. Read insight files from ${VAULT_PATH}/Projects/ArkaOS/Dreams/*.md
2. Parse plugin-compat frontmatter (type: arkaos-insight)
3. Filter by --since window (default: today)
4. Render compact list:
       [date] [confidence] [title]
                sources: [[file1]], [[file2]]
                body: <first 200 chars>
5. Wait for follow-up: promote / discard / open
```

Insights are produced by `core/cognition/dreaming.py` running locally
on a schedule defined in `~/.arkaos/schedules.yaml` (default 02:00 user
time). The engine is backend-agnostic per the 2026-05-13 Conclave
Phase 4 correction — uses Claude Code by default, Ollama if the user
opts in via `cognitiveBackend: ollama` in `profile.json`.

## Cost & budget

Dreaming runs **once per night**, costs depend on the configured
backend:

- **Claude Code backend (default):** consumes the user's existing
  Claude session tokens (~3-10k tokens / night per 20 clusters).
- **Ollama backend (opt-in):** zero token cost, ~15-30 min compute
  on the user's machine.
- **Anthropic API backend:** per-call billing per the user's API key.

`/arka costs` surfaces the spend if Dreaming used a metered backend.
Variable Reward driver is the surprise of *what* ArkaOS surfaces, not
the cost of *running* the engine.

## Boundaries

- **Read-only over the vault.** This skill never writes to or deletes
  vault notes. Dreaming v2 writes, this skill only reads.
- **Promote handoff stays explicit.** `/arka dreams promote <id>`
  spawns a /pm backlog item — it does not act on the insight itself.
  The user is always the decision-maker.
- **No auto-dismiss.** Even insights the user ignores stay in the
  vault for future retrieval. Build the data moat.

## Cross-references

- Engine: `core/cognition/dreaming.py` (PR8 v2.30.0)
- Backend abstraction: `core/runtime/llm_provider.py`
- Strategy: [[2026-05-13-arkaos-local-personal-agi]]
- Memory: [[project_arkaos_local_personal_agi]]
- Companion skill: `/arka research` (one-off research) — different
  primitive, similar fan-out pattern
