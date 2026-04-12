# Content Sync (Sub-feature A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Propagate core ArkaOS content (CLAUDE.md, rules, hooks, constitution excerpt) to every project during `/arka update`, preserving project-authored customizations via a managed-region merge algorithm.

**Architecture:** One new module `content_merger.py` (pure merge algorithm) + one orchestrator `content_syncer.py` (per-project sync for 4 artefact classes) + schema additions + engine wiring. Intelligent merge uses HTML-comment markers (`<!-- arkaos:managed:start ... -->`) — core-owned region is overwritten, user content is preserved forever.

**Tech Stack:** Python 3.11, Pydantic, PyYAML, pytest. Follows `.claude/rules/python-core.md`.

---

## Context for the Engineer

The sync engine (`core/sync/`) currently runs 3 phases: MCP configs, settings, descriptors. Phase pattern: each syncer has a `sync_*` public function returning a Pydantic result. Engine wires phases in `core/sync/engine.py`; reporter aggregates in `core/sync/reporter.py`.

**Sources of truth (this repo):**
- CLAUDE.md base template: `config/user-claude.md` (already exists)
- Standards (to be treated as rules): `config/standards/*.md` (communication, orchestration, ecosystem-workflow)
- Hooks: `config/hooks/*.sh` (existing)
- Constitution: `config/constitution.yaml` (existing)

**Targets (per project):**
- `<project>/.claude/CLAUDE.md` — full merge with managed region
- `<project>/.claude/rules/*.md` — full file replacement (rules are core-owned; no custom)
- `<project>/.claude/hooks/*.sh` — full file replacement (chmod +x preserved)
- `<project>/.claude/constitution-applicable.md` — generated from constitution.yaml

**Stack overlays (NEW):** `config/standards/claude-md-overlays/<stack>.md` — per-stack additions appended inside the managed region. Stacks: `laravel.md`, `nuxt.md`, `python.md`, `node.md`. Unknown stack → no overlay.

**Managed region markers (exact syntax):**
```markdown
<!-- arkaos:managed:start version=X.Y.Z hash=<sha256-12> -->
...core content...
<!-- arkaos:managed:end -->
```

Hash is the first 12 hex chars of sha256 over the managed content (excluding markers). `version` is current ArkaOS version from `VERSION` file.

**Merge rules:**
1. Target file has no markers → prepend fresh managed block at top of file (preserves any existing body as "project notes" below).
2. Target file has balanced markers → replace only content between markers.
3. Target file has unbalanced markers (one missing, nested, etc.) → write side-by-side `.arkaos-new` file, emit error, do not touch original.
4. If new managed content hash matches existing hash → report `unchanged`, skip write.

---

## File Structure

**Create:**
- `core/sync/content_merger.py` — pure merge algorithm (managed-region logic)
- `core/sync/content_syncer.py` — per-project orchestration for 4 artefact classes
- `config/standards/claude-md-overlays/laravel.md`
- `config/standards/claude-md-overlays/nuxt.md`
- `config/standards/claude-md-overlays/python.md`
- `config/standards/claude-md-overlays/node.md`
- `tests/python/test_content_merger.py`
- `tests/python/test_content_syncer.py`

**Modify:**
- `core/sync/schema.py` — add `ContentSyncResult`, extend `SyncReport`
- `core/sync/engine.py` — add Phase 4 (content sync) after descriptors
- `core/sync/reporter.py` — report content sync results

---

## Task 1: Schema additions

**Files:** Modify `core/sync/schema.py`

- [ ] **Step 1: Add ContentSyncResult and extend SyncReport**

Append to `core/sync/schema.py` (after `SkillSyncResult`):

```python
class ContentSyncResult(BaseModel):
    """Result of syncing content artefacts (CLAUDE.md, rules, hooks, constitution) for a project."""

    path: str
    status: str
    artefacts_updated: list[str] = Field(default_factory=list)
    artefacts_unchanged: list[str] = Field(default_factory=list)
    artefacts_errored: list[str] = Field(default_factory=list)
    error: str | None = None
```

Modify the `SyncReport` class to add this field after `skill_results`:

```python
    content_results: list[ContentSyncResult] = Field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add core/sync/schema.py
git commit -m "feat(sync): add ContentSyncResult schema"
```

---

