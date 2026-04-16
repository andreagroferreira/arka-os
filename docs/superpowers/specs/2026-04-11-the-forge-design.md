# The Forge — ArkaOS Intelligent Planning Engine

> Multi-agent planning system with complexity-based escalation, critic synthesis, visual companion, and knowledge-driven pattern reuse.

**Date:** 2026-04-11
**Status:** Draft
**Author:** Andre Groferreira + ArkaOS Platform Squad
**ArkaOS Version Target:** 2.14.0
**Inspired by:** Claude Code UltraPlan (research preview, April 2026)

---

## 1. Problem Statement

Planning complex tasks in AI agent systems has two failure modes:

1. **Shallow planning** — a single agent generates one approach, misses alternatives, and the user discovers problems during execution.
2. **Context-switch planning** — the plan is generated elsewhere (cloud, browser) and the user loses flow, context, and control.

Claude's UltraPlan attempts to solve (1) with multi-agent exploration but creates (2) by forcing a CLI-to-browser transition. It also suffers from stale snapshots, GitHub-only repos, bypassed security hooks, and session instability (20+ open bugs as of April 2026).

ArkaOS already has a Workflow Engine, Living Specs, State Tracker, Synapse context injection, and Quality Gate — but lacks an explicit multi-agent planning mode that explores alternatives before committing to a path.

## 2. Solution: The Forge

The Forge is a **terminal-first, governance-aware, knowledge-driven planning engine** that:

- Analyzes prompt complexity and scales agent count accordingly
- Launches parallel explorer agents with different lenses (pragmatic, architectural, contrarian)
- Synthesizes the best elements via an independent Plan Critic
- Presents plans in the terminal with an optional visual companion for complex plans
- Persists everything to YAML (execution) and Obsidian (knowledge)
- Hands off to the appropriate ArkaOS execution mechanism (skill, focused workflow, or generated enterprise workflow)
- Learns from completed plans via pattern extraction

### 2.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Terminal is master** | Everything works in the terminal. Browser companion is optional, never required. |
| **Governance native** | The Forge respects and is monitored by the Constitution, hooks, and Quality Gate. |
| **Knowledge compounds** | Every plan feeds Obsidian. Every future forge benefits from past plans. |
| **Proportional effort** | Simple prompts get 1 agent. Complex prompts get 3 + critic. Never overkill. |
| **No cloud dependency** | Everything runs locally. No repo syncing to external servers. |
| **No context loss** | Snapshot refresh detects repo changes. Handoff injects forge decisions into execution. |

### 2.2 Competitive Differentiation vs UltraPlan

| Dimension | UltraPlan | The Forge |
|-----------|-----------|-----------|
| Runs where | Anthropic cloud (CCR) | Local (terminal) |
| Terminal blocked | No (async) | No (subagents) |
| Browser required | Yes (forced) | No (optional companion) |
| Agent scaling | A/B tested (inconsistent) | Deterministic by complexity score |
| Explorer lenses | Unknown differentiation | Pragmatic / Architectural / Contrarian |
| Critic | Evaluates without attachment | Evaluates + must reject + must find risks |
| Repo context | Stale snapshot, GitHub-only | Live local + snapshot refresh on change |
| Hook compliance | Bypasses local hooks | Fully governed by Constitution + hooks |
| Knowledge reuse | None | Obsidian patterns from completed plans |
| Execution | Cloud PR or teleport back | Skill routing / workflow generation / enterprise workflow |
| Session stability | Timeouts, 404s, 90min limit | Local — no timeouts, no cloud failures |
| Plan persistence | `.claude/plans/<name>.md` | YAML (execution) + Obsidian (knowledge) + HTML (companion) |

## 3. Architecture

### 3.1 System Overview

