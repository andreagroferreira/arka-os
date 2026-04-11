---
name: arka-forge
description: >
  The Forge — ArkaOS intelligent multi-agent planning engine. Complexity-based
  escalation, critic synthesis, visual companion, Obsidian persistence.
  Analyses any prompt across 5 dimensions, routes to 1-3 explorer subagents,
  runs a critic synthesis, and produces an approved ForgePlan before execution.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch, WebSearch]
---

# The Forge — ArkaOS Intelligent Planning Engine

> **Engine:** `core/forge/` | **Plans stored:** `~/.arkaos/plans/` | **Obsidian:** `ArkaOS/Forge/`
> **Tiers:** Shallow (score ≤30) · Standard (31-65) · Deep (≥66)
> **Explorers:** Pragmatic · Architectural · Contrarian

## Commands

| Command | Description | When to use |
|---------|-------------|-------------|
| `/forge <prompt>` | Forge a new plan | Any task you want planned before executing |
| `/forge resume` | Resume approved plan | After a session break, repo drift, or restart |
| `/forge status` | Show active forge status | Check what plan is currently active |
| `/forge history` | List all past plans | Browse plans saved in `~/.arkaos/plans/` |
| `/forge show <id>` | Show plan detail | Inspect a specific plan by ID |
| `/forge compare <id1> <id2>` | Compare two plans side-by-side | Evaluate alternative approaches |
| `/forge patterns` | List extracted patterns | See reusable patterns from past plans |
| `/forge cancel` | Cancel active forge | Discard current plan without executing |

---

## Main Flow: `/forge <prompt>`

Execute every step sequentially. Never skip steps. Announce each step before running it.

### Step 1 — Context Snapshot

Collect the current repo context by running these Bash commands:

```bash
git rev-parse HEAD         # commit hash
git branch --show-current  # branch name
git remote get-url origin  # repo name
cat VERSION 2>/dev/null || echo "unknown"  # ArkaOS version
```

Build a context dict:
```
repo: <origin url or directory name>
branch: <current branch>
commit_at_forge: <HEAD hash>
arkaos_version: <VERSION file content>
prompt: <original user prompt>
```

### Step 2 — Obsidian Knowledge Check

Search Obsidian for relevant patterns and past plans using the MCP obsidian tool:

1. Search `ArkaOS/Forge/Patterns/` for patterns matching keywords from the prompt
2. Search `ArkaOS/Forge/Plans/` for plans with similar names or tags

Collect:
- `similar_plans: list[str]` — IDs of plans with overlapping domain/scope
- `reused_patterns: list[str]` — pattern names that match this prompt's domain

If Obsidian is unavailable, set both to `[]` and continue.

### Step 3 — Complexity Analysis

Call the complexity scorer via Python:

```python
import sys
sys.path.insert(0, '<repo_root>')
from core.forge.complexity import analyze_complexity

result = analyze_complexity(
    prompt="<user prompt>",
    affected_files=[],          # estimate from prompt keywords: auth→auth/, db→core/db/, etc.
    departments=[],             # estimate from prompt: "deploy"→ops, "feature"→dev, etc.
    similar_plans=similar_plans,
    reused_patterns=reused_patterns,
)
print(f"score={result.score} tier={result.tier.value}")
print(f"scope={result.dimensions.scope} deps={result.dimensions.dependencies}")
print(f"ambiguity={result.dimensions.ambiguity} risk={result.dimensions.risk} novelty={result.dimensions.novelty}")
```

Run this as a Bash command: `cd <repo_root> && python -c "..."`.

Display the complexity breakdown using the renderer:

```python
from core.forge.renderer import render_complexity
print(render_complexity(result))
```

### Step 4 — Tier Confirmation

Display to user:

```
⚒ FORGE — Complexity Analysis

  Score: <score>/100 (<Tier>)
  │ Scope    │ <n> │ ██████░░░░
  │ Deps     │ <n> │ ████░░░░░░
  │ Ambig.   │ <n> │ ███████░░░
  │ Risk     │ <n> │ █████░░░░░
  │ Novelty  │ <n> │ ██░░░░░░░░

  Tier: <Tier> → <N> explorer(s) + <critic>
  Similar plans: <list or "none found">
  Reusing patterns: <list or "none">

Proceed with <Tier> tier? [Y/n/override shallow|standard|deep]
```