## Task 2: Content merger — failing tests

**Files:** Create `tests/python/test_content_merger.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for core.sync.content_merger — managed-region merge algorithm."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.content_merger import (
    MergeResult,
    merge_managed_content,
    compute_managed_hash,
)


def test_hash_is_stable_for_same_content() -> None:
    h1 = compute_managed_hash("hello world")
    h2 = compute_managed_hash("hello world")
    assert h1 == h2
    assert len(h1) == 12


def test_hash_differs_for_different_content() -> None:
    assert compute_managed_hash("a") != compute_managed_hash("b")


def test_merge_into_file_without_markers_prepends_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# Project notes\n\nCustom content here.\n")

    result = merge_managed_content(
        target_text="# Project notes\n\nCustom content here.\n",
        managed_content="CORE",
        version="2.17.0",
    )

    assert result.status == "updated"
    assert "<!-- arkaos:managed:start" in result.new_text
    assert "CORE" in result.new_text
    assert "<!-- arkaos:managed:end -->" in result.new_text
    assert "Custom content here." in result.new_text
    assert result.new_text.index("CORE") < result.new_text.index("Custom content")


def test_merge_replaces_existing_managed_block() -> None:
    target = (
        "<!-- arkaos:managed:start version=2.16.0 hash=abc123abc123 -->\n"
        "OLD CORE\n"
        "<!-- arkaos:managed:end -->\n\n"
        "## Project notes\n\nCustom.\n"
    )

    result = merge_managed_content(
        target_text=target,
        managed_content="NEW CORE",
        version="2.17.0",
    )

    assert result.status == "updated"
    assert "OLD CORE" not in result.new_text
    assert "NEW CORE" in result.new_text
    assert "Custom." in result.new_text
    assert "version=2.17.0" in result.new_text


def test_merge_unchanged_when_hash_matches() -> None:
    managed = "STABLE"
    hash12 = compute_managed_hash(managed)
    target = (
        f"<!-- arkaos:managed:start version=2.17.0 hash={hash12} -->\n"
        f"{managed}\n"
        "<!-- arkaos:managed:end -->\n"
    )

    result = merge_managed_content(
        target_text=target,
        managed_content=managed,
        version="2.17.0",
    )

    assert result.status == "unchanged"
    assert result.new_text == target


def test_merge_detects_unbalanced_markers_as_error() -> None:
    target = (
        "<!-- arkaos:managed:start version=2.16.0 hash=abc123abc123 -->\n"
        "ORPHAN START\n"
    )

    result = merge_managed_content(
        target_text=target,
        managed_content="ANYTHING",
        version="2.17.0",
    )

    assert result.status == "error"
    assert "unbalanced" in (result.error or "").lower()


def test_merge_preserves_empty_target() -> None:
    result = merge_managed_content(
        target_text="",
        managed_content="CORE",
        version="2.17.0",
    )
    assert result.status == "updated"
    assert "CORE" in result.new_text
```

- [ ] **Step 2: Run to verify all fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_content_merger.py -v`

Expected: ImportError (module does not exist). All tests fail.

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_content_merger.py
git commit -m "test(sync): content merger managed-region tests"
```

---

## Task 3: Content merger — implementation

**Files:** Create `core/sync/content_merger.py`

- [ ] **Step 1: Implement the module**

