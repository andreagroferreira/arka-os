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
    (core / "config" / "standards" / "stack-rules").mkdir(parents=True)
    (core / "config" / "hooks").mkdir(parents=True)
    (core / "config").mkdir(parents=True, exist_ok=True)

    (core / "config" / "user-claude.md").write_text("# ArkaOS CLAUDE Template\n")
    (core / "config" / "standards" / "stack-rules" / "python.md").write_text(
        '---\npaths:\n  - "**/*.py"\n---\n\n## Python Rules\n'
    )
    (core / "config" / "standards" / "stack-rules" / "node.md").write_text(
        '---\npaths:\n  - "**/*.js"\n---\n\n## Node Rules\n'
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
    # Stack conventions deploy as path-scoped rules, not CLAUDE.md text.
    assert "Python Rules" not in text
    assert "CLAUDE.md" in result.artefacts_updated


def test_sync_deploys_stack_rule_with_frontmatter(
    core_repo: Path, project: Project
) -> None:
    result = sync_project_content(project)

    rule = Path(project.path) / ".claude" / "rules" / "arkaos-stack-python.md"
    assert rule.exists()
    text = rule.read_text()
    assert text.startswith("---\npaths:")
    assert "## Python Rules" in text
    assert "rules/arkaos-stack-python.md" in result.artefacts_updated


def test_sync_stack_alias_and_casefold(core_repo: Path, tmp_path: Path) -> None:
    proj_dir = tmp_path / "alias-project"
    (proj_dir / ".claude").mkdir(parents=True)
    project = Project(
        path=str(proj_dir), name="alias-project",
        stack=["javascript", "Python"],
    )

    sync_project_content(project)

    rules_dir = proj_dir / ".claude" / "rules"
    assert (rules_dir / "arkaos-stack-node.md").exists()
    assert (rules_dir / "arkaos-stack-python.md").exists()


def test_sync_stack_dedupe_when_aliases_collide(
    core_repo: Path, tmp_path: Path
) -> None:
    proj_dir = tmp_path / "dedupe-project"
    (proj_dir / ".claude").mkdir(parents=True)
    project = Project(
        path=str(proj_dir), name="dedupe-project",
        stack=["javascript", "typescript", "node"],
    )

    result = sync_project_content(project)

    deployed = [a for a in result.artefacts_updated if "arkaos-stack-" in a]
    assert deployed == ["rules/arkaos-stack-node.md"]


def test_sync_removes_stale_stack_rules_on_stack_change(
    core_repo: Path, tmp_path: Path
) -> None:
    proj_dir = tmp_path / "churn-project"
    (proj_dir / ".claude").mkdir(parents=True)
    node_proj = Project(
        path=str(proj_dir), name="churn-project", stack=["node"],
    )
    sync_project_content(node_proj)
    assert (proj_dir / ".claude" / "rules" / "arkaos-stack-node.md").exists()

    py_proj = Project(
        path=str(proj_dir), name="churn-project", stack=["python"],
    )
    sync_project_content(py_proj)

    rules_dir = proj_dir / ".claude" / "rules"
    assert not (rules_dir / "arkaos-stack-node.md").exists()
    assert (rules_dir / "arkaos-stack-python.md").exists()


def test_sync_unknown_stack_deploys_nothing(
    core_repo: Path, tmp_path: Path
) -> None:
    proj_dir = tmp_path / "exotic-project"
    (proj_dir / ".claude").mkdir(parents=True)
    project = Project(
        path=str(proj_dir), name="exotic-project", stack=["terraform"],
    )

    sync_project_content(project)

    rules_dir = proj_dir / ".claude" / "rules"
    assert not list(rules_dir.glob("arkaos-stack-*.md"))


def test_sync_never_deletes_non_namespaced_rules(
    core_repo: Path, project: Project
) -> None:
    rules_dir = Path(project.path) / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    user_rule = rules_dir / "my-own-rule.md"
    user_rule.write_text("# Mine\n")

    sync_project_content(project)

    assert user_rule.exists()
    assert user_rule.read_text() == "# Mine\n"


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
