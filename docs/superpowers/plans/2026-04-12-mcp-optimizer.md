# MCP Optimizer (Sub-feature B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Checkbox syntax tracks progress.

**Goal:** Per-project MCP optimization — mark unused MCPs as deferred, inject env vars from a user vault, honor per-project overrides. Expected saving: ~70k tokens/session on typical projects.

**Architecture:** New `mcp_optimizer.py` runs between `mcp_syncer` and `settings_syncer`. It takes the syncer's McpSyncResult, applies a YAML policy registry + optional AI fallback for ambiguous MCPs + project override, then filters the `final_mcp_list` down to only active MCPs (deferred ones are removed from `enabledMcpjsonServers`). Separately it injects env values from `~/.arkaos/secrets.json` into the `.mcp.json` where declared, and generates `.env.example` for missing vars.

**Tech Stack:** Python 3.11, Pydantic, PyYAML, pytest. Optional `anthropic` SDK for Haiku calls (feature-flagged; deterministic fallback when unavailable).

---

## Context for the Engineer

**What exists already (do NOT change):**
- `core/sync/mcp_syncer.py` — writes full `.mcp.json` based on stack registry. Its output `McpSyncResult.final_mcp_list` contains ALL MCPs the project has.
- `core/sync/settings_syncer.py` — takes `McpSyncResult` and writes `enabledMcpjsonServers` into `.claude/settings.local.json`. If a server is not in that list, its tools are not loaded.

**Key integration insight:** "Deferred" = absent from `enabledMcpjsonServers`. So the optimizer's job is to narrow `final_mcp_list` to only the active ones before `settings_syncer` consumes it. `.mcp.json` itself keeps ALL server definitions (so they remain available if user opts in later).

**New files:**
- `config/mcp-policy.yaml` — declarative rules
- `core/sync/policy_loader.py` — parses + matches policy
- `core/sync/mcp_optimizer.py` — orchestrator (policy → AI → override → env injection)
- `core/sync/ai_mcp_decider.py` — Haiku client with deterministic fallback + disk cache
- Per-project `.arkaos/mcp-override.yaml` — user override (no file to create in repo)

**Secrets vault:** `~/.arkaos/secrets.json` — user-owned, chmod 600, read-only access.

---

## File Structure

**Create:**
- `config/mcp-policy.yaml`
- `core/sync/policy_loader.py`
- `core/sync/mcp_optimizer.py`
- `core/sync/ai_mcp_decider.py`
- `tests/python/test_policy_loader.py`
- `tests/python/test_mcp_optimizer.py`
- `tests/python/test_ai_mcp_decider.py`

**Modify:**
- `core/sync/schema.py` — extend `McpSyncResult` with `mcps_deferred: list[str]`; add new result types if needed
- `core/sync/engine.py` — insert optimizer phase after mcp_syncer, before settings_syncer
- `core/sync/reporter.py` — reflect deferred MCPs in report

---

## Task 1 — Schema extension

**Files:** `core/sync/schema.py`

- [ ] **Step 1: Add `mcps_deferred` to `McpSyncResult`**

Add field after `mcps_preserved`:
```python
    mcps_deferred: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add core/sync/schema.py
git commit -m "feat(sync): add mcps_deferred field to McpSyncResult"
```

---

## Task 2 — Policy file (starter content)

**Files:** Create `config/mcp-policy.yaml`

- [ ] **Step 1: Create the policy file**

```yaml
# ArkaOS MCP Policy Registry
# Controls which MCPs load eagerly vs deferred per project stack/ecosystem.
# Rules evaluated top-to-bottom; first match wins. "ambiguous: ['*']" means
# all other MCPs defer to AI (or fallback heuristic when AI unavailable).

version: 1
policies:
  - match:
      stack_includes: [laravel, php]
    active: [context7, gh-grep, postgres, supabase]
    deferred: [canva, clickup, firecrawl, chrome, gmail, calendar, claude-in-chrome]
    ambiguous: []

  - match:
      stack_includes: [nuxt, vue, react, next]
    active: [context7, gh-grep, playwright, claude-in-chrome]
    deferred: [postgres, supabase, canva, clickup, gmail, calendar]
    ambiguous: []

  - match:
      ecosystem: marketing
    active: [canva, gmail, calendar, firecrawl, clickup]
    deferred: [postgres, supabase, playwright]
    ambiguous: []

  - match:
      ecosystem: content
    active: [canva, firecrawl, youtube-transcript]
    deferred: [postgres, clickup]
    ambiguous: []

  - match:
      default: true
    active: [context7]
    deferred: []
    ambiguous: ["*"]
```