Wait for user input. Accept `Y` or Enter to proceed. Accept `override <tier>` to change tier. Accept `n` to abort.

### Step 5 — Launch Explorer Subagents

Launch explorer subagents **in parallel** based on confirmed tier:

| Tier | Explorers | Run |
|------|-----------|-----|
| shallow | 1 — Pragmatic only | Sequential (inline) |
| standard | 2 — Pragmatic + Architectural | Parallel via Agent tool |
| deep | 3 — Pragmatic + Architectural + Contrarian | Parallel via Agent tool |

For **shallow**, run the Pragmatic explorer inline (no subagent needed — just generate the approach directly).

For **standard** and **deep**, use the Agent tool to dispatch each explorer as a subagent. Pass the full explorer prompt (see Explorer Subagent Instructions below).

Each explorer must return a structured response:
```
EXPLORER: <lens>
SUMMARY: <2-3 sentence description of the approach>
KEY_DECISIONS:
  - decision: <what>
    rationale: <why>
PHASES:
  - name: <phase name>
    department: <dev|ops|mkt|brand|fin|strat|pm|saas|landing|content|ecom|kb|sales|lead|community|org>
    agents: [<agent names>]
    deliverables: [<list>]
    acceptance_criteria: [<list>]
    depends_on: [<phase names that must complete first>]
```

### Step 6 — Launch Critic Subagent

Assemble all explorer outputs. Strip explorer lens labels (anonymize) before sending to critic.

Launch a Critic subagent via the Agent tool with the Critic Subagent Instructions below.

The critic must return:
```
CONFIDENCE: <0.0-1.0>
SYNTHESIS:
  pragmatic: [<adopted elements>]
  architectural: [<adopted elements>]
  contrarian: [<adopted elements>]  # if applicable
REJECTED:
  - element: <what was rejected>
    reason: <why>
RISKS:
  - risk: <description>
    severity: high|medium|low
    mitigation: <how to address>
FINAL_PHASES:
  - name: <phase name>
    department: <dept>
    agents: [<list>]
    deliverables: [<list>]
    acceptance_criteria: [<list>]
    depends_on: [<list>]
```

### Step 7 — Render Terminal Output

Build the ForgePlan object and render it:

```python
from core.forge.renderer import render_terminal
from core.forge.handoff import select_execution_path

# Build plan object from collected data
# Call render_terminal(plan) to get the display string
# Call select_execution_path(plan.plan_phases) to determine execution route
```

Display:
```
⚒ FORGE — <Plan Name>

▸ Context Snapshot
  Repo: <repo> @ <commit>
  ArkaOS: <version> | Branch: <branch>

▸ Complexity Analysis
  <render_complexity output>

▸ Critic Verdict
  Confidence: <score>
  ✓ <N> elements adopted
  ✗ <N> elements rejected
  ⚠ <N> risks identified

▸ Plan: <N> phases across <N> department(s)
  Phase 1: <name>                     [dept]     ░░░░░░░░
  Phase 2: <name>                     [dept]     ░░░░░░░░
  ...

  Execution: <type> → <target>
  Departments: <list>
  QG required: yes

  [A]pprove  [R]evise  [C]ompanion  [D]etail phase  [Q]uit
```

### Step 8 — User Decision

Wait for user input and handle each option:

| Input | Action |
|-------|--------|
| `A` or `approve` | Proceed to Step 9 (handoff) |
| `R <text>` or `revise <text>` | Proceed to Revision Flow |
| `C` or `companion` | Generate HTML companion (Step 6a), then re-show menu |
| `D <n>` or `detail <n>` | Show full detail for phase N (agents, deliverables, criteria), then re-show menu |
| `Q` or `quit` | Save plan as `draft`, clear active, exit |

### Step 6a — Visual Companion (on C input)

Generate HTML via the renderer and serve locally:

```python
from core.forge.renderer import render_html, should_suggest_companion

html_content = render_html(plan)
# Write to /tmp/forge-<plan_id>.html
```

