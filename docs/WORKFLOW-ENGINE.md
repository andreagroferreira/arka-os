# ArkaOS Workflow System

How YAML-defined workflows are structured and executed: phase sequencing, gate evaluation, state persistence, and the full dev-feature workflow as a worked example.

Execution is orchestrated by the runtime — hooks, skills, and the Task tool — against the declarative YAML contract validated by `core/workflow/schema.py` + `loader.py`. A Python phase executor (`WorkflowEngine`) existed but had no production callers and was removed as dead code (see `docs/adr/2026-07-09-remove-dead-orchestration.md`).

For the workflow system's place in the broader call chain see [ARCHITECTURE.md](ARCHITECTURE.md). For the Python module map see [CORE-ENGINE.md](CORE-ENGINE.md).

---

## Workflow YAML Structure

A workflow lives in `departments/{dept}/workflows/{name}.yaml`. The Pydantic model that validates it is `core/workflow/schema.py::Workflow`.

**Top-level fields:**

| Field | Type | Required | Purpose |
|---|---|---|---|
| `id` | string | yes | Unique identifier (e.g. `dev-feature`) |
| `name` | string | yes | Human-readable name shown in announcements |
| `description` | string | no | One-line summary |
| `department` | string | yes | Owning department slug (e.g. `dev`, `saas`) |
| `tier` | `enterprise` \| `focused` \| `specialist` | no | Controls expected phase count and overhead |
| `command` | string | no | CLI command that triggers this workflow |
| `requires_branch` | bool | no | Must be running on a feature branch |
| `requires_spec` | bool | no | Must have an approved spec before execution |
| `quality_gate_required` | bool | no | Quality Gate phase is mandatory (default true) |
| `max_duration_minutes` | int | no | Soft time limit (0 = none) |
| `phases` | list | yes | Ordered list of phase definitions |

**Workflow tiers:**

| Tier | Phase count | When to use |
|---|---|---|
| `enterprise` | 7–10 | Complex features, launches, architecture changes |
| `focused` | 3–4 | Medium tasks: audits, optimisations, defined deliverables |
| `specialist` | 1–2 | Simple tasks: single-file reviews, quick analysis |

**Phase fields:**

| Field | Type | Required | Purpose |
|---|---|---|---|
| `id` | string | yes | Stable identifier used by `depends_on` and state tracking |
| `name` | string | yes | Display name used in announcements |
| `description` | string | no | What this phase does |
| `agents` | list | yes | Agent assignments (see below) |
| `gate` | Gate | no | Gate that must pass before the next phase starts |
| `outputs` | list | no | Documents/artefacts produced by this phase |
| `depends_on` | list\[string\] | no | Phase IDs that must complete before this one starts |
| `skip_if` | string | no | Boolean expression; phase is skipped when true |
| `model_override` | `haiku` \| `sonnet` \| `opus` | no | Forces a specific model for all agents in this phase |
| `status` | runtime | — | Managed by the engine: pending/in\_progress/completed/skipped/failed/blocked |

**Agent assignment fields:**

| Field | Type | Default | Purpose |
|---|---|---|---|
| `agent_id` | string | — | ID matching an agent YAML file |
| `role` | string | `""` | What this agent does within the phase |
| `parallel` | bool | false | Can run concurrently with other parallel-flagged agents |
| `optional` | bool | false | Phase can complete without this agent's output |

**Gate fields:**

| Field | Type | Default | Purpose |
|---|---|---|---|
| `type` | GateType | `auto` | Gate behaviour (see Gate Types below) |
| `description` | string | `""` | Human-readable explanation shown when pausing |
| `condition` | string | null | Python expression for `condition` gate type |
| `required_verdict` | string | `APPROVED` | Verdict string required to pass a `quality_gate` |
| `timeout_seconds` | int | 0 | Seconds before the gate times out (0 = no timeout) |

**Phase output fields:**

| Field | Type | Purpose |
|---|---|---|
| `type` | string | Output category: `document`, `code`, `review`, `decision` |
| `format` | string | File format: `markdown`, `yaml`, `json`, `code` |
| `obsidian_path` | string | Vault path template (supports `{project}`, `{number}`) |
| `description` | string | What this output contains |

