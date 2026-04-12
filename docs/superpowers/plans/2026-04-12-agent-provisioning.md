# Agent Provisioning (Sub-feature C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Every project ships with a stack-based baseline of agents (Phase 8 of sync); when a project tries to dispatch an agent it doesn't have, a PreToolUse hook copies it from core if present, or surfaces a structured approval request if the agent needs to be created.

**Architecture:** Two complementary mechanisms. (1) `agent_provisioner.py` runs as Phase 8 of `/arka update` — copies allowlisted agent files into `<project>/.claude/agents/`. (2) `agent-provision.sh` hook runs on each `Task` tool call — inspects `subagent_type`, copies from core on demand, or blocks with an approval message when the agent is unknown.

**Scope cut:** Automatic agent *creation* (dispatching Skill Architect to author a new agent YAML) is OUT of v2.17.0. The hook surfaces the gap as an actionable blocking message; the user runs `/platform-arka agent provision <name>` which starts the Architect flow. For this plan we ship the command as a stub that opens a documented flow but does not auto-execute Architect dispatch — that is a follow-up feature.

**Tech Stack:** Python 3.11, bash, pytest.

---

## Context for the Engineer

**Agent storage in the repo:**
- Source of truth: `departments/<dept>/agents/<name>.yaml` (behavioral DNA) + `departments/<dept>/agents/<name>.md` (prompt/instructions). Some agents have only `.yaml`; some both.
- Registry: `knowledge/agents-registry-v2.json` — machine-readable index of all core agents.

**Per-project destination:**
- `<project>/.claude/agents/<name>.md` — Claude Code expects flat dir of markdown files.
- For this plan: if both `.yaml` and `.md` exist in core, we concatenate them into a single `.md` file for the project (YAML frontmatter-style + prompt below). If only `.yaml` exists, render it directly as the `.md` with frontmatter syntax.

**Stack → baseline mapping:**
- `config/agent-allowlists/<stack>.yaml` — declarative list of agent names each stack gets.
- If a project's stack matches multiple entries, union the allowlists.
- Every project always gets the Quality Gate trio (`cqo`, `copy-director`, `tech-ux-director`) plus `strategy-director`.

**PreToolUse hook shape (Claude Code contract):**
- Hook receives JSON on stdin with tool name and parameters.
- Exit 0 = allow. Exit 2 with stderr message = block with that message shown to the model.
- For this feature: on `Task` tool use, read `subagent_type` from the JSON, check if the agent file exists under `<cwd>/.claude/agents/<name>.md`. If not, check core. If in core, copy and allow. If not in core, block with structured `additionalContext` message.

---

## File Structure

**Create:**
- `config/agent-allowlists/laravel.yaml`
- `config/agent-allowlists/nuxt.yaml`
- `config/agent-allowlists/python.yaml`
- `config/agent-allowlists/node.yaml`
- `config/agent-allowlists/_base.yaml` — agents every project gets
- `core/sync/agent_provisioner.py`
- `config/hooks/agent-provision.sh`
- `tests/python/test_agent_provisioner.py`

**Modify:**
- `core/sync/schema.py` — `AgentProvisionResult` + `SyncReport.agent_results`
- `core/sync/engine.py` — Phase 8 wiring
- `core/sync/reporter.py` — agent row

---

## Task 1 — Schema

**Files:** `core/sync/schema.py`

- [ ] **Step 1: Add result model and extend SyncReport**

Append to `core/sync/schema.py` (after `ContentSyncResult`):

```python
class AgentProvisionResult(BaseModel):
    """Result of syncing baseline agents for a project."""

    path: str
    status: str
    agents_added: list[str] = Field(default_factory=list)
    agents_unchanged: list[str] = Field(default_factory=list)
    agents_errored: list[str] = Field(default_factory=list)
    error: str | None = None
```

Extend `SyncReport` (add field after `content_results`):

```python
    agent_results: list[AgentProvisionResult] = Field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add core/sync/schema.py
git commit -m "feat(sync): add AgentProvisionResult schema"
```

---

## Task 2 — Allowlist files

**Files:** Create 5 YAML files under `config/agent-allowlists/`.

- [ ] **Step 1: `_base.yaml`** (every project)

```yaml
# Baseline agents every project gets regardless of stack.
stack: _base
baseline:
  - strategy-director
  - cqo
  - copy-director
  - tech-ux-director
```

