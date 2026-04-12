# ArkaOS v2 — The Operating System for AI Agent Teams

> 56 agents. 16 departments. ~180 commands. Multi-runtime. Framework-backed.

## Version

- **Current:** 2.0.0-alpha.1
- **Branch:** v2

## Identity

- **Product:** ArkaOS
- **Company:** WizardingCode
- **Owner:** Andre Groferreira
- **Purpose:** Orchestrate specialized AI agents across every business domain

## What Makes ArkaOS Different

No other framework covers all 4 layers with multi-domain support:

| Layer | ArkaOS |
|-------|--------|
| Spec Framework | Living Specs with bidirectional sync |
| Planning System | YAML workflow engine with phases and gates |
| Execution Agents | 56 agents across 16 domains (not just dev) |
| Runtime Engine | Claude Code, Codex CLI, Gemini CLI, Cursor |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Installer | Node.js/Bun (`npx arkaos install`) |
| Core Engine | Python (Pydantic, PyYAML) |
| CLI & Hooks | Bash |
| Workflows | YAML (declarative, version-controlled) |
| Agent Definitions | YAML (4-framework behavioral DNA) |
| Config | JSON |
| Knowledge | Obsidian |

## Department Commands

| Prefix | Department | Lead | Commands |
|--------|-----------|------|----------|
| `/do` | Universal Orchestrator | — | Natural language routing |
| `/dev` | Development | Paulo | 16 |
| `/mkt` | Marketing & Growth | Luna | 12 |
| `/brand` | Brand & Design | Valentina | 12 |
| `/fin` | Finance & Investment | Helena (CFO) | 10 |
| `/strat` | Strategy & Innovation | Tomas | 10 |
| `/ecom` | E-Commerce | Ricardo | 12 |
| `/kb` | Knowledge Management | Clara | 12 |
| `/ops` | Operations & Automation | Daniel | 10 |
| `/pm` | Project Management | Carolina | 12 |
| `/saas` | SaaS & Micro-SaaS | Tiago | 14 |
| `/landing` | Landing Pages & Funnels | Ines | 14 |
| `/content` | Content & Viralization | Rafael | 14 |
| `/community` | Communities & Groups | Beatriz | 14 |
| `/sales` | Sales & Negotiation | Miguel | 10 |
| `/lead` | Leadership & People | Rodrigo | 10 |
| `/org` | Organization & Teams | Sofia (COO) | 10 |

## Update & Sync System

### How Updates Work (2-step process)

| Step | Command | What it does |
|------|---------|-------------|
| 1 | `npx arkaos@latest update` | Downloads latest ArkaOS core, updates hooks, resets sync state |
| 2 | `/arka update` (inside Claude Code) | AI-powered sync of all project configs, MCP, settings, skills |

### Step 1: Core Update (terminal)

```bash
npx arkaos@latest update
```

This updates:
- Python dependencies
- Hook scripts (SessionStart, UserPromptSubmit, PostToolUse, PreCompact, CwdChanged)
- CLI wrapper (`arka-claude`)
- `/arka` skill
- Constitution and config files
- Resets sync state → triggers `[arka:update-available]` on next Claude session

### Step 2: Project Sync (Claude Code)

```
/arka update
```

This syncs all projects:
- Ecosystem skills (agent types, workflows)
- Project descriptors (stacks, status, paths)
- MCP configs (`.mcp.json` per project)
- Settings (`.claude/settings.local.json` per project)
- Generates sync report

### Auto-Detection

When core updates but projects aren't synced, the SessionStart hook shows:
```
[arka:update-available] Core vX.Y.Z != synced vX.Y.Z. Run /arka update.
```

### State file

`~/.arkaos/sync-state.json` — tracks version, last sync timestamp, project/skill counts, errors

## Agent Hierarchy

Inspired by SpaceX (flat, mission-driven), Google (matrix), Anthropic (small teams, safety embedded).

| Tier | Role | Agents | Authority |
|------|------|--------|-----------|
| 0 | C-Suite | Marco (CTO), Helena (CFO), Sofia (COO), Marta (CQO), Eduardo, Francisca | Veto |
| 1 | Squad Leads | 15 department leads | Orchestrate |
| 2 | Specialists | 35 domain experts | Execute |

## Model Routing

Per-tier default model assignment for cost optimization without quality loss:

