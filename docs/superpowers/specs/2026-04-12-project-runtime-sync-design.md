# Project Runtime Sync — v2.17.0 Design Spec

**Date:** 2026-04-12
**Target version:** v2.17.0 (umbrella) + v2.16.1 (bundled patch)
**Author:** Platform Squad
**Status:** Approved for planning

## Problem

`/arka update` currently syncs only three artefacts per project: `.mcp.json` (stack normalization), `.claude/settings.local.json`, and descriptors. Everything else that dictates project behavior — `CLAUDE.md`, rules, agents, hooks, constitution excerpts — is left frozen at the version the project was onboarded with.

Consequences:

- Core rules added in v2.16.0 (`model-routing`, `subagent-discipline`) are **not active** in any of the 81 projects.
- New agents added to core are invisible to projects unless manually copied.
- MCP servers load ~93k tokens/session of tools the project will never use (e.g., Canva tools in a Laravel backend), wiping out the 40k gain from the v2.16.0 campaign.
- Missing env vars produce unstructured warnings per session (e.g., `fovory-supplier-sync` postgres).
- A descriptor bug (`core/sync/descriptor_syncer.py` treats scalar `stack:` as iterable) crashes sync for 2 projects and is shipped since v2.16.0.

## Goals

1. Every `/arka update` brings **all 81 projects** to the current core behavior: CLAUDE.md, rules, hooks, agents, constitution — not just configs.
2. MCP configs per project are **optimized** (deferred-load unused servers) — target saving ~70k tokens/session.
3. Env var gaps are **resolved deterministically**: injected from a user vault when present, surfaced as structured warnings when not.
4. Agents the project needs but doesn't have are **provisioned just-in-time** (copied from core, or created if missing) with an approval gate.
5. Sync is **self-healing**: transient errors retry; idempotent re-runs converge.
6. Ship the v2.16.1 descriptor bugfix as part of the same release train.

## Non-goals

- Rewriting the sync discovery layer (`core/sync/discovery.py`).
- Changing the runtime adapters (Claude Code, Codex, Gemini, Cursor).
- Retroactive migration of v1 projects (existing migration path stays).
- A UI for policy editing (YAML-only in this release).

## Architecture

```
/arka update  (CLI)
  │
  ▼
core/sync/engine.py  ── discovers 81 projects ───┐
  │                                              │
  ▼                                              ▼
  Phase 1: MCP Optimizer (hybrid C+A)       Reporter
  Phase 2: Settings
  Phase 3: Descriptors  (bugfix from 2.16.1)
  Phase 4: Content Sync — CLAUDE.md merge
  Phase 5: Content Sync — rules/*
  Phase 6: Content Sync — hooks/*
  Phase 7: Content Sync — constitution excerpts
  Phase 8: Agent Baseline Sync (per-stack allowlist)
    │
    └─ Runtime (separate, triggered by Claude Code hooks):
       Dynamic Agent Provisioning
         • PreToolUse hook intercepts missing agent dispatch
         • Checks core registry → copies to project
         • If missing in core → approval gate → Skill Architect creates → commit → retry dispatch
  Phase 9: Self-healing wrap (retry + idempotence assertions)
```

All phases reuse the existing `Project` schema (`core/sync/schema.py`). Each phase returns a typed result with `status ∈ {unchanged, updated, error}` and a `changes: list[str]` trail.

## Sub-feature decomposition

The umbrella is decomposed into four sub-features, each with its own implementation plan and PR. A fifth item (v2.16.1 patch) ships first.

| # | Sub-feature | Phases it owns | Risk | Plan order |
|---|---|---|---|---|
| **0** | **v2.16.1 patch** — descriptor bugfix + 2 file normalization | Phase 3 fix | Low | 1st |
| **A** | **Content Sync** — merge engine for CLAUDE.md, rules, hooks, constitution | 4, 5, 6, 7 | Medium | 2nd |
| **B** | **MCP Optimizer** — hybrid policy+AI, env vault, override | 1 upgrade | Medium | 3rd |
| **C** | **Dynamic Agent Provisioning** — hook + command, auto create with approval | 8 + runtime | High | 4th |
| **D** | **Self-healing Sync** — retry, structured errors, idempotence | 9 | Low | 5th |

Release cuts after D ships → `v2.17.0`.

## Sub-feature A — Content Sync

**Goal:** project-local versions of CLAUDE.md, rules, hooks, and relevant constitution rules converge to the core's current state while preserving project-authored customizations.

