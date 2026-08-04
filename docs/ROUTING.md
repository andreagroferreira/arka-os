# ArkaOS Routing

> How a request becomes a department squad, a command, and an execution —
> the routing contract. Single source of the contract:
> `.arkaos/specs/skill-invocation-contract.yaml` (spec-driven, approved).

Every request routes through a department squad. ArkaOS never responds
as a generic assistant. Routing happens in three stages:

1. **Resolve** — what does the user want? (`/do` + Synapse layers)
2. **Invoke** — which hub skill runs? (the skill-invocation contract)
3. **Learn** — was the route right? (routing scores, redo-risk)

## Stage 1 — Resolve: Synapse layers

`core/synapse/engine.py` runs 12 context layers in priority order
(<100 ms target; ~87 ms cold, ~83 ms warm). Each layer injects context
or a hint; empty layers are skipped:

| Layer | What it injects |
|---|---|
| L0 Constitution | Governance rules from `config/constitution.yaml` |
| L1 Department | Detected department via keyword/prefix matching (`DepartmentLayer`) |
| L2 Agent | Active agent profile (behavioral DNA YAML) |
| L2.5 KB context | Vector-store retrieval (Jaccard fallback on the Obsidian vault) |
| L2.6 AgentExperiences | Past Quality Gate lessons for the dispatched specialist |
| L2.7 Graphify | Code-graph grounding nodes (when configured) |
| L3 Project | `.arkaos.json` stack info (framework, language, version) |
| L4 Branch | Current git branch name and context |
| L5 CommandHints | Matched skills/commands from input analysis — **the routing hint** |
| L5.5 RoutingFeedback | `[arka:redo-risk]` from `~/.arkaos/routing-scores.json` |
| L6 QualityGate | Current QG status and recent verdicts |
| L7.5 PatternLibrary | Prior PatternCards matching prompt keywords |
| L8 ForgeContext | Active Forge plan decisions, risks, rejected approaches |
| L9 SessionMemory | Restored session context from the memory store |

The `/do` orchestrator (`arka/SKILL.md`, `/do <description>`) resolves
natural language to a department + command. When `/do` resolves to a
skill that is not installed, it degrades to the curated default surface
with a visible note.

## Stage 2 — Invoke: routing IS tool invocation

Announcing a squad in prose is **not** routing. The contract
(`skill-invocation-contract.yaml`, PR-A4, enforced across 4 prompt
surfaces) requires an actual hub-skill invocation:

- SessionStart injects `ARKA:SKILL-CONTRACT` as systemMessage —
  "routing IS tool invocation; announcing in prose without invoking is
  not routing".
- L5 emits an **imperative** skill hint: `[arka:skill-hint]
  Skill(arka-dev) -> /dev feature`. No legacy `[hint:` tags.
- Department → hub mapping: `mkt → marketing`, `fin → finance`,
  `strat → strategy`, `lead → leadership`, `arka → arka`,
  `do → arka`; unknown departments fall back to `arka-<dept>` and never
  raise. A structural test proves all 17 registry departments resolve to
  existing hubs.
- CLI.md and CLAUDE.md carry the same contract in tool form.

## Stage 3 — Learn: routing scores

Two feedback loops close the routing cycle:

- **F1-B1 aggregator** turns Quality Gate / judge verdicts into
  `~/.arkaos/routing-scores.json` per department: approvals/samples over
  a 90-day window with smoothed score.
- **F1-B2 / L5.5** reads those scores and injects
  `[arka:redo-risk] <department>: <approvals>/<samples> approved (90d,
  smoothed <score>)` — a non-blocking warning when a department has a
  high redo rate, so the operator can tighten the brief instead of
  burning a gate cycle.

## The 4-gate evidence flow

Routing is the first gate. Every non-trivial request then runs the
canonical 4-gate flow (G1 CONTEXT → G2 PLAN → G3 EXECUTE → G4 REVIEW,
see `arka/skills/flow/SKILL.md` and `docs/ARCHITECTURE.md`), with the
Quality Gate as an absolute-veto review layer on every workflow.

## Read further

- `core/synapse/engine.py` + `core/synapse/layers.py` — the engine
- `.arkaos/specs/skill-invocation-contract.yaml` — the contract
- `core/synapse/routing_feedback_layer.py` — the learning loop
- `docs/COMMANDS.md` — the full command surface