| Tier | Model | Who |
|---|---|---|
| 0 | opus | C-Suite + Quality Gate (Marta, Eduardo, Francisca) |
| 1 | sonnet | 15 Squad Leads |
| 2 | sonnet | Specialists (default) |
| 2/3 | haiku | Mechanical roles (commit writers, routing, data fetchers) |

**Task-type overrides:**
- Quality Gate phases: ALWAYS opus (NON-NEGOTIABLE)
- Architecture/design/spec/ADR phases: opus
- Forge complex/super tiers: opus
- Commit messages, changelog, keyword extraction: haiku

When dispatching subagents, the orchestrator MUST pass the `model` parameter to the Task tool based on the agent's YAML `model:` field.

## Behavioral DNA (4 Frameworks per Agent)

Every agent has a complete behavioral profile:
- **DISC** — How they act (communication style)
- **Enneagram** — Why they act (core motivation, core fear)
- **Big Five/OCEAN** — How much of each trait (0-100 scale)
- **MBTI** — How they process information (cognitive functions)

Agent YAML files: `departments/*/agents/*.yaml`

## Constitution

`config/constitution.yaml` defines governance with 4 enforcement levels:

**NON-NEGOTIABLE (15 rules):** branch-isolation, obsidian-output, authority-boundaries, security-gate, context-first, solid-clean-code, spec-driven, human-writing, squad-routing, full-visibility, sequential-validation, mandatory-qa, arka-supremacy, context-verification, forge-governance

**QUALITY GATE:** Marta (CQO) orchestrates Eduardo (Copy) + Francisca (Tech). Absolute veto. Binary APPROVED/REJECTED. Runs on EVERY workflow.

**MUST (7 rules):** conventional-commits, test-coverage >= 80%, pattern-matching, actionable-output, memory-persistence, workflow-standard, forge-persistence

**SHOULD (4 rules):** research-first, self-critique, kb-contribution, complexity-assessment

## Core Systems

| System | Purpose | Code |
|--------|---------|------|
| **Synapse v2** | 8-layer context injection (<1ms, caching) | `core/synapse/` |
| **Workflow Engine** | YAML workflows with phases, gates, parallelization | `core/workflow/` |
| **Agent Schema** | 4-framework DNA with consistency validation | `core/agents/` |
| **Squad Framework** | Department + ad-hoc project squads (matrix) | `core/squads/` |
| **Subagent Pattern** | Fresh instances per task, ~379 token handoff | `core/runtime/subagent.py` |
| **Living Specs** | Bidirectional spec/code sync, deltas, patterns | `core/specs/` |
| **Governance** | Constitution, quality gates, audit trails | `core/governance/` |
| **Multi-Runtime** | Claude Code, Codex, Gemini, Cursor adapters | `core/runtime/` |
| **The Forge** | Multi-agent planning with complexity escalation | `core/forge/` |

## Workflows

Enterprise workflows (7-10 phases, for complex tasks):
- Every workflow has a Quality Gate phase (mandatory)
- User approval gates between key phases
- Parallel agent execution where independent
- Full visibility: every phase announced

Focused workflows (3-4 phases, for medium tasks).
Specialist workflows (1-2 phases, for simple tasks).

Workflow YAML files: `departments/*/workflows/*.yaml`

## Squad Routing (NON-NEGOTIABLE)

Every request routes through a department squad. ArkaOS never responds as a generic assistant. Plain text input is resolved via `/do` orchestrator.

Routing: Synapse L1 (keyword detection) + L5 (command hints) + hook context tags.

## Knowledge Base

16 areas of framework-backed knowledge:

1. Branding (Primal, StoryBrand, Archetypes)
2. Design (Nielsen, Atomic Design, Laws of UX)
3. Strategy (Porter, Blue Ocean, BMC, Wardley, 7 Powers)
4. Finance (Damodaran DCF, Unit Economics, COSO ERM)
5. Marketing (AARRR, Growth Loops, Schwartz, PLG, STEPPS)
6. GTM/Launch (Hormozi, Brunson, PLF, Crossing the Chasm)
7. Organization (Lencioni, Team Topologies, OKRs, Netflix Culture)
8. Development (SOLID, DDD, TDD, DORA, OWASP)
9. Project Management (Scrum, Kanban, Shape Up, Continuous Discovery)
10. Operations (Lean, Theory of Constraints, Automation)
11. E-Commerce (ResearchXL, RFM, MACH, Baymard)
12. Knowledge (Zettelkasten, BASB, SECI Model)
13. SaaS (PLG, T2D3, Micro-SaaS Playbook)
14. Landing Pages (AIDA, PAS, Value Ladder, Grand Slam Offer)
15. Communities (SPACES, Membership Economy, Platform Matrix)
16. Content (STEPPS, Hook Architecture, Content OS)