```
/forge <prompt>
    |
    v
+-------------------+
| Complexity Scorer  |  core/forge/complexity.py
| (5 dimensions)     |  Consults Obsidian for novelty
+-------------------+
    |
    v  Tier: shallow | standard | deep
+-------------------+
| Explorer Agents    |  1-3 subagents in parallel
| (lensed)           |  Pragmatic / Architectural / Contrarian
+-------------------+
    |
    v  1-3 approaches
+-------------------+
| Plan Critic        |  Independent synthesis agent
| (6 criteria)       |  Or inline self-critique for shallow
+-------------------+
    |
    v  CriticVerdict + ForgePlan
+-------------------+
| Renderer           |  core/forge/renderer.py
| Terminal + HTML     |  Terminal always, companion if tier warrants
+-------------------+
    |
    v  User: approve / revise / cancel
+-------------------+
| Handoff Engine     |  core/forge/handoff.py
| (3 paths)          |  Skill / Focused workflow / Enterprise workflow
+-------------------+
    |
    v  Execution via ArkaOS mechanisms
+-------------------+
| Persistence        |  core/forge/persistence.py
| YAML + Obsidian    |  Plans, patterns, index
+-------------------+
```

### 3.2 File Structure

```
core/forge/                    # Python core engine
├── __init__.py                # Module exports
├── schema.py                  # Pydantic models: ForgePlan, Approach, CriticVerdict, ComplexityScore
├── complexity.py              # Complexity scorer (5 dimensions, 0-100)
├── persistence.py             # YAML save + Obsidian markdown export + pattern extraction
├── renderer.py                # Terminal ANSI output + standalone HTML companion generator
└── handoff.py                 # Execution path routing + workflow YAML generation

skills/arka-forge/SKILL.md     # User-facing skill (commands, orchestration)

tests/python/
├── test_forge_schema.py       # Schema validation tests
├── test_forge_complexity.py   # Complexity scorer tests
├── test_forge_persistence.py  # Persistence + Obsidian export tests
├── test_forge_renderer.py     # Renderer output tests
└── test_forge_handoff.py      # Handoff routing + workflow generation tests
```

### 3.3 Integration Points

| System | Integration |
|--------|------------|
| **Synapse** | New L8 layer: Forge Context (plan decisions, risks, rejected approaches) |
| **State Tracker (SP1)** | Forge execution uses `workflow_state.init()`, `update_phase()`, `add_violation()` |
| **SessionStart hook** | Shows active/pending forge plans |
| **UserPromptSubmit hook** | Injects forge context via Synapse L8 |
| **PostToolUse hook** | Detects forge violations: drift, scope-creep, skip-phase, rejected-approach |
| **Constitution** | 2 new rules: `forge-governance` (non-negotiable), `forge-persistence` (must) |
| **Quality Gate** | Mandatory on all forge plan executions |
| **Obsidian** | Plans, patterns, index at `WizardingCode Internal/ArkaOS/Forge/` |

## 4. Complexity Scoring

### 4.1 Dimensions

| Dimension | Weight | Signals |
|-----------|--------|---------|
| **Scope** | 30% | Number of files/modules affected, departments involved |
| **Dependencies** | 25% | Modules depending on affected code, dependency tree depth |
| **Ambiguity** | 20% | Vagueness of prompt, open questions, implicit requirements |
| **Risk** | 15% | Touches governance, security, data, shared infrastructure |
| **Novelty** | 10% | Similar plans exist in Obsidian? Reusable patterns available? |

### 4.2 Tiers

| Tier | Score | Explorers | Critic | Visual Companion |
|------|-------|-----------|--------|------------------|
| **Shallow** | 0-30 | 1 agent | Inline self-critique | Terminal only |
| **Standard** | 31-65 | 2 agents parallel | 1 Plan Critic agent | Terminal, companion available |
| **Deep** | 66-100 | 3 agents parallel | 1 Plan Critic agent | Terminal + companion suggested |

The user always sees the calculated tier and can override before explorers launch.

### 4.3 Novelty — Obsidian Knowledge Check

Before scoring, the complexity scorer searches the Obsidian vault:

- `WizardingCode Internal/ArkaOS/Forge/Plans/` — completed plans with similar scope
- `WizardingCode Internal/ArkaOS/Forge/Patterns/` — extracted reusable patterns

If similar plans exist, the novelty dimension score decreases, which lowers the overall complexity and may reduce the tier. Patterns from past plans are injected into explorer context so they build on validated approaches rather than starting from zero.

## 5. Explorer Agents

### 5.1 Lenses

Each explorer receives the same prompt and context but a different optimization lens:

| Explorer | Lens | Priority | Personality |
|----------|------|----------|-------------|
| **Explorer A** | Pragmatic | Minimum effort, maximum reuse, ship fast | "What's the simplest thing that works?" |
| **Explorer B** | Architectural | Long-term quality, extensibility, patterns | "What's the right way to build this?" |
| **Explorer C** | Contrarian | Challenge assumptions, find risks, radical alternatives | "What is everyone missing?" |

Explorer C only runs in Deep tier. Its purpose is to prevent groupthink — it actively looks for what the other approaches would fail at.

### 5.2 Explorer Output Format

Each explorer produces:

```yaml
approach:
  explorer: "pragmatic"  # or "architectural" or "contrarian"
  summary: "One paragraph describing the approach"
  key_decisions:
    - decision: "Use existing workflow engine for execution"
      rationale: "Avoids new infrastructure, proven system"
    - decision: "..."
  phases:
    - name: "Phase name"
      deliverables: ["file1.py", "file2.py"]
      effort: "small"  # small | medium | large
  estimated_total_effort: "medium"
  risks:
    - "Risk description"
  reuses_patterns: ["pattern-name-from-obsidian"]
```

### 5.3 Explorer Context

Each explorer receives:

- Original user prompt
- Repo structure summary (from Synapse)
- Relevant Obsidian patterns (from novelty check)
- ArkaOS Constitution rules (compressed)
- Current ArkaOS version and capabilities
- Its specific lens instructions

Explorers do NOT see each other's output. They work independently.

## 6. Plan Critic

### 6.1 Evaluation Criteria

The Critic receives all explorer outputs anonymized (Approach A, B, C) and evaluates against:

| Criterion | Question | Weight |
|-----------|----------|--------|
| **Viability** | Implementable with current stack/resources? | 25% |
| **Completeness** | Covers all requirements? Missing edge cases? | 20% |
| **Risk** | What can go wrong? Fragile dependencies? Breaking changes? | 20% |
| **Effort** | Proportional to value? Ignored simplifications? | 15% |
| **Reuse** | Leverages existing patterns? Generates reusable patterns? | 10% |
| **Governance** | Respects Constitution, SOLID, Quality Gate, branch strategy? | 10% |

### 6.2 Critic Rules

1. **Never picks one approach wholesale** — always synthesizes best elements from each
2. **Must reject at least 1 element** — if nothing is rejected, the analysis was superficial
3. **Must identify at least 1 risk** — plans without risks are poorly analyzed plans
4. **Confidence score (0-1)** — if < 0.5, Forge asks user for more context before proceeding
5. **Governance validation** — checks plan against Constitution rules before presenting

### 6.3 CriticVerdict Schema

```yaml
verdict:
  recommended: "synthesis"
  synthesis:
    from_explorer_a:
      - "Element description"
    from_explorer_b:
      - "Element description"
    from_explorer_c:
      - "Element description"
    original:
      - "Elements not proposed by any explorer"
  rejected_elements:
    - element: "Description"
      reason: "Why rejected"
    - element: "..."
      reason: "..."
  risks:
    - risk: "Description"
      mitigation: "How to mitigate"
      severity: "low | medium | high"
  confidence: 0.82
  estimated_phases: 5
  estimated_departments: ["dev", "ops"]
```

### 6.4 Shallow Tier: Inline Critique

When tier is Shallow (1 explorer), there is no separate Critic agent. The single explorer performs a self-critique pass at the end using the same 6 criteria but in a single inference. Less robust, proportional to complexity.

## 7. ForgePlan Schema

### 7.1 Complete Schema