```bash
# Write HTML file
python -c "
import sys
sys.path.insert(0, '<repo_root>')
# ... build plan, call render_html, write to /tmp/forge-<id>.html
"

# Serve on random available port
python -m http.server 0 --directory /tmp &
# Open in browser
open http://localhost:<port>/forge-<id>.html
```

Tell user: "Visual companion available at http://localhost:<port>/forge-<id>.html"

Note: For `shallow` tier, companion is not generated (`should_suggest_companion()` returns `"none"`).
For `standard`, it is available on request. For `deep`, proactively suggest it.

### Step 9 — Handoff (on Approve)

1. Check for repo drift since the snapshot:

```python
from core.forge.handoff import check_repo_drift
drift = check_repo_drift(plan.context.commit_at_forge)
if drift["changed"]:
    # Warn user: "Repo changed since forge: X files modified"
    # Ask: "Re-run complexity analysis? [y/N]"
```

2. Determine execution path:

```python
from core.forge.handoff import select_execution_path, generate_workflow_yaml
path = select_execution_path(plan.plan_phases)
```

3. If path type is `workflow` or `enterprise_workflow`, generate and save the YAML:

```python
workflow_yaml = generate_workflow_yaml(plan)
# Write to .arkaos/workflows/<plan_id>.yaml
```

4. Update plan status to `approved`, set `executed_at` timestamp.

5. Save and set as active:

```python
from core.forge.persistence import save_plan, set_active_plan
save_plan(plan)
set_active_plan(plan.id)
```

6. Announce:

```
⚒ FORGE — Approved

  Plan ID: <id>
  Execution: <type> → <target>
  Branch: <suggested branch name>

  Ready. Proceeding with execution.
```

7. Hand off to the appropriate executor:
   - `skill` → invoke the named ArkaOS skill with plan context
   - `workflow` or `enterprise_workflow` → invoke `/dev feature` or equivalent department command, passing forge context as preamble

### Step 10 — Persist to YAML + Obsidian

After approval (or on quit/cancel):

```python
from core.forge.persistence import save_plan, export_to_obsidian

path = save_plan(plan)
obsidian_path = export_to_obsidian(plan)
```

For approved + completed plans, also extract patterns:

```python
from core.forge.persistence import extract_patterns
patterns = extract_patterns(plan)
if patterns:
    print(f"  Patterns extracted: {len(patterns)}")
```

---

## Explorer Subagent Instructions

Each explorer subagent receives this preamble, then its specific lens instruction.

**Preamble (send to all explorers):**

```
You are an expert planning agent within ArkaOS. Your task is to produce a
structured execution plan for the following prompt.

PROMPT: <original user prompt>

REPO CONTEXT:
  Repo: <repo>
  Branch: <branch>
  Commit: <commit>
  ArkaOS: <version>

OBSIDIAN KNOWLEDGE:
  Similar plans found: <list or "none">
  Reusable patterns: <list or "none">

CONSTITUTION RULES (non-negotiable):
  - branch-isolation: all work on feature branches, never main
  - spec-driven: spec must exist before implementation
  - solid-clean-code: SOLID + Clean Code on all code
  - mandatory-qa: tests must pass, coverage >= 80%
  - quality-gate: Marta + Eduardo + Francisca must APPROVE before done
  - conventional-commits: all commits follow conventional commit format

AVAILABLE DEPARTMENTS: dev, ops, mkt, brand, fin, strat, pm, saas,
  landing, content, ecom, kb, sales, lead, community, org

AVAILABLE AGENTS (examples):
  dev: Paulo (lead), Gabriel (architect), Andre (backend), Diana (frontend),
       Bruno (security), Carlos (devops), Rita (qa), Vasco (dba)
  ops: Daniel (lead), Lucas (automation)
  mkt: Luna (lead), Sofia (growth), Pedro (analytics), Carla (email)
  brand: Valentina (lead), Miguel (visual), Ana (copy), Joao (ux)
  quality (cross-cutting): Marta (CQO), Eduardo (copy), Francisca (tech)

Your output MUST follow this exact format:
EXPLORER: <your lens name>
SUMMARY: <2-3 sentences>
KEY_DECISIONS:
  - decision: <what>
    rationale: <why>
PHASES:
  - name: <phase name>
    department: <dept>
    agents: [<names>]
    deliverables: [<items>]
    acceptance_criteria: [<items>]
    depends_on: [<phase names>]
```