### Merge model (intelligent merge, not overwrite)

Every target file is divided into **managed regions** and **free regions** using HTML comment markers:

```markdown
<!-- arkaos:managed:start version=2.17.0 hash=abc123 -->
...core-owned content, overwritten on every sync...
<!-- arkaos:managed:end -->

## Project-specific notes

...user content, preserved forever...
```

**On sync:**

1. Read target file from project.
2. If the file has no marker block → treat entire file as project-authored; prepend a fresh managed block at the top.
3. If markers exist → replace only the content between them. Compute hash of new managed content; if unchanged, report `unchanged`.
4. On parse errors (malformed markers, unbalanced, encoding) → fall back to writing a new file at `<target>.arkaos-new`, leave original untouched, emit error.

### Files in scope

| File | Source | Target | Managed strategy |
|---|---|---|---|
| `CLAUDE.md` | `CLAUDE.md` (core) + stack overlays | `<project>/.claude/CLAUDE.md` or `<project>/CLAUDE.md` | Managed block |
| Rules | `config/standards/rules/*.md` | `<project>/.claude/rules/*.md` | Full file replace if unchanged by project, else managed block |
| Hooks | `config/hooks/*.sh` | `<project>/.claude/hooks/*.sh` | Full file replace (hooks are not hand-edited per project) |
| Constitution excerpt | filtered `config/constitution.yaml` | `<project>/.claude/constitution-applicable.md` | Full file generate |

### Stack overlays

Core CLAUDE.md is generic. Per stack, additional sections are merged in:

- Laravel → SOLID reminders, Form Request conventions
- Nuxt/Vue → Composition API, composables patterns
- Python → pytest, virtual env rules

Overlays live in `config/standards/claude-md-overlays/<stack>.md` and are concatenated into the managed block.

## Sub-feature B — MCP Optimizer (hybrid)

**Goal:** each project's `.mcp.json` declares only the MCPs it needs loaded; the rest are marked `"deferred": true` so runtimes use ToolSearch instead of eager loading.

### Files

- **`config/mcp-policy.yaml`** (core, versioned) — deterministic rules
- **`~/.arkaos/secrets.json`** (user, gitignored, chmod 600) — env var vault
- **`<project>/.arkaos/mcp-override.yaml`** (project, versioned) — project-level overrides

See "Schemas" section below for concrete shapes.

### Decision pipeline per project

```
for each MCP in project.mcp.json:
  1. policy_decision = apply_policy(mcp, project.stack, project.ecosystem)
     # returns: active | deferred | ambiguous
  2. if policy_decision == ambiguous:
     ai_decision = haiku_decide(mcp, project.stack, project.ecosystem, cache_key)
     # cache_key = hash(stack + ecosystem + mcp_name)
     # cached in ~/.arkaos/mcp-decisions.cache.json
  3. final = override.force_active/force_deferred if present else (policy or ai) decision
  4. write .mcp.json with "deferred": true on deferred ones
  5. for each env var in mcp.env required:
     - if vault has value → inject (into .env or direct in .mcp.json if marked safe)
     - else → append to <project>/.env.example with placeholder, emit structured warning
```

### AI prompt contract (Haiku)

Input: project stack list, ecosystem, ambiguous MCP name + its advertised purpose.
Output: strict JSON `{"decision": "active" | "deferred", "reason": "<=80 chars>"}`.
Budget: max 500 tokens per call. All calls cached by `(stack_hash, ecosystem, mcp_name)`.

## Sub-feature C — Dynamic Agent Provisioning

**Goal:** when a project dispatches an agent it doesn't have, the system provisions it (from core, or creates it with approval) and retries the dispatch — no crash.

### Baseline (Phase 8, sync-time)

Each project ships with a **stack-based allowlist** of core agents copied into `<project>/.claude/agents/`. Examples:

- Laravel → backend-dev, qa-eng, devops-eng, architect, security-eng
- Nuxt → frontend-dev, backend-dev, qa-eng, devops-eng
- Content — content-creator, copywriter, seo-analyst
- Every project → strategy-director, cqo, copy-director, tech-ux-director (Quality Gate trio always present)

Allowlists live in `config/agent-allowlists/<stack>.yaml`.

### Runtime provisioning (hook-driven)

**Hook:** `config/hooks/agent-provision.sh` registered as `PreToolUse` for the `Task` tool.

