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


def test_sync_rejects_path_traversal_in_allowlist(
    fake_core: Path, project: Project, tmp_path: Path
) -> None:
    # Allowlist entry that tries to escape the departments dir
    (fake_core / "config" / "agent-allowlists" / "laravel.yaml").write_text(
        "stack: laravel\nbaseline:\n  - ../../../etc/passwd\n  - backend-dev\n"
    )

    # Snapshot sensitive location outside the project
    outside = tmp_path / "outside-sentinel"
    outside.write_text("untouched")

    result = sync_project_agents(project)

    # The bogus entry should be reported as errored, not written anywhere.
    assert "../../../etc/passwd" in result.agents_errored
    # backend-dev should still be added normally.
    assert "backend-dev" in result.agents_added
    # Sensitive location must not be altered.
    assert outside.read_text() == "untouched"