**Pragmatic Explorer lens instruction:**

```
Your lens: PRAGMATIC
Question to answer: "What is the simplest thing that works?"
Principles:
  - Minimum viable approach — reuse existing patterns, avoid over-engineering
  - Maximum reuse of existing ArkaOS skills and workflows
  - Fewer phases is better — collapse where safe to do so
  - Prefer known, proven solutions over novel ones
  - Identify what can be skipped without meaningful quality loss
Be direct. Challenge gold-plating. Propose the leanest plan that still
satisfies all Constitution rules.
```

**Architectural Explorer lens instruction:**

```
Your lens: ARCHITECTURAL
Question to answer: "What is the right way to build this for the long term?"
Principles:
  - Long-term extensibility and maintainability over short-term speed
  - Proper separation of concerns, clean boundaries
  - Identify technical debt that would be created by a simpler approach
  - Ensure observability, testability, and deployability are first-class
  - Reference DDD, SOLID, Clean Architecture where applicable
Be thorough. Do not cut corners that will create future problems.
```

**Contrarian Explorer lens instruction:**

```
Your lens: CONTRARIAN
Question to answer: "What is everyone missing or assuming wrongly?"
Principles:
  - Challenge the premise of the prompt — is this the right problem to solve?
  - Surface hidden dependencies, risks, and blockers others would miss
  - Question every assumed constraint — are they real?
  - Propose an alternative framing if the original prompt is misguided
  - Identify the single biggest risk in the other approaches
Be adversarial but constructive. Your job is to stress-test assumptions,
not to be contrarian for its own sake. You must still produce a valid plan.
```

---

## Critic Subagent Instructions

The critic receives anonymized approaches (lens labels stripped). Send this prompt:

```
You are the Plan Critic within ArkaOS. You have received <N> independent
planning approaches for the same prompt. Your job is to synthesize the best
plan by combining the strongest elements from each approach.

PROMPT: <original user prompt>

APPROACHES:
<approach_1_phases_and_decisions — label stripped>
---
<approach_2_phases_and_decisions — label stripped>
---
<approach_3_phases_and_decisions — label stripped, if deep tier>

RULES:
  - You MUST adopt the best elements from multiple approaches (do not just pick one)
  - You MUST reject at least 1 element with a clear reason
  - You MUST identify at least 1 risk in the final plan
  - Confidence score must reflect genuine uncertainty (do not always output 0.9)
  - The final phase list MUST include a Quality Gate phase as the penultimate step
  - The final phase list MUST include an Obsidian persistence phase as the last step
  - All Constitution rules apply to the final plan

Your output MUST follow this exact format:
CONFIDENCE: <0.0-1.0>
SYNTHESIS:
  approach_1: [<adopted elements from approach 1>]
  approach_2: [<adopted elements from approach 2>]
  approach_3: [<adopted elements from approach 3, if applicable>]
REJECTED:
  - element: <what>
    reason: <why>
RISKS:
  - risk: <description>
    severity: high|medium|low
    mitigation: <how to address>
FINAL_PHASES:
  - name: <phase name>
    department: <dept>
    agents: [<names>]
    deliverables: [<items>]
    acceptance_criteria: [<items>]
    depends_on: [<phase names>]
```

---

## Revision Flow

Triggered when user inputs `R <revision text>` at the decision menu.

1. Do NOT re-run explorers. The critic re-evaluates incrementally.
2. Increment `plan.revision_count` by 1.
3. Send the critic subagent the current plan + user revision text:

```
REVISION REQUEST: <user revision text>
CURRENT PLAN VERSION: <revision_count>

Current phases:
<current final phases>

Current risks:
<current risks>

Update the plan to incorporate the revision. Apply the same output format.
Only change what the revision explicitly requests. Preserve everything else.
```

4. Update plan with new critic output.
5. Re-render terminal output (Step 7) with updated plan.
6. Re-show the `[A]pprove [R]evise [C]ompanion [D]etail [Q]uit` menu.

Maximum 5 revisions. After 5, warn user and offer approve-as-is or quit.

---

## Secondary Commands

### `/forge resume`