Flow:
1. Hook reads the `subagent_type` from the Task call.
2. If the agent exists locally in `.claude/agents/` → allow.
3. If not, checks core registry (`knowledge/agents-registry-v2.json`):
   - **Exists in core** → copy to `<project>/.claude/agents/<name>.md`, log, allow.
   - **Missing in core** → emit `additionalContext`: *"Agent `<name>` not found. Approve creation? [yes/no]"*. Hook exits 2 with blocking message (per Claude Code hook contract).
4. On approval, user runs `/platform-arka agent provision <name>` which invokes the Skill Architect squad:
   - Architect drafts agent YAML with 4-framework DNA (DISC/Enneagram/Big Five/MBTI)
   - Quality Gate reviews
   - On approval, commits to core + registry, then copies to project
   - User re-dispatches the Task

### Explicit command

`/platform-arka agent provision <name>` — same flow, anticipatory. Useful for CI or when user knows they'll need an agent.

## Sub-feature D — Self-healing Sync

**Goal:** transient errors retry; idempotent re-runs converge to desired state; debug is actionable.

### Retry strategy

- Each phase wrapped by `self_healing.run_phase(phase_fn, max_retries=3, backoff=exp)`.
- Retry only on error statuses (`updated` and `unchanged` never retry).
- After max retries, error is recorded in `sync-state.json` but other projects/phases continue.

### Structured errors

Replace current stringly-typed errors with:

```python
class SyncError(BaseModel):
    phase: Literal["mcp", "settings", "descriptor", "content", "agents"]
    project_path: str
    code: str                # e.g., "descriptor.stack.not_list"
    message: str
    context: dict = {}       # e.g., {"raw_value": "Python 3.8+"}
    retry_count: int = 0
```

### Idempotence assertions

Integration tests run `/arka update` twice back-to-back against a test fixture; assert second run reports all phases `unchanged`.

## Schemas

### `config/mcp-policy.yaml`

```yaml
version: 1
policies:
  - match:
      stack_includes: [laravel, php]
    active: [context7, gh-grep, postgres, supabase]
    deferred: [canva, clickup, firecrawl, chrome, gmail, calendar]
  - match:
      stack_includes: [nuxt, vue, react, next]
    active: [context7, gh-grep, playwright, chrome]
    deferred: [postgres, supabase, canva, clickup]
  - match:
      ecosystem: marketing
    active: [canva, gmail, calendar, firecrawl]
    deferred: [postgres, supabase]
  - match: { default: true }
    active: [context7]
    ambiguous: ["*"]
```

Match rules are evaluated top-to-bottom; first match wins. The `ambiguous` key is a list (or `["*"]` for "all remaining") — AI resolves these.

### `~/.arkaos/secrets.json`

```json
{
  "global": {
    "GITHUB_TOKEN": "ghp_...",
    "ANTHROPIC_API_KEY": "sk-ant-..."
  },
  "per_project": {
    "fovory-supplier-sync": {
      "PG_HOST": "localhost",
      "PG_PORT": "5432",
      "PG_USER": "fovory",
      "PG_PASSWORD": "...",
      "PG_DATABASE": "fovory"
    }
  }
}
```

File is `chmod 600` on write. Loader validates permissions before reading; refuses if world/group-readable.

### `<project>/.arkaos/mcp-override.yaml`

```yaml
force_active: [canva]
force_deferred: [postgres]
reason: "canva needed for brand assets even though stack is Laravel"
```

Overrides always win. `reason` is required (audit trail).

### Agent allowlist (`config/agent-allowlists/laravel.yaml`)

```yaml
stack: laravel
baseline:
  - strategy-director
  - backend-dev
  - qa-eng
  - devops-eng
  - architect
  - security-eng
  - cqo
  - copy-director
  - tech-ux-director
```

## New modules

```
core/sync/
  mcp_optimizer.py       # Sub-feature B
  policy_loader.py       # Loads & matches mcp-policy.yaml
  content_syncer.py      # Sub-feature A (CLAUDE.md, rules, hooks, constitution)
  content_merger.py      # Managed-region merge algorithm
  agent_provisioner.py   # Sub-feature C baseline + provisioning entry
  self_healing.py        # Sub-feature D wrapper

config/
  mcp-policy.yaml                    # NEW
  agent-allowlists/<stack>.yaml      # NEW (one per supported stack)
  standards/claude-md-overlays/      # NEW (stack-specific CLAUDE.md sections)
  hooks/agent-provision.sh           # NEW PreToolUse hook

tests/python/
  test_mcp_optimizer.py
  test_policy_loader.py
  test_content_syncer.py
  test_content_merger.py
  test_agent_provisioner.py
  test_self_healing.py
  test_runtime_sync_integration.py   # End-to-end: 3 mock projects, two sync runs
```

