"""Tests for core.sync.descriptor_syncer — project descriptor sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from core.sync.descriptor_syncer import sync_all_descriptors, sync_descriptor
from core.sync.schema import Project

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DESCRIPTOR_TEMPLATE = """\
---
name: {name}
path: {path}
status: {status}
stack:
  - Laravel 11
---
# {name}
Content here...
"""


def _write_descriptor(tmp_path: Path, name: str, project_path: str, status: str = "active") -> Path:
    desc_file = tmp_path / f"{name}.md"
    desc_file.write_text(_DESCRIPTOR_TEMPLATE.format(
        name=name, path=project_path, status=status
    ))
    return desc_file


def _make_project(
    tmp_path: Path,
    name: str = "test-app",
    stack: list[str] | None = None,
    create_dir: bool = True,
    with_descriptor: bool = True,
    status: str = "active",
) -> Project:
    proj_dir = tmp_path / name
    if create_dir:
        proj_dir.mkdir(exist_ok=True)

    desc_path = None
    if with_descriptor:
        desc_path = str(_write_descriptor(tmp_path, name, str(proj_dir), status))

    return Project(
        path=str(proj_dir),
        name=name,
        stack=stack or [],
        descriptor_path=desc_path,
    )


# ---------------------------------------------------------------------------
# TestSyncDescriptor
# ---------------------------------------------------------------------------


class TestSyncDescriptor:
    def test_archive_missing_path(self, tmp_path: Path) -> None:
        """When the project path doesn't exist, status should be set to archived."""
        project = _make_project(tmp_path, name="gone-app", create_dir=False)

        result = sync_descriptor(project)

        assert result.status == "updated"
        assert any("archived" in c for c in result.changes)

        content = Path(project.descriptor_path).read_text()
        assert "status: archived" in content

    def test_update_stack(self, tmp_path: Path) -> None:
        """When detected stack differs from frontmatter, stack should be updated."""
        project = _make_project(
            tmp_path, name="nuxt-app", stack=["nuxt", "vue"], create_dir=True
        )

        result = sync_descriptor(project)

        assert result.status == "updated"
        assert any("stack" in c for c in result.changes)

        content = Path(project.descriptor_path).read_text()
        assert "nuxt" in content

    def test_auto_pause_inactive(self, tmp_path: Path) -> None:
        """When last commit was 45 days ago and status is active, should pause."""
        project = _make_project(tmp_path, name="stale-app", stack=[], status="active")

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=45
        ):
            result = sync_descriptor(project)

        assert result.status == "updated"
        assert any("paused" in c for c in result.changes)

        content = Path(project.descriptor_path).read_text()
        assert "status: paused" in content

    def test_auto_reactivate(self, tmp_path: Path) -> None:
        """When last commit was 3 days ago and status is paused, should reactivate."""
        project = _make_project(tmp_path, name="revived-app", stack=[], status="paused")

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=3
        ):
            result = sync_descriptor(project)

        assert result.status == "updated"
        assert any("active" in c for c in result.changes)

        content = Path(project.descriptor_path).read_text()
        assert "status: active" in content

    def test_unchanged(self, tmp_path: Path) -> None:
        """When stack matches and activity is within normal range, status is unchanged."""
        project = _make_project(
            tmp_path, name="steady-app", stack=["laravel"], status="active"
        )

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=15
        ):
            result = sync_descriptor(project)

        assert result.status == "unchanged"
        assert result.changes == []

    def test_skip_without_descriptor(self, tmp_path: Path) -> None:
        """When descriptor_path is None, should return unchanged immediately."""
        project = _make_project(
            tmp_path, name="no-desc-app", with_descriptor=False
        )
        assert project.descriptor_path is None

        result = sync_descriptor(project)

        assert result.status == "unchanged"
        assert result.changes == []

    def test_body_preserved_after_update(self, tmp_path: Path) -> None:
        """The markdown body below the frontmatter must be preserved on write."""
        project = _make_project(tmp_path, name="body-app", stack=[], status="active")

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=45
        ):
            sync_descriptor(project)

        content = Path(project.descriptor_path).read_text()
        assert "# body-app" in content
        assert "Content here..." in content


# ---------------------------------------------------------------------------
# TestSyncAllDescriptors
# ---------------------------------------------------------------------------


class TestSyncAllDescriptors:
    def test_batch(self, tmp_path: Path) -> None:
        """sync_all_descriptors processes each project and returns one result each."""
        p1 = _make_project(tmp_path, name="app-one", stack=[], status="active")
        p2 = _make_project(tmp_path, name="app-two", stack=[], status="paused")

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=15
        ):
            results = sync_all_descriptors([p1, p2])

        assert len(results) == 2
        paths = {r.path for r in results}
        assert p1.path in paths
        assert p2.path in paths

    def test_empty_list_returns_empty(self) -> None:
        """Empty project list returns an empty result list."""
        results = sync_all_descriptors([])
        assert results == []
