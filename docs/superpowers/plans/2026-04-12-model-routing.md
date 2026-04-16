# PR 3 — Model Routing Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute task-by-task.

**Goal:** Route agent dispatch to Haiku/Sonnet/Opus based on tier and task type to reduce per-turn cost by ~60-70% while preserving quality on Quality Gate and architectural work.

**Architecture:** ArkaOS runs inside Claude Code CLI (no direct API calls). Model selection happens via the Task tool's `model` parameter when dispatching subagents. This PR adds `model:` fields to agent YAMLs and workflow phases, then updates orchestrator skills to instruct Claude to pass the model parameter when dispatching.

**Tech Stack:** YAML, Markdown, no code changes.

---

## Model Assignment Convention

| Tier | Agents | Default Model | Rationale |
|---|---|---|---|
| 0 (C-Suite) | CTO, CFO, COO, CQO, Copy, Tech | **opus** | Final authority, veto power |
| 0 (Quality Gate) | Marta, Eduardo, Francisca | **opus** | NON-NEGOTIABLE — quality critical |
| 1 (Squad Leads) | 15 dept leads | **sonnet** | Orchestration, judgment |
| 2 (Specialists) | 35 domain experts | **sonnet** | Default execution |
| 2 (Mechanical) | commit-writer, routing, keyword extraction | **haiku** | Cheap, fast tasks |

**Task-type overrides** (take precedence over tier default):
- Architecture design, ADRs, complexity ≥ complex → **opus**
- Quality Gate phase → **opus** (always)
- Commit messages, changelog, routing decisions → **haiku**
- All other execution → **sonnet**

---

## Task 1: Extend Agent YAML schema

**Files:**
- Modify: `core/agents/schema.py` — add `model: Optional[str]` field to Agent dataclass
- Modify: `tests/python/agents/test_schema.py` (or equivalent) — add test for model field

- [ ] Step 1.1: Read current Agent schema at `core/agents/schema.py:236-266`
- [ ] Step 1.2: Add `model: Optional[Literal["haiku", "sonnet", "opus"]] = None` field
- [ ] Step 1.3: Add validator: if `model` is None, derive from tier (0→opus, 1→sonnet, 2→sonnet)
- [ ] Step 1.4: Write test: YAML with `model: haiku` loads correctly
- [ ] Step 1.5: Write test: YAML without `model` derives from tier
- [ ] Step 1.6: Run `pytest tests/ -k "test_agent_schema"` — all pass
- [ ] Step 1.7: Commit: `feat(agents): add model field to Agent schema with tier fallback`

---

## Task 2: Add `model:` to Quality Gate agents (NON-NEGOTIABLE — do first)

**Files:**
- Modify: `departments/quality/agents/marta.yaml`
- Modify: `departments/quality/agents/eduardo.yaml`
- Modify: `departments/quality/agents/francisca.yaml`

- [ ] Step 2.1: Add `model: opus` to each (tier 0 default, but explicit for safety)
- [ ] Step 2.2: Commit: `feat(quality): pin Quality Gate agents to opus`

---

## Task 3: Add `model:` to C-Suite (Tier 0)

**Files:**
- `departments/*/agents/*.yaml` where tier = 0 (Marco/CTO, Helena/CFO, Sofia/COO, plus any others)

- [ ] Step 3.1: Grep for `tier: 0` across agent YAMLs — list all
- [ ] Step 3.2: Add `model: opus` to each (explicit, redundant with default but safe)
- [ ] Step 3.3: Commit: `feat(agents): pin Tier 0 agents to opus`

---

## Task 4: Add `model:` to Squad Leads (Tier 1)

**Files:**
- `departments/*/agents/*.yaml` where tier = 1 (15 dept leads)

- [ ] Step 4.1: Grep for `tier: 1` across agent YAMLs
- [ ] Step 4.2: Add `model: sonnet` to each
- [ ] Step 4.3: Commit: `feat(agents): route Tier 1 squad leads to sonnet`

---

## Task 5: Add `model:` to Specialists (Tier 2)

**Files:**
- `departments/*/agents/*.yaml` where tier = 2 (~35 specialists)

- [ ] Step 5.1: Grep for `tier: 2` across agent YAMLs
- [ ] Step 5.2: Batch-add `model: sonnet` as default to all
- [ ] Step 5.3: Manually override specific agents to `haiku`:
  - Any agent whose role is "commit writer", "message formatter", "keyword extractor"
  - (list generated from Step 5.1 — review each)
- [ ] Step 5.4: Commit: `feat(agents): route Tier 2 specialists to sonnet (haiku for mechanical roles)`

---

## Task 6: Extend Workflow Phase schema

**Files:**
- Modify: `core/workflow/schema.py` — add `model_override: Optional[str]` to Phase class
- Modify: corresponding test file