- [ ] **Step 2: Commit**

```bash
git add config/mcp-policy.yaml
git commit -m "feat(sync): MCP policy registry with deterministic stack/ecosystem rules"
```

---

## Task 3 — Policy loader tests (fail first)

**Files:** Create `tests/python/test_policy_loader.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for core.sync.policy_loader — MCP policy matching."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.policy_loader import (
    PolicyDecision,
    load_policy,
    decide,
)


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(
        "version: 1\n"
        "policies:\n"
        "  - match: {stack_includes: [laravel]}\n"
        "    active: [context7, postgres]\n"
        "    deferred: [canva, clickup]\n"
        "    ambiguous: []\n"
        "  - match: {ecosystem: marketing}\n"
        "    active: [canva, gmail]\n"
        "    deferred: [postgres]\n"
        "    ambiguous: []\n"
        "  - match: {default: true}\n"
        "    active: [context7]\n"
        "    deferred: []\n"
        "    ambiguous: ['*']\n"
    )
    return p


def test_load_policy_returns_rules_in_order(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    assert len(policy.rules) == 3
    assert policy.rules[0].active == ["context7", "postgres"]


def test_decide_matches_laravel_stack(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(
        policy, mcps=["context7", "postgres", "canva", "firecrawl"],
        stack=["laravel"], ecosystem=None,
    )
    assert decision.active == ["context7", "postgres"]
    assert decision.deferred == ["canva"]
    assert decision.ambiguous == ["firecrawl"]


def test_decide_marketing_ecosystem_overrides_stack(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(
        policy, mcps=["canva", "gmail", "postgres"],
        stack=["unknown"], ecosystem="marketing",
    )
    assert "canva" in decision.active
    assert "postgres" in decision.deferred


def test_decide_falls_back_to_default_with_ambiguous_wildcard(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(
        policy, mcps=["context7", "something-new"],
        stack=["rust"], ecosystem=None,
    )
    assert "context7" in decision.active
    assert "something-new" in decision.ambiguous


def test_decide_returns_empty_lists_for_empty_mcps(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    decision = decide(policy, mcps=[], stack=["laravel"], ecosystem=None)
    assert decision.active == []
    assert decision.deferred == []
    assert decision.ambiguous == []


def test_first_rule_wins(policy_file: Path) -> None:
    policy = load_policy(policy_file)
    # laravel stack AND marketing ecosystem: first (laravel) wins
    decision = decide(
        policy, mcps=["canva"],
        stack=["laravel"], ecosystem="marketing",
    )
    # canva is deferred in laravel rule, active in marketing rule
    # laravel matched first → deferred
    assert decision.deferred == ["canva"]
    assert decision.active == []
```

- [ ] **Step 2: Run**

`cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_policy_loader.py -v`