---

## Gate Types

Defined in `core/workflow/schema.py::GateType`. Gates are honoured by the orchestrating runtime per the 4-gate evidence flow (`arka/skills/flow/SKILL.md`).

| Gate type | Value | Behaviour |
|---|---|---|
| Auto | `auto` | Phase completes; next phase starts immediately. No user interaction. |
| User approval | `user_approval` | Orchestration pauses. ArkaOS announces the gate description and waits for explicit user confirmation before proceeding. Silence is not approval. |
| Quality gate | `quality_gate` | Marta (CQO) dispatches Eduardo (copy director) and Francisca (tech director) in parallel. Both must return `APPROVED`. Any `REJECTED` verdict resets the preceding phase to `pending` for rework. |
| Budget check | `budget_check` | `BudgetManager.check_budget(tier, estimated_tokens)` is consulted. If the tier quota is exhausted, the gate fails and Tier 0 is notified. When usage exceeds 80% the gate passes but emits a warning. |
| Condition | `condition` | Passes when the `condition` expression evaluates to true against the current workflow context. Reserved for branching; not used in shipped workflows. |

---

## Phase Execution

The orchestrating runtime processes phases in list order, enforcing two Constitution rules unconditionally:

- `sequential-validation`: Phase N+1 does not start until phase N is `completed` or `skipped`.
- `full-visibility`: Every phase transition is announced to the user before the phase runs.

**Execution semantics (the contract the YAML declares):**

```
for each phase in workflow.phases:
    if phase.skip_if evaluates true:
        mark SKIPPED, announce, continue

    if phase.depends_on has unmet phases:
        mark BLOCKED, announce, stop

    announce phase start with its agents
    dispatch agents (parallel or sequential per agent.parallel flag)

    if the phase fails:
        mark workflow FAILED, announce, stop

    mark phase COMPLETED
    save declared outputs to the Obsidian vault
    announce phase completion

    evaluate gate:
        if gate passes: continue to next phase
        if gate fails:  reset phase to PENDING for rework

if all phases COMPLETED or SKIPPED:
    mark workflow COMPLETED
```

Phase state transitions are persisted by the Stop hook (`gate_checkpoint.py` → `state.py`), which is what makes structured resume possible after an interruption.

**Parallel agents within a phase:**

When multiple agents in a phase carry `parallel: true`, they are logically concurrent — orchestration does not block on individual agent completion before starting the next parallel agent. Agents without `parallel: true` run sequentially within the phase. The phase itself is still sequential with respect to the workflow (the next phase does not start until all agents in the current phase are done).

**Model routing within phases:**

If a phase sets `model_override`, all agents in that phase run on the specified model regardless of their agent YAML's default. Architecture and Quality Gate phases in the `dev-feature` workflow both set `model_override: opus` — this matches the Constitution's MUST rule `model-routing` (Quality Gate phases always use Opus).

---

## State Persistence

`core/workflow/state.py` maintains `~/.arkaos/workflow-state.json`. The file is written atomically via a temp-file rename (`os.replace`), making it safe for concurrent hook reads.

**State file structure:**

```json
{
  "session_id": "3f9a2b1c-...",
  "started_at": "2026-06-01T14:23:00+00:00",
  "workflow": "dev-feature",
  "project": "my-project",
  "branch": "feat/auth-rework",
  "phases": {
    "spec":         {"status": "completed", "at": "2026-06-01T14:25:00+00:00"},
    "research":     {"status": "completed", "at": "2026-06-01T14:28:00+00:00"},
    "architecture": {"status": "in_progress", "at": "2026-06-01T14:30:00+00:00"},
    "implementation": {"status": "pending"},
    "quality-gate": {"status": "pending"}
  },
  "violations": []
}
```

**API:**