```yaml
forge_plan:
  # Identity
  id: "forge-YYYY-MM-DD-<slug>"
  name: "Human-readable plan name"
  created_at: "ISO 8601 timestamp"
  forged_by: "User name"
  version: 1  # Increments on each revision

  # Context snapshot
  context:
    repo: "repository name"
    branch: "current branch"
    commit_at_forge: "git SHA"
    arkaos_version: "semantic version"
    prompt: "Original user prompt"
    context_refreshed: false

  # Scoring
  complexity:
    score: 0-100
    tier: "shallow | standard | deep"
    dimensions:
      scope: 0-100
      dependencies: 0-100
      ambiguity: 0-100
      risk: 0-100
      novelty: 0-100
    similar_plans: ["plan IDs from Obsidian"]
    reused_patterns: ["pattern names"]

  # Exploration
  approaches:
    - explorer: "pragmatic | architectural | contrarian"
      summary: "..."
      key_decisions: [{decision, rationale}]
      phases: [{name, deliverables, effort}]
      estimated_total_effort: "small | medium | large"
      risks: ["..."]
      reuses_patterns: ["..."]

  # Critic synthesis
  critic:
    verdict: "synthesis"
    synthesis:
      from_explorer_a: ["..."]
      from_explorer_b: ["..."]
      from_explorer_c: ["..."]
      original: ["..."]
    rejected_elements: [{element, reason}]
    risks: [{risk, mitigation, severity}]
    confidence: 0.0-1.0
    estimated_phases: N
    estimated_departments: ["..."]

  # The plan
  plan:
    goal: "What this plan achieves"
    phases:
      - name: "Phase name"
        department: "department ID"
        agents: ["agent roles"]
        deliverables: ["file paths"]
        acceptance_criteria: ["criteria"]
        depends_on: ["phase names"]
        context_from_forge:
          decisions: ["relevant decisions"]
          risks: ["relevant risks"]
    execution_path:
      type: "skill | workflow | enterprise_workflow"
      target: "skill name or workflow YAML path"
      departments: ["involved departments"]
      estimated_commits: N

  # Governance
  governance:
    constitution_check: "passed | failed"
    violations: []
    quality_gate_required: true
    branch_strategy: "feature/<name>"

  # Lifecycle
  status: "draft | reviewing | approved | executing | completed | rejected | cancelled | archived"
  approved_at: "ISO 8601 or null"
  approved_by: "name or null"
  executed_at: "ISO 8601 or null"
  completion_notes: "string or null"
```

### 7.2 Status Lifecycle

```
draft → reviewing → approved → executing → completed → archived
                  ↘ rejected (persisted for learning)
         cancelled (from any pre-execution state)
```

## 8. Persistence

### 8.1 Three Destinations

| Destination | Format | Purpose |
|-------------|--------|---------|
| `~/.arkaos/plans/<id>.yaml` | Full YAML schema | Execution, state, quick reference |
| `~/.arkaos/plans/active.yaml` | Symlink | Points to the currently active plan (max 1) |
| Obsidian vault | Structured markdown | Knowledge base, human reference, future reuse |

### 8.2 Obsidian Structure

```
WizardingCode Internal/ArkaOS/Forge/
├── Plans/
│   ├── 2026-04-11-ultraplan-feature.md
│   └── ...
├── Patterns/
│   ├── python-core-module-pattern.md
│   ├── hook-integration-pattern.md
│   └── ...
└── Index.md   # Map of Content linking all plans
```

### 8.3 Obsidian Plan Document Format

Each plan exported to Obsidian includes:

- YAML frontmatter: tags, status, confidence, complexity, dates
- Context section: repo, branch, commit, ArkaOS version
- Original prompt
- Approaches explored (all explorers, summarized)
- Critic synthesis: adopted elements, rejected elements with reasons, risks with mitigations
- Final plan: phases with deliverables and acceptance criteria
- Execution details: path, branch, result
- Patterns extracted (links to Pattern notes)
- Lessons learned (populated on completion)

### 8.4 Pattern Extraction

When a plan reaches `completed` status, `persistence.py` extracts reusable patterns:

- Common phase structures that succeeded
- Dependency patterns between modules
- Risk-mitigation pairs that proved effective
- Department coordination patterns

Patterns are saved as individual Obsidian notes in `Forge/Patterns/` with:
- Source plan reference
- Reuse count (incremented each time the novelty scorer finds it)
- Pattern description and applicability conditions

### 8.5 Rejected Plans

Rejected plans are also persisted to Obsidian. The system learns from failures:
- What the critic flagged
- Why the user rejected
- What changed in the re-forge

## 9. Terminal Rendering

### 9.1 Progressive Output

The terminal renderer shows each forge stage as it completes:

1. **Context snapshot** — repo, version, active workflows
2. **Obsidian knowledge check** — similar plans found, patterns available
3. **Complexity analysis** — score, dimensions (ASCII bar chart), tier
4. **Tier confirmation** — user can override
5. **Explorer progress** — parallel progress bars per explorer
6. **Critic verdict** — confidence, adopted/rejected/risks summary
7. **Plan overview** — phases, departments, execution path
8. **Action menu** — Approve / Revise / Companion / Detail / Quit

### 9.2 Action Menu

| Key | Action |
|-----|--------|
| `A` | Approve plan → proceed to handoff |
| `R` | Revise → enter revision prompt, critic re-evaluates incrementally |
| `C` | Open visual companion in browser (if available for tier) |
| `D` + number | Show detail for a specific phase |
| `Q` | Quit / cancel forge |

### 9.3 Revision Flow

Revisions are incremental — explorers do not re-run. The critic re-evaluates with the user's revision incorporated. The plan version increments. If the revision fundamentally changes scope (new departments, different goal), the forge warns and offers to re-forge from scratch.

## 10. Visual Companion

### 10.1 When It Appears

| Tier | Behaviour |
|------|-----------|
| **Shallow** | Never suggested |
| **Standard** | `[C]ompanion available` in menu, no insistence |
| **Deep** | Actively suggested: "Complex plan (5 phases, 2 depts). Open visual companion? [Y/n]" |

### 10.2 What It Shows (beyond terminal)

| Feature | Terminal | Companion |
|---------|----------|-----------|
| Complexity dimensions | ASCII bars | SVG radar chart |
| Explorer approaches | Sequential text | 3-column side-by-side |
| Critic flow | Text list | Visual diagram: green (adopted) / red (rejected) |
| Phase dependencies | `depends_on` text | SVG directed graph |
| Risk assessment | Text list | Severity x probability heatmap |
| Similar Obsidian plans | Text links | Cards with preview and similarity score |

### 10.3 Technical Implementation

- **Output:** Single standalone HTML file at `~/.arkaos/forge-companion/<plan-id>.html`
- **Serving:** `python -m http.server 0 --bind 127.0.0.1` on random port, auto-opens browser
- **Stack:** Zero external dependencies — CSS Grid/Flexbox, inline SVG, vanilla JS
- **Theme:** ArkaOS brand (dark mode default)
- **Size target:** < 50KB per HTML file
- **Lifecycle:** Server starts on companion open, dies on plan approval/cancel. HTML files cleaned after 7 days.

### 10.4 Interaction Model

The companion is **read-only**. All actions (approve, revise, cancel) happen in the terminal. The companion is a viewer, not a controller. This is the fundamental difference from UltraPlan — no context switch for actions.

## 11. Handoff & Execution

### 11.1 Execution Path Selection

After plan approval, the handoff engine analyzes the plan and selects:

| Condition | Path | What Happens |
|-----------|------|-------------|
| 1 phase, 1 department | **Skill routing** | Routes to appropriate `/arka-<dept>` skill with forge context |
| 2-3 phases, 1 department | **Focused workflow** | Uses existing department workflow or generates focused YAML |
| 4+ phases or 2+ departments | **Enterprise workflow** | Generates full workflow YAML with all phases, gates, agents |

### 11.2 Context Injection at Handoff

Every execution phase receives `context_from_forge`:

- **Decisions** relevant to the phase (so agents don't re-explore)
- **Risks** relevant to the phase (so agents mitigate proactively)
- **Rejected approaches** (so agents don't accidentally re-implement rejected ideas)
- **Patterns** to reuse (from Obsidian)

### 11.3 Snapshot Refresh at Handoff

Before execution starts, the handoff checks if the repo changed since forge:

```python
current_commit = git_head()
if current_commit != plan.context.commit_at_forge:
    changed_files = git_diff_files(plan.context.commit_at_forge, current_commit)
    affected_phases = check_overlap(changed_files, plan.phases)
    if affected_phases:
        # Warn user: N phases affected by repo changes
        # Options: proceed | re-forge | abort
```

### 11.4 Generated Workflow YAML

For enterprise path, the handoff generates a complete workflow YAML:

- Phase definitions with agents, skills, deliverables, acceptance criteria
- Gate types (auto, user_approval, quality_gate)
- `depends_on` chains matching the forge plan
- `context_from_forge` per phase
- Branch strategy from forge governance
- Quality Gate as final mandatory phase
- Obsidian output path

### 11.5 Save Plan Only

If the user chooses not to execute immediately:

1. Plan YAML saved to `~/.arkaos/plans/`
2. Workflow YAML saved (if generated)
3. Exported to Obsidian
4. Status remains `approved`
5. Next SessionStart shows: "Forge plan pending — run `/forge resume`"

## 12. Hook Integration & Governance

### 12.1 SessionStart Hook

Shows active or pending forge plans in the ArkaOS banner:

- **Active forge:** explorer progress, critic status
- **Pending plan:** plan name, status, branch, `/forge resume` hint

### 12.2 UserPromptSubmit Hook — Synapse L8

New Synapse layer injecting forge context when a plan is active:

- Plan ID and status
- Current executing phase
- Key decisions from critic synthesis
- Active risks
- Rejected approaches

Any agent working during forge execution automatically sees this context.

### 12.3 PostToolUse Hook — Violation Detection

| Violation | Trigger | Severity |
|-----------|---------|----------|
| `forge-drift` | Agent decision contradicts a forge plan decision | Warning |
| `forge-scope-creep` | Agent edits files outside phase deliverables | Warning |
| `forge-skip-phase` | Agent works on future phase deliverables (depends_on not met) | Block |
| `forge-rejected-approach` | Agent implements something the critic explicitly rejected | Block |

Warnings prompt the user for confirmation. Blocks prevent the action entirely.

All violations are recorded in the State Tracker for auditing.

### 12.4 Constitution Rules

Two new rules added to `config/constitution.yaml`:

| Rule ID | Level | Description |
|---------|-------|-------------|
| `forge-governance` | NON-NEGOTIABLE | Forge plans must pass critic validation and governance check before approval |
| `forge-persistence` | MUST | All forge plans (approved and rejected) must be persisted to Obsidian |

## 13. Skill: arka-forge

### 13.1 Commands

| Command | Description |
|---------|-------------|
| `/forge <prompt>` | Forge a new plan |
| `/forge resume` | Resume an approved but unexecuted plan |
| `/forge status` | Status of active forge (explorers, critic, phase) |
| `/forge history` | List past plans from `~/.arkaos/plans/` |
| `/forge show <id>` | Show plan detail (terminal or companion) |
| `/forge compare <id1> <id2>` | Compare two plans side-by-side |
| `/forge patterns` | List patterns extracted from completed plans |
| `/forge cancel` | Cancel active forge |

### 13.2 Relationship to Existing Skills

The Forge is **upstream** — it produces plans. Existing skills are **downstream** — they execute plans.

| Situation | Without Forge | With Forge |
|-----------|--------------|------------|
| Simple, clear feature | `/dev feature` direct | `/dev feature` direct (unchanged) |
| Complex feature | `/dev feature` → agent plans inline | `/forge` → multi-agent plan → handoff to `/dev` |
| Cross-department work | Manual, ad-hoc | `/forge` → enterprise workflow generated → departments coordinate |
| Large refactor | `/arka-refactor-plan` | `/forge` (may use refactor-plan as explorer input) |

## 14. Success Criteria

| Criterion | Measurement |
|-----------|-------------|
| Plans are more thorough than single-agent | Critic confidence > 0.6 on average |
| No browser dependency | 100% of actions available in terminal |
| Knowledge compounds | Novelty score decreases for similar subsequent plans |
| Governance enforced | Zero forge violations reach production undetected |
| Pattern reuse | At least 1 pattern reused per 5 forge sessions (after initial ramp) |
| Terminal stays responsive | Explorer execution does not block user interaction |
| Obsidian always populated | Every plan (approved or rejected) has an Obsidian document |

## 15. Out of Scope (v1)

- Real-time collaboration (multiple users forging simultaneously)
- Cloud execution (plans always execute locally)
- AI model selection per explorer (all use the same model)
- Cost estimation in tokens/money per phase
- Automatic re-forge on repo drift (manual decision only)
- Dashboard UI integration (terminal + companion only for v1)
- Integration with external project management tools (ClickUp, Linear)