Expected: ImportError, all fail.

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_policy_loader.py
git commit -m "test(sync): policy loader tests"
```

---

## Task 4 — Policy loader implementation

**Files:** Create `core/sync/policy_loader.py`

- [ ] **Step 1: Implement**

```python
"""MCP policy loader and matcher for the ArkaOS Sync Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class PolicyRule:
    match: dict
    active: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)


@dataclass
class Policy:
    rules: list[PolicyRule]


@dataclass
class PolicyDecision:
    active: list[str]
    deferred: list[str]
    ambiguous: list[str]


def load_policy(path: Path) -> Policy:
    """Load and parse an mcp-policy.yaml file."""
    data = yaml.safe_load(path.read_text()) or {}
    rules = [
        PolicyRule(
            match=r.get("match", {}),
            active=list(r.get("active", [])),
            deferred=list(r.get("deferred", [])),
            ambiguous=list(r.get("ambiguous", [])),
        )
        for r in data.get("policies", [])
    ]
    return Policy(rules=rules)


def decide(
    policy: Policy,
    mcps: list[str],
    stack: list[str],
    ecosystem: str | None,
) -> PolicyDecision:
    """Apply the first matching rule and classify each MCP."""
    if not mcps:
        return PolicyDecision(active=[], deferred=[], ambiguous=[])

    rule = _first_match(policy, stack, ecosystem)
    if rule is None:
        return PolicyDecision(active=[], deferred=[], ambiguous=list(mcps))

    wildcard = "*" in rule.ambiguous
    active: list[str] = []
    deferred: list[str] = []
    ambiguous: list[str] = []

    for mcp in mcps:
        if mcp in rule.active:
            active.append(mcp)
        elif mcp in rule.deferred:
            deferred.append(mcp)
        elif mcp in rule.ambiguous:
            ambiguous.append(mcp)
        elif wildcard:
            ambiguous.append(mcp)
        else:
            deferred.append(mcp)

    return PolicyDecision(active=active, deferred=deferred, ambiguous=ambiguous)


def _first_match(
    policy: Policy, stack: list[str], ecosystem: str | None
) -> PolicyRule | None:
    stack_set = {s.lower() for s in stack}
    for rule in policy.rules:
        match = rule.match
        if match.get("default"):
            return rule
        stack_inc = match.get("stack_includes")
        if stack_inc and any(s.lower() in stack_set for s in stack_inc):
            return rule
        eco = match.get("ecosystem")
        if eco and ecosystem and eco == ecosystem:
            return rule
    return None
```

- [ ] **Step 2: Run tests**

`python -m pytest tests/python/test_policy_loader.py -v`

All 6 must PASS.

- [ ] **Step 3: Commit**

```bash
git add core/sync/policy_loader.py
git commit -m "feat(sync): policy loader with stack/ecosystem matching"
```

---

## Task 5 — AI decider tests (fail first)

**Files:** Create `tests/python/test_ai_mcp_decider.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for core.sync.ai_mcp_decider — AI fallback for ambiguous MCPs."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.ai_mcp_decider import decide_ambiguous, AIUnavailable


@pytest.fixture
def cache_path(tmp_path: Path) -> Path:
    return tmp_path / "cache.json"


def test_empty_ambiguous_returns_empty(cache_path: Path) -> None:
    result = decide_ambiguous(
        ambiguous=[], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=None,
    )
    assert result == {}


def test_heuristic_fallback_defers_all_when_no_ai(cache_path: Path) -> None:
    result = decide_ambiguous(
        ambiguous=["firecrawl", "clickup"],
        stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=None,
    )
    assert result == {"firecrawl": "deferred", "clickup": "deferred"}


def test_ai_call_is_cached(cache_path: Path) -> None:
    call_count = {"n": 0}

    def fake_ai(name: str, stack: list[str], ecosystem: str | None) -> str:
        call_count["n"] += 1
        return "active"

    r1 = decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    r2 = decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    assert r1 == {"firecrawl": "active"}
    assert r2 == {"firecrawl": "active"}
    assert call_count["n"] == 1, "cache should prevent duplicate AI calls"


def test_ai_unavailable_falls_back_to_heuristic(cache_path: Path) -> None:
    def failing_ai(name: str, stack: list[str], ecosystem: str | None) -> str:
        raise AIUnavailable("rate limited")

    result = decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=failing_ai,
    )
    assert result == {"firecrawl": "deferred"}


def test_cache_key_differs_per_stack(cache_path: Path) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_ai(name: str, stack: list[str], ecosystem: str | None) -> str:
        calls.append((name, tuple(stack)))
        return "active"

    decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    decide_ambiguous(
        ambiguous=["firecrawl"], stack=["nuxt"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    assert len(calls) == 2
```

- [ ] **Step 2: Run (expect fail)**

`python -m pytest tests/python/test_ai_mcp_decider.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_ai_mcp_decider.py
git commit -m "test(sync): AI MCP decider tests"
```

---

## Task 6 — AI decider implementation

**Files:** Create `core/sync/ai_mcp_decider.py`

- [ ] **Step 1: Implement**

```python
"""AI-backed decider for MCPs the policy could not classify.

