# Sync Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hybrid sync engine that makes `/arka update` actually propagate core changes (MCPs, settings, descriptors, features) to all projects.

**Architecture:** Python module `core/sync/` with 7 files handling deterministic sync (MCPs, settings, descriptors) plus a feature registry (`core/sync/features/*.yaml`) that AI subagents use to update ecosystem skill text. The SKILL.md orchestrates: calls Python for phases 1-3+5, dispatches 1 AI subagent for phase 4.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pathlib, subprocess, json (stdlib). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-11-sync-engine-design.md`

---

## File Structure

```
core/sync/
├── __init__.py              # Public API exports
├── schema.py                # Pydantic models for all sync data
├── manifest.py              # Phase 1: change manifest builder
├── discovery.py             # Phase 2: project discovery + stack detection
├── mcp_syncer.py            # Phase 3a: .mcp.json sync
├── settings_syncer.py       # Phase 3b: settings.local.json sync
├── descriptor_syncer.py     # Phase 3c: project descriptor updates
├── engine.py                # Orchestrator: runs all phases, CLI entry
├── reporter.py              # Phase 5: formatted report + state write
└── features/                # Feature registry (YAML)
    ├── forge.yaml
    ├── spec-gate.yaml
    ├── workflow-tiers.yaml
    └── quality-gate.yaml

tests/python/
├── test_sync_schema.py
├── test_sync_manifest.py
├── test_sync_discovery.py
├── test_sync_mcp_syncer.py
├── test_sync_settings_syncer.py
├── test_sync_descriptor_syncer.py
├── test_sync_engine.py
└── test_sync_reporter.py
```

---

### Task 1: Schema Models

**Files:**
- Create: `core/sync/schema.py`
- Create: `core/sync/__init__.py`
- Test: `tests/python/test_sync_schema.py`

- [ ] **Step 1: Write failing tests for schema models**

```python
# tests/python/test_sync_schema.py
import pytest
from core.sync.schema import (
    ChangeManifest,
    FeatureSpec,
    Project,
    McpSyncResult,
    SettingsSyncResult,
    DescriptorSyncResult,
    SyncReport,
)


class TestFeatureSpec:
    def test_create_minimal(self) -> None:
        f = FeatureSpec(
            name="forge-integration",
            added_in="2.14.0",
            mandatory=True,
            section_title="Forge Integration",
            detection_pattern="arka-forge",
            content="## Forge Integration\n\nContent here.",
        )
        assert f.name == "forge-integration"
        assert f.deprecated_in is None

    def test_deprecated_feature(self) -> None:
        f = FeatureSpec(
            name="old-feature",
            added_in="2.10.0",
            mandatory=False,
            section_title="Old Feature",
            detection_pattern="old-feat",
            content="## Old Feature",
            deprecated_in="2.15.0",
        )
        assert f.deprecated_in == "2.15.0"


class TestChangeManifest:
    def test_first_sync(self) -> None:
        m = ChangeManifest(
            previous_version="pending-sync",
            current_version="2.14.0",
            is_first_sync=True,
            features=[],
            new_features=[],
            deprecated_features=[],
        )
        assert m.is_first_sync is True

    def test_incremental_sync(self) -> None:
        feat = FeatureSpec(
            name="forge",
            added_in="2.14.0",
            mandatory=True,
            section_title="Forge",
            detection_pattern="arka-forge",
            content="## Forge",
        )
        m = ChangeManifest(
            previous_version="2.13.0",
            current_version="2.14.0",
            is_first_sync=False,
            features=[feat],
            new_features=["forge"],
            deprecated_features=[],
        )
        assert len(m.features) == 1
        assert m.new_features == ["forge"]


class TestProject:
    def test_create_with_ecosystem(self) -> None:
        p = Project(
            path="/Users/test/Herd/crm-rockport",
            name="crm-rockport",
            ecosystem="rockport",
            stack=["laravel", "php"],
            descriptor_path="/some/path.md",
            has_mcp_json=True,
            has_settings=True,
        )
        assert p.ecosystem == "rockport"
        assert p.stack == ["laravel", "php"]

    def test_create_without_ecosystem(self) -> None:
        p = Project(
            path="/Users/test/Work/my-app",
            name="my-app",
            ecosystem=None,
            stack=["nuxt", "vue"],
            descriptor_path=None,
            has_mcp_json=False,
            has_settings=False,
        )
        assert p.ecosystem is None
        assert p.descriptor_path is None


class TestMcpSyncResult:
    def test_updated(self) -> None:
        r = McpSyncResult(
            path="/test/project",
            status="updated",
            mcps_added=["laravel-boost"],
            mcps_removed=["old-mcp"],
            mcps_updated=["context7"],
            mcps_preserved=["custom-mcp"],
            final_mcp_list=["arka-prompts", "context7", "laravel-boost", "custom-mcp"],
        )
        assert r.status == "updated"
        assert r.error is None

    def test_error(self) -> None:
        r = McpSyncResult(
            path="/test/project",
            status="error",
            mcps_added=[],
            mcps_removed=[],
            mcps_updated=[],
            mcps_preserved=[],
            final_mcp_list=[],
            error="Failed to parse .mcp.json",
        )
        assert r.error == "Failed to parse .mcp.json"


class TestSettingsSyncResult:
    def test_created(self) -> None:
        r = SettingsSyncResult(
            path="/test/project",
            status="created",
            servers_added=["arka-prompts", "context7"],
            servers_removed=[],
        )
        assert r.status == "created"

    def test_unchanged(self) -> None:
        r = SettingsSyncResult(
            path="/test/project",
            status="unchanged",
            servers_added=[],
            servers_removed=[],
        )
        assert r.status == "unchanged"


class TestDescriptorSyncResult:
    def test_archived(self) -> None:
        r = DescriptorSyncResult(
            path="/test/descriptor.md",
            status="archived",
            changes=["status: active -> archived (path not found)"],
        )
        assert r.status == "archived"
        assert len(r.changes) == 1


class TestSyncReport:
    def test_create_report(self) -> None:
        r = SyncReport(
            previous_version="2.13.0",
            current_version="2.14.0",
            mcp_results=[],
            settings_results=[],
            descriptor_results=[],
            skill_results=[],
            errors=[],
        )
        assert r.previous_version == "2.13.0"
        assert r.errors == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.sync'`

- [ ] **Step 3: Create the sync module with schema**

```python
# core/sync/__init__.py
"""ArkaOS Sync Engine — Hybrid sync for /arka update."""

from core.sync.schema import (
    ChangeManifest,
    DescriptorSyncResult,
    FeatureSpec,
    McpSyncResult,
    Project,
    SettingsSyncResult,
    SkillSyncResult,
    SyncReport,
)

__all__ = [
    "ChangeManifest",
    "DescriptorSyncResult",
    "FeatureSpec",
    "McpSyncResult",
    "Project",
    "SettingsSyncResult",
    "SkillSyncResult",
    "SyncReport",
]
```

```python
# core/sync/schema.py
"""Pydantic models for all sync engine data structures."""

from pydantic import BaseModel


class FeatureSpec(BaseModel):
    """A propagatable feature from the feature registry."""

    name: str
    added_in: str
    mandatory: bool
    section_title: str
    detection_pattern: str
    content: str
    deprecated_in: str | None = None


class ChangeManifest(BaseModel):
    """Result of comparing last sync state with current version."""

    previous_version: str
    current_version: str
    is_first_sync: bool
    features: list[FeatureSpec]
    new_features: list[str]
    deprecated_features: list[str]


class Project(BaseModel):
    """A discovered project with detected metadata."""

    path: str
    name: str
    ecosystem: str | None = None
    stack: list[str] = []
    descriptor_path: str | None = None
    has_mcp_json: bool = False
    has_settings: bool = False


class McpSyncResult(BaseModel):
    """Result of syncing .mcp.json for one project."""

    path: str
    status: str  # "updated" | "unchanged" | "created" | "error"
    mcps_added: list[str] = []
    mcps_removed: list[str] = []
    mcps_updated: list[str] = []
    mcps_preserved: list[str] = []
    final_mcp_list: list[str] = []
    error: str | None = None


class SettingsSyncResult(BaseModel):
    """Result of syncing settings.local.json for one project."""

    path: str
    status: str  # "updated" | "unchanged" | "created" | "error"
    servers_added: list[str] = []
    servers_removed: list[str] = []
    error: str | None = None


class DescriptorSyncResult(BaseModel):
    """Result of syncing a project descriptor."""

    path: str
    status: str  # "updated" | "unchanged" | "archived" | "error"
    changes: list[str] = []
    error: str | None = None


class SkillSyncResult(BaseModel):
    """Result of syncing an ecosystem skill (AI phase)."""

    skill_name: str
    status: str  # "updated" | "unchanged" | "error"
    features_added: list[str] = []
    features_removed: list[str] = []
    error: str | None = None


class SyncReport(BaseModel):
    """Complete sync report across all phases."""

    previous_version: str
    current_version: str
    mcp_results: list[McpSyncResult] = []
    settings_results: list[SettingsSyncResult] = []
    descriptor_results: list[DescriptorSyncResult] = []
    skill_results: list[SkillSyncResult] = []
    errors: list[str] = []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_schema.py -v`
Expected: All 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/__init__.py core/sync/schema.py tests/python/test_sync_schema.py
git commit -m "feat(sync): add schema models for sync engine"
```

---

### Task 2: Feature Registry YAML Files

**Files:**
- Create: `core/sync/features/forge.yaml`
- Create: `core/sync/features/spec-gate.yaml`
- Create: `core/sync/features/workflow-tiers.yaml`
- Create: `core/sync/features/quality-gate.yaml`

- [ ] **Step 1: Create forge feature file**

```yaml
# core/sync/features/forge.yaml
name: forge-integration
added_in: "2.14.0"
mandatory: true
section_title: "Forge Integration"
detection_pattern: "arka-forge"
deprecated_in: null
content: |
  ## Forge Integration

  Complex requests (complexity score >= 5) are automatically routed to
  The Forge for multi-agent planning before execution.

  - Phase 0.5: Forge analysis (after spec creation, before squad planning)
  - Complexity assessment: automatic via Synapse L8 (ForgeContextLayer)
  - Manual invocation: `/forge` command
  - Handoff: Forge outputs structured plan → squad executes phases
