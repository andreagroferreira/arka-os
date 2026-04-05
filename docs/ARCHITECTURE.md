# ArkaOS Architecture

Technical deep-dive into how ArkaOS works. This covers the data flow, every core system, the hook lifecycle, Synapse context injection, workflow execution, the vector knowledge DB, and the dashboard stack.

## Complete Data Flow

Every interaction with ArkaOS follows this path:

```
You type something in your AI coding tool
       |
       v
[Hook] user-prompt-submit-v2.sh fires
       |
       v
[Bridge] scripts/synapse-bridge.py receives your input as JSON
       |
       v
[Synapse] 9-layer context engine runs (<200ms total)
       |-- L0: Constitution     --> governance rules from config/constitution.yaml
       |-- L1: Department       --> detected department from keyword/intent matching
       |-- L2: Agent            --> active agent profile (YAML behavioral DNA)
       |-- L3: Project          --> .arkaos.json stack info (framework, language, version)
       |-- L3.5: Knowledge      --> vector DB search for relevant indexed content
       |-- L4: Branch           --> current git branch name and context
       |-- L5: Command Hints    --> matched skills/commands from input analysis
       |-- L6: Quality Gate     --> current QG status (active/idle/reviewing)
       |-- L7: Time             --> time-of-day context (morning/afternoon/evening)
       |
       v
[Context] All layers merged into a context string
       |
       v
[Injection] Context string injected into the AI prompt as system context
       |
       v
[AI] Claude/Codex/Gemini/Cursor processes with full ArkaOS context
       |
       v
[Hook] post-tool-use-v2.sh tracks error patterns
       |
       v
[Output] Results saved to Obsidian vault with frontmatter
       |
       v
[Quality Gate] If workflow active, Marta/Eduardo/Francisca review
       |
       v
You receive the result
```

## Core Systems

### Synapse Engine (`core/synapse/`)

The context injection system. Runs on every prompt. Each layer is a Python module that produces a context fragment. Layers are cached and invalidated on change.

| File | Purpose |
|------|---------|
| `core/synapse/__init__.py` | Layer registry and orchestration |
| `core/synapse/engine.py` | Main engine: runs all layers, merges output, caches results |
| `core/synapse/layers/` | Individual layer implementations (L0-L7) |
| `core/synapse/cache.py` | Layer caching with TTL and invalidation |

How caching works: L0 (Constitution) and L2 (Agent) rarely change, so they cache for the session. L4 (Branch) and L7 (Time) refresh on every call. L3.5 (Knowledge) caches by query hash for 5 minutes.

Real output from the Synapse bridge:

```bash
echo '{"user_input":"fix the authentication bug in the login controller"}' | python scripts/synapse-bridge.py
```

```json
{
  "context_string": "[CONSTITUTION: branch-isolation, solid-clean-code, spec-driven...] [DEPT: dev] [AGENT: backend-dev-andre] [PROJECT: laravel 11.x, php 8.3] [KNOWLEDGE: 3 relevant notes found] [BRANCH: feat/auth-fix] [COMMANDS: /dev debug, /dev code-review, /dev security-audit] [QG: idle] [TIME: afternoon]",
  "layers": {
    "L0_constitution": {"ms": 2, "cached": true},
    "L1_department": {"ms": 8, "cached": false, "detected": "dev"},
    "L2_agent": {"ms": 3, "cached": true},
    "L3_project": {"ms": 5, "cached": true},
    "L3.5_knowledge": {"ms": 89, "cached": false, "results": 3},
    "L4_branch": {"ms": 12, "cached": false},
    "L5_commands": {"ms": 6, "cached": false, "matches": 3},
    "L6_quality_gate": {"ms": 1, "cached": true},
    "L7_time": {"ms": 1, "cached": false}
  },
  "total_ms": 127
}
```

### Workflow Engine (`core/workflow/`)

Executes YAML-defined workflows with phases, gates, agent assignments, and parallel execution.

| File | Purpose |
|------|---------|
| `core/workflow/engine.py` | Phase executor, gate evaluator, state machine |
| `core/workflow/loader.py` | Loads and validates workflow YAML files |
| `core/workflow/gates.py` | Gate types: auto, user_approval, budget_check, quality_gate |
| `core/workflow/state.py` | Workflow state persistence (in-progress, blocked, completed) |

Real workflow YAML example (`departments/dev/workflows/feature.yaml`):