- [ ] **Step 2: `laravel.yaml`**

```yaml
stack: laravel
baseline:
  - backend-dev
  - senior-dev
  - architect
  - qa
  - devops
  - security
  - analyst
```

- [ ] **Step 3: `nuxt.yaml`**

```yaml
stack: nuxt
baseline:
  - frontend-dev
  - backend-dev
  - architect
  - qa
  - devops
```

- [ ] **Step 4: `python.yaml`**

```yaml
stack: python
baseline:
  - senior-dev
  - architect
  - qa
  - devops
  - analyst
```

- [ ] **Step 5: `node.yaml`**

```yaml
stack: node
baseline:
  - backend-dev
  - senior-dev
  - architect
  - qa
  - devops
```

- [ ] **Step 6: Commit**

```bash
git add config/agent-allowlists/
git commit -m "feat(sync): stack-based agent allowlists"
```

---

## Task 3 — Agent provisioner tests (fail first)

**Files:** Create `tests/python/test_agent_provisioner.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for core.sync.agent_provisioner — baseline agent sync per project."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.agent_provisioner import (
    resolve_allowlist,
    sync_project_agents,
)
from core.sync.schema import Project


@pytest.fixture
def fake_core(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    core = tmp_path / "core"
    (core / "config" / "agent-allowlists").mkdir(parents=True)
    (core / "departments" / "dev" / "agents").mkdir(parents=True)
    (core / "departments" / "strategy" / "agents").mkdir(parents=True)

    (core / "config" / "agent-allowlists" / "_base.yaml").write_text(
        "stack: _base\nbaseline:\n  - strategy-director\n"
    )
    (core / "config" / "agent-allowlists" / "laravel.yaml").write_text(
        "stack: laravel\nbaseline:\n  - backend-dev\n  - qa\n"
    )

    # Core agent files
    (core / "departments" / "dev" / "agents" / "backend-dev.yaml").write_text(
        "name: backend-dev\nrole: senior\n"
    )
    (core / "departments" / "dev" / "agents" / "backend-dev.md").write_text(
        "# Backend Dev\n\nBuilds stuff.\n"
    )
    (core / "departments" / "dev" / "agents" / "qa.yaml").write_text(
        "name: qa\n"
    )
    (core / "departments" / "strategy" / "agents" / "strategy-director.md").write_text(
        "# Strategy Director\n"
    )

    monkeypatch.setenv("ARKAOS_CORE_ROOT", str(core))
    return core


@pytest.fixture
def project(tmp_path: Path) -> Project:
    p = tmp_path / "proj"
    (p / ".claude").mkdir(parents=True)
    return Project(path=str(p), name="proj", stack=["laravel"])


def test_resolve_allowlist_merges_base_and_stack(fake_core: Path) -> None:
    agents = resolve_allowlist(["laravel"])
    assert set(agents) == {"strategy-director", "backend-dev", "qa"}


def test_resolve_allowlist_unknown_stack_returns_base(fake_core: Path) -> None:
    agents = resolve_allowlist(["rust"])
    assert agents == ["strategy-director"]


def test_resolve_allowlist_multiple_stacks_unions(fake_core: Path) -> None:
    # add nuxt allowlist
    (fake_core / "config" / "agent-allowlists" / "nuxt.yaml").write_text(
        "stack: nuxt\nbaseline:\n  - frontend-dev\n"
    )
    (fake_core / "departments" / "dev" / "agents" / "frontend-dev.yaml").write_text(
        "name: frontend-dev\n"
    )
    agents = set(resolve_allowlist(["laravel", "nuxt"]))
    assert {"backend-dev", "qa", "frontend-dev", "strategy-director"} <= agents


def test_sync_copies_agents_to_project(fake_core: Path, project: Project) -> None:
    result = sync_project_agents(project)

    assert result.status == "updated"
    agents_dir = Path(project.path) / ".claude" / "agents"
    assert (agents_dir / "backend-dev.md").exists()
    assert (agents_dir / "qa.md").exists()
    assert (agents_dir / "strategy-director.md").exists()
    assert "backend-dev" in result.agents_added


def test_sync_concatenates_yaml_and_md_when_both_exist(
    fake_core: Path, project: Project
) -> None:
    sync_project_agents(project)

    backend_md = (Path(project.path) / ".claude" / "agents" / "backend-dev.md").read_text()
    assert "---" in backend_md  # YAML frontmatter delimiter
    assert "name: backend-dev" in backend_md
    assert "Backend Dev" in backend_md


def test_sync_renders_yaml_only_agent_as_frontmatter(
    fake_core: Path, project: Project
) -> None:
    sync_project_agents(project)

    qa_md = (Path(project.path) / ".claude" / "agents" / "qa.md").read_text()
    assert "---" in qa_md
    assert "name: qa" in qa_md


def test_sync_idempotent_on_second_run(fake_core: Path, project: Project) -> None:
    sync_project_agents(project)
    r2 = sync_project_agents(project)
    assert r2.status == "unchanged"
    assert set(r2.agents_unchanged) >= {"backend-dev", "qa", "strategy-director"}


def test_sync_reports_missing_core_agent_as_errored(
    fake_core: Path, project: Project
) -> None:
    # Add an allowlist entry for an agent that has no source file.
    (fake_core / "config" / "agent-allowlists" / "laravel.yaml").write_text(
        "stack: laravel\nbaseline:\n  - ghost-agent\n  - backend-dev\n"
    )

    result = sync_project_agents(project)
    assert "ghost-agent" in result.agents_errored
    assert "backend-dev" in result.agents_added
```