Falls back to deterministic heuristic (defer all unknowns) when the AI
is unavailable or a call fails. Decisions are cached on disk keyed by
(stack, ecosystem, mcp_name) to guarantee idempotence across runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable


class AIUnavailable(RuntimeError):
    pass


AiCaller = Callable[[str, list[str], str | None], str]


def decide_ambiguous(
    ambiguous: list[str],
    stack: list[str],
    ecosystem: str | None,
    cache_path: Path,
    call_ai: AiCaller | None,
) -> dict[str, str]:
    if not ambiguous:
        return {}

    cache = _load_cache(cache_path)
    result: dict[str, str] = {}

    for mcp in ambiguous:
        key = _cache_key(mcp, stack, ecosystem)
        cached = cache.get(key)
        if cached in {"active", "deferred"}:
            result[mcp] = cached
            continue

        decision = _resolve(mcp, stack, ecosystem, call_ai)
        result[mcp] = decision
        cache[key] = decision

    _save_cache(cache_path, cache)
    return result


def _resolve(
    mcp: str,
    stack: list[str],
    ecosystem: str | None,
    call_ai: AiCaller | None,
) -> str:
    if call_ai is None:
        return "deferred"
    try:
        raw = call_ai(mcp, stack, ecosystem)
    except AIUnavailable:
        return "deferred"
    return raw if raw in {"active", "deferred"} else "deferred"


def _cache_key(mcp: str, stack: list[str], ecosystem: str | None) -> str:
    raw = f"{mcp}|{','.join(sorted(stack))}|{ecosystem or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))
```

- [ ] **Step 2: Run tests**

`python -m pytest tests/python/test_ai_mcp_decider.py -v`

All 5 must PASS.

- [ ] **Step 3: Commit**

```bash
git add core/sync/ai_mcp_decider.py
git commit -m "feat(sync): AI MCP decider with disk cache and heuristic fallback"
```

---

## Task 7 — MCP Optimizer tests (fail first)

**Files:** Create `tests/python/test_mcp_optimizer.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for core.sync.mcp_optimizer — orchestrator for policy + AI + env + override."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.sync.mcp_optimizer import optimize_project_mcps
from core.sync.schema import McpSyncResult, Project


@pytest.fixture
def policy_file(tmp_path: Path) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(
        "version: 1\n"
        "policies:\n"
        "  - match: {stack_includes: [laravel]}\n"
        "    active: [context7, postgres]\n"
        "    deferred: [canva, clickup]\n"
        "    ambiguous: []\n"
        "  - match: {default: true}\n"
        "    active: [context7]\n"
        "    ambiguous: ['*']\n"
    )
    return p


def _make_mcp_json(project_dir: Path, servers: dict) -> None:
    (project_dir / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))