| Function | Purpose |
|---|---|
| `init_workflow(workflow, project, phases)` | Creates a new state file; overwrites any existing state |
| `get_state()` | Reads current state; returns `None` if no active workflow |
| `update_phase(phase, status, artifact)` | Updates a phase status; validates phase name and status value |
| `set_branch(branch)` | Records the git branch |
| `add_violation(rule, detail, tool, file, severity)` | Appends a governance violation to the violations list |
| `is_phase_completed(phase)` | Returns true if the phase status is `completed` |
| `clear_workflow()` | Removes the state file (end of workflow) |

The `state_reader.sh` script exposes `get_state` to bash hooks without requiring a Python sub-process.

---

## Worked Example: dev-feature

The full `departments/dev/workflows/feature.yaml` defines nine phases for a new feature. This is an `enterprise`-tier workflow.

```yaml
id: dev-feature
name: Feature Development
description: Full enterprise workflow for implementing a new feature
department: dev
tier: enterprise
command: "/dev feature"
requires_branch: true
requires_spec: true
quality_gate_required: true

phases:
  - id: spec
    name: Specification
    model_override: opus
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
    model_override: opus
    agents:
      - agent_id: architect-gabriel
        role: Design architecture and write ADR
      - agent_id: cto-marco
        role: Review and approve architecture
    gate:
      type: user_approval
      description: Architecture design approved by CTO
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
      - agent_id: frontend-dev-diana
        role: Frontend implementation
        parallel: true
    gate:
      type: auto
    depends_on:
      - architecture

  - id: self-critique
    name: Self-Critique
    agents:
      - agent_id: tech-lead-paulo
        role: Code quality review against Clean Code and SOLID
    gate:
      type: auto

  - id: security
    name: Security Audit
    agents:
      - agent_id: security-eng-bruno
        role: Security audit and vulnerability assessment
    gate:
      type: auto

  - id: qa
    name: Quality Assurance
    agents:
      - agent_id: qa-eng-rita
        role: Full test suite execution and coverage analysis
    gate:
      type: auto

  - id: quality-gate
    name: Quality Gate
    model_override: opus
    agents:
      - agent_id: cqo-marta
        role: Orchestrate quality review
      - agent_id: copy-director-eduardo
        role: Review all text, comments, documentation
        parallel: true
      - agent_id: tech-director-francisca
        role: Review code quality, tests, UX, security
        parallel: true
    gate:
      type: quality_gate
      description: All three quality reviewers must approve
      required_verdict: APPROVED

  - id: documentation
    name: Documentation & KB
    agents:
      - agent_id: analyst-lucas
        role: Documentation and knowledge base update
    gate:
      type: auto
    outputs:
      - type: document
        format: markdown
        obsidian_path: "Projects/{project}/Docs/"
```

**Gate summary for this workflow:**

| After phase | Gate type | What happens |
|---|---|---|
| spec | user\_approval | ArkaOS pauses; proceeds only on explicit user confirmation |
| research | auto | Continues immediately |
| architecture | user\_approval | ArkaOS pauses; proceeds only on explicit user confirmation |
| implementation | auto | Continues immediately (depends\_on architecture) |
| self-critique | auto | Continues immediately |
| security | auto | Continues immediately |
| qa | auto | Continues immediately |
| quality-gate | quality\_gate | Eduardo and Francisca both must return APPROVED |
| documentation | auto | Workflow completes |

---

## Adding a New Workflow

1. Create `departments/{dept}/workflows/{name}.yaml`.
2. Set `id`, `name`, `department`, `tier`, `command`.
3. Add phases in execution order. Every workflow that produces user-facing output must include a `quality-gate` phase as the penultimate phase.
4. Validate by loading: `python -c "from core.workflow.loader import load_workflow; print(load_workflow('departments/{dept}/workflows/{name}.yaml'))"`.
5. Register the command in the department skill index if it should appear in `/help` output.

The `quality_gate_required: true` flag is the convention but not programmatically enforced by the loader — it is enforced by `WorkflowEnforcer` at runtime and by the `mandatory-qa` Constitution rule.

---

Related: [CORE-ENGINE.md](CORE-ENGINE.md) | [ARCHITECTURE.md](ARCHITECTURE.md) | [BENCHMARKS.md](BENCHMARKS.md)
