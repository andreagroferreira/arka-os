# 00 · Glossary

← [Wiki Home](Home.md)

Every ArkaOS term, explained in plain language. If a page uses a word you do
not recognize, look it up here first.

## A

- **Agent** — a specialized AI persona with a role (e.g. "Tech Lead"), a
  behavioral profile, and a scope of authority. ArkaOS ships 89 agent
  definitions across 17 departments (88 unique — one role, `cro-specialist`,
  is shared by E-Commerce and Landing).
- **ADR (Architecture Decision Record)** — a dated, numbered document that
  records a significant technical decision, its context, and its
  consequences. ArkaOS keeps 19 in `docs/adr/`.
- **Approval gate** — a point in a workflow where the operator explicitly
  approves before work continues.

## B

- **Behavioral DNA** — the four frameworks that profile every agent: DISC
  (how they act), Enneagram (why they act), Big Five/OCEAN (how much of each
  trait), MBTI (how they process information). Kept in the agent's YAML file.

## C

- **Command** — a slash-command skill trigger such as `/dev feature` or
  `/mkt email-sequence`. 298 exist: 276 department commands plus 22 `/arka`
  meta commands.
- **Constitution** — the governance rulebook (`config/constitution.yaml`)
  with three enforcement levels: **NON-NEGOTIABLE** (6 rules, verifiable by
  evidence), **MUST** (28 rules), **SHOULD** (12 rules).
- **Core skills** — the 340 skills that ship in the repo: 325 department
  skills plus 15 `/arka` meta skills.
- **Curated skills** — the subset of department skills (42) hand-selected by
  department leads as their default working set; the rest are packed into
  plugins.
- **Cognitive Layer** — the system that gives ArkaOS institutional memory:
  session digests, nightly Dreaming passes, morning Research briefings.

## D

- **Department** — a domain squad with a lead agent, specialists, skills, and
  commands. 17 exist; 16 have a command prefix (Development `/dev`, Marketing
  `/mkt`, …) and the Quality Gate is cross-cutting.
- **Dreaming** — the nightly background process that consolidates the day's
  sessions into insights and knowledge-base entries.
- **Doctor** — `npx arkaos doctor`, the diagnostic that verifies your
  installation (Python, Node, hooks, Synapse, knowledge DB, agent/skill
  counts).

## E

- **Ecosystem** — a group of related projects (e.g. an API plus its frontend)
  managed together as one context.
- **Evidence Flow** — the canonical 4-gate handling of every non-trivial
  request: G1 context, G2 approved plan, G3 executed work with real test
  runs, G4 review. Replaced the old 13-phase flow. Single source of the full
  spec: `arka/skills/flow/SKILL.md`.
- **Excellence mandate** — a NON-NEGOTIABLE rule: every deliverable targets
  excellence, not acceptance; unfinished or default-quality work loops back
  instead of shipping.

## F

- **Forge** — the multi-agent planning engine that analyses a request across
  5 dimensions, dispatches explorer agents, and produces an approved plan
  before execution.
- **Framework** — an enterprise methodology an agent applies (e.g. StoryBrand
  for branding, ResearchXL for CRO, DCF for valuation). Agents cite the
  frameworks they use.

## H

- **Hook** — a script ArkaOS installs into your AI runtime's hook surface
  (SessionStart, UserPromptSubmit, PostToolUse, …) to inject context, run
  token-hygiene checks, and enforce gates.
- **Hub skill** — the department entry-point skill (`arka-dev`, `arka-brand`,
  …) that routes a request to the right squad. Routing is complete only when
  the hub skill is invoked.

## K

- **KB / Knowledge Base** — the Obsidian-vault-backed, vector-indexed store
  of everything ArkaOS learns: articles, transcripts, personas, and project
  knowledge. Searched automatically by Synapse.

## M

- **Marketplace skills** — 10 skills published as standalone installable
  packs beyond the core.
- **MCP (Model Context Protocol)** — the standard ArkaOS uses to connect AI
  tools to servers (Obsidian, ClickUp, Context7, Firecrawl, …). 35 servers
  ship in the registry.
- **Model Fabric** — the operator's role → model routing config
  (`~/.arkaos/models.yaml`); quality-critical work always runs the best model
  available. Fusion builds diverse review panels.
- **Meta skills / commands** — the 15 `/arka` skills (update, status,
  recipes, costs, dreams, …) and 22 `/arka` commands that operate ArkaOS
  itself rather than a business domain.

## P

- **Persona** — a callable advisor built from KB content (articles,
  transcripts) with a voice signature and behavioral DNA.
- **Plugin skills** — 259 non-curated department skills exported into
  installable packs (the "department packs"); curated skills stay in the core.
- **Preflight** — `npx arkaos preflight`, the mandatory release step that
  checks version alignment, auth, and remote state before any release.

## Q

- **Quality Gate** — the mandatory review every workflow passes through:
  Marta (CQO) orchestrates Eduardo (Copy & Language) and Francisca (Technical
  & UX), and issues a binary APPROVED/REJECTED verdict with absolute veto.
- **QG ledger / digests** — the recorded Quality Gate decisions and the
  periodic summaries that keep the team honest about what shipped and why.

## R

- **Recipe** — a validated, QG-approved feature build (files, acceptance
  criteria, apply notes) captured for reuse across projects.
- **Research** — the morning background pass that scans the knowledge base
  and feeds the day's context; also a general fan-out skill (`/arka
  research`).
- **Runtime** — the AI coding tool ArkaOS runs inside: Claude Code, Codex
  CLI, Gemini CLI, Cursor, OpenCode, and Zed/Copilot (6 supported).
- **Routing** — resolving a request to a department squad, announced as
  `[arka:routing] <dept> -> <lead>`. Routing IS tool invocation: the
  department hub skill must actually be called.

## S

- **Skill** — a packaged capability: a SKILL.md with instructions, tools, and
  workflow. Skills are how departments encode expertise.
- **Skill pack** — the curated core vs. plugin marketplace split that keeps
  context within budget while everything stays installable.
- **Squad** — a department team: lead + specialists, or an ad-hoc project
  squad in the matrix structure.
- **Synapse** — the 12-layer context-injection engine that grounds every
  request in project context, routing, and knowledge before the squad works.
- **Synapse L2.5** — the knowledge-base injection layer inside the
  Intelligence Loop.

## T

- **Tier** — authority level: Tier 0 C-Suite (veto), Tier 1 squad leads
  (orchestrate), Tier 2 specialists (execute), Tier 3 support.
- **Trivial bypass** — `[arka:trivial] <reason>`, the only allowed shortcut
  past the Evidence Flow, for a single-file edit under 10 lines.

## W

- **Workflow** — a YAML-defined process with phases, gates, and
  parallelization; every workflow ends in a Quality Gate phase.