```python
"""Managed-region content merger for the ArkaOS Sync Engine.

Merges core-owned content into project files while preserving any
project-authored content outside the managed region. Uses HTML comment
markers to delimit the managed block.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

_START_RE = re.compile(
    r"<!--\s*arkaos:managed:start(?:\s+version=(?P<version>\S+))?"
    r"(?:\s+hash=(?P<hash>[0-9a-f]{12}))?\s*-->",
)
_END_RE = re.compile(r"<!--\s*arkaos:managed:end\s*-->")


@dataclass
class MergeResult:
    """Outcome of a managed-region merge operation."""

    status: Literal["updated", "unchanged", "error"]
    new_text: str
    error: str | None = None


def compute_managed_hash(content: str) -> str:
    """Return the first 12 hex chars of sha256 over managed content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def merge_managed_content(
    target_text: str, managed_content: str, version: str
) -> MergeResult:
    """Merge managed_content into target_text inside the managed region.

    Returns status "updated" when the file changes, "unchanged" when the
    new hash matches the existing one, or "error" when markers are
    unbalanced.
    """
    starts = list(_START_RE.finditer(target_text))
    ends = list(_END_RE.finditer(target_text))

    if len(starts) != len(ends):
        return MergeResult(
            status="error",
            new_text=target_text,
            error=f"unbalanced markers: {len(starts)} starts, {len(ends)} ends",
        )

    if len(starts) > 1:
        return MergeResult(
            status="error",
            new_text=target_text,
            error="multiple managed blocks are not supported",
        )

    new_hash = compute_managed_hash(managed_content)
    new_block = _render_block(managed_content, version, new_hash)

    if not starts:
        return _prepend_block(target_text, new_block)

    start_match = starts[0]
    end_match = ends[0]
    if end_match.start() < start_match.end():
        return MergeResult(
            status="error",
            new_text=target_text,
            error="end marker appears before start marker",
        )

    existing_hash = start_match.group("hash")
    if existing_hash == new_hash:
        return MergeResult(status="unchanged", new_text=target_text)

    new_text = (
        target_text[: start_match.start()]
        + new_block
        + target_text[end_match.end() :]
    )
    return MergeResult(status="updated", new_text=new_text)


def _render_block(content: str, version: str, content_hash: str) -> str:
    """Render a managed block with start/end markers around content."""
    return (
        f"<!-- arkaos:managed:start version={version} hash={content_hash} -->\n"
        f"{content}\n"
        "<!-- arkaos:managed:end -->"
    )


def _prepend_block(target_text: str, new_block: str) -> MergeResult:
    """Prepend a managed block to target_text, preserving trailing content."""
    separator = "\n\n" if target_text else "\n"
    new_text = f"{new_block}{separator}{target_text}" if target_text else f"{new_block}\n"
    return MergeResult(status="updated", new_text=new_text)
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_content_merger.py -v`

Expected: all 7 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add core/sync/content_merger.py
git commit -m "feat(sync): managed-region content merger"
```

---

## Task 4: Stack overlays — content

**Files:** Create overlay files

- [ ] **Step 1: Create `config/standards/claude-md-overlays/laravel.md`**

```markdown
## Laravel Stack Conventions

- Services + Repositories pattern; no logic in controllers.
- Form Requests for all input validation.
- API Resources for response shaping.
- Feature Tests with RefreshDatabase trait.
- Eloquent relationships over raw joins.
- Conventional commits: `feat(scope): ...`, `fix(scope): ...`.
```

- [ ] **Step 2: Create `config/standards/claude-md-overlays/nuxt.md`**

```markdown
## Nuxt / Vue Stack Conventions

- Composition API only; no Options API.
- TypeScript everywhere; no plain JS Vue files.
- `composables/` for shared reactive logic.
- `useFetch`/`useAsyncData` for server-side data.
- `~` alias for project root imports.
- Tailwind for styling; avoid scoped styles unless necessary.
```

- [ ] **Step 3: Create `config/standards/claude-md-overlays/python.md`**

```markdown
## Python Stack Conventions

- Type hints on every function signature.
- Pydantic for validation; dataclasses for pure data.
- `pytest` with fixtures; no `unittest.TestCase`.
- Functions under 30 lines; one responsibility.
- Docstrings on public API only; self-documenting code elsewhere.
- Virtual environments; never global `pip install`.
```

- [ ] **Step 4: Create `config/standards/claude-md-overlays/node.md`**

```markdown
## Node.js Stack Conventions

- ESM modules (import/export); no CommonJS `require()`.
- Support Node and Bun runtimes when writing CLI tooling.
- Graceful fallbacks when optional dependencies are missing.
- All paths via `os.homedir()` or `path.join`; never hardcoded.
- No interactive prompts in headless/CI runs.
```

- [ ] **Step 5: Commit**

```bash
git add config/standards/claude-md-overlays/
git commit -m "feat(sync): stack-specific CLAUDE.md overlays"
```

---

## Task 5: Content syncer — failing tests

**Files:** Create `tests/python/test_content_syncer.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for core.sync.content_syncer — per-project content sync orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.content_syncer import sync_project_content
from core.sync.schema import Project