- [ ] **Step 2: Run (expect fail)**

```
cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_agent_provisioner.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_agent_provisioner.py
git commit -m "test(sync): agent provisioner tests"
```

---

## Task 4 — Agent provisioner implementation

**Files:** Create `core/sync/agent_provisioner.py`

- [ ] **Step 1: Implement**

```python
"""Agent provisioner — copies baseline agents into each project's .claude/agents/.

Resolves stack-based allowlists (plus the _base allowlist applied to every
project), locates source agent files under departments/**/agents/, and
materializes them as flat markdown files with YAML frontmatter the project's
Claude Code can consume.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from core.sync.schema import AgentProvisionResult, Project


def _core_root() -> Path:
    env = os.environ.get("ARKAOS_CORE_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def resolve_allowlist(stack: list[str]) -> list[str]:
    """Return the union of baseline agent names for the given stack tokens."""
    core = _core_root()
    allowlist_dir = core / "config" / "agent-allowlists"
    agents: set[str] = set()

    _extend_from_file(allowlist_dir / "_base.yaml", agents)
    for stack_name in stack:
        _extend_from_file(allowlist_dir / f"{stack_name.lower()}.yaml", agents)

    return sorted(agents)


def sync_project_agents(project: Project) -> AgentProvisionResult:
    """Materialize baseline agent markdown files in <project>/.claude/agents/."""
    try:
        return _do_sync(project)
    except Exception as exc:  # noqa: BLE001
        return AgentProvisionResult(
            path=project.path, status="error", error=str(exc)
        )


def sync_all_agents(projects: list[Project]) -> list[AgentProvisionResult]:
    return [sync_project_agents(p) for p in projects]


def _extend_from_file(path: Path, agents: set[str]) -> None:
    if not path.exists():
        return
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return
    for name in data.get("baseline", []) or []:
        if isinstance(name, str):
            agents.add(name)


def _do_sync(project: Project) -> AgentProvisionResult:
    core = _core_root()
    agents_dir = Path(project.path) / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    allowlist = resolve_allowlist(project.stack)
    added: list[str] = []
    unchanged: list[str] = []
    errored: list[str] = []

    for name in allowlist:
        rendered = _render_agent(core, name)
        if rendered is None:
            errored.append(name)
            continue

        target = agents_dir / f"{name}.md"
        if target.exists() and target.read_text() == rendered:
            unchanged.append(name)
            continue
        target.write_text(rendered)
        added.append(name)

    status = "error" if errored and not added and not unchanged else (
        "updated" if added else "unchanged"
    )
    return AgentProvisionResult(
        path=project.path,
        status=status,
        agents_added=added,
        agents_unchanged=unchanged,
        agents_errored=errored,
    )


def _render_agent(core: Path, name: str) -> str | None:
    yaml_path = _find_agent_file(core, name, ".yaml")
    md_path = _find_agent_file(core, name, ".md")

    if yaml_path is None and md_path is None:
        return None

    parts: list[str] = []
    if yaml_path is not None:
        parts.append("---")
        parts.append(yaml_path.read_text().strip())
        parts.append("---")
    if md_path is not None:
        parts.append(md_path.read_text().rstrip())

    return "\n".join(parts) + "\n"


def _find_agent_file(core: Path, name: str, suffix: str) -> Path | None:
    for dept in (core / "departments").iterdir() if (core / "departments").exists() else []:
        candidate = dept / "agents" / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    return None
```

