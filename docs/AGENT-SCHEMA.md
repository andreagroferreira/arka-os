# Agent Schema

Reference for contributors defining or auditing ArkaOS agent YAML files.

## Overview

Every ArkaOS agent is a single YAML file under `departments/<dept>/agents/<id>.yaml`. The file is parsed by Pydantic (`core/agents/schema.py`), validated for cross-framework consistency (`core/agents/validator.py`), and loaded into the `DNARegistry` at runtime (`core/agents/dna_registry.py`).

The repository currently contains 82 agents across 17 departments, organized into four tiers.

## Agent Tiers

| Tier | Name | Count | Authority |
|------|------|-------|-----------|
| 0 | C-Suite | 6 | Veto; no escalation target |
| 1 | Squad Lead | 18 | Orchestrate; approve architecture |
| 2 | Specialist | 55 | Execute; no veto |
| 3 | Support | 3 | Mechanical tasks (commits, routing, data fetching) |

Tier is enforced by the validator: tier-2+ agents that have `veto: true` produce a hard error; tier-0 agents that set `escalates_to` produce a warning.

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique slug across all agents (e.g. `backend-dev-andre`). Used as the memory path suffix and registry key. |
| `name` | string | Yes | Human name (e.g. `Andre`). Must be unique across departments. |
| `role` | string | Yes | Short role label (e.g. `Backend Core Lead`). |
| `department` | string | Yes | Must match the parent directory name (e.g. `dev`). |
| `tier` | integer 0-3 | Yes | See tier table above. |
| `model` | `haiku` / `sonnet` / `opus` | No | Overrides the tier default at dispatch time. Omit to use tier default. |
| `parent_squad` | string | No | Slug of the parent squad for sub-squad agents (e.g. `dev`). |
| `sub_squad_role` | string | No | Role within the sub-squad (e.g. `lead`). Requires `parent_squad`. |
| `memory_path` | string | No | Auto-filled to `~/.claude/agent-memory/arka-<id>/MEMORY.md` when omitted. |
| `behavioral_dna` | object | Yes | Four-framework personality. See below. |
| `mental_models` | object | No | Decision-making frameworks. |
| `authority` | object | No | What the agent may approve, veto, or delegate. |
| `expertise` | object | No | Domains, frameworks, depth. |
| `communication` | object | No | Tone, format, vocabulary level. |
| `signature_markers` | object | No | DNA fidelity markers for behavior enforcement (optional, tier-1+ agents). |

### Default model by tier

When `model` is omitted, the runtime resolves it at dispatch:

- Tier 0: `opus`
- Tiers 1, 2, 3: `sonnet`

Haiku is assigned explicitly for mechanical roles (commit writers, keyword extractors).

## behavioral_dna

The `behavioral_dna` block is mandatory and contains all four frameworks.

```yaml
behavioral_dna:
  disc:        # How the agent acts
    ...
  enneagram:   # Why the agent acts
    ...
  big_five:    # How much of each trait
    ...
  mbti:        # How the agent processes information
    ...
```

### disc

DISC describes observable behavior — communication style, how the agent acts under pressure, what motivates it.

| Field | Type | Required | Valid values |
|-------|------|----------|-------------|
| `primary` | string | Yes | `D`, `I`, `S`, `C` |
| `secondary` | string | Yes | `D`, `I`, `S`, `C` (must differ from primary) |
| `label` | string | No | Auto-filled to e.g. `Analyst-Supporter` when omitted |
| `communication_style` | string | No | Free text describing how the agent communicates |
| `under_pressure` | string | No | Free text describing behavior under stress |
| `motivator` | string | No | Free text describing what drives the agent |

DISC type meanings:

| Type | Name | Observable behavior |
|------|------|---------------------|
| D | Dominance | Direct, decisive, results-focused, bottom-line first |
| I | Influence | Enthusiastic, collaborative, people-focused |
| S | Steadiness | Calm, supportive, patient, consistent |
| C | Conscientiousness | Analytical, precise, systematic, quality-focused |

### enneagram

