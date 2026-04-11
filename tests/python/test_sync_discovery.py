"""Tests for core.sync.discovery — project discovery with stack detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.sync.discovery import (
    detect_stack,
    discover_all_projects,
    discover_from_descriptors,
    discover_from_ecosystems,
    discover_from_filesystem,
)
from core.sync.schema import Project


# --- TestDetectStack ---

class TestDetectStack:
    def test_laravel_from_composer(self, tmp_path: Path) -> None:
        composer = {"require": {"laravel/framework": "^11.0", "php": "^8.2"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        stack = detect_stack(tmp_path)
        assert "php" in stack
        assert "laravel" in stack

    def test_nuxt_from_package_json(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"nuxt": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_stack(tmp_path)
        assert "nuxt" in stack
        assert "vue" in stack
        assert "javascript" in stack

    def test_react_and_next_from_package_json(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"next": "^14.0.0", "react": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_stack(tmp_path)
        assert "next" in stack
        assert "react" in stack
        assert "javascript" in stack

    def test_python_from_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "app"\n')
        stack = detect_stack(tmp_path)
        assert "python" in stack

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        stack = detect_stack(tmp_path)
        assert stack == []

    def test_vue_without_nuxt(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        stack = detect_stack(tmp_path)
        assert "vue" in stack
        assert "nuxt" not in stack
        assert "javascript" in stack


# --- TestDiscoverFromDescriptors ---

class TestDiscoverFromDescriptors:
    def test_single_file_descriptor(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "my-app"
        project_dir.mkdir()
        descriptor_dir = tmp_path / "descriptors"
        descriptor_dir.mkdir()
        desc = descriptor_dir / "my-app.md"
        desc.write_text(
            f"---\nname: my-app\npath: {project_dir}\necosystem: client_retail\nstatus: active\n---\n# My App\n"
        )
        projects = discover_from_descriptors(descriptor_dir)
        assert len(projects) == 1
        assert projects[0].name == "my-app"
        assert projects[0].ecosystem == "client_retail"
        assert projects[0].path == str(project_dir)

    def test_skip_nonexistent_path(self, tmp_path: Path) -> None:
        descriptor_dir = tmp_path / "descriptors"
        descriptor_dir.mkdir()
        desc = descriptor_dir / "missing.md"
        desc.write_text("---\nname: missing\npath: /does/not/exist/anywhere\n---\n")
        projects = discover_from_descriptors(descriptor_dir)
        assert projects == []

    def test_subdirectory_with_project_md(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "sub-app"
        project_dir.mkdir()
        descriptor_dir = tmp_path / "descriptors"
        descriptor_dir.mkdir()
        subdir = descriptor_dir / "sub-app"
        subdir.mkdir()
        project_md = subdir / "PROJECT.md"
        project_md.write_text(
            f"---\nname: sub-app\npath: {project_dir}\necosystem: client_commerce\n---\n# Sub App\n"
        )
        projects = discover_from_descriptors(descriptor_dir)
        assert len(projects) == 1
        assert projects[0].name == "sub-app"
        assert projects[0].ecosystem == "client_commerce"

    def test_descriptor_path_is_set(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        descriptor_dir = tmp_path / "desc"
        descriptor_dir.mkdir()
        desc = descriptor_dir / "proj.md"
        desc.write_text(f"---\nname: proj\npath: {project_dir}\n---\n")
        projects = discover_from_descriptors(descriptor_dir)
        assert projects[0].descriptor_path == str(desc)

    def test_nonexistent_descriptor_dir_returns_empty(self, tmp_path: Path) -> None:
        projects = discover_from_descriptors(tmp_path / "no-such-dir")
        assert projects == []


# --- TestDiscoverFromFilesystem ---

class TestDiscoverFromFilesystem:
    def test_find_project_with_mcp_json(self, tmp_path: Path) -> None:
        proj = tmp_path / "mcp-project"
        proj.mkdir()
        (proj / ".mcp.json").write_text("{}")
        projects = discover_from_filesystem([tmp_path])
        names = [p.name for p in projects]
        assert "mcp-project" in names
        found = next(p for p in projects if p.name == "mcp-project")
        assert found.has_mcp_json is True

    def test_find_project_with_claude_dir(self, tmp_path: Path) -> None:
        proj = tmp_path / "claude-project"
        proj.mkdir()
        (proj / ".claude").mkdir()
        projects = discover_from_filesystem([tmp_path])
        names = [p.name for p in projects]
        assert "claude-project" in names
        found = next(p for p in projects if p.name == "claude-project")
        assert found.has_settings is True

    def test_skip_non_project_dirs(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain-dir"
        plain.mkdir()
        projects = discover_from_filesystem([tmp_path])
        names = [p.name for p in projects]
        assert "plain-dir" not in names

    def test_multiple_scan_dirs(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        proj_a = dir_a / "proj-a"
        proj_a.mkdir()
        (proj_a / ".mcp.json").write_text("{}")
        proj_b = dir_b / "proj-b"
        proj_b.mkdir()
        (proj_b / ".claude").mkdir()
        projects = discover_from_filesystem([dir_a, dir_b])
        names = [p.name for p in projects]
        assert "proj-a" in names
        assert "proj-b" in names


# --- TestDiscoverFromEcosystems ---

class TestDiscoverFromEcosystems:
    def test_extract_projects_from_ecosystems_json(self, tmp_path: Path) -> None:
        proj = tmp_path / "crm"
        proj.mkdir()
        ecosystems_file = tmp_path / "ecosystems.json"
        ecosystems_file.write_text(json.dumps({
            "ecosystems": {
                "client_retail": {
                    "name": "ClientRetail",
                    "projects": ["crm"],
                    "project_paths": {"crm": str(proj)},
                }
            }
        }))
        projects = discover_from_ecosystems(ecosystems_file)
        assert len(projects) == 1
        assert projects[0].name == "crm"
        assert projects[0].ecosystem == "client_retail"
        assert projects[0].path == str(proj)

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        projects = discover_from_ecosystems(tmp_path / "no-such-file.json")
        assert projects == []

    def test_skips_missing_project_paths(self, tmp_path: Path) -> None:
        ecosystems_file = tmp_path / "ecosystems.json"
        ecosystems_file.write_text(json.dumps({
            "ecosystems": {
                "test": {
                    "name": "Test",
                    "project_paths": {"ghost": "/does/not/exist"},
                }
            }
        }))
        projects = discover_from_ecosystems(ecosystems_file)
        assert projects == []


# --- TestDiscoverAllProjects ---

class TestDiscoverAllProjects:
    def test_deduplication_by_path(self, tmp_path: Path) -> None:
        proj = tmp_path / "shared-app"
        proj.mkdir()
        (proj / ".mcp.json").write_text("{}")

        desc_dir = tmp_path / "desc"
        desc_dir.mkdir()
        desc_file = desc_dir / "shared-app.md"
        desc_file.write_text(
            f"---\nname: shared-app\npath: {proj}\necosystem: client_retail\n---\n"
        )

        ecosystems_file = tmp_path / "ecosystems.json"
        ecosystems_file.write_text(json.dumps({
            "ecosystems": {
                "client_retail": {
                    "name": "ClientRetail",
                    "project_paths": {"shared-app": str(proj)},
                }
            }
        }))

        projects = discover_all_projects(desc_dir, [tmp_path], ecosystems_file)
        paths = [p.path for p in projects]
        assert paths.count(str(proj)) == 1

    def test_ecosystem_data_enriches_filesystem_discovery(self, tmp_path: Path) -> None:
        proj = tmp_path / "eco-app"
        proj.mkdir()
        (proj / ".mcp.json").write_text("{}")

        ecosystems_file = tmp_path / "ecosystems.json"
        ecosystems_file.write_text(json.dumps({
            "ecosystems": {
                "edp": {
                    "name": "EDP",
                    "project_paths": {"eco-app": str(proj)},
                }
            }
        }))

        desc_dir = tmp_path / "no-desc"
        desc_dir.mkdir()

        projects = discover_all_projects(desc_dir, [tmp_path], ecosystems_file)
        found = next((p for p in projects if p.name == "eco-app"), None)
        assert found is not None
        assert found.ecosystem == "edp"

    def test_results_are_sorted_by_name(self, tmp_path: Path) -> None:
        for name in ["zebra", "alpha", "mango"]:
            d = tmp_path / name
            d.mkdir()
            (d / ".mcp.json").write_text("{}")

        projects = discover_all_projects(
            tmp_path / "no-desc",
            [tmp_path],
            tmp_path / "no-eco.json",
        )
        names = [p.name for p in projects]
        assert names == sorted(names)

    def test_descriptor_wins_over_ecosystem(self, tmp_path: Path) -> None:
        proj = tmp_path / "winner"
        proj.mkdir()

        desc_dir = tmp_path / "desc"
        desc_dir.mkdir()
        desc_file = desc_dir / "winner.md"
        desc_file.write_text(
            f"---\nname: winner\npath: {proj}\necosystem: desc-eco\n---\n"
        )

        ecosystems_file = tmp_path / "ecosystems.json"
        ecosystems_file.write_text(json.dumps({
            "ecosystems": {
                "eco-eco": {
                    "name": "Eco",
                    "project_paths": {"winner": str(proj)},
                }
            }
        }))

        projects = discover_all_projects(desc_dir, [], ecosystems_file)
        found = next(p for p in projects if p.name == "winner")
        assert found.ecosystem == "desc-eco"