```yaml
id: dev-feature
name: Feature Development
department: dev
tier: enterprise
command: "/dev feature"
requires_branch: true
requires_spec: true
quality_gate_required: true

phases:
  - id: spec
    name: Specification
    agents:
      - agent_id: tech-lead-paulo
        role: Orchestrate spec creation
      - agent_id: architect-gabriel
        role: Technical feasibility check
    gate:
      type: user_approval
      description: User must approve the spec before proceeding

  - id: research
    name: Research
    agents:
      - agent_id: analyst-lucas
        role: Research libraries and patterns
        parallel: true
      - agent_id: architect-gabriel
        role: Review existing architecture
        parallel: true
    gate:
      type: auto

  - id: architecture
    name: Architecture
    agents:
      - agent_id: architect-gabriel
        role: Design architecture and write ADR
      - agent_id: cto-marco
        role: Review and approve architecture
    gate:
      type: user_approval
    outputs:
      - type: document
        format: markdown
        obsidian_path: "Projects/{project}/Architecture/ADR-{number}.md"

  - id: implementation
    name: Implementation
    agents:
      - agent_id: backend-dev-andre
        role: Backend implementation
        parallel: true
      - agent_id: frontend-dev-mariana
        role: Frontend implementation
        parallel: true
    gate:
      type: auto

  # ... testing, security audit, self-critique phases ...

  - id: quality-gate
    name: Quality Gate
    agents:
      - agent_id: cqo-marta
        role: Orchestrate final review
    gate:
      type: quality_gate
```

Execution flow for gates:
- `auto` -- phase completes, next phase starts immediately
- `user_approval` -- ArkaOS pauses and asks you to confirm before proceeding
- `budget_check` -- verifies token budget is available for the department tier
- `quality_gate` -- Marta dispatches Eduardo (text) and Francisca (tech), both must APPROVE

### Agent Schema (`core/agents/`)

Every agent is defined in a YAML file with 4-framework behavioral DNA.

| File | Purpose |
|------|---------|
| `core/agents/schema.py` | Pydantic schema for agent YAML validation |
| `core/agents/loader.py` | Loads all agent YAMLs from departments |
| `core/agents/validator.py` | Cross-validates DISC/Enneagram/MBTI/Big Five consistency |
| `core/agents/registry.py` | In-memory registry of all loaded agents |

Agent YAML files live at `departments/{dept}/agents/{agent-name}.yaml`. The validator ensures that an agent's DISC profile is consistent with their MBTI and Big Five scores (e.g., a high-C DISC should have high Conscientiousness in Big Five).

### Squad Framework (`core/squads/`)

Manages department squads (permanent) and project squads (ad-hoc, cross-department).

| File | Purpose |
|------|---------|
| `core/squads/department.py` | Department squad: lead + specialists for a domain |
| `core/squads/project.py` | Project squad: cross-department team for a specific project |
| `core/squads/router.py` | Routes requests to the correct squad |

Department squads follow Team Topologies patterns: stream-aligned (dev, marketing), platform (ops, knowledge), enabling (strategy, leadership).

### Knowledge System (`core/knowledge/`)

Vector database for semantic search over your indexed content.

| File | Purpose |
|------|---------|
| `core/knowledge/embedder.py` | Generates embeddings (OpenAI ada-002 or local) |
| `core/knowledge/chunker.py` | Splits documents into overlapping chunks |
| `core/knowledge/vectordb.py` | sqlite-vss vector storage and search |
| `core/knowledge/ingest.py` | Pipeline: source detection, download, transcribe, chunk, embed, store |

Ingestion flow for a YouTube video:

```
POST /api/knowledge/ingest {"source": "https://youtube.com/...", "type": "youtube"}
  |
  v
[Task Queue] Background task created (task-0042)
  |
  v
[Download] yt-dlp extracts audio
  |
  v
[Transcribe] Whisper generates transcript with timestamps
  |
  v
[Chunk] Transcript split into ~500 token overlapping chunks
  |
  v
[Embed] Each chunk embedded via OpenAI ada-002
  |
  v
[Store] Vectors stored in sqlite-vss with metadata
  |
  v
[Index] Full-text index updated for hybrid search
  |
  v
[Complete] Task status: completed, chunks: 47
```

Search combines vector similarity (semantic) with full-text search (keyword) and returns ranked results with relevance scores.

### Budget System (`core/budget/`)

Tracks token usage by department and tier. Each tier has a daily budget. The workflow engine checks budget before starting a phase (via `budget_check` gate).

| File | Purpose |
|------|---------|
| `core/budget/tracker.py` | Records token usage per department/agent |
| `core/budget/limits.py` | Tier limits and daily reset logic |
| `core/budget/api.py` | Budget query and reporting |

### Orchestration (`core/orchestration/`)

Four coordination patterns for multi-agent work:

| Pattern | How It Works | When Used |
|---------|-------------|-----------|
| **Solo Sprint** | Single department, lead assigns to one agent | Simple tasks: code review, SEO audit |
| **Domain Deep-Dive** | One agent runs multiple skills in sequence | Research tasks: validate idea, deep analysis |
| **Multi-Agent Handoff** | Cross-department pipeline with structured handoffs | Complex tasks: feature development, brand launch |
| **Skill Chain** | Procedural pipeline without agent identity | Automation: ingest-chunk-embed-store |

### Personas (`core/personas/`)

Create custom personas from knowledge sources and optionally clone them as ArkaOS agents.

| File | Purpose |
|------|---------|
| `core/personas/builder.py` | Persona creation from source analysis |
| `core/personas/cloner.py` | Clone persona into agent YAML format |
| `core/personas/storage.py` | Persona persistence |