@pytest.fixture
def core_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal fake core repo layout and point the syncer at it."""
    core = tmp_path / "core-repo"
    (core / "config" / "standards" / "claude-md-overlays").mkdir(parents=True)
    (core / "config" / "hooks").mkdir(parents=True)
    (core / "config").mkdir(parents=True, exist_ok=True)

    (core / "config" / "user-claude.md").write_text("# ArkaOS CLAUDE Template\n")
    (core / "config" / "standards" / "claude-md-overlays" / "python.md").write_text(
        "## Python Rules\n"
    )
    (core / "config" / "standards" / "communication.md").write_text("# Communication\n")
    (core / "config" / "hooks" / "session-start.sh").write_text("#!/bin/bash\necho start\n")
    (core / "config" / "constitution.yaml").write_text(
        "rules:\n  - name: squad-routing\n    level: NON-NEGOTIABLE\n"
    )
    (core / "VERSION").write_text("2.17.0\n")

    monkeypatch.setenv("ARKAOS_CORE_ROOT", str(core))
    return core


@pytest.fixture
def project(tmp_path: Path) -> Project:
    proj_dir = tmp_path / "my-project"
    (proj_dir / ".claude").mkdir(parents=True)
    return Project(
        path=str(proj_dir),
        name="my-project",
        stack=["python"],
    )


def test_sync_creates_claude_md_with_managed_block(core_repo: Path, project: Project) -> None:
    result = sync_project_content(project)

    assert result.status in {"updated", "unchanged"}
    claude_md = Path(project.path) / ".claude" / "CLAUDE.md"
    assert claude_md.exists()
    text = claude_md.read_text()
    assert "<!-- arkaos:managed:start" in text
    assert "ArkaOS CLAUDE Template" in text
    assert "Python Rules" in text
    assert "CLAUDE.md" in result.artefacts_updated


def test_sync_copies_rules(core_repo: Path, project: Project) -> None:
    sync_project_content(project)

    rules_dir = Path(project.path) / ".claude" / "rules"
    assert (rules_dir / "communication.md").exists()
    assert (rules_dir / "communication.md").read_text() == "# Communication\n"


def test_sync_copies_hooks_and_preserves_executable(core_repo: Path, project: Project) -> None:
    sync_project_content(project)

    hook = Path(project.path) / ".claude" / "hooks" / "session-start.sh"
    assert hook.exists()
    import os
    assert os.access(hook, os.X_OK), "hook must be executable"


def test_sync_preserves_user_content_outside_managed_block(
    core_repo: Path, project: Project
) -> None:
    claude_md = Path(project.path) / ".claude" / "CLAUDE.md"
    claude_md.write_text("# Project Notes\n\nMy custom notes.\n")

    sync_project_content(project)

    text = claude_md.read_text()
    assert "My custom notes." in text


def test_sync_idempotent(core_repo: Path, project: Project) -> None:
    sync_project_content(project)
    r2 = sync_project_content(project)

    assert r2.status == "unchanged"
    assert r2.artefacts_unchanged  # at least one


def test_sync_writes_constitution_applicable(core_repo: Path, project: Project) -> None:
    sync_project_content(project)
    cfile = Path(project.path) / ".claude" / "constitution-applicable.md"
    assert cfile.exists()
    assert "squad-routing" in cfile.read_text()
```

- [ ] **Step 2: Run to verify all fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_content_syncer.py -v`

Expected: ImportError, all fail.

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_content_syncer.py
git commit -m "test(sync): content syncer orchestration tests"
```

---

## Task 6: Content syncer — implementation

**Files:** Create `core/sync/content_syncer.py`

- [ ] **Step 1: Implement the module**

```python
"""Content syncer for the ArkaOS Sync Engine.

Syncs CLAUDE.md (with intelligent merge), rules, hooks, and a generated
constitution excerpt into each project's .claude/ directory.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from core.sync.content_merger import merge_managed_content
from core.sync.schema import ContentSyncResult, Project