Enneagram describes motivation — the core drive and core fear that explain why the agent acts as it does.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | integer 1-9 | Yes | Enneagram type |
| `wing` | integer 1-9 | Yes | Must be adjacent to type (e.g. type 5 accepts wing 4 or 6) |
| `core_motivation` | string | No | Free text |
| `core_fear` | string | No | Free text |
| `subtype` | string | No | `self-preservation`, `social`, `sexual` |
| `label` | string | No | Auto-filled to e.g. `5w6 — The Investigator` |
| `center` | string | No | Auto-filled from type: `body` (8,9,1), `heart` (2,3,4), `head` (5,6,7) |
| `growth_arrow` | integer | No | Auto-filled from type |
| `stress_arrow` | integer | No | Auto-filled from type |

Enneagram type names: 1 The Reformer, 2 The Helper, 3 The Achiever, 4 The Individualist, 5 The Investigator, 6 The Loyalist, 7 The Enthusiast, 8 The Challenger, 9 The Peacemaker.

### big_five

Big Five (OCEAN) uses a continuous 0-100 scale for each trait.

| Field | Range | Description |
|-------|-------|-------------|
| `openness` | 0-100 | Creativity, curiosity |
| `conscientiousness` | 0-100 | Organization, discipline |
| `extraversion` | 0-100 | Energy, sociability |
| `agreeableness` | 0-100 | Cooperation, empathy |
| `neuroticism` | 0-100 | Emotional reactivity |

All five fields are required integers. There is no auto-fill; each value must be chosen deliberately to reflect the agent's personality.

### mbti

MBTI describes how the agent processes information through its cognitive function stack.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | string | Yes | One of the 16 MBTI types (e.g. `INTJ`, `ENFJ`) |
| `dominant` | string | No | Auto-filled from type |
| `auxiliary` | string | No | Auto-filled from type |
| `tertiary` | string | No | Auto-filled from type |
| `inferior` | string | No | Auto-filled from type |

All four cognitive functions are auto-filled from the type string. You only need to specify `type`.

Cognitive functions: `Ni` (Introverted Intuition), `Ne` (Extraverted Intuition), `Si` (Introverted Sensing), `Se` (Extraverted Sensing), `Ti` (Introverted Thinking), `Te` (Extraverted Thinking), `Fi` (Introverted Feeling), `Fe` (Extraverted Feeling).

## mental_models

| Field | Type | Max items | Description |
|-------|------|-----------|-------------|
| `primary` | list of strings | 5 | Main decision frameworks (e.g. `Clean Architecture (Uncle Bob)`) |
| `secondary` | list of strings | 5 | Supporting heuristics |

## authority

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `veto` | boolean | false | Can block any decision. Tier 0 only. |
| `push_code` | boolean | false | May push code to the repository. |
| `deploy` | boolean | false | May trigger deployments. |
| `approve_architecture` | boolean | false | May approve architecture decisions. |
| `approve_quality` | boolean | false | May approve quality gates. |
| `approve_budget` | boolean | false | May approve budget. |
| `block_release` | boolean | false | May block a release. |
| `block_delivery` | boolean | false | May block a delivery. |
| `orchestrate` | boolean | false | May dispatch subagents. |
| `delegates_to` | list of strings | [] | Agent IDs this agent can assign work to. |
| `escalates_to` | string or null | null | Agent ID to escalate unresolvable issues to. Tier 0 agents leave this null. |

## expertise

| Field | Type | Description |
|-------|------|-------------|
| `domains` | list of strings | Topic areas (e.g. `Laravel 11 / PHP 8.3`) |
| `frameworks` | list of strings | Named frameworks used (e.g. `Clean Architecture`) |
| `knowledge_sources` | list of strings | Obsidian `[[wikilinks]]` grounding this agent's expertise |
| `depth` | string | `novice`, `intermediate`, `expert`, or `master` |
| `years_equivalent` | integer | Experience depth in years equivalent |

## communication