- [ ] Step 6.1: Add `model_override: Optional[Literal["haiku", "sonnet", "opus"]] = None` to Phase
- [ ] Step 6.2: Write test: phase with `model_override: opus` parses correctly
- [ ] Step 6.3: Run pytest — pass
- [ ] Step 6.4: Commit: `feat(workflow): add model_override field to Phase schema`

---

## Task 7: Add `model_override` to Quality Gate phases (all workflows)

**Files:**
- All `departments/*/workflows/*.yaml` files that have a quality_gate phase

- [ ] Step 7.1: Grep for `gate: QUALITY_GATE` or `phase: quality_gate` across workflow YAMLs
- [ ] Step 7.2: Add `model_override: opus` to each quality_gate phase
- [ ] Step 7.3: Commit: `feat(workflow): enforce opus for all Quality Gate phases`

---

## Task 8: Add `model_override` to architecture/design phases

**Files:**
- Workflow YAMLs with phases named: architecture, design, ADR, spec, complexity, forge

- [ ] Step 8.1: Grep workflow YAMLs for these phase names
- [ ] Step 8.2: Add `model_override: opus` where complexity/arch judgment is needed
- [ ] Step 8.3: Commit: `feat(workflow): pin architecture phases to opus`

---

## Task 9: Update Forge complexity escalation

**Files:**
- `arka/skills/forge/SKILL.md`
- `arka/skills/forge/references/complexity-engine.md`

- [ ] Step 9.1: Read current complexity tiers (simple/standard/complex/super)
- [ ] Step 9.2: Update tier → model mapping:
  - simple → haiku (fast routing)
  - standard → sonnet (default)
  - complex → opus (multi-explorer synthesis)
  - super → opus (highest judgment)
- [ ] Step 9.3: Instruct SKILL.md: "When dispatching explorer subagents via Task tool, include `model: <tier_model>`"
- [ ] Step 9.4: Mirror to `~/.claude/skills/arka-forge/`
- [ ] Step 9.5: Commit: `feat(forge): route explorer subagents by complexity tier`

---

## Task 10: Update orchestrator skills to pass model on dispatch

**Files:**
- `arka/SKILL.md` (main `/arka` orchestrator)
- Department orchestrator skills: `/arka-dev`, `/arka-pm`, `/arka-marketing`, etc. (the 17 dept skills)

- [ ] Step 10.1: Add to each orchestrator skill a section titled "Model Selection":
  ```
  When dispatching a Task tool call to an agent, include the model parameter 
  from the agent's YAML `model:` field. Default to `sonnet` if not specified.
  Quality Gate dispatch always uses `model: opus` regardless of agent YAML.
  ```
- [ ] Step 10.2: Commit: `feat(skills): instruct orchestrators to pass model on Task dispatch`

---

## Task 11: Update CLAUDE.md with Model Routing convention

**Files:**
- `CLAUDE.md`

- [ ] Step 11.1: Add a new section "## Model Routing" after "## Agent Hierarchy"
- [ ] Step 11.2: Document the tier → model mapping table
- [ ] Step 11.3: Document task-type overrides
- [ ] Step 11.4: Document that Quality Gate is ALWAYS opus (NON-NEGOTIABLE)
- [ ] Step 11.5: Commit: `docs: document Model Routing convention in CLAUDE.md`

---

## Task 12: Register Constitution rule

**Files:**
- `config/constitution.yaml`

- [ ] Step 12.1: Add under MUST rules: `model-routing: Tier → model mapping enforced; Quality Gate always opus`
- [ ] Step 12.2: Commit: `feat(governance): register model-routing as MUST rule`

---

## Task 13: Smoke test with real workflow

- [ ] Step 13.1: Pick a small workflow (e.g., `/dev code-review` or `/brand colors`)
- [ ] Step 13.2: Invoke it — observe that subagents are dispatched with correct model parameters
- [ ] Step 13.3: Check Quality Gate explicitly runs on opus
- [ ] Step 13.4: Note any discrepancies for follow-up

---

## Task 14: Quality Gate + merge

- [ ] Step 14.1: Dispatch formal QG review (Marta)
- [ ] Step 14.2: Address any blockers
- [ ] Step 14.3: On APPROVED, merge `optimize/token-consumption-pr3` → master (no release yet — bundle with later PRs)

---

## Out of Scope (deferred)

- Runtime cost tracking by model (requires API instrumentation — PR 4 territory)
- Dynamic model switching mid-task (not supported by Task tool)
- Auto-detection of task type from prompt (could use Synapse L1 but adds complexity — keep explicit for now)
- User-level model overrides (via settings or per-session flag)

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Haiku not good enough for some "mechanical" tasks | Start conservative — only commit writers, changelog on haiku. Rest on sonnet. |
| Quality Gate runs on sonnet by accident | Task 2 pins Marta/Eduardo/Francisca to opus; Task 7 pins QG phase to opus; redundant but safe |
| Forge complex plans degrade on Sonnet | Task 9 explicitly maps complex/super → opus |
| Users on Haiku-only plan | Add fallback: if requested model unavailable, use default. (Out of scope; document) |