- [ ] **Step 2: Run tests**

```
python -m pytest tests/python/test_agent_provisioner.py -v
```

All 8 must PASS.

- [ ] **Step 3: Full suite**

`python -m pytest tests/python/ -q` — 2277 + 8 = 2285 passing.

- [ ] **Step 4: Commit**

```bash
git add core/sync/agent_provisioner.py
git commit -m "feat(sync): agent provisioner for stack-based baseline sync"
```

---

## Task 5 — Engine wiring (Phase 8)

**Files:** Modify `core/sync/engine.py` and `core/sync/reporter.py`

- [ ] **Step 1: Wire into engine**

After the content sync phase in `engine.py`:

```python
from core.sync.agent_provisioner import sync_all_agents

# after content_results = sync_all_content(projects):
agent_results = sync_all_agents(projects)
```

Pass `agent_results` to `build_report(...)`.

- [ ] **Step 2: Update reporter**

In `core/sync/reporter.py`:
1. Add `agent_results: list[AgentProvisionResult] | None = None` parameter to `build_report`.
2. Extend `_collect_errors` to iterate `agent_results` and emit:
   - `f"Agents({r.path}): {r.error}"` if `r.error`
   - `f"Agents({r.path}): missing core file for {a}"` for each a in `r.agents_errored`
3. Add an "Agents" row to the phase table mirroring existing rows.

- [ ] **Step 3: Run full suite**

`python -m pytest tests/python/ -q` — 0 regressions.

- [ ] **Step 4: Commit**

```bash
git add core/sync/engine.py core/sync/reporter.py
git commit -m "feat(sync): wire agent provisioner as Phase 8 of /arka update"
```

---

## Task 6 — PreToolUse hook for runtime provisioning

**Files:** Create `config/hooks/agent-provision.sh`

- [ ] **Step 1: Implement the hook**

```bash
#!/usr/bin/env bash
# ArkaOS PreToolUse hook for dynamic agent provisioning.
# Intercepts Task tool calls: if subagent_type is not present in the
# project's .claude/agents/, copies it from ArkaOS core when available,
# or blocks with an approval-request message when the agent must be
# created via `/platform-arka agent provision <name>`.

set -euo pipefail

# Hook contract: stdin is a JSON payload with fields tool_name + tool_input.
payload="$(cat)"

tool_name="$(echo "$payload" | jq -r '.tool_name // ""')"
if [ "$tool_name" != "Task" ]; then
    exit 0
fi

subagent_type="$(echo "$payload" | jq -r '.tool_input.subagent_type // ""')"
if [ -z "$subagent_type" ] || [ "$subagent_type" = "null" ]; then
    exit 0
fi

project_root="$(pwd)"
project_agents_dir="$project_root/.claude/agents"
target="$project_agents_dir/${subagent_type}.md"

if [ -f "$target" ]; then
    exit 0
fi

# Agent missing locally — try copying from ArkaOS core.
core_root="${ARKAOS_CORE_ROOT:-}"
if [ -z "$core_root" ]; then
    core_root="$(npm root -g 2>/dev/null)/arkaos"
fi

if [ -d "$core_root/departments" ]; then
    mkdir -p "$project_agents_dir"
    python3 - "$core_root" "$subagent_type" "$target" <<'PY' || true
import os, sys
from pathlib import Path

core = Path(sys.argv[1])
name = sys.argv[2]
target = Path(sys.argv[3])

yaml_path = None
md_path = None
for dept in (core / "departments").iterdir():
    agents = dept / "agents"
    if not agents.is_dir():
        continue
    y = agents / f"{name}.yaml"
    m = agents / f"{name}.md"
    if y.exists() and yaml_path is None:
        yaml_path = y
    if m.exists() and md_path is None:
        md_path = m

if yaml_path is None and md_path is None:
    sys.exit(2)

parts = []
if yaml_path is not None:
    parts.append("---")
    parts.append(yaml_path.read_text().strip())
    parts.append("---")
if md_path is not None:
    parts.append(md_path.read_text().rstrip())

target.write_text("\n".join(parts) + "\n")
PY
    if [ -f "$target" ]; then
        echo "[arka:provisioned] Copied agent '$subagent_type' from ArkaOS core." >&2
        exit 0
    fi
fi

# Agent not in project and not in core — surface an approval-request.
cat >&2 <<MSG
[arka:provision-needed] Agent '$subagent_type' is not installed in this
project and does not exist in ArkaOS core. To create it, run:

    /platform-arka agent provision $subagent_type

This opens the Skill Architect flow which drafts the agent YAML with
4-framework DNA, goes through Quality Gate, and commits to core before
propagating to the project. Blocking dispatch until the agent exists.
MSG
exit 2
```