```

- [ ] **Step 2: Create spec-gate feature file**

```yaml
# core/sync/features/spec-gate.yaml
name: spec-driven-gate
added_in: "2.13.0"
mandatory: true
section_title: "Spec-Driven Development"
detection_pattern: "arka-spec"
deprecated_in: null
content: |
  ## Spec-Driven Development

  Phase 0 of all workflows. No implementation begins without a validated spec.

  - Invocation: automatic before any feature/fix work
  - Gate: spec must be approved before planning phase starts
  - Storage: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  - Review: user approval required on written spec
```

- [ ] **Step 3: Create workflow-tiers feature file**

```yaml
# core/sync/features/workflow-tiers.yaml
name: workflow-tiers
added_in: "2.12.0"
mandatory: true
section_title: "Workflow Tiers"
detection_pattern: "Enterprise.*phase|Focused.*phase|Specialist.*phase"
deprecated_in: null
content: |
  ## Workflow Tiers

  Three workflow tiers based on task complexity:

  | Tier | Phases | When |
  |------|--------|------|
  | Enterprise | 7-10 phases | Complex features, multi-file changes |
  | Focused | 3-5 phases | Medium tasks, single-domain changes |
  | Specialist | 1-2 phases | Simple tasks, quick fixes |

  Tier selection is automatic based on complexity assessment.
  Quality Gate phase is mandatory on ALL tiers.
```

- [ ] **Step 4: Create quality-gate feature file**

```yaml
# core/sync/features/quality-gate.yaml
name: quality-gate
added_in: "2.10.0"
mandatory: true
section_title: "Quality Gate"
detection_pattern: "Marta.*CQO|Quality Gate"
deprecated_in: null
content: |
  ## Quality Gate

  Mandatory on every workflow. Nothing ships without approval.

  - **Marta (CQO):** Orchestrates review, absolute veto power
  - **Eduardo (Copy Director):** Reviews all text output
  - **Francisca (Tech Director):** Reviews all code and technical output
  - Verdict: APPROVED or REJECTED (binary, no partial)
```

- [ ] **Step 5: Commit**

```bash
git add core/sync/features/
git commit -m "feat(sync): add feature registry YAML files"
```

---

### Task 3: Change Manifest Builder

**Files:**
- Create: `core/sync/manifest.py`
- Test: `tests/python/test_sync_manifest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_manifest.py
import pytest
from pathlib import Path
from core.sync.schema import ChangeManifest, FeatureSpec
from core.sync.manifest import load_features, build_manifest