| Field | Type | Description |
|-------|------|-------------|
| `language` | string | BCP 47 language code (e.g. `en`, `pt`) |
| `tone` | string | Free text description of tone (e.g. `concise, technical, shows code`) |
| `vocabulary_level` | string | `basic`, `intermediate`, `advanced`, or `specialist` |
| `preferred_format` | string | Free text (e.g. `code snippets with inline comments`) |
| `avoid` | list of strings | Patterns the agent must not use in output |

## Cross-Framework Consistency Validation

`core/agents/validator.py` runs five checks after Pydantic parsing. All checks are advisory warnings except the veto/tier check which is a hard error.

### Check 1: DISC primary vs Enneagram type

| DISC primary | Compatible Enneagram types |
|-------------|---------------------------|
| D | 1, 3, 7, 8 |
| I | 2, 3, 7, 9 |
| S | 2, 6, 9 |
| C | 1, 5, 6 |

An S with Enneagram 8 (Challenger) is flagged as unusual. The combination is not rejected, but the contributor should have a deliberate reason.

### Check 2: DISC primary vs MBTI type

| DISC primary | Compatible MBTI types |
|-------------|----------------------|
| D | ENTJ, ESTJ, INTJ, ESTP, ENTP |
| I | ENFP, ESFP, ENFJ, ENTP, ESFJ |
| S | ISFJ, INFP, ESFJ, ISFP, INFJ |
| C | INTJ, ISTJ, INTP, ISTP, INFJ |

### Check 3: DISC primary vs Big Five expectations

| DISC primary | Big Five trait | Expected range |
|-------------|---------------|----------------|
| D | extraversion | mid-high (45-100) |
| D | agreeableness | low-mid (0-55) |
| D | conscientiousness | mid-high (45-100) |
| I | extraversion | high (65-100) |
| I | agreeableness | mid-high (45-100) |
| I | openness | mid-high (45-100) |
| S | agreeableness | high (65-100) |
| S | neuroticism | low-mid (0-55) |
| S | extraversion | low-mid (0-55) |
| C | conscientiousness | high (65-100) |
| C | openness | mid-high (45-100) |
| C | neuroticism | low-mid (0-55) |

A C-type agent with conscientiousness of 30 will produce a warning: the precision-driven DISC style is inconsistent with low discipline.

### Check 4: Tier vs authority.veto

- Tier 0: expected to have `veto: true` (warning if missing)
- Tier 2+: must not have `veto: true` (hard error)

### Check 5: Tier 0 vs escalates_to

Tier 0 agents are the top of the hierarchy. Setting `escalates_to` on a tier-0 agent produces a warning.

### Validation score

The validator returns a score from 0.0 to 1.0 (fraction of checks passed). `is_valid` is `false` only when there are hard errors (tier-2+ with veto). Warnings do not block loading.

## How Agents Are Loaded

`core/agents/loader.py` provides two public functions:

**`load_agent(path)`** — reads a single YAML file, calls `Agent.model_validate(data)`. Raises `FileNotFoundError` or `ValueError` on failure.

**`load_all_agents(base_dir, department=None)`** — scans `<base_dir>/*/agents/` using `rglob("*.yaml")`, which picks up sub-squad subdirectories (e.g. `departments/dev/agents/backend-core/*.yaml`). Failed files emit a `warnings.warn` and are skipped; the rest are returned.

## The DNA Registry

`core/agents/dna_registry.py` provides a `DNARegistry` class and a module-level singleton:

```python
from core.agents.dna_registry import get_registry

registry = get_registry()
agent = registry.get("backend-dev-andre")
c_types = registry.by_disc(DISCType.C)
analysts = registry.by_big_five(conscientiousness_min=80)
```

Available query methods: `get(id)`, `all()`, `by_disc(primary)`, `by_enneagram(type)`, `by_mbti(type)`, `by_department(dept)`, `by_tier(tier)`, `by_big_five(...)`, `compatible_with(id)`, `contrasting_disc(id)`.

## The Agents Registry JSON

`core/agents/registry_gen.py` generates `knowledge/agents-registry-v2.json` from all YAML files. Run it with:

```bash
python -m core.agents.registry_gen
```