Make executable:
```bash
chmod +x config/hooks/agent-provision.sh
```

- [ ] **Step 2: Register in settings template**

Check `config/settings-template.json` for the `hooks` section. Add PreToolUse entry:
```json
"PreToolUse": [
  {
    "matcher": "Task",
    "hooks": [
      { "type": "command", "command": "$HOME/.claude/hooks/agent-provision.sh" }
    ]
  }
]
```

(Adapt path style to match existing entries in the template.)

- [ ] **Step 3: Verify hook syntax**

```bash
bash -n config/hooks/agent-provision.sh
```

Expected: no output (syntactically valid).

- [ ] **Step 4: Commit**

```bash
git add config/hooks/agent-provision.sh config/settings-template.json
git commit -m "feat(runtime): PreToolUse hook for dynamic agent provisioning"
```

---

## Task 7 — Integration test

**Files:** Modify `tests/python/test_sync_integration.py`

- [ ] **Step 1: Add Phase 8 idempotence test**

Add a test method `test_agent_provisioning_idempotent`:
- Build a project with `stack=["python"]` (use the existing integration fixture pattern).
- Run `run_sync` once: assert at least one agent was added (`agent_results[0].agents_added` non-empty).
- Run again: assert `agent_results[0].status == "unchanged"`.
- Assert `<project>/.claude/agents/strategy-director.md` exists.

- [ ] **Step 2: Run**

```
python -m pytest tests/python/test_sync_integration.py -v -k agent
```

PASS.

- [ ] **Step 3: Full suite**

```
python -m pytest tests/python/ -q
```

2285 + 1 = 2286 passing.

- [ ] **Step 4: Commit**

```bash
git add tests/python/test_sync_integration.py
git commit -m "test(sync): agent provisioning idempotence integration"
```

---

## Task 8 — Quality Gate and merge

- [ ] **Step 1: Dispatch Marta**

Security Engineer should also review — the PreToolUse hook executes code at runtime. Verify: (a) path traversal impossible (agent names are sanitized or restricted), (b) hook fails safe (exit 0 on unrelated tools, exit 2 only when truly blocking), (c) no secrets leakage through stderr messages.

- [ ] **Step 2: Address findings, re-submit if needed**

- [ ] **Step 3: On APPROVED, merge to master**

```bash
git checkout master
git merge --no-ff feature/agent-provisioning -m "Merge Sub-feature C: Agent Provisioning"
git branch -d feature/agent-provisioning
```

- [ ] **Step 4: No release yet — Sub-D is next**

---

## Out of scope for v2.17.0

- Auto-creation of new agents via Skill Architect when not in core. The hook surfaces the request; `/platform-arka agent provision <name>` will be implemented in v2.18.0. This keeps Sub-C shippable.

## Self-review

- **Spec coverage:** Phase 8 baseline ✅ (Tasks 1-5). Runtime hook ✅ (Task 6). Allowlists ✅ (Task 2). Idempotence ✅ (Task 7). Reporter ✅ (Task 5). Auto-creation flow intentionally deferred — documented.
- **Placeholders:** None.
- **Type consistency:** `AgentProvisionResult.agents_added/unchanged/errored: list[str]` consistent. `resolve_allowlist(stack: list[str]) -> list[str]` and `sync_project_agents(project: Project) -> AgentProvisionResult` stable.
- **Scope:** Sub-feature C only. Does not touch Sub-D (self-healing) or release.