def _core_root() -> Path:
    """Return the ArkaOS core repo root.

    Honors the ``ARKAOS_CORE_ROOT`` environment variable for tests; falls
    back to the directory two levels above this file.
    """
    env = os.environ.get("ARKAOS_CORE_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def sync_project_content(project: Project) -> ContentSyncResult:
    """Sync CLAUDE.md, rules, hooks, and constitution excerpt for a project."""
    try:
        return _do_sync(project)
    except Exception as exc:  # noqa: BLE001
        return ContentSyncResult(
            path=project.path, status="error", error=str(exc)
        )


def _do_sync(project: Project) -> ContentSyncResult:
    """Execute content sync for all four artefact classes."""
    core = _core_root()
    version = (core / "VERSION").read_text().strip()
    project_claude = Path(project.path) / ".claude"
    project_claude.mkdir(parents=True, exist_ok=True)

    updated: list[str] = []
    unchanged: list[str] = []
    errored: list[str] = []

    _sync_claude_md(core, project, project_claude, version, updated, unchanged, errored)
    _sync_rules(core, project_claude, updated, unchanged, errored)
    _sync_hooks(core, project_claude, updated, unchanged, errored)
    _sync_constitution(core, project_claude, updated, unchanged, errored)

    status = "updated" if updated else ("error" if errored else "unchanged")
    return ContentSyncResult(
        path=project.path,
        status=status,
        artefacts_updated=updated,
        artefacts_unchanged=unchanged,
        artefacts_errored=errored,
    )


def _sync_claude_md(
    core: Path,
    project: Project,
    project_claude: Path,
    version: str,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    """Build managed content and merge into <project>/.claude/CLAUDE.md."""
    base = (core / "config" / "user-claude.md").read_text()
    overlays_dir = core / "config" / "standards" / "claude-md-overlays"
    overlays: list[str] = []
    for stack in project.stack:
        overlay = overlays_dir / f"{stack}.md"
        if overlay.exists():
            overlays.append(overlay.read_text())

    managed_content = "\n\n".join([base, *overlays]).strip()
    target_file = project_claude / "CLAUDE.md"
    target_text = target_file.read_text() if target_file.exists() else ""

    result = merge_managed_content(target_text, managed_content, version)
    if result.status == "error":
        errored.append(f"CLAUDE.md: {result.error}")
        sidecar = target_file.with_suffix(".md.arkaos-new")
        sidecar.write_text(managed_content)
        return
    if result.status == "unchanged":
        unchanged.append("CLAUDE.md")
        return
    target_file.write_text(result.new_text)
    updated.append("CLAUDE.md")


def _sync_rules(
    core: Path,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    """Copy core standards into <project>/.claude/rules/ (full replace)."""
    src = core / "config" / "standards"
    dst = project_claude / "rules"
    dst.mkdir(parents=True, exist_ok=True)
    for rule in src.glob("*.md"):
        target = dst / rule.name
        src_text = rule.read_text()
        if target.exists() and target.read_text() == src_text:
            unchanged.append(f"rules/{rule.name}")
            continue
        target.write_text(src_text)
        updated.append(f"rules/{rule.name}")


def _sync_hooks(
    core: Path,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    """Copy core hooks, preserving executable bit."""
    src = core / "config" / "hooks"
    dst = project_claude / "hooks"
    dst.mkdir(parents=True, exist_ok=True)
    for hook in src.glob("*.sh"):
        target = dst / hook.name
        src_text = hook.read_text()
        if target.exists() and target.read_text() == src_text:
            unchanged.append(f"hooks/{hook.name}")
            continue
        shutil.copy2(hook, target)
        target.chmod(0o755)
        updated.append(f"hooks/{hook.name}")


def _sync_constitution(
    core: Path,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    """Render a human-readable excerpt of the constitution for the project."""
    src = core / "config" / "constitution.yaml"
    target = project_claude / "constitution-applicable.md"
    data = yaml.safe_load(src.read_text()) or {}
    rules = data.get("rules", [])
    lines = ["# ArkaOS Constitution — Applicable Rules", ""]
    for rule in rules:
        lines.append(f"- **{rule.get('name', '?')}** — {rule.get('level', '?')}")
    body = "\n".join(lines) + "\n"
    if target.exists() and target.read_text() == body:
        unchanged.append("constitution-applicable.md")
        return
    target.write_text(body)
    updated.append("constitution-applicable.md")


def sync_all_content(projects: list[Project]) -> list[ContentSyncResult]:
    """Sync content artefacts for all projects."""
    return [sync_project_content(p) for p in projects]
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_content_syncer.py -v`

Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add core/sync/content_syncer.py
git commit -m "feat(sync): per-project content syncer orchestrator

Syncs CLAUDE.md (managed-region merge), rules, hooks, and
a generated constitution excerpt into <project>/.claude/."
```

---

## Task 7: Wire content sync into the engine

**Files:** Modify `core/sync/engine.py` and `core/sync/reporter.py`

- [ ] **Step 1: Inspect current engine**

Read `core/sync/engine.py` to locate where phases are orchestrated. Find the function that runs descriptor sync and add content sync immediately after, following the same pattern.

- [ ] **Step 2: Add content sync phase**

Add to the main sync function, after descriptor sync completes:

```python
from core.sync.content_syncer import sync_all_content

# ... after descriptor_results = sync_all_descriptors(projects):
content_results = sync_all_content(projects)
```

Pass `content_results` into the `SyncReport` constructor.

- [ ] **Step 3: Update reporter**

In `core/sync/reporter.py`, locate the summary table renderer. Add a new row for "Content" with `Total / Updated / Unchanged / Errors` counts computed from `content_results`. Use the same counting logic as existing rows.

- [ ] **Step 4: Run full test suite**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/ -q`

Expected: all previous tests + new content sync tests pass. 0 regressions.

- [ ] **Step 5: Commit**

```bash
git add core/sync/engine.py core/sync/reporter.py
git commit -m "feat(sync): wire content sync as Phase 4 of /arka update"
```

---

## Task 8: End-to-end integration test

**Files:** Modify `tests/python/test_sync_integration.py` (or create new test)

- [ ] **Step 1: Add a two-run idempotence test**

Locate existing integration test pattern. Add a test that runs `/arka update` equivalent twice in sequence against a fixture project with `stack=["python"]`:

```python
def test_content_sync_idempotent_across_two_runs(tmp_path, monkeypatch):
    # Setup fake core root + project (mirror test_content_syncer fixtures)
    # Run sync engine once → assert content_results[0].status == "updated"
    # Run sync engine again → assert content_results[0].status == "unchanged"
```

Copy the full fixture setup from `test_content_syncer.py` to keep the test self-contained.

- [ ] **Step 2: Run**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_integration.py -v -k content`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/python/test_sync_integration.py
git commit -m "test(sync): content sync idempotence integration test"
```

---

## Task 9: Full regression suite

**Files:** none (verification)

- [ ] **Step 1: Run complete suite**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/ -q`

Expected: 2244 previous + ~14 new (7 merger + 6 syncer + 1 integration) = ~2258 passing, 0 failures.

- [ ] **Step 2: If any regression**

STOP. Report as BLOCKED with failing test output. Do not proceed.

---

## Task 10: Quality Gate and merge prep

**Files:** none (process gate)

- [ ] **Step 1: Dispatch Marta (CQO) for review**

Same protocol as v2.16.1: diff `git diff master..HEAD`, Francisca reviews code quality, Eduardo reviews any user-facing copy (CLAUDE.md template wording, overlay docs).

- [ ] **Step 2: On APPROVED, merge to master**

```bash
git checkout master
git merge --no-ff feature/content-sync -m "Merge Sub-feature A: Content Sync"
```

- [ ] **Step 3: Do NOT release yet**

Version bump + release happens only after Sub-features B, C, D also merge. This is part of v2.17.0 umbrella. Stay on master, no tag, no npm publish.

---

## Self-review

- **Spec coverage** (v2.17.0 design spec Sub-feature A): CLAUDE.md merge ✅ (Tasks 3, 6), rules ✅ (Task 6), hooks ✅ (Task 6), constitution ✅ (Task 6), stack overlays ✅ (Task 4), idempotence ✅ (Task 8), reporter ✅ (Task 7). All covered.
- **Placeholders:** None. All code shown verbatim; all commands explicit.
- **Type consistency:** `ContentSyncResult.artefacts_updated: list[str]` consistent across Task 1 schema and Task 6 implementation. `MergeResult.status` matches across Task 2 test expectations and Task 3 literal type. `sync_project_content(project: Project) -> ContentSyncResult` signature stable.
- **Scope:** Focused on content merge + 4 artefact classes. Does not touch MCP optimization (Sub-feature B), agent provisioning (Sub-feature C), or self-healing (Sub-feature D).