The output file includes `_meta` with total counts, tier distribution, department distribution, and DISC distribution. It is the machine-readable source of truth consumed by the dashboard and Synapse.

## Annotated Example

The following is a complete, production agent definition (`departments/dev/agents/backend-dev.yaml`, abbreviated for clarity).

```yaml
# Identity
id: backend-dev-andre        # Unique slug. Becomes ~/.claude/agent-memory/arka-backend-dev-andre/
name: Andre
role: Backend Core Lead
department: dev              # Must match parent directory
tier: 2                      # Specialist: executes, no veto
model: sonnet                # Explicit; sonnet is also the tier-2 default

# Sub-squad placement (v2.27.0 pattern)
parent_squad: dev
sub_squad_role: lead

behavioral_dna:
  disc:
    primary: C               # Conscientiousness: analytical, systematic
    secondary: S             # Steadiness: methodical, not urgent
    communication_style: "Methodical, code-speaks, prefers PRs over meetings"
    under_pressure: "Goes quieter, writes more tests, refactors for safety"
    motivator: "Clean architecture, well-tested code, elegant solutions"

  enneagram:
    type: 5                  # Investigator: deep mastery drive
    wing: 6                  # Adjacent wing — valid (5 accepts 4 or 6)
    core_motivation: "Deep mastery of backend systems and patterns"
    core_fear: "Shipping untested code or fragile architecture"
    subtype: self-preservation

  big_five:
    openness: 65             # C-type: mid-high, within expected range
    conscientiousness: 88    # C-type: high — passes Check 3
    extraversion: 28         # C-type: low — slightly outside low-mid; produces warning
    agreeableness: 58        # C-type: mid — acceptable
    neuroticism: 22          # C-type: low-mid — passes Check 3

  mbti:
    type: ISTJ               # C-compatible — passes Check 2
    # dominant/auxiliary/tertiary/inferior auto-filled: Si, Te, Fi, Ne

mental_models:
  primary:
    - "Clean Architecture (Uncle Bob)"
    - "DDD Tactical Patterns (Vernon)"
  secondary:
    - "Repository Pattern"
    - "CQRS"

authority:
  push_code: true
  # veto omitted (defaults false) — correct for tier 2
  delegates_to:
    - laravel-eng-goncalo
    - python-eng-diogo
  escalates_to: tech-lead-paulo

expertise:
  domains:
    - Laravel 11 / PHP 8.3
    - PostgreSQL / Supabase
    - REST API design
  frameworks:
    - Clean Architecture
    - TDD
  depth: expert
  years_equivalent: 10

communication:
  language: en
  tone: "concise, technical, shows code"
  vocabulary_level: specialist
  preferred_format: "code snippets with inline comments"
  avoid:
    - "business logic in controllers"
    - "raw SQL in application layer"
```

## Sub-Squad Agents

From v2.27.0, agents may belong to a sub-squad inside their department. This is declared with `parent_squad` and `sub_squad_role`. Sub-squad YAML files may live in a subdirectory under the department's `agents/` folder (e.g. `departments/dev/agents/backend-core/laravel-eng.yaml`). The `rglob` in `load_all_agents` picks these up automatically.

`sub_squad_role` is only valid when `parent_squad` is also set. Setting one without the other raises a Pydantic `ValueError`.

## Behavior Enforcement

`core/agents/behavior_enforcer.py` provides advisory runtime checks that compare agent output against its DNA profile. These are warnings only — they do not block execution. The enforcer checks:

- **Tone**: D-type agents must use decisive command language; S-type agents must not use urgency markers; C-type agents must use structured output.
- **Vocabulary**: `specialist`-level agents should use domain-specific technical terms.
- **Communication style**: agents with `preferred_format: structured` should use headers, numbered lists, or tables in long outputs.
- **Avoid list**: outputs containing any string from `communication.avoid` produce an INFO-level drift.

---

Related: [ARCHITECTURE.md](ARCHITECTURE.md) — system data flow and core modules. [DEPARTMENTS.md](DEPARTMENTS.md) — per-department agent roster. [GETTING-STARTED.md](GETTING-STARTED.md) — contributor setup.
