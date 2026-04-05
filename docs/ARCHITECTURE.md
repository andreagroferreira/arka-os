# ArkaOS Architecture

## Data Flow

```
User Input
  |
  v
Bash Hook (user-prompt-submit-v2.sh)
  |
  v
Synapse Bridge (scripts/synapse-bridge.py)
  |
  v
Synapse Engine (9 layers, <200ms)
  |-- L0: Constitution (governance rules)
  |-- L1: Department (detected from input)
  |-- L2: Agent (active agent profile)
  |-- L3: Project (stack, config)
  |-- L3.5: Knowledge Retrieval (vector DB search)
  |-- L4: Branch (git branch)
  |-- L5: Command Hints (matching commands)
  |-- L6: Quality Gate (status)
  |-- L7: Time (morning/afternoon/evening)
  |
  v
Context injected into Claude prompt
  |
  v
Claude responds with ArkaOS context
  |
  v
Output saved to Obsidian vault
```

## Core Systems

| System | Location | Purpose |
|--------|----------|---------|
| **Synapse** | `core/synapse/` | 9-layer context injection with caching |
| **Workflow Engine** | `core/workflow/` | YAML phases, gates, parallelization |
| **Agents** | `core/agents/` | 4-framework behavioral DNA schemas |
| **Squads** | `core/squads/` | Department + project teams (Team Topologies) |
| **Budget** | `core/budget/` | Token tracking per tier/department |
| **Knowledge** | `core/knowledge/` | Vector DB (sqlite-vss), chunking, embedding |
| **Obsidian** | `core/obsidian/` | Vault writer with frontmatter |
| **Orchestration** | `core/orchestration/` | 4 coordination patterns |
| **Personas** | `core/personas/` | Create and clone personas as agents |
| **Governance** | `core/governance/` | Constitution, quality gates |
| **Tasks** | `core/tasks/` | Background task queue with persistence |
| **Runtime** | `core/runtime/` | Multi-runtime adapters + subagent dispatch |
| **Specs** | `core/specs/` | Living specification system |

## Hook System

Claude Code hooks execute automatically on every interaction:

| Hook | When | What It Does |
|------|------|-------------|
| `user-prompt-submit-v2.sh` | Every prompt | Calls Synapse bridge for context injection |
| `post-tool-use-v2.sh` | After tool calls | Tracks error patterns in gotchas.json |
| `pre-compact-v2.sh` | Before compaction | Saves session digest |

## Workflow Execution

```
Workflow started (YAML definition)
  |
  v
Phase 1: Agent(s) execute
  |-> Budget check (if BUDGET_CHECK gate)
  |-> Agent produces output
  |-> Output saved to Obsidian
  |-> Gate evaluation (auto / user_approval / quality_gate)
  |
  v
Phase 2-N: Sequential execution with gates
  |
  v
Quality Gate (mandatory final phase)
  |-> Marta dispatches Eduardo (text) + Francisca (tech)
  |-> Both must APPROVE
  |-> REJECTED = loop back with issues
  |
  v
Delivery to user
```

## Orchestration Patterns

| Pattern | When to Use |
|---------|------------|
| Solo Sprint | Single department, fast delivery |
| Domain Deep-Dive | One agent, stacked skills for depth |
| Multi-Agent Handoff | Cross-department with structured handoffs |
| Skill Chain | Procedural pipeline, no agent identity |

## Dashboard

FastAPI backend (port 3334) + Nuxt 4 frontend (port 3333).

Start: `npx arkaos dashboard`
