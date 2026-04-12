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