class TestLoadFeatures:
    def test_load_from_directory(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        (feat_dir / "forge.yaml").write_text(
            "name: forge\n"
            'added_in: "2.14.0"\n'
            "mandatory: true\n"
            "section_title: Forge\n"
            "detection_pattern: arka-forge\n"
            "content: |\n"
            "  ## Forge\n"
            "  Content here.\n"
        )
        features = load_features(feat_dir)
        assert len(features) == 1
        assert features[0].name == "forge"
        assert features[0].added_in == "2.14.0"

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        features = load_features(feat_dir)
        assert features == []

    def test_skip_non_yaml_files(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        (feat_dir / "readme.txt").write_text("not a feature")
        features = load_features(feat_dir)
        assert features == []

    def test_load_deprecated_feature(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        (feat_dir / "old.yaml").write_text(
            "name: old-feat\n"
            'added_in: "2.10.0"\n'
            "mandatory: false\n"
            "section_title: Old\n"
            "detection_pattern: old-pattern\n"
            'deprecated_in: "2.15.0"\n'
            "content: |\n"
            "  ## Old Feature\n"
        )
        features = load_features(feat_dir)
        assert features[0].deprecated_in == "2.15.0"


class TestBuildManifest:
    def test_first_sync(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        (feat_dir / "forge.yaml").write_text(
            "name: forge\n"
            'added_in: "2.14.0"\n'
            "mandatory: true\n"
            "section_title: Forge\n"
            "detection_pattern: arka-forge\n"
            "content: |\n"
            "  ## Forge\n"
        )
        manifest = build_manifest(
            previous_version="pending-sync",
            current_version="2.14.0",
            features_dir=feat_dir,
        )
        assert manifest.is_first_sync is True
        assert len(manifest.features) == 1
        assert manifest.new_features == ["forge"]

    def test_incremental_sync_new_feature(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        (feat_dir / "old.yaml").write_text(
            "name: quality-gate\n"
            'added_in: "2.10.0"\n'
            "mandatory: true\n"
            "section_title: QG\n"
            "detection_pattern: Quality Gate\n"
            "content: |\n"
            "  ## QG\n"
        )
        (feat_dir / "new.yaml").write_text(
            "name: forge\n"
            'added_in: "2.14.0"\n'
            "mandatory: true\n"
            "section_title: Forge\n"
            "detection_pattern: arka-forge\n"
            "content: |\n"
            "  ## Forge\n"
        )
        manifest = build_manifest(
            previous_version="2.13.0",
            current_version="2.14.0",
            features_dir=feat_dir,
        )
        assert manifest.is_first_sync is False
        assert "forge" in manifest.new_features
        assert "quality-gate" not in manifest.new_features

    def test_incremental_sync_deprecated_feature(self, tmp_path: Path) -> None:
        feat_dir = tmp_path / "features"
        feat_dir.mkdir()
        (feat_dir / "old.yaml").write_text(
            "name: old-feat\n"
            'added_in: "2.10.0"\n'
            "mandatory: false\n"
            "section_title: Old\n"
            "detection_pattern: old\n"
            'deprecated_in: "2.14.0"\n'
            "content: |\n"
            "  ## Old\n"
        )
        manifest = build_manifest(
            previous_version="2.13.0",
            current_version="2.14.0",
            features_dir=feat_dir,
        )
        assert "old-feat" in manifest.deprecated_features
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.sync.manifest'`

- [ ] **Step 3: Implement manifest.py**

```python
# core/sync/manifest.py
"""Phase 1: Build change manifest from sync state and feature registry."""

from pathlib import Path

import yaml

from core.sync.schema import ChangeManifest, FeatureSpec

_FIRST_SYNC_MARKERS = {"pending-sync", "none", ""}


def load_features(features_dir: Path) -> list[FeatureSpec]:
    """Load all feature specs from YAML files in a directory."""
    if not features_dir.is_dir():
        return []
    features: list[FeatureSpec] = []
    for path in sorted(features_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        if raw:
            features.append(FeatureSpec(**raw))
    return features


def _is_version_newer(version: str, baseline: str) -> bool:
    """Check if version was added after baseline (simple semver compare)."""
    try:
        v_parts = [int(x) for x in version.split(".")]
        b_parts = [int(x) for x in baseline.split(".")]
        return v_parts > b_parts
    except (ValueError, AttributeError):
        return True


def build_manifest(
    previous_version: str,
    current_version: str,
    features_dir: Path,
) -> ChangeManifest:
    """Build a change manifest comparing previous sync to current state."""
    features = load_features(features_dir)
    is_first = previous_version in _FIRST_SYNC_MARKERS

    new_features = _find_new_features(features, previous_version, is_first)
    deprecated = _find_deprecated_features(features, previous_version, is_first)

    return ChangeManifest(
        previous_version=previous_version,
        current_version=current_version,
        is_first_sync=is_first,
        features=features,
        new_features=new_features,
        deprecated_features=deprecated,
    )


def _find_new_features(
    features: list[FeatureSpec],
    previous_version: str,
    is_first: bool,
) -> list[str]:
    """Find features added since previous version."""
    if is_first:
        return [f.name for f in features if f.deprecated_in is None]
    return [
        f.name
        for f in features
        if f.deprecated_in is None
        and _is_version_newer(f.added_in, previous_version)
    ]


def _find_deprecated_features(
    features: list[FeatureSpec],
    previous_version: str,
    is_first: bool,
) -> list[str]:
    """Find features deprecated since previous version."""
    if is_first:
        return []
    return [
        f.name
        for f in features
        if f.deprecated_in is not None
        and _is_version_newer(f.deprecated_in, previous_version)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_manifest.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/manifest.py tests/python/test_sync_manifest.py
git commit -m "feat(sync): add change manifest builder with feature registry loading"
```

---

### Task 4: Project Discovery

**Files:**
- Create: `core/sync/discovery.py`
- Test: `tests/python/test_sync_discovery.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_discovery.py
import json
import pytest
from pathlib import Path
from core.sync.schema import Project
from core.sync.discovery import (
    detect_stack,
    discover_from_descriptors,
    discover_from_filesystem,
    discover_from_ecosystems,
    discover_all_projects,
)


class TestDetectStack:
    def test_laravel_project(self, tmp_path: Path) -> None:
        composer = {"require": {"laravel/framework": "^11.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        stack = detect_stack(tmp_path)
        assert "laravel" in stack

    def test_nuxt_project(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"nuxt": "^3.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_stack(tmp_path)
        assert "nuxt" in stack

    def test_react_project(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"react": "^18.0", "next": "^14.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_stack(tmp_path)
        assert "react" in stack
        assert "next" in stack

    def test_python_project(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        stack = detect_stack(tmp_path)
        assert "python" in stack

    def test_empty_project(self, tmp_path: Path) -> None:
        stack = detect_stack(tmp_path)
        assert stack == []

    def test_vue_without_nuxt(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"vue": "^3.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_stack(tmp_path)
        assert "vue" in stack
        assert "nuxt" not in stack


class TestDiscoverFromDescriptors:
    def test_single_file_descriptor(self, tmp_path: Path) -> None:
        desc = tmp_path / "projects"
        desc.mkdir()
        (desc / "crm.md").write_text(
            "---\n"
            "name: crm\n"
            f"path: {tmp_path / 'crm'}\n"
            "ecosystem: rockport\n"
            "status: active\n"
            "stack:\n"
            "  - Laravel 11\n"
            "---\n"
            "# CRM\n"
        )
        (tmp_path / "crm").mkdir()
        projects = discover_from_descriptors(desc)
        assert len(projects) == 1
        assert projects[0].name == "crm"
        assert projects[0].ecosystem == "rockport"

    def test_skip_nonexistent_path(self, tmp_path: Path) -> None:
        desc = tmp_path / "projects"
        desc.mkdir()
        (desc / "ghost.md").write_text(
            "---\n"
            "name: ghost\n"
            "path: /nonexistent/path\n"
            "status: active\n"
            "---\n"
        )
        projects = discover_from_descriptors(desc)
        assert len(projects) == 0

    def test_directory_descriptor(self, tmp_path: Path) -> None:
        desc = tmp_path / "projects"
        proj_dir = desc / "my-proj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "PROJECT.md").write_text(
            "---\n"
            "name: my-proj\n"
            f"path: {tmp_path / 'my-proj'}\n"
            "status: active\n"
            "---\n"
        )
        (tmp_path / "my-proj").mkdir(exist_ok=True)
        projects = discover_from_descriptors(desc)
        assert len(projects) == 1


class TestDiscoverFromFilesystem:
    def test_find_project_with_mcp_json(self, tmp_path: Path) -> None:
        proj = tmp_path / "my-app"
        proj.mkdir()
        (proj / ".mcp.json").write_text("{}")
        projects = discover_from_filesystem([tmp_path])
        assert len(projects) == 1
        assert projects[0].name == "my-app"
        assert projects[0].has_mcp_json is True

    def test_find_project_with_claude_dir(self, tmp_path: Path) -> None:
        proj = tmp_path / "my-app"
        (proj / ".claude").mkdir(parents=True)
        projects = discover_from_filesystem([tmp_path])
        assert len(projects) == 1

    def test_skip_non_project_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "random-dir").mkdir()
        projects = discover_from_filesystem([tmp_path])
        assert len(projects) == 0

    def test_multiple_scan_dirs(self, tmp_path: Path) -> None:
        dir1 = tmp_path / "herd"
        dir2 = tmp_path / "work"
        dir1.mkdir()
        dir2.mkdir()
        p1 = dir1 / "laravel-app"
        p1.mkdir()
        (p1 / ".mcp.json").write_text("{}")
        p2 = dir2 / "nuxt-app"
        (p2 / ".claude").mkdir(parents=True)
        projects = discover_from_filesystem([dir1, dir2])
        assert len(projects) == 2


class TestDiscoverFromEcosystems:
    def test_extract_projects(self, tmp_path: Path) -> None:
        eco_file = tmp_path / "ecosystems.json"
        proj_path = tmp_path / "crm"
        proj_path.mkdir()
        eco_file.write_text(json.dumps({
            "ecosystems": {
                "rockport": {
                    "name": "Rockport",
                    "projects": ["crm"],
                    "project_paths": {
                        "crm": str(proj_path),
                    },
                }
            }
        }))
        projects = discover_from_ecosystems(eco_file)
        assert len(projects) == 1
        assert projects[0].ecosystem == "rockport"

    def test_missing_file(self, tmp_path: Path) -> None:
        projects = discover_from_ecosystems(tmp_path / "nope.json")
        assert projects == []


class TestDiscoverAllProjects:
    def test_deduplication_by_path(self, tmp_path: Path) -> None:
        proj = tmp_path / "my-app"
        proj.mkdir()
        (proj / ".mcp.json").write_text("{}")

        desc_dir = tmp_path / "descriptors"
        desc_dir.mkdir()
        (desc_dir / "my-app.md").write_text(
            "---\n"
            "name: my-app\n"
            f"path: {proj}\n"
            "ecosystem: test\n"
            "status: active\n"
            "---\n"
        )

        projects = discover_all_projects(
            descriptor_dir=desc_dir,
            scan_dirs=[tmp_path],
            ecosystems_file=tmp_path / "eco.json",
        )
        paths = [p.path for p in projects]
        assert paths.count(str(proj)) == 1

    def test_ecosystem_enriches_filesystem_discovery(self, tmp_path: Path) -> None:
        proj = tmp_path / "crm"
        proj.mkdir()
        (proj / ".mcp.json").write_text("{}")

        desc_dir = tmp_path / "descriptors"
        desc_dir.mkdir()
        (desc_dir / "crm.md").write_text(
            "---\n"
            "name: crm\n"
            f"path: {proj}\n"
            "ecosystem: rockport\n"
            "status: active\n"
            "---\n"
        )

        projects = discover_all_projects(
            descriptor_dir=desc_dir,
            scan_dirs=[tmp_path],
            ecosystems_file=tmp_path / "eco.json",
        )
        assert len(projects) == 1
        assert projects[0].ecosystem == "rockport"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement discovery.py**

```python
# core/sync/discovery.py
"""Phase 2: Project discovery from descriptors, filesystem, and ecosystems."""

import json
import re
from pathlib import Path

import yaml

from core.sync.schema import Project

_NUXT_PATTERN = re.compile(r"nuxt", re.IGNORECASE)
_NEXT_PATTERN = re.compile(r"next", re.IGNORECASE)
_REACT_PATTERN = re.compile(r"^react$", re.IGNORECASE)
_VUE_PATTERN = re.compile(r"^vue$", re.IGNORECASE)


def detect_stack(project_path: Path) -> list[str]:
    """Detect tech stack from package manager files."""
    stack: list[str] = []
    stack.extend(_detect_from_composer(project_path))
    stack.extend(_detect_from_package_json(project_path))
    stack.extend(_detect_from_pyproject(project_path))
    return stack


def _detect_from_composer(project_path: Path) -> list[str]:
    """Detect Laravel/PHP from composer.json."""
    composer_file = project_path / "composer.json"
    if not composer_file.is_file():
        return []
    try:
        data = json.loads(composer_file.read_text())
        requires = data.get("require", {})
        stack = ["php"]
        if "laravel/framework" in requires:
            stack.append("laravel")
        return stack
    except (json.JSONDecodeError, OSError):
        return []


def _detect_from_package_json(project_path: Path) -> list[str]:
    """Detect JS framework from package.json."""
    pkg_file = project_path / "package.json"
    if not pkg_file.is_file():
        return []
    try:
        data = json.loads(pkg_file.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        stack: list[str] = []
        if any(_NUXT_PATTERN.search(k) for k in deps):
            stack.append("nuxt")
            stack.append("vue")
        elif any(_VUE_PATTERN.search(k) for k in deps):
            stack.append("vue")
        if any(_NEXT_PATTERN.search(k) for k in deps):
            stack.append("next")
        if any(_REACT_PATTERN.search(k) for k in deps):
            stack.append("react")
        return stack
    except (json.JSONDecodeError, OSError):
        return []


def _detect_from_pyproject(project_path: Path) -> list[str]:
    """Detect Python from pyproject.toml."""
    if (project_path / "pyproject.toml").is_file():
        return ["python"]
    return []


def _parse_descriptor_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown file."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def discover_from_descriptors(descriptor_dir: Path) -> list[Project]:
    """Discover projects from descriptor .md files."""
    if not descriptor_dir.is_dir():
        return []
    projects: list[Project] = []
    for item in sorted(descriptor_dir.iterdir()):
        fm = _read_descriptor_item(item)
        if not fm:
            continue
        path_str = fm.get("path", "")
        if not path_str or not Path(path_str).is_dir():
            continue
        project_path = Path(path_str)
        projects.append(Project(
            path=str(project_path),
            name=fm.get("name", project_path.name),
            ecosystem=fm.get("ecosystem"),
            stack=detect_stack(project_path),
            descriptor_path=str(item if item.is_file() else item / "PROJECT.md"),
            has_mcp_json=(project_path / ".mcp.json").is_file(),
            has_settings=(project_path / ".claude" / "settings.local.json").is_file(),
        ))
    return projects


def _read_descriptor_item(item: Path) -> dict:
    """Read frontmatter from a descriptor file or directory."""
    if item.is_file() and item.suffix == ".md":
        return _parse_descriptor_frontmatter(item.read_text())
    if item.is_dir():
        project_md = item / "PROJECT.md"
        if project_md.is_file():
            return _parse_descriptor_frontmatter(project_md.read_text())
    return {}


def discover_from_filesystem(scan_dirs: list[Path]) -> list[Project]:
    """Discover projects by scanning directories for .mcp.json or .claude/."""
    projects: list[Project] = []
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for item in sorted(scan_dir.iterdir()):
            if not item.is_dir():
                continue
            has_mcp = (item / ".mcp.json").is_file()
            has_claude = (item / ".claude").is_dir()
            if not has_mcp and not has_claude:
                continue
            projects.append(Project(
                path=str(item),
                name=item.name,
                stack=detect_stack(item),
                has_mcp_json=has_mcp,
                has_settings=(item / ".claude" / "settings.local.json").is_file(),
            ))
    return projects


def discover_from_ecosystems(ecosystems_file: Path) -> list[Project]:
    """Discover projects from ecosystems.json registry."""
    if not ecosystems_file.is_file():
        return []
    try:
        data = json.loads(ecosystems_file.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    projects: list[Project] = []
    for eco_name, eco in data.get("ecosystems", {}).items():
        paths = eco.get("project_paths", {})
        for proj_name, proj_path in paths.items():
            if not Path(proj_path).is_dir():
                continue
            pp = Path(proj_path)
            projects.append(Project(
                path=str(pp),
                name=proj_name,
                ecosystem=eco_name,
                stack=detect_stack(pp),
                has_mcp_json=(pp / ".mcp.json").is_file(),
                has_settings=(pp / ".claude" / "settings.local.json").is_file(),
            ))
    return projects


def discover_all_projects(
    descriptor_dir: Path,
    scan_dirs: list[Path],
    ecosystems_file: Path,
) -> list[Project]:
    """Discover and deduplicate projects from all 3 sources."""
    desc_projects = discover_from_descriptors(descriptor_dir)
    fs_projects = discover_from_filesystem(scan_dirs)
    eco_projects = discover_from_ecosystems(ecosystems_file)
    return _deduplicate(desc_projects, fs_projects, eco_projects)


def _deduplicate(
    desc: list[Project],
    fs: list[Project],
    eco: list[Project],
) -> list[Project]:
    """Deduplicate by path. Descriptor data wins for ecosystem/name."""
    seen: dict[str, Project] = {}
    for project in eco + fs + desc:
        resolved = str(Path(project.path).resolve())
        existing = seen.get(resolved)
        if existing is None:
            seen[resolved] = project
        else:
            seen[resolved] = _merge_project(existing, project)
    return sorted(seen.values(), key=lambda p: p.name)


def _merge_project(existing: Project, incoming: Project) -> Project:
    """Merge two project entries, preferring non-None values from incoming."""
    return Project(
        path=existing.path,
        name=incoming.name or existing.name,
        ecosystem=incoming.ecosystem or existing.ecosystem,
        stack=incoming.stack or existing.stack,
        descriptor_path=incoming.descriptor_path or existing.descriptor_path,
        has_mcp_json=existing.has_mcp_json or incoming.has_mcp_json,
        has_settings=existing.has_settings or incoming.has_settings,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_discovery.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/discovery.py tests/python/test_sync_discovery.py
git commit -m "feat(sync): add project discovery with stack detection and deduplication"
```

---

### Task 5: MCP Syncer

**Files:**
- Create: `core/sync/mcp_syncer.py`
- Test: `tests/python/test_sync_mcp_syncer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_mcp_syncer.py
import json
import pytest
from pathlib import Path
from core.sync.schema import Project, McpSyncResult
from core.sync.mcp_syncer import (
    load_registry,
    resolve_mcps_for_stack,
    sync_project_mcp,
    sync_all_mcps,
)

_SAMPLE_REGISTRY = {
    "_meta": {"description": "test"},
    "mcpServers": {
        "arka-prompts": {
            "command": "uv",
            "args": ["--directory", "{home}/.claude/skills/arka/mcp-server", "run", "server.py"],
            "category": "base",
        },
        "context7": {
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp"],
            "category": "base",
        },
        "laravel-boost": {
            "command": "npx",
            "args": ["laravel-boost-mcp"],
            "category": "laravel",
        },
        "serena": {
            "command": "uvx",
            "args": ["serena", "start-mcp-server", "--project", "{cwd}"],
            "category": "laravel",
        },
    },
}


class TestLoadRegistry:
    def test_load_valid(self, tmp_path: Path) -> None:
        reg_file = tmp_path / "registry.json"
        reg_file.write_text(json.dumps(_SAMPLE_REGISTRY))
        registry = load_registry(reg_file)
        assert "arka-prompts" in registry
        assert registry["arka-prompts"]["category"] == "base"

    def test_missing_file(self, tmp_path: Path) -> None:
        registry = load_registry(tmp_path / "nope.json")
        assert registry == {}


class TestResolveMcpsForStack:
    def test_base_only(self) -> None:
        mcps = resolve_mcps_for_stack(_SAMPLE_REGISTRY["mcpServers"], [])
        names = [name for name, _ in mcps]
        assert "arka-prompts" in names
        assert "context7" in names
        assert "laravel-boost" not in names

    def test_laravel_stack(self) -> None:
        mcps = resolve_mcps_for_stack(_SAMPLE_REGISTRY["mcpServers"], ["laravel", "php"])
        names = [name for name, _ in mcps]
        assert "arka-prompts" in names
        assert "laravel-boost" in names
        assert "serena" in names

    def test_empty_registry(self) -> None:
        mcps = resolve_mcps_for_stack({}, ["laravel"])
        assert mcps == []


class TestSyncProjectMcp:
    def test_create_new_mcp_json(self, tmp_path: Path) -> None:
        project = Project(path=str(tmp_path), name="test", stack=["laravel"])
        result = sync_project_mcp(
            project=project,
            registry=_SAMPLE_REGISTRY["mcpServers"],
            home_path="/Users/test",
        )
        assert result.status == "created"
        assert "arka-prompts" in result.final_mcp_list
        assert "laravel-boost" in result.final_mcp_list
        mcp_file = tmp_path / ".mcp.json"
        assert mcp_file.is_file()
        data = json.loads(mcp_file.read_text())
        assert "mcpServers" in data

    def test_preserve_custom_mcps(self, tmp_path: Path) -> None:
        existing = {
            "mcpServers": {
                "arka-prompts": {"command": "old", "args": []},
                "my-custom-mcp": {"command": "custom", "args": ["--flag"]},
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(existing))
        project = Project(path=str(tmp_path), name="test", stack=[], has_mcp_json=True)
        result = sync_project_mcp(
            project=project,
            registry=_SAMPLE_REGISTRY["mcpServers"],
            home_path="/Users/test",
        )
        assert "my-custom-mcp" in result.mcps_preserved
        assert "my-custom-mcp" in result.final_mcp_list
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert "my-custom-mcp" in data["mcpServers"]

    def test_update_existing_mcp_args(self, tmp_path: Path) -> None:
        existing = {
            "mcpServers": {
                "arka-prompts": {"command": "old-cmd", "args": ["old"]},
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(existing))
        project = Project(path=str(tmp_path), name="test", stack=[], has_mcp_json=True)
        result = sync_project_mcp(
            project=project,
            registry=_SAMPLE_REGISTRY["mcpServers"],
            home_path="/Users/test",
        )
        assert "arka-prompts" in result.mcps_updated
        data = json.loads((tmp_path / ".mcp.json").read_text())
        assert data["mcpServers"]["arka-prompts"]["command"] == "uv"

    def test_serena_project_path(self, tmp_path: Path) -> None:
        project = Project(path=str(tmp_path), name="test", stack=["laravel"])
        result = sync_project_mcp(
            project=project,
            registry=_SAMPLE_REGISTRY["mcpServers"],
            home_path="/Users/test",
        )
        data = json.loads((tmp_path / ".mcp.json").read_text())
        serena_args = data["mcpServers"]["serena"]["args"]
        assert str(tmp_path) in serena_args

    def test_unchanged_when_already_correct(self, tmp_path: Path) -> None:
        registry = _SAMPLE_REGISTRY["mcpServers"]
        existing = {"mcpServers": {}}
        for name, cfg in registry.items():
            if cfg["category"] == "base":
                resolved = dict(cfg)
                resolved["args"] = [
                    a.replace("{home}", "/Users/test") for a in cfg["args"]
                ]
                existing["mcpServers"][name] = {
                    "command": resolved["command"],
                    "args": resolved["args"],
                }
        (tmp_path / ".mcp.json").write_text(json.dumps(existing))
        project = Project(path=str(tmp_path), name="test", stack=[], has_mcp_json=True)
        result = sync_project_mcp(
            project=project,
            registry=registry,
            home_path="/Users/test",
        )
        assert result.status == "unchanged"


class TestSyncAllMcps:
    def test_multiple_projects(self, tmp_path: Path) -> None:
        p1 = tmp_path / "proj1"
        p2 = tmp_path / "proj2"
        p1.mkdir()
        p2.mkdir()
        projects = [
            Project(path=str(p1), name="proj1", stack=["laravel"]),
            Project(path=str(p2), name="proj2", stack=["nuxt"]),
        ]
        reg_file = tmp_path / "registry.json"
        reg_file.write_text(json.dumps(_SAMPLE_REGISTRY))
        results = sync_all_mcps(projects, reg_file, "/Users/test")
        assert len(results) == 2
        assert all(r.status in ("created", "updated", "unchanged") for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_mcp_syncer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement mcp_syncer.py**

```python
# core/sync/mcp_syncer.py
"""Phase 3a: Sync .mcp.json files for all projects."""

import json
from pathlib import Path

from core.sync.schema import McpSyncResult, Project

_STACK_TO_CATEGORIES: dict[str, list[str]] = {
    "laravel": ["laravel"],
    "php": ["laravel"],
    "nuxt": ["nuxt"],
    "vue": ["nuxt"],
    "next": ["react"],
    "react": ["react"],
    "shopify": ["ecommerce"],
}


def load_registry(registry_path: Path) -> dict:
    """Load MCP server registry from JSON file."""
    if not registry_path.is_file():
        return {}
    try:
        data = json.loads(registry_path.read_text())
        return data.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_mcps_for_stack(
    registry: dict,
    stack: list[str],
) -> list[tuple[str, dict]]:
    """Determine which MCPs a project should have based on stack."""
    allowed = {"base"}
    for tech in stack:
        allowed.update(_STACK_TO_CATEGORIES.get(tech.lower(), []))
    return [
        (name, cfg)
        for name, cfg in sorted(registry.items())
        if cfg.get("category", "base") in allowed
    ]


def sync_project_mcp(
    project: Project,
    registry: dict,
    home_path: str,
) -> McpSyncResult:
    """Sync .mcp.json for a single project."""
    try:
        return _do_sync(project, registry, home_path)
    except Exception as e:
        return McpSyncResult(
            path=project.path, status="error", error=str(e),
        )


def _do_sync(
    project: Project,
    registry: dict,
    home_path: str,
) -> McpSyncResult:
    """Core sync logic for one project's .mcp.json."""
    project_path = Path(project.path)
    mcp_file = project_path / ".mcp.json"
    current = _read_current_mcps(mcp_file)
    target = resolve_mcps_for_stack(registry, project.stack)

    resolved_target = _resolve_placeholders(target, home_path, project.path)
    registry_names = {name for name, _ in resolved_target}

    added, removed, updated, preserved = _diff_mcps(
        current, resolved_target, registry_names, registry,
    )

    if not added and not removed and not updated:
        final_list = sorted(current.keys())
        return McpSyncResult(
            path=project.path,
            status="unchanged",
            mcps_preserved=[n for n in current if n not in registry],
            final_mcp_list=final_list,
        )

    merged = _build_merged(current, resolved_target, registry_names, registry)
    _write_mcp_json(mcp_file, merged)

    return McpSyncResult(
        path=project.path,
        status="created" if not current else "updated",
        mcps_added=added,
        mcps_removed=removed,
        mcps_updated=updated,
        mcps_preserved=preserved,
        final_mcp_list=sorted(merged.keys()),
    )


def _read_current_mcps(mcp_file: Path) -> dict:
    """Read current .mcp.json servers, or empty dict if missing."""
    if not mcp_file.is_file():
        return {}
    try:
        data = json.loads(mcp_file.read_text())
        return data.get("mcpServers", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_placeholders(
    target: list[tuple[str, dict]],
    home_path: str,
    project_path: str,
) -> list[tuple[str, dict]]:
    """Replace {home} and {cwd} placeholders in MCP configs."""
    resolved: list[tuple[str, dict]] = []
    for name, cfg in target:
        new_cfg = dict(cfg)
        new_cfg["args"] = [
            a.replace("{home}", home_path).replace("{cwd}", project_path)
            for a in cfg.get("args", [])
        ]
        if "env" in cfg:
            new_cfg["env"] = {
                k: v.replace("{home}", home_path).replace("{cwd}", project_path)
                for k, v in cfg["env"].items()
            }
        resolved.append((name, new_cfg))
    return resolved


def _diff_mcps(
    current: dict,
    target: list[tuple[str, dict]],
    registry_names: set[str],
    full_registry: dict,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Calculate add/remove/update/preserve lists."""
    target_dict = dict(target)
    added = [n for n in target_dict if n not in current]
    removed = [
        n for n in current
        if n in full_registry and n not in target_dict
    ]
    updated = _find_updated(current, target_dict)
    preserved = [n for n in current if n not in full_registry]
    return added, removed, updated, preserved


def _find_updated(current: dict, target: dict) -> list[str]:
    """Find MCPs that exist in both but have different config."""
    updated: list[str] = []
    for name in current:
        if name not in target:
            continue
        cur = {k: v for k, v in current[name].items() if k != "category"}
        tgt = {k: v for k, v in target[name].items() if k != "category"}
        if cur != tgt:
            updated.append(name)
    return updated


def _build_merged(
    current: dict,
    target: list[tuple[str, dict]],
    registry_names: set[str],
    full_registry: dict,
) -> dict:
    """Build the final merged MCP dict."""
    merged: dict = {}
    for name, cfg in target:
        clean = {k: v for k, v in cfg.items() if k not in ("category", "description", "required_env")}
        merged[name] = clean
    for name, cfg in current.items():
        if name not in full_registry and name not in merged:
            merged[name] = cfg
    return merged


def _write_mcp_json(mcp_file: Path, servers: dict) -> None:
    """Write .mcp.json with proper formatting."""
    mcp_file.write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n")


def sync_all_mcps(
    projects: list[Project],
    registry_path: Path,
    home_path: str,
) -> list[McpSyncResult]:
    """Sync .mcp.json for all projects."""
    registry = load_registry(registry_path)
    return [
        sync_project_mcp(project, registry, home_path)
        for project in projects
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_mcp_syncer.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/mcp_syncer.py tests/python/test_sync_mcp_syncer.py
git commit -m "feat(sync): add MCP syncer with registry-based merge and placeholder resolution"
```

---

### Task 6: Settings Syncer

**Files:**
- Create: `core/sync/settings_syncer.py`
- Test: `tests/python/test_sync_settings_syncer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_settings_syncer.py
import json
import pytest
from pathlib import Path
from core.sync.schema import McpSyncResult, SettingsSyncResult
from core.sync.settings_syncer import sync_project_settings, sync_all_settings


class TestSyncProjectSettings:
    def test_create_new_settings(self, tmp_path: Path) -> None:
        mcp_result = McpSyncResult(
            path=str(tmp_path),
            status="created",
            final_mcp_list=["arka-prompts", "context7", "laravel-boost"],
        )
        result = sync_project_settings(tmp_path, mcp_result)
        assert result.status == "created"
        settings_file = tmp_path / ".claude" / "settings.local.json"
        assert settings_file.is_file()
        data = json.loads(settings_file.read_text())
        assert data["enableAllProjectMcpServers"] is True
        assert set(data["enabledMcpjsonServers"]) == {"arka-prompts", "context7", "laravel-boost"}

    def test_update_existing_preserves_permissions(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing = {
            "permissions": {
                "allow": ["Bash(php artisan:*)", "Read", "Grep"]
            },
            "enabledMcpjsonServers": ["arka-prompts"],
        }
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        mcp_result = McpSyncResult(
            path=str(tmp_path),
            status="updated",
            final_mcp_list=["arka-prompts", "context7", "laravel-boost"],
        )
        result = sync_project_settings(tmp_path, mcp_result)
        assert result.status == "updated"
        data = json.loads((claude_dir / "settings.local.json").read_text())
        assert "Bash(php artisan:*)" in data["permissions"]["allow"]
        assert "laravel-boost" in data["enabledMcpjsonServers"]

    def test_unchanged_when_already_correct(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing = {
            "permissions": {"allow": ["Read"]},
            "enableAllProjectMcpServers": True,
            "enabledMcpjsonServers": ["arka-prompts", "context7"],
        }
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        mcp_result = McpSyncResult(
            path=str(tmp_path),
            status="unchanged",
            final_mcp_list=["arka-prompts", "context7"],
        )
        result = sync_project_settings(tmp_path, mcp_result)
        assert result.status == "unchanged"

    def test_add_and_remove_servers(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing = {
            "enabledMcpjsonServers": ["arka-prompts", "old-server"],
        }
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        mcp_result = McpSyncResult(
            path=str(tmp_path),
            status="updated",
            final_mcp_list=["arka-prompts", "new-server"],
        )
        result = sync_project_settings(tmp_path, mcp_result)
        assert "new-server" in result.servers_added
        assert "old-server" in result.servers_removed


class TestSyncAllSettings:
    def test_batch_sync(self, tmp_path: Path) -> None:
        p1 = tmp_path / "proj1"
        p2 = tmp_path / "proj2"
        p1.mkdir()
        p2.mkdir()
        mcp_results = [
            McpSyncResult(path=str(p1), status="created", final_mcp_list=["arka-prompts"]),
            McpSyncResult(path=str(p2), status="created", final_mcp_list=["arka-prompts", "context7"]),
        ]
        results = sync_all_settings(mcp_results)
        assert len(results) == 2
        assert all(r.status in ("created", "updated", "unchanged") for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_settings_syncer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement settings_syncer.py**

```python
# core/sync/settings_syncer.py
"""Phase 3b: Sync settings.local.json for all projects."""

import json
from pathlib import Path

from core.sync.schema import McpSyncResult, SettingsSyncResult

_DEFAULT_PERMISSIONS = {
    "allow": ["Read", "Grep", "Glob", "WebFetch"],
}


def sync_project_settings(
    project_path: Path,
    mcp_result: McpSyncResult,
) -> SettingsSyncResult:
    """Sync settings.local.json for one project."""
    try:
        return _do_sync(project_path, mcp_result)
    except Exception as e:
        return SettingsSyncResult(
            path=str(project_path), status="error", error=str(e),
        )


def _do_sync(
    project_path: Path,
    mcp_result: McpSyncResult,
) -> SettingsSyncResult:
    """Core sync logic for one project's settings."""
    settings_file = project_path / ".claude" / "settings.local.json"
    current = _read_current_settings(settings_file)
    target_servers = sorted(mcp_result.final_mcp_list)

    current_servers = sorted(current.get("enabledMcpjsonServers", []))
    has_flag = current.get("enableAllProjectMcpServers") is True

    if current_servers == target_servers and has_flag and current:
        return SettingsSyncResult(
            path=str(project_path), status="unchanged",
        )

    added = [s for s in target_servers if s not in current_servers]
    removed = [s for s in current_servers if s not in target_servers]
    is_new = not settings_file.is_file()

    merged = _build_merged_settings(current, target_servers)
    _write_settings(settings_file, merged)

    return SettingsSyncResult(
        path=str(project_path),
        status="created" if is_new else "updated",
        servers_added=added,
        servers_removed=removed,
    )


def _read_current_settings(settings_file: Path) -> dict:
    """Read current settings, or empty dict if missing."""
    if not settings_file.is_file():
        return {}
    try:
        return json.loads(settings_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _build_merged_settings(current: dict, target_servers: list[str]) -> dict:
    """Build merged settings preserving permissions."""
    merged = dict(current)
    if "permissions" not in merged:
        merged["permissions"] = dict(_DEFAULT_PERMISSIONS)
    merged["enableAllProjectMcpServers"] = True
    merged["enabledMcpjsonServers"] = target_servers
    return merged


def _write_settings(settings_file: Path, data: dict) -> None:
    """Write settings.local.json with proper formatting."""
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, indent=2) + "\n")


def sync_all_settings(
    mcp_results: list[McpSyncResult],
) -> list[SettingsSyncResult]:
    """Sync settings for all projects based on MCP sync results."""
    return [
        sync_project_settings(Path(result.path), result)
        for result in mcp_results
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_settings_syncer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/settings_syncer.py tests/python/test_sync_settings_syncer.py
git commit -m "feat(sync): add settings syncer with permission preservation"
```

---

### Task 7: Descriptor Syncer

**Files:**
- Create: `core/sync/descriptor_syncer.py`
- Test: `tests/python/test_sync_descriptor_syncer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_descriptor_syncer.py
import pytest
from pathlib import Path
from unittest.mock import patch
from core.sync.schema import Project, DescriptorSyncResult
from core.sync.descriptor_syncer import sync_descriptor, sync_all_descriptors


class TestSyncDescriptor:
    def test_archive_missing_path(self, tmp_path: Path) -> None:
        desc = tmp_path / "ghost.md"
        desc.write_text(
            "---\n"
            "name: ghost\n"
            "path: /nonexistent/path\n"
            "status: active\n"
            "---\n"
            "# Ghost Project\n"
        )
        project = Project(
            path="/nonexistent/path",
            name="ghost",
            descriptor_path=str(desc),
        )
        result = sync_descriptor(project)
        assert result.status == "archived"
        content = desc.read_text()
        assert "status: archived" in content

    def test_update_stack(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / "my-app"
        proj_dir.mkdir()
        import json
        (proj_dir / "composer.json").write_text(
            json.dumps({"require": {"laravel/framework": "^11.0"}})
        )
        desc = tmp_path / "my-app.md"
        desc.write_text(
            "---\n"
            "name: my-app\n"
            f"path: {proj_dir}\n"
            "status: active\n"
            "stack:\n"
            "  - Vue 3\n"
            "---\n"
            "# My App\n"
        )
        project = Project(
            path=str(proj_dir),
            name="my-app",
            stack=["php", "laravel"],
            descriptor_path=str(desc),
        )
        result = sync_descriptor(project)
        assert result.status == "updated"
        assert any("stack" in c for c in result.changes)

    def test_auto_pause_inactive(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / "old-app"
        proj_dir.mkdir()
        desc = tmp_path / "old-app.md"
        desc.write_text(
            "---\n"
            "name: old-app\n"
            f"path: {proj_dir}\n"
            "status: active\n"
            "---\n"
            "# Old App\n"
        )
        project = Project(
            path=str(proj_dir),
            name="old-app",
            descriptor_path=str(desc),
        )
        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=45,
        ):
            result = sync_descriptor(project)
        assert result.status == "updated"
        assert any("paused" in c for c in result.changes)

    def test_auto_reactivate(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / "active-app"
        proj_dir.mkdir()
        desc = tmp_path / "active-app.md"
        desc.write_text(
            "---\n"
            "name: active-app\n"
            f"path: {proj_dir}\n"
            "status: paused\n"
            "---\n"
            "# Active App\n"
        )
        project = Project(
            path=str(proj_dir),
            name="active-app",
            descriptor_path=str(desc),
        )
        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=3,
        ):
            result = sync_descriptor(project)
        assert result.status == "updated"
        assert any("active" in c for c in result.changes)

    def test_unchanged(self, tmp_path: Path) -> None:
        proj_dir = tmp_path / "stable"
        proj_dir.mkdir()
        desc = tmp_path / "stable.md"
        desc.write_text(
            "---\n"
            "name: stable\n"
            f"path: {proj_dir}\n"
            "status: active\n"
            "stack:\n"
            "  - python\n"
            "---\n"
            "# Stable\n"
        )
        project = Project(
            path=str(proj_dir),
            name="stable",
            stack=["python"],
            descriptor_path=str(desc),
        )
        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=10,
        ):
            result = sync_descriptor(project)
        assert result.status == "unchanged"

    def test_skip_without_descriptor(self, tmp_path: Path) -> None:
        project = Project(path=str(tmp_path), name="no-desc", descriptor_path=None)
        result = sync_descriptor(project)
        assert result.status == "unchanged"


class TestSyncAllDescriptors:
    def test_batch(self, tmp_path: Path) -> None:
        p1 = tmp_path / "p1"
        p1.mkdir()
        desc1 = tmp_path / "p1.md"
        desc1.write_text(f"---\nname: p1\npath: {p1}\nstatus: active\n---\n")
        projects = [
            Project(path=str(p1), name="p1", descriptor_path=str(desc1)),
            Project(path=str(tmp_path / "p2"), name="p2", descriptor_path=None),
        ]
        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=10,
        ):
            results = sync_all_descriptors(projects)
        assert len(results) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_descriptor_syncer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement descriptor_syncer.py**

```python
# core/sync/descriptor_syncer.py
"""Phase 3c: Sync project descriptors with status and stack updates."""

import re
import subprocess
from pathlib import Path

import yaml

from core.sync.schema import DescriptorSyncResult, Project

_PAUSE_THRESHOLD_DAYS = 30
_REACTIVATE_THRESHOLD_DAYS = 7


def sync_descriptor(project: Project) -> DescriptorSyncResult:
    """Sync a single project descriptor."""
    if not project.descriptor_path:
        return DescriptorSyncResult(path=project.path, status="unchanged")
    try:
        return _do_sync(project)
    except Exception as e:
        return DescriptorSyncResult(
            path=project.path, status="error", error=str(e),
        )


def _do_sync(project: Project) -> DescriptorSyncResult:
    """Core sync logic for one descriptor."""
    desc_path = Path(project.descriptor_path)  # type: ignore[arg-type]
    if not desc_path.is_file():
        return DescriptorSyncResult(path=project.path, status="unchanged")

    text = desc_path.read_text()
    frontmatter, body = _split_frontmatter(text)
    if not frontmatter:
        return DescriptorSyncResult(path=project.path, status="unchanged")

    changes: list[str] = []
    project_path = Path(project.path)

    if not project_path.is_dir():
        frontmatter["status"] = "archived"
        changes.append("status: active -> archived (path not found)")
        _write_descriptor(desc_path, frontmatter, body)
        return DescriptorSyncResult(
            path=project.path, status="archived", changes=changes,
        )

    _check_stack(frontmatter, project.stack, changes)
    _check_activity(frontmatter, project_path, changes)

    if not changes:
        return DescriptorSyncResult(path=project.path, status="unchanged")

    _write_descriptor(desc_path, frontmatter, body)
    return DescriptorSyncResult(
        path=project.path, status="updated", changes=changes,
    )


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
        return fm, parts[2]
    except yaml.YAMLError:
        return {}, text


def _check_stack(
    frontmatter: dict,
    detected_stack: list[str],
    changes: list[str],
) -> None:
    """Update stack if detection differs from descriptor."""
    if not detected_stack:
        return
    current = frontmatter.get("stack", [])
    current_lower = {s.lower().split()[0] for s in (current or [])}
    detected_lower = set(detected_stack)
    if current_lower != detected_lower:
        frontmatter["stack"] = detected_stack
        changes.append(f"stack updated: {current} -> {detected_stack}")


def _check_activity(
    frontmatter: dict,
    project_path: Path,
    changes: list[str],
) -> None:
    """Check git activity and update status accordingly."""
    days = _get_last_commit_days(project_path)
    if days is None:
        return
    current_status = frontmatter.get("status", "active")
    if days > _PAUSE_THRESHOLD_DAYS and current_status == "active":
        frontmatter["status"] = "paused"
        changes.append(f"status: active -> paused ({days}d since last commit)")
    elif days < _REACTIVATE_THRESHOLD_DAYS and current_status == "paused":
        frontmatter["status"] = "active"
        changes.append(f"status: paused -> active ({days}d since last commit)")


def _get_last_commit_days(project_path: Path) -> int | None:
    """Get days since last git commit, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        from datetime import datetime, timezone

        date_str = result.stdout.strip()
        if not date_str:
            return None
        commit_date = datetime.fromisoformat(date_str)
        now = datetime.now(timezone.utc)
        return (now - commit_date).days
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _write_descriptor(desc_path: Path, frontmatter: dict, body: str) -> None:
    """Write updated descriptor preserving markdown body."""
    fm_text = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    desc_path.write_text(f"---\n{fm_text}---{body}")


def sync_all_descriptors(projects: list[Project]) -> list[DescriptorSyncResult]:
    """Sync descriptors for all projects."""
    return [sync_descriptor(project) for project in projects]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_descriptor_syncer.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/descriptor_syncer.py tests/python/test_sync_descriptor_syncer.py
git commit -m "feat(sync): add descriptor syncer with auto-pause and stack detection"
```

---

### Task 8: Reporter

**Files:**
- Create: `core/sync/reporter.py`
- Test: `tests/python/test_sync_reporter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_reporter.py
import json
import pytest
from pathlib import Path
from core.sync.schema import (
    McpSyncResult,
    SettingsSyncResult,
    DescriptorSyncResult,
    SkillSyncResult,
    SyncReport,
)
from core.sync.reporter import (
    build_report,
    write_sync_state,
    format_report,
)


class TestBuildReport:
    def test_empty_report(self) -> None:
        report = build_report("2.13.0", "2.14.0", [], [], [], [])
        assert report.previous_version == "2.13.0"
        assert report.current_version == "2.14.0"
        assert report.errors == []

    def test_report_with_results(self) -> None:
        mcp = [McpSyncResult(path="/p1", status="updated", mcps_added=["x"])]
        settings = [SettingsSyncResult(path="/p1", status="updated", servers_added=["x"])]
        desc = [DescriptorSyncResult(path="/p1", status="updated", changes=["stack updated"])]
        skills = [SkillSyncResult(skill_name="fovory", status="updated", features_added=["forge"])]
        report = build_report("2.13.0", "2.14.0", mcp, settings, desc, skills)
        assert len(report.mcp_results) == 1
        assert len(report.skill_results) == 1

    def test_report_collects_errors(self) -> None:
        mcp = [McpSyncResult(path="/p1", status="error", error="parse fail")]
        report = build_report("2.13.0", "2.14.0", mcp, [], [], [])
        assert len(report.errors) == 1
        assert "parse fail" in report.errors[0]


class TestWriteSyncState:
    def test_write_state(self, tmp_path: Path) -> None:
        state_file = tmp_path / "sync-state.json"
        report = SyncReport(
            previous_version="2.13.0",
            current_version="2.14.0",
            mcp_results=[McpSyncResult(path="/p1", status="updated")],
            settings_results=[SettingsSyncResult(path="/p1", status="updated")],
        )
        write_sync_state(state_file, report)
        data = json.loads(state_file.read_text())
        assert data["version"] == "2.14.0"
        assert data["projects_synced"] == 1
        assert "last_sync" in data


class TestFormatReport:
    def test_format_with_changes(self) -> None:
        report = SyncReport(
            previous_version="2.13.0",
            current_version="2.14.0",
            mcp_results=[
                McpSyncResult(path="/p1", status="updated", mcps_added=["laravel-boost"]),
                McpSyncResult(path="/p2", status="unchanged"),
            ],
            settings_results=[
                SettingsSyncResult(path="/p1", status="updated"),
                SettingsSyncResult(path="/p2", status="unchanged"),
            ],
            descriptor_results=[
                DescriptorSyncResult(path="/p1", status="updated", changes=["stack updated"]),
            ],
            skill_results=[
                SkillSyncResult(skill_name="fovory", status="updated", features_added=["forge"]),
            ],
        )
        text = format_report(report)
        assert "v2.13.0" in text
        assert "v2.14.0" in text
        assert "MCPs" in text
        assert "Errors: 0" in text

    def test_format_empty_report(self) -> None:
        report = SyncReport(
            previous_version="2.14.0",
            current_version="2.14.0",
        )
        text = format_report(report)
        assert "v2.14.0" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_reporter.py -v`
Expected: FAIL

- [ ] **Step 3: Implement reporter.py**

```python
# core/sync/reporter.py
"""Phase 5: Build sync report and write state file."""

import json
from datetime import datetime, timezone
from pathlib import Path

from core.sync.schema import (
    DescriptorSyncResult,
    McpSyncResult,
    SettingsSyncResult,
    SkillSyncResult,
    SyncReport,
)

_SEPARATOR = "=" * 55


def build_report(
    previous_version: str,
    current_version: str,
    mcp_results: list[McpSyncResult],
    settings_results: list[SettingsSyncResult],
    descriptor_results: list[DescriptorSyncResult],
    skill_results: list[SkillSyncResult],
) -> SyncReport:
    """Aggregate all phase results into a single report."""
    errors = _collect_errors(mcp_results, settings_results, descriptor_results, skill_results)
    return SyncReport(
        previous_version=previous_version,
        current_version=current_version,
        mcp_results=mcp_results,
        settings_results=settings_results,
        descriptor_results=descriptor_results,
        skill_results=skill_results,
        errors=errors,
    )


def _collect_errors(
    mcp: list[McpSyncResult],
    settings: list[SettingsSyncResult],
    desc: list[DescriptorSyncResult],
    skills: list[SkillSyncResult],
) -> list[str]:
    """Collect error messages from all results."""
    errors: list[str] = []
    for r in mcp:
        if r.error:
            errors.append(f"MCP [{r.path}]: {r.error}")
    for r in settings:
        if r.error:
            errors.append(f"Settings [{r.path}]: {r.error}")
    for r in desc:
        if r.error:
            errors.append(f"Descriptor [{r.path}]: {r.error}")
    for r in skills:
        if r.error:
            errors.append(f"Skill [{r.skill_name}]: {r.error}")
    return errors


def write_sync_state(state_file: Path, report: SyncReport) -> None:
    """Write sync state JSON after successful sync."""
    project_paths = {r.path for r in report.mcp_results}
    state = {
        "version": report.current_version,
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "projects_synced": len(project_paths),
        "skills_synced": len(report.skill_results),
        "errors": report.errors,
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2) + "\n")


def format_report(report: SyncReport) -> str:
    """Format sync report for terminal display."""
    lines = [
        _SEPARATOR,
        f"  ArkaOS Sync Complete — v{report.previous_version} → v{report.current_version}",
        _SEPARATOR,
        "",
    ]
    lines.append(_format_phase_line("MCPs", report.mcp_results))
    lines.append(_format_phase_line("Settings", report.settings_results))
    lines.append(_format_phase_line("Descriptors", report.descriptor_results))
    lines.append(_format_skill_line(report.skill_results))
    lines.append("")
    lines.extend(_format_key_changes(report))
    lines.append(f"  Errors: {len(report.errors)}")
    if report.errors:
        for err in report.errors:
            lines.append(f"    - {err}")
    lines.append(_SEPARATOR)
    return "\n".join(lines)


def _format_phase_line(label: str, results: list) -> str:
    """Format a summary line for a sync phase."""
    total = len(results)
    updated = sum(1 for r in results if r.status in ("updated", "created"))
    unchanged = sum(1 for r in results if r.status == "unchanged")
    return f"  {label}:{' ' * (14 - len(label))}{total} synced ({updated} updated, {unchanged} unchanged)"


def _format_skill_line(results: list[SkillSyncResult]) -> str:
    """Format skill sync summary line."""
    total = len(results)
    updated = sum(1 for r in results if r.status == "updated")
    unchanged = sum(1 for r in results if r.status == "unchanged")
    return f"  Skills:       {total} ecosystems synced ({updated} updated, {unchanged} unchanged)"


def _format_key_changes(report: SyncReport) -> list[str]:
    """Extract key changes for the report."""
    lines: list[str] = []
    _add_mcp_changes(report.mcp_results, lines)
    _add_descriptor_changes(report.descriptor_results, lines)
    _add_skill_changes(report.skill_results, lines)
    if lines:
        lines.insert(0, "  Key changes:")
        lines.append("")
    return lines


def _add_mcp_changes(results: list[McpSyncResult], lines: list[str]) -> None:
    """Add MCP change details to report lines."""
    added: dict[str, list[str]] = {}
    for r in results:
        for mcp in r.mcps_added:
            added.setdefault(mcp, []).append(Path(r.path).name)
    for mcp, projects in added.items():
        lines.append(f"  - MCP '{mcp}' added to: {', '.join(projects)}")


def _add_descriptor_changes(
    results: list[DescriptorSyncResult],
    lines: list[str],
) -> None:
    """Add descriptor change details to report lines."""
    paused = [Path(r.path).name for r in results if r.status == "updated" and any("paused" in c for c in r.changes)]
    archived = [Path(r.path).name for r in results if r.status == "archived"]
    if paused:
        lines.append(f"  - Auto-paused (>30d inactive): {', '.join(paused)}")
    if archived:
        lines.append(f"  - Archived (path not found): {', '.join(archived)}")


def _add_skill_changes(
    results: list[SkillSyncResult],
    lines: list[str],
) -> None:
    """Add skill change details to report lines."""
    features: dict[str, list[str]] = {}
    for r in results:
        for feat in r.features_added:
            features.setdefault(feat, []).append(r.skill_name)
    for feat, skills in features.items():
        lines.append(f"  - '{feat}' added to: {', '.join(skills)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_reporter.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/sync/reporter.py tests/python/test_sync_reporter.py
git commit -m "feat(sync): add reporter with formatted output and state persistence"
```

---

### Task 9: Engine Orchestrator

**Files:**
- Create: `core/sync/engine.py`
- Modify: `core/sync/__init__.py`
- Test: `tests/python/test_sync_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_sync_engine.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from core.sync.engine import run_sync
from core.sync.schema import SyncReport


class TestRunSync:
    def _setup_env(self, tmp_path: Path) -> dict:
        """Create a minimal sync environment for testing."""
        arkaos_home = tmp_path / ".arkaos"
        arkaos_home.mkdir()
        (arkaos_home / "sync-state.json").write_text(json.dumps({
            "version": "pending-sync",
            "last_sync": "",
            "projects_synced": 0,
            "skills_synced": 0,
            "errors": [],
        }))
        (arkaos_home / ".repo-path").write_text(str(tmp_path / "repo"))

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("2.14.0")

        features_dir = repo / "core" / "sync" / "features"
        features_dir.mkdir(parents=True)
        (features_dir / "forge.yaml").write_text(
            "name: forge\n"
            'added_in: "2.14.0"\n'
            "mandatory: true\n"
            "section_title: Forge\n"
            "detection_pattern: arka-forge\n"
            "content: |\n"
            "  ## Forge\n"
        )

        skills_dir = tmp_path / "skills"
        (skills_dir / "arka" / "mcps").mkdir(parents=True)
        (skills_dir / "arka" / "mcps" / "registry.json").write_text(json.dumps({
            "mcpServers": {
                "arka-prompts": {
                    "command": "uv",
                    "args": ["run", "server.py"],
                    "category": "base",
                },
            }
        }))
        (skills_dir / "arka" / "projects").mkdir()
        (skills_dir / "arka" / "knowledge").mkdir()
        (skills_dir / "arka" / "knowledge" / "ecosystems.json").write_text(
            json.dumps({"ecosystems": {}})
        )

        proj = tmp_path / "projects" / "my-app"
        proj.mkdir(parents=True)
        (proj / ".mcp.json").write_text("{}")

        (arkaos_home / "profile.json").write_text(json.dumps({
            "projectsDir": str(tmp_path / "projects"),
        }))

        return {
            "arkaos_home": str(arkaos_home),
            "skills_dir": str(skills_dir),
            "home_path": str(tmp_path),
        }

    def test_full_sync(self, tmp_path: Path) -> None:
        env = self._setup_env(tmp_path)
        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=10,
        ):
            report = run_sync(
                arkaos_home=Path(env["arkaos_home"]),
                skills_dir=Path(env["skills_dir"]),
                home_path=env["home_path"],
            )
        assert isinstance(report, SyncReport)
        assert report.current_version == "2.14.0"
        assert len(report.mcp_results) >= 1

    def test_sync_writes_state(self, tmp_path: Path) -> None:
        env = self._setup_env(tmp_path)
        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=10,
        ):
            run_sync(
                arkaos_home=Path(env["arkaos_home"]),
                skills_dir=Path(env["skills_dir"]),
                home_path=env["home_path"],
            )
        state = json.loads(
            (Path(env["arkaos_home"]) / "sync-state.json").read_text()
        )
        assert state["version"] == "2.14.0"
        assert state["projects_synced"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement engine.py**

```python
# core/sync/engine.py
"""Sync engine orchestrator — runs all deterministic phases."""

import json
import re
import sys
from pathlib import Path

from core.sync.descriptor_syncer import sync_all_descriptors
from core.sync.discovery import discover_all_projects
from core.sync.manifest import build_manifest
from core.sync.mcp_syncer import sync_all_mcps
from core.sync.reporter import build_report, format_report, write_sync_state
from core.sync.schema import SyncReport
from core.sync.settings_syncer import sync_all_settings


def run_sync(
    arkaos_home: Path,
    skills_dir: Path,
    home_path: str,
) -> SyncReport:
    """Run the full deterministic sync (phases 1-3 + 5)."""
    previous_version = _read_previous_version(arkaos_home)
    current_version = _read_current_version(arkaos_home)
    features_dir = _resolve_features_dir(arkaos_home)

    manifest = build_manifest(previous_version, current_version, features_dir)

    projects = _discover_projects(arkaos_home, skills_dir)

    registry_path = skills_dir / "arka" / "mcps" / "registry.json"
    mcp_results = sync_all_mcps(projects, registry_path, home_path)

    settings_results = sync_all_settings(mcp_results)

    descriptor_results = sync_all_descriptors(projects)

    report = build_report(
        previous_version,
        current_version,
        mcp_results,
        settings_results,
        descriptor_results,
        skill_results=[],
    )

    state_file = arkaos_home / "sync-state.json"
    write_sync_state(state_file, report)

    return report


def _read_previous_version(arkaos_home: Path) -> str:
    """Read last synced version from sync-state.json."""
    state_file = arkaos_home / "sync-state.json"
    if not state_file.is_file():
        return "pending-sync"
    try:
        data = json.loads(state_file.read_text())
        return data.get("version", "pending-sync")
    except (json.JSONDecodeError, OSError):
        return "pending-sync"


def _read_current_version(arkaos_home: Path) -> str:
    """Read current ArkaOS version from the repo."""
    repo_path = _read_repo_path(arkaos_home)
    if not repo_path:
        return "unknown"
    version_file = repo_path / "VERSION"
    if version_file.is_file():
        return version_file.read_text().strip()
    return "unknown"


def _read_repo_path(arkaos_home: Path) -> Path | None:
    """Read ArkaOS repo path from .repo-path file."""
    repo_file = arkaos_home / ".repo-path"
    if not repo_file.is_file():
        return None
    path_str = repo_file.read_text().strip()
    repo = Path(path_str)
    return repo if repo.is_dir() else None


def _resolve_features_dir(arkaos_home: Path) -> Path:
    """Find the features directory in the ArkaOS repo."""
    repo_path = _read_repo_path(arkaos_home)
    if repo_path:
        return repo_path / "core" / "sync" / "features"
    return arkaos_home / "config" / "sync" / "features"


def _parse_scan_dirs(projects_dir_str: str) -> list[Path]:
    """Parse projectsDir string into actual directory paths."""
    dirs: list[Path] = []
    for segment in re.split(r",\s*", projects_dir_str):
        path_match = re.match(r"(/[^\s]+)", segment.strip())
        if path_match:
            p = Path(path_match.group(1))
            if p.is_dir():
                dirs.append(p)
    return dirs


def _discover_projects(arkaos_home: Path, skills_dir: Path):
    """Discover all projects from 3 sources."""
    descriptor_dir = skills_dir / "arka" / "projects"
    ecosystems_file = skills_dir / "arka" / "knowledge" / "ecosystems.json"

    profile_file = arkaos_home / "profile.json"
    scan_dirs: list[Path] = []
    if profile_file.is_file():
        try:
            profile = json.loads(profile_file.read_text())
            scan_dirs = _parse_scan_dirs(profile.get("projectsDir", ""))
        except (json.JSONDecodeError, OSError):
            pass

    return discover_all_projects(descriptor_dir, scan_dirs, ecosystems_file)


def main() -> None:
    """CLI entry point for sync engine."""
    import argparse

    parser = argparse.ArgumentParser(description="ArkaOS Sync Engine")
    parser.add_argument("--home", required=True, help="ArkaOS home directory")
    parser.add_argument("--skills", required=True, help="Skills directory")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    args = parser.parse_args()

    home_path = str(Path.home())
    report = run_sync(
        arkaos_home=Path(args.home),
        skills_dir=Path(args.skills),
        home_path=home_path,
    )

    if args.output == "json":
        print(report.model_dump_json(indent=2))
    else:
        print(format_report(report))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update __init__.py with engine export**

```python
# core/sync/__init__.py
"""ArkaOS Sync Engine — Hybrid sync for /arka update."""

from core.sync.schema import (
    ChangeManifest,
    DescriptorSyncResult,
    FeatureSpec,
    McpSyncResult,
    Project,
    SettingsSyncResult,
    SkillSyncResult,
    SyncReport,
)
from core.sync.engine import run_sync

__all__ = [
    "ChangeManifest",
    "DescriptorSyncResult",
    "FeatureSpec",
    "McpSyncResult",
    "Project",
    "SettingsSyncResult",
    "SkillSyncResult",
    "SyncReport",
    "run_sync",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_engine.py -v`
Expected: All 2 tests PASS

- [ ] **Step 6: Run full sync test suite**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_*.py -v`
Expected: All tests across all 7 test files PASS

- [ ] **Step 7: Commit**

```bash
git add core/sync/engine.py core/sync/__init__.py tests/python/test_sync_engine.py
git commit -m "feat(sync): add engine orchestrator with CLI entry point"
```

---

### Task 10: Update SKILL.md for /arka update

**Files:**
- Modify: `departments/ops/skills/update/SKILL.md` (or wherever the arka-update skill lives in the repo)

- [ ] **Step 1: Find the arka-update skill source file in the repo**

Run: `find /Users/andreagroferreira/AIProjects/arka-os/departments -name "SKILL.md" -path "*update*" 2>/dev/null; ls /Users/andreagroferreira/AIProjects/arka-os/departments/*/skills/*/SKILL.md 2>/dev/null | grep -i update`

This locates the repo-side source of the skill that gets deployed to `~/.claude/skills/arka-update/SKILL.md`.

- [ ] **Step 2: Rewrite the SKILL.md to use the Python engine**

The SKILL.md must instruct Claude Code to:
1. Call `python -m core.sync.engine --home ~/.arkaos --skills ~/.claude/skills --output json`
2. Parse the JSON output
3. If the manifest contains ecosystem skills to update → dispatch 1 subagent with feature registry + skill list
4. Display the formatted report

The key change: replace the 4-subagent pure-AI approach with 1 Python call + 1 AI subagent for skill text updates only.

Write the updated SKILL.md with clear instructions for:
- Phase 1-3+5: `python -m core.sync.engine` (deterministic)
- Phase 4: AI subagent reads `core/sync/features/*.yaml`, checks each `~/.claude/skills/arka-{ecosystem}/SKILL.md` for missing `detection_pattern`, injects `content` block where missing

- [ ] **Step 3: Commit**

```bash
git add departments/*/skills/*/SKILL.md
git commit -m "feat(sync): rewrite /arka update SKILL.md to use hybrid sync engine"
```

---

### Task 11: Installer Integration

**Files:**
- Modify: `installer/update.js`

- [ ] **Step 1: Find the skills deployment section in update.js**

Read `installer/update.js` and find the section that copies skills and MCP files (around lines 254-381 based on earlier research).

- [ ] **Step 2: Add feature registry copy step**

After the existing MCP infrastructure copy, add:
```javascript
// Copy feature registry for sync engine
const featuresSource = path.join(ARKAOS_ROOT, 'core', 'sync', 'features');
const featuresDest = path.join(ARKAOS_HOME, 'config', 'sync', 'features');
if (fs.existsSync(featuresSource)) {
    fs.mkdirSync(featuresDest, { recursive: true });
    const files = fs.readdirSync(featuresSource).filter(f => f.endsWith('.yaml'));
    for (const file of files) {
        fs.copyFileSync(path.join(featuresSource, file), path.join(featuresDest, file));
    }
    log(`  ✓ Feature registry: ${files.length} features copied`);
}
```

- [ ] **Step 3: Run existing installer tests (if any)**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && ls tests/ | head -20`
Check for installer/node tests and run them if they exist.

- [ ] **Step 4: Commit**

```bash
git add installer/update.js
git commit -m "feat(sync): add feature registry copy to installer update flow"
```

---

### Task 12: Full Integration Test

**Files:**
- Test: `tests/python/test_sync_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/python/test_sync_integration.py
"""End-to-end integration test for the sync engine."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
from core.sync.engine import run_sync
from core.sync.reporter import format_report


class TestFullSyncIntegration:
    def _build_environment(self, tmp_path: Path) -> tuple[Path, Path, str]:
        """Build a complete mock environment with multiple projects."""
        home = tmp_path / "home"
        arkaos_home = home / ".arkaos"
        arkaos_home.mkdir(parents=True)

        (arkaos_home / "sync-state.json").write_text(json.dumps({
            "version": "pending-sync",
            "last_sync": "",
            "projects_synced": 0,
            "skills_synced": 0,
            "errors": [],
        }))

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "VERSION").write_text("2.14.0")
        (arkaos_home / ".repo-path").write_text(str(repo))

        features_dir = repo / "core" / "sync" / "features"
        features_dir.mkdir(parents=True)
        (features_dir / "forge.yaml").write_text(
            "name: forge\n"
            'added_in: "2.14.0"\n'
            "mandatory: true\n"
            "section_title: Forge\n"
            "detection_pattern: arka-forge\n"
            "content: |\n"
            "  ## Forge content\n"
        )

        skills_dir = home / ".claude" / "skills"
        (skills_dir / "arka" / "mcps").mkdir(parents=True)
        (skills_dir / "arka" / "mcps" / "registry.json").write_text(json.dumps({
            "mcpServers": {
                "arka-prompts": {
                    "command": "uv",
                    "args": ["run", "server.py"],
                    "category": "base",
                },
                "context7": {
                    "command": "npx",
                    "args": ["-y", "@upstash/context7-mcp"],
                    "category": "base",
                },
                "laravel-boost": {
                    "command": "npx",
                    "args": ["laravel-boost"],
                    "category": "laravel",
                },
            }
        }))

        (skills_dir / "arka" / "knowledge").mkdir()
        (skills_dir / "arka" / "knowledge" / "ecosystems.json").write_text(
            json.dumps({"ecosystems": {}})
        )
        (skills_dir / "arka" / "projects").mkdir()

        herd = tmp_path / "herd"
        herd.mkdir()

        laravel_proj = herd / "crm-app"
        laravel_proj.mkdir()
        (laravel_proj / "composer.json").write_text(
            json.dumps({"require": {"laravel/framework": "^11.0"}})
        )
        (laravel_proj / ".mcp.json").write_text(json.dumps({
            "mcpServers": {
                "arka-prompts": {"command": "old", "args": []},
                "my-custom": {"command": "custom", "args": []},
            }
        }))

        nuxt_proj = herd / "web-app"
        nuxt_proj.mkdir()
        (nuxt_proj / "package.json").write_text(
            json.dumps({"dependencies": {"nuxt": "^3.0", "vue": "^3.0"}})
        )

        (arkaos_home / "profile.json").write_text(json.dumps({
            "projectsDir": str(herd),
        }))

        (skills_dir / "arka" / "projects" / "crm-app.md").write_text(
            f"---\nname: crm-app\npath: {laravel_proj}\n"
            "ecosystem: rockport\nstatus: active\n"
            "stack:\n  - Laravel 11\n---\n# CRM App\n"
        )

        return arkaos_home, skills_dir, str(home)

    def test_full_first_sync(self, tmp_path: Path) -> None:
        arkaos_home, skills_dir, home_path = self._build_environment(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=5,
        ):
            report = run_sync(arkaos_home, skills_dir, home_path)

        assert report.current_version == "2.14.0"
        assert len(report.mcp_results) >= 2

        laravel_result = next(
            r for r in report.mcp_results if "crm-app" in r.path
        )
        assert "laravel-boost" in laravel_result.final_mcp_list
        assert "my-custom" in laravel_result.mcps_preserved
        assert "arka-prompts" in laravel_result.final_mcp_list

        state = json.loads((arkaos_home / "sync-state.json").read_text())
        assert state["version"] == "2.14.0"
        assert state["projects_synced"] >= 2

    def test_report_output(self, tmp_path: Path) -> None:
        arkaos_home, skills_dir, home_path = self._build_environment(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days",
            return_value=5,
        ):
            report = run_sync(arkaos_home, skills_dir, home_path)

        text = format_report(report)
        assert "v2.14.0" in text
        assert "MCPs" in text
        assert "Errors: 0" in text
```

- [ ] **Step 2: Run integration test**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/python/test_sync_integration.py -v`
Expected: All 2 tests PASS

- [ ] **Step 3: Run entire test suite to check for regressions**

Run: `cd /Users/andreagroferreira/AIProjects/arka-os && python -m pytest tests/ --tb=short -q`
Expected: All existing tests + all new sync tests PASS (2100+ total)

- [ ] **Step 4: Commit**

```bash
git add tests/python/test_sync_integration.py
git commit -m "test(sync): add end-to-end integration test for full sync flow"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | Schema models (Pydantic v2) | 11 |
| 2 | Feature registry YAML files | - |
| 3 | Change manifest builder | 7 |
| 4 | Project discovery + stack detection | 14 |
| 5 | MCP syncer (registry merge) | 9 |
| 6 | Settings syncer (permission preservation) | 5 |
| 7 | Descriptor syncer (auto-pause, stack) | 7 |
| 8 | Reporter (formatted output, state write) | 5 |
| 9 | Engine orchestrator + CLI | 2 |
| 10 | SKILL.md rewrite for hybrid approach | - |
| 11 | Installer integration (feature copy) | - |
| 12 | Full integration test | 2 |
| **Total** | **12 tasks** | **~62 tests** |