## Data flow (single `/arka update` run)

```
cli/arka.update
  → engine.discover_all_projects()           # returns list[Project]
  → for each project p in projects:
       with self_healing.wrap(p):
         r1 = mcp_optimizer.sync(p)           # Phase 1 (upgraded)
         r2 = settings_syncer.sync(p)         # Phase 2 (unchanged)
         r3 = descriptor_syncer.sync(p)       # Phase 3 (bug fixed)
         r4 = content_syncer.sync_claude_md(p)
         r5 = content_syncer.sync_rules(p)
         r6 = content_syncer.sync_hooks(p)
         r7 = content_syncer.sync_constitution(p)
         r8 = agent_provisioner.sync_baseline(p)
         reporter.record(p, [r1..r8])
  → reporter.emit_summary()
  → sync_state.write()
```

## Error handling

- Phase errors are **non-fatal per project**: other projects continue.
- Phase errors are **non-fatal within a project** for subsequent phases when safe (e.g., MCP error doesn't block content sync). Dependencies documented in `self_healing.py`.
- Every error has a structured code; codes live in `core/sync/errors.py` as an enum for grep-ability.
- On unrecoverable errors after retries, `sync-state.json` grows an `errors[]` entry; next `/arka update` re-attempts them first.

## Testing strategy

- **Unit coverage target: >=90%** for all new modules (`tests/python/test_*.py`).
- **Integration:** three fixture projects (`laravel-fixture`, `nuxt-fixture`, `content-fixture`) under `tests/python/fixtures/runtime-sync/`. Two back-to-back sync runs assert idempotence.
- **AI mock:** Haiku calls stubbed with deterministic fake in unit tests; real call exercised only in a single opt-in integration test gated by `ARKAOS_AI_E2E=1`.
- **Regression:** all 2297 current tests must remain green.
- **Manual acceptance:** one real `/arka update` on live 81 projects, then a fresh Claude Code session on a sample Laravel project measures MCP tool-context tokens; target < 25k (down from 93k).

## Release plan

1. **v2.16.1 patch (day 0):** descriptor bugfix + normalize 2 affected descriptor files. Own branch, own PR, Quality Gate, release same day.
2. **Sub-feature A** (`feature/content-sync`): worktree, plan via writing-plans, subagent execution, Quality Gate, merge.
3. **Sub-feature B** (`feature/mcp-optimizer`): same flow. Depends on A only for shared self-healing wrapper scaffolding (if D lands earlier) — otherwise independent.
4. **Sub-feature C** (`feature/agent-provisioning`): same flow. Highest risk; extra review by Security Engineer (runtime code execution).
5. **Sub-feature D** (`feature/self-healing-sync`): same flow. Can ship in parallel with C.
6. **Release v2.17.0:** bundle A+B+C+D, bump VERSION/package.json/pyproject.toml, changelog, GitHub release, `npm publish`.

## Open questions

None. All decisions locked during brainstorming (2026-04-12):

- Merge model: intelligent merge (managed regions) — confirmed.
- Agent allocation: stack-baseline + JIT provisioning with approval — confirmed.
- Rollback: none; self-healing retry only — confirmed.
- AI in MCP optimizer: hybrid (policy first, AI for ambiguous) with cache — confirmed.
- v2.16.1 bundled into v2.17.0 release train but shipped as separate PR first — confirmed.

## Success metrics

- **Token context per session:** < 25k MCP tools (from 93k) on a sample Laravel project → ~70k/session saved.
- **Sync errors:** 0 on the current 81 projects after release (descriptor bug cleared).
- **Rule propagation:** all 81 projects carry the current `model-routing` + `subagent-discipline` MUST rules (verified by grep on `.claude/constitution-applicable.md`).
- **Agent provisioning:** dispatching a missing agent in a test project does not crash; triggers the provisioning flow end-to-end.
- **Idempotence:** two consecutive `/arka update` runs report `unchanged` on run 2 across all phases.
- **Regression:** 2297 + new tests (~150) all green.