## Coding Standards

- **Laravel:** Services + Repositories, Form Requests, API Resources, Feature Tests
- **Vue/Nuxt:** Composition API only, TypeScript, composables
- **React/Next.js:** TypeScript, Server Components, App Router, shadcn/ui
- **Python:** Type hints, Pydantic, virtual environments
- **SOLID** (NON-NEGOTIABLE): SRP, OCP, LSP, ISP, DIP
- **Clean Code** (NON-NEGOTIABLE): Self-documenting names, no dead code, max 3 nesting, functions under 30 lines
- **Git:** Conventional commits, feature branches

## File Structure (v2)

```
arkaos/
├── CLAUDE.md                          # This file
├── CONSTITUTION.md                    # Governance (markdown, references YAML)
├── VERSION                            # 2.0.0-alpha.1
├── package.json                       # npm package
├── pyproject.toml                     # Python project
├── installer/                         # Node.js installer (npx arkaos install)
│   ├── cli.js                         # CLI entry point
│   ├── detect-runtime.js              # Auto-detect runtime
│   ├── index.js                       # Installation flow
│   └── adapters/                      # Runtime-specific adapters
├── core/                              # Python core engine
│   ├── agents/                        # Agent schema + validator + loader
│   ├── synapse/                       # 8-layer context injection
│   ├── workflow/                      # YAML workflow engine
│   ├── squads/                        # Squad framework
│   ├── specs/                         # Living Specs
│   ├── governance/                    # Constitution + quality gates
│   └── runtime/                       # Multi-runtime adapters + subagent
├── departments/                       # 16 departments + quality
│   ├── dev/                           # 9 agents, 16 commands
│   ├── marketing/                     # 4 agents, 12 commands
│   ├── brand/                         # 4 agents, 12 commands
│   ├── finance/                       # 3 agents, 10 commands
│   ├── strategy/                      # 3 agents, 10 commands
│   ├── ecom/                          # 4 agents, 12 commands
│   ├── kb/                            # 3 agents, 12 commands
│   ├── ops/                           # 2 agents, 10 commands
│   ├── pm/                            # 3 agents, 12 commands
│   ├── saas/                          # 3 agents, 14 commands
│   ├── landing/                       # 4 agents, 14 commands
│   ├── content/                       # 4 agents, 14 commands
│   ├── community/                     # 2 agents, 14 commands
│   ├── sales/                         # 2 agents, 10 commands
│   ├── leadership/                    # 2 agents, 10 commands
│   ├── org/                           # 1 agent, 10 commands
│   └── quality/                       # 3 agents (cross-cutting)
├── arka/                              # Main orchestrator
│   └── SKILL.md                       # /do routing, /arka commands
├── config/
│   └── constitution.yaml              # Constitution v2
├── knowledge/
│   └── agents-registry-v2.json        # Auto-generated from YAML
├── tests/
│   └── python/                        # 542 tests (pytest)
└── docs/                              # Documentation
```

## Release Pipeline

| Step | Command | Notes |
|------|---------|-------|
| 1. Bump version | Update `VERSION`, `package.json`, `pyproject.toml` | All three must match |
| 2. Commit | `git commit -m "chore: bump to vX.Y.Z"` | |
| 3. Push | `git push origin master` | |
| 4. GitHub release | `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."` | |
| 5. npm publish | `npm publish --access public` | Uses ~/.npmrc token |
| 6. Verify | `npm view arkaos version` | Must show new version |

**npm auth:** Token in `~/.npmrc` as `//registry.npmjs.org/:_authToken=<token>`. If 403, use temp config with `--userconfig`. Account: `wizardingcode`.

## How To Work

1. **Any request** → Routes through `/do` to the correct department
2. **Squad handles it** → Lead assigns, specialists execute, Quality Gate reviews
3. **Framework-backed** → Every action uses validated enterprise frameworks
4. **Output to Obsidian** → All deliverables saved to vault
5. **Quality Gate** → Nothing reaches user without APPROVED from Marta