### Task System (`core/tasks/`)

Background task queue for long-running operations (knowledge ingestion, analysis jobs).

| File | Purpose |
|------|---------|
| `core/tasks/queue.py` | Task queue with persistence |
| `core/tasks/worker.py` | Task execution and status updates |
| `core/tasks/api.py` | Task query and management |

### Governance (`core/governance/`)

Constitution enforcement and quality gate orchestration.

| File | Purpose |
|------|---------|
| `core/governance/constitution.py` | Rule loading and enforcement checking |
| `core/governance/quality_gate.py` | QG orchestration: dispatch Eduardo + Francisca, collect verdicts |
| `config/constitution.yaml` | The constitution: 13 non-negotiable rules + must/should rules |

### Runtime Adapters (`core/runtime/`)

Multi-runtime support via adapter pattern.

| File | Purpose |
|------|---------|
| `core/runtime/claude_code.py` | Claude Code adapter (hooks, CLAUDE.md injection) |
| `core/runtime/codex.py` | Codex CLI adapter |
| `core/runtime/gemini.py` | Gemini CLI adapter |
| `core/runtime/cursor.py` | Cursor adapter (rules injection) |
| `core/runtime/subagent.py` | Subagent dispatch: fresh instances per task, ~379 token handoff |

## Hook Lifecycle

Hooks are bash scripts that fire at specific points in the AI tool's lifecycle.

### `user-prompt-submit-v2.sh`

**When:** Every time you submit a prompt.

**What it does:**
1. Captures your input text
2. Calls `python scripts/synapse-bridge.py` with the input
3. Receives the context string (all 9 Synapse layers merged)
4. Injects the context into the prompt as a system-level prefix

**File path:** `~/.arkaos/hooks/user-prompt-submit-v2.sh`

### `post-tool-use-v2.sh`

**When:** After every tool call (file read, bash command, etc.)

**What it does:**
1. Checks tool output for error patterns
2. Records errors in `gotchas.json` for the project
3. Tracks tool usage for budget accounting

**File path:** `~/.arkaos/hooks/post-tool-use-v2.sh`

### `pre-compact-v2.sh`

**When:** Before Claude Code compacts conversation (when context gets large)

**What it does:**
1. Saves a session digest (summary of what happened) to Obsidian
2. Preserves agent memory and task state
3. Ensures no context is lost during compaction

**File path:** `~/.arkaos/hooks/pre-compact-v2.sh`

## Dashboard Architecture

Two-process architecture: Python API backend + Nuxt 4 frontend.

```
Browser (localhost:3333)
    |
    v
[Nuxt 4 Frontend] -- SSR + client hydration
    |                  Pages: index, agents/, commands, budget,
    |                         tasks, knowledge, personas, health
    v
[FastAPI Backend] (localhost:3334)
    |
    |-- /api/overview     --> reads agent/skill/workflow counts
    |-- /api/agents       --> loads from core/agents/registry
    |-- /api/commands     --> aggregates skill frontmatter
    |-- /api/budget       --> reads from core/budget/tracker
    |-- /api/tasks        --> reads from core/tasks/queue
    |-- /api/knowledge    --> interfaces with core/knowledge/vectordb
    |-- /api/personas     --> interfaces with core/personas/storage
    |-- /api/health       --> runs diagnostic checks
    |-- /api/metrics      --> hook performance timing
    |
    v
[Core Python Engine]
    |-- SQLite (tasks, budget, personas)
    |-- sqlite-vss (knowledge vectors)
    |-- YAML files (agents, workflows, skills)
    |-- JSON files (constitution, config)
```

Start both with a single command:

```bash
npx arkaos dashboard
# FastAPI starts on :3334
# Nuxt dev server starts on :3333
# Browser opens automatically
```

## File Structure Reference

```
~/.arkaos/                          # Installation directory
├── core/                           # Python core engine
│   ├── synapse/                    # 9-layer context injection
│   ├── workflow/                   # YAML workflow engine
│   ├── agents/                     # Agent schema + validation
│   ├── squads/                     # Squad framework
│   ├── budget/                     # Token tracking
│   ├── knowledge/                  # Vector DB
│   ├── obsidian/                   # Vault writer
│   ├── orchestration/              # 4 coordination patterns
│   ├── personas/                   # Persona builder + cloner
│   ├── governance/                 # Constitution + QG
│   ├── tasks/                      # Background task queue
│   ├── runtime/                    # Multi-runtime adapters
│   └── specs/                      # Living specifications
├── departments/                    # 17 departments
│   ├── dev/                        # 10 agents, 41 skills, 3 workflows
│   ├── marketing/                  # 4 agents, 14 skills
│   ├── brand/                      # 4 agents, 12 skills
│   └── ...                         # (14 more departments)
├── hooks/                          # Bash hooks for runtimes
├── scripts/                        # Synapse bridge + CLI tools
├── dashboard/                      # Nuxt 4 frontend
├── config/                         # constitution.yaml
└── knowledge/                      # Agent registry JSON
```