1. Call `get_active_plan()` from `core.forge.persistence`
2. If no active plan: "No active forge plan. Run `/forge <prompt>` to start."
3. If plan found:
   - Call `check_repo_drift(plan.context.commit_at_forge)`
   - If drift detected: warn user, offer to re-run complexity analysis
   - Re-render terminal output (Step 7)
   - Re-show decision menu (Step 8)

### `/forge status`

1. Call `get_active_plan()` from `core.forge.persistence`
2. If none: "No active forge plan."
3. Display:
```
⚒ FORGE — Active Plan

  ID: <id>
  Name: <name>
  Status: <status>
  Tier: <tier> | Score: <score>/100
  Confidence: <critic confidence>
  Phases: <N> across <depts>
  Created: <timestamp>
  Revisions: <count>
```

### `/forge history`

1. Call `list_plans()` from `core.forge.persistence`
2. If empty: "No forge plans found in ~/.arkaos/plans/"
3. Display table:
```
⚒ FORGE — History

  ID                    Name                    Status      Tier      Conf.  Created
  forge-20260411-abc1   Add auth module         approved    deep      0.87   2026-04-11
  forge-20260410-def2   Refactor billing flow   completed   standard  0.74   2026-04-10
  ...
```

### `/forge show <id>`

1. Call `load_plan(id)` from `core.forge.persistence`
2. If not found: "Plan <id> not found."
3. Display full terminal render via `render_terminal(plan)`
4. Then show all approaches (explorer summaries) and full critic verdict.

### `/forge compare <id1> <id2>`

1. Load both plans via `load_plan()`
2. Display side-by-side:
```
⚒ FORGE — Comparing Plans

  Left: <id1> (<name1>)  |  Right: <id2> (<name2>)
  Score: <s1>/100 (<tier1>) | Score: <s2>/100 (<tier2>)
  Confidence: <c1>          | Confidence: <c2>
  Phases: <n1>              | Phases: <n2>

  PHASES LEFT                     PHASES RIGHT
  ─────────────────────────────── ───────────────────────────────
  Phase 1: <name>  [dept]         Phase 1: <name>  [dept]
  Phase 2: <name>  [dept]         Phase 2: <name>  [dept]
  ...

  RISK DELTA:
  Left risks not in right: <list>
  Right risks not in left: <list>
```

### `/forge patterns`

1. Call `load_patterns()` from `core.forge.persistence`
2. If empty: "No patterns found in ArkaOS/Forge/Patterns/"
3. Display:
```
⚒ FORGE — Reusable Patterns

  Name                              Tier      Depts          Phases  Used
  repo-dev-ops-pattern              deep      dev, ops       6       3
  repo-dev-pattern                  standard  dev            4       7
  ...
```

### `/forge cancel`

1. Load active plan via `get_active_plan()`
2. If none: "No active plan to cancel."
3. Confirm: "Cancel plan '<name>'? This cannot be undone. [y/N]"
4. On confirm: set `plan.status = ForgeStatus.CANCELLED`, call `save_plan()`, call `clear_active_plan()`
5. "Forge plan cancelled. No changes were made to the codebase."

---

## Constitution Compliance

The Forge enforces these Constitution rules at the plan level:

| Rule | Enforcement |
|------|-------------|
| `branch-isolation` | Every plan must include a "Create feature branch" step in Phase 1 |
| `spec-driven` | Plans touching code must have a Specification phase before Implementation |
| `mandatory-qa` | All plans must include a QA phase (Rita) before Quality Gate |
| `quality-gate` | All plans must end with a Quality Gate phase (Marta + Eduardo + Francisca) |
| `obsidian-output` | All plans must end with an Obsidian persistence step |
| `conventional-commits` | Remind in handoff message |

If a critic output violates any of these, inject the missing phases automatically before showing the plan to the user. Announce: "Constitution enforcement: added missing <phase name> phase."

---

## Plan ID Format

Plan IDs follow the format: `forge-YYYYMMDD-<4-char hex>`

Example: `forge-20260411-a3f2`

Generate with:
```python
import hashlib, datetime
date = datetime.date.today().strftime("%Y%m%d")
suffix = hashlib.md5(prompt.encode()).hexdigest()[:4]
plan_id = f"forge-{date}-{suffix}"
```