def test_optimize_laravel_defers_marketing_mcps(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    proj.mkdir()
    _make_mcp_json(proj, {"context7": {}, "postgres": {}, "canva": {}, "clickup": {}})

    mcp_result = McpSyncResult(
        path=str(proj), status="updated",
        final_mcp_list=["canva", "clickup", "context7", "postgres"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    result = optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=None, cache_path=tmp_path / "cache.json",
    )

    assert set(result.mcps_deferred) == {"canva", "clickup"}
    assert set(result.final_mcp_list) == {"context7", "postgres"}


def test_override_forces_active(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    (proj / ".arkaos").mkdir(parents=True)
    _make_mcp_json(proj, {"context7": {}, "canva": {}})
    (proj / ".arkaos" / "mcp-override.yaml").write_text(
        "force_active: [canva]\n"
        "force_deferred: []\n"
        "reason: brand work needs it\n"
    )

    mcp_result = McpSyncResult(
        path=str(proj), status="updated",
        final_mcp_list=["canva", "context7"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    result = optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=None, cache_path=tmp_path / "cache.json",
    )

    assert "canva" in result.final_mcp_list
    assert "canva" not in result.mcps_deferred


def test_override_forces_deferred(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    (proj / ".arkaos").mkdir(parents=True)
    _make_mcp_json(proj, {"context7": {}, "postgres": {}})
    (proj / ".arkaos" / "mcp-override.yaml").write_text(
        "force_active: []\n"
        "force_deferred: [postgres]\n"
        "reason: local db only\n"
    )

    mcp_result = McpSyncResult(
        path=str(proj), status="updated",
        final_mcp_list=["context7", "postgres"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    result = optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=None, cache_path=tmp_path / "cache.json",
    )

    assert "postgres" in result.mcps_deferred
    assert "postgres" not in result.final_mcp_list


def test_env_vault_injects_secrets(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    proj.mkdir()
    _make_mcp_json(proj, {
        "postgres": {"env": {"PG_HOST": "", "PG_PASSWORD": ""}},
        "context7": {},
    })
    vault = tmp_path / "secrets.json"
    vault.write_text(json.dumps({
        "global": {},
        "per_project": {
            "p": {"PG_HOST": "localhost", "PG_PASSWORD": "secret"}
        }
    }))
    os.chmod(vault, 0o600)

    mcp_result = McpSyncResult(
        path=str(proj), status="updated",
        final_mcp_list=["context7", "postgres"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=vault, cache_path=tmp_path / "cache.json",
    )

    mcp_data = json.loads((proj / ".mcp.json").read_text())
    assert mcp_data["mcpServers"]["postgres"]["env"]["PG_HOST"] == "localhost"
    assert mcp_data["mcpServers"]["postgres"]["env"]["PG_PASSWORD"] == "secret"


def test_missing_secrets_generate_env_example(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    proj.mkdir()
    _make_mcp_json(proj, {"postgres": {"env": {"PG_HOST": "", "PG_PASSWORD": ""}}})

    mcp_result = McpSyncResult(
        path=str(proj), status="updated",
        final_mcp_list=["postgres"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=None, cache_path=tmp_path / "cache.json",
    )

    env_example = proj / ".env.example"
    assert env_example.exists()
    text = env_example.read_text()
    assert "PG_HOST" in text
    assert "PG_PASSWORD" in text


def test_vault_rejected_when_world_readable(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    proj.mkdir()
    _make_mcp_json(proj, {"postgres": {"env": {"PG_HOST": ""}}})
    vault = tmp_path / "bad_secrets.json"
    vault.write_text(json.dumps({"global": {}, "per_project": {"p": {"PG_HOST": "x"}}}))
    os.chmod(vault, 0o644)  # world-readable

    mcp_result = McpSyncResult(
        path=str(proj), status="updated", final_mcp_list=["postgres"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    result = optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=vault, cache_path=tmp_path / "cache.json",
    )

    # Vault refused: PG_HOST stays empty (not injected)
    mcp_data = json.loads((proj / ".mcp.json").read_text())
    assert mcp_data["mcpServers"]["postgres"]["env"]["PG_HOST"] == ""
```

- [ ] **Step 2: Run (expect fail)**

`python -m pytest tests/python/test_mcp_optimizer.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_mcp_optimizer.py
git commit -m "test(sync): MCP optimizer orchestration tests"
```

---

## Task 8 — MCP Optimizer implementation

**Files:** Create `core/sync/mcp_optimizer.py`

- [ ] **Step 1: Implement**

```python
"""MCP Optimizer — narrows the active MCP list per project via policy,
AI fallback, and per-project override; injects env secrets from a vault;
generates .env.example for missing values.

Runs between mcp_syncer (produces full .mcp.json) and settings_syncer
(writes enabledMcpjsonServers). Deferred MCPs are simply absent from the
returned ``final_mcp_list`` — their definitions remain in ``.mcp.json``
so user can opt-in later.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import yaml

from core.sync.ai_mcp_decider import decide_ambiguous
from core.sync.policy_loader import decide, load_policy
from core.sync.schema import McpSyncResult, Project


def optimize_project_mcps(
    project: Project,
    mcp_result: McpSyncResult,
    policy_path: Path,
    vault_path: Path | None,
    cache_path: Path,
    call_ai=None,
) -> McpSyncResult:
    """Return a new McpSyncResult with deferred MCPs removed from final_mcp_list."""
    if mcp_result.status == "error" or not mcp_result.final_mcp_list:
        return mcp_result

    policy = load_policy(policy_path)
    pd = decide(policy, mcp_result.final_mcp_list, project.stack, project.ecosystem)
    ai_decisions = decide_ambiguous(
        pd.ambiguous, project.stack, project.ecosystem, cache_path, call_ai
    )

    active = set(pd.active)
    deferred = set(pd.deferred)
    for name, decision in ai_decisions.items():
        (active if decision == "active" else deferred).add(name)

    override = _load_override(Path(project.path))
    active = (active | set(override.get("force_active", []))) - set(override.get("force_deferred", []))
    deferred = (deferred | set(override.get("force_deferred", []))) - set(override.get("force_active", []))

    _inject_env_vars(Path(project.path), vault_path, project.name)

    return mcp_result.model_copy(update={
        "final_mcp_list": sorted(active),
        "mcps_deferred": sorted(deferred),
    })


def _load_override(project_path: Path) -> dict:
    override = project_path / ".arkaos" / "mcp-override.yaml"
    if not override.exists():
        return {}
    try:
        return yaml.safe_load(override.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return {}


def _inject_env_vars(project_path: Path, vault_path: Path | None, project_name: str) -> None:
    mcp_file = project_path / ".mcp.json"
    if not mcp_file.exists():
        return

    data = json.loads(mcp_file.read_text())
    servers = data.get("mcpServers", {})

    vault = _load_vault(vault_path) if vault_path else {}
    global_env = vault.get("global", {})
    project_env = vault.get("per_project", {}).get(project_name, {})
    merged_env = {**global_env, **project_env}

    missing: dict[str, str] = {}
    changed = False

    for server_name, config in servers.items():
        env = config.get("env") or {}
        for var_name, current in env.items():
            if current:
                continue
            if var_name in merged_env:
                env[var_name] = merged_env[var_name]
                changed = True
            else:
                missing[var_name] = server_name

        if env:
            config["env"] = env

    if changed:
        mcp_file.write_text(json.dumps(data, indent=2) + "\n")

    if missing:
        _write_env_example(project_path, missing)


def _load_vault(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        st = path.stat()
    except OSError:
        return {}
    # Refuse world- or group-readable files
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_env_example(project_path: Path, missing: dict[str, str]) -> None:
    lines = ["# Auto-generated by ArkaOS MCP Optimizer", ""]
    for var, server in sorted(missing.items()):
        lines.append(f"# required by {server}")
        lines.append(f"{var}=")
    (project_path / ".env.example").write_text("\n".join(lines) + "\n")


def optimize_all_mcps(
    projects: list[Project],
    mcp_results: list[McpSyncResult],
    policy_path: Path,
    vault_path: Path | None,
    cache_path: Path,
) -> list[McpSyncResult]:
    by_path = {r.path: r for r in mcp_results}
    out: list[McpSyncResult] = []
    for p in projects:
        mr = by_path.get(p.path)
        if mr is None:
            continue
        out.append(optimize_project_mcps(p, mr, policy_path, vault_path, cache_path))
    return out
```

- [ ] **Step 2: Run tests**

`python -m pytest tests/python/test_mcp_optimizer.py -v`

All 6 must PASS.

- [ ] **Step 3: Full suite**

`python -m pytest tests/python/ -q`

No regressions.

- [ ] **Step 4: Commit**

```bash
git add core/sync/mcp_optimizer.py
git commit -m "feat(sync): MCP optimizer with policy + AI + override + env vault"
```

---

## Task 9 — Engine wiring

**Files:** Modify `core/sync/engine.py`

- [ ] **Step 1: Locate existing MCP phase**

Read `core/sync/engine.py`. Find where `sync_all_mcps` is called.

- [ ] **Step 2: Insert optimizer between mcp_syncer and settings_syncer**

After `mcp_results = sync_all_mcps(...)`:

```python
from core.sync.mcp_optimizer import optimize_all_mcps
from pathlib import Path as _Path

_policy_path = _Path(__file__).resolve().parents[2] / "config" / "mcp-policy.yaml"
_vault_path = _Path.home() / ".arkaos" / "secrets.json"
_cache_path = _Path.home() / ".arkaos" / "mcp-decisions.cache.json"

if _policy_path.exists():
    mcp_results = optimize_all_mcps(
        projects, mcp_results, _policy_path,
        _vault_path if _vault_path.exists() else None,
        _cache_path,
    )
```

(Prefer placing imports at the top; use underscores only if needed to avoid collisions. Follow the existing style in engine.py.)

- [ ] **Step 3: Run full suite**

`python -m pytest tests/python/ -q`

- [ ] **Step 4: Commit**

```bash
git add core/sync/engine.py
git commit -m "feat(sync): wire MCP optimizer into sync engine"
```

---

## Task 10 — Reporter update

**Files:** Modify `core/sync/reporter.py`

- [ ] **Step 1: Reflect deferred MCPs**

Locate the MCP row renderer. Adjust the "Updated" label description to also mention deferred count, e.g., the row now reports `Updated (X)  [deferred: Y]` or similar — prefer a small additional column or a parenthetical that doesn't break existing tests.

Minimal change: leave existing columns intact; add a brief summary line after the table when `sum(len(r.mcps_deferred) for r in mcp_results) > 0`:

```
Deferred MCPs: 42 across 15 projects.
```

- [ ] **Step 2: Update any affected reporter tests**

`python -m pytest tests/python/test_sync_reporter.py -v`

If tests fail only because of the new deferred line, update the assertions to accept it. Do NOT change counting logic.

- [ ] **Step 3: Full suite**

`python -m pytest tests/python/ -q`

- [ ] **Step 4: Commit**

```bash
git add core/sync/reporter.py tests/python/test_sync_reporter.py
git commit -m "feat(sync): report deferred MCP summary"
```

---

## Task 11 — Integration test

**Files:** Modify `tests/python/test_sync_integration.py`

- [ ] **Step 1: Add end-to-end test**

Add `test_mcp_optimizer_defers_canva_on_laravel_stack`:
- Build fixture project with stack=["laravel"], `.mcp.json` containing `context7`, `postgres`, `canva`.
- Ensure `config/mcp-policy.yaml` exists in the repo (it does, from Task 2).
- Run the sync engine.
- Assert the resulting `settings.local.json` `enabledMcpjsonServers` contains `context7`, `postgres` but NOT `canva`.

- [ ] **Step 2: Run**

`python -m pytest tests/python/test_sync_integration.py -v -k mcp_optimizer`

PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_sync_integration.py
git commit -m "test(sync): MCP optimizer end-to-end integration"
```

---

## Task 12 — Full regression + Quality Gate + merge

- [ ] **Step 1: Full suite**

`python -m pytest tests/python/ -q`

Expect 2258 + ~19 new = ~2277 passing. 0 failures.

- [ ] **Step 2: Dispatch Quality Gate**

Same protocol as Sub-A: Marta reviews diff; Francisca for code/tests; Eduardo for policy docs/commit messages.

- [ ] **Step 3: On APPROVED, merge to master**

```bash
git checkout master
git merge --no-ff feature/mcp-optimizer -m "Merge Sub-feature B: MCP Optimizer"
git branch -d feature/mcp-optimizer
```

- [ ] **Step 4: No release yet**

v2.17.0 cut happens after Sub-C and Sub-D merge.

---

## Self-review

- **Spec coverage:** Policy loader ✅ (T3-4), AI fallback + cache ✅ (T5-6), Optimizer with override + env vault ✅ (T7-8), Engine wiring ✅ (T9), Reporter ✅ (T10), Integration test ✅ (T11). All spec items have tasks.
- **Placeholders:** None.
- **Type consistency:** `PolicyDecision.active/deferred/ambiguous: list[str]` used consistently. `AiCaller` signature `Callable[[str, list[str], str | None], str]` matches all test fakes. `McpSyncResult.mcps_deferred: list[str]` added in T1, consumed in T8, reported in T10.
- **Scope:** Only Sub-feature B. Does not touch content sync, agent provisioning, or self-healing.
