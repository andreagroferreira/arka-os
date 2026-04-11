"""Tests for core.sync.mcp_syncer — registry-based .mcp.json sync."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.sync.mcp_syncer import (
    load_registry,
    resolve_mcps_for_stack,
    sync_all_mcps,
    sync_project_mcp,
)
from core.sync.schema import Project

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_SAMPLE_REGISTRY = {
    "_meta": {"description": "test"},
    "mcpServers": {
        "arka-prompts": {
            "command": "uv",
            "args": [
                "--directory",
                "{home}/.claude/skills/arka/mcp-server",
                "run",
                "server.py",
            ],
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


def _write_registry(tmp_path: Path, data: dict | None = None) -> Path:
    reg_file = tmp_path / "registry.json"
    reg_file.write_text(json.dumps(data if data is not None else _SAMPLE_REGISTRY))
    return reg_file


def _make_project(tmp_path: Path, name: str = "test-app", stack: list[str] | None = None) -> Project:
    proj_dir = tmp_path / name
    proj_dir.mkdir(exist_ok=True)
    return Project(path=str(proj_dir), name=name, stack=stack or [])


# ---------------------------------------------------------------------------
# TestLoadRegistry
# ---------------------------------------------------------------------------


class TestLoadRegistry:
    def test_valid_file_returns_mcp_servers(self, tmp_path: Path) -> None:
        reg_file = _write_registry(tmp_path)
        registry = load_registry(reg_file)
        assert "arka-prompts" in registry
        assert "context7" in registry
        assert "laravel-boost" in registry
        assert "_meta" not in registry  # top-level keys not under mcpServers are excluded

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        registry = load_registry(tmp_path / "nonexistent.json")
        assert registry == {}

    def test_malformed_json_returns_empty_dict(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{")
        registry = load_registry(bad_file)
        assert registry == {}

    def test_file_without_mcp_servers_key_returns_empty(self, tmp_path: Path) -> None:
        reg_file = tmp_path / "registry.json"
        reg_file.write_text(json.dumps({"_meta": {"v": 1}}))
        registry = load_registry(reg_file)
        assert registry == {}


# ---------------------------------------------------------------------------
# TestResolveMcpsForStack
# ---------------------------------------------------------------------------


class TestResolveMcpsForStack:
    def test_empty_stack_returns_base_only(self) -> None:
        registry = _SAMPLE_REGISTRY["mcpServers"]
        result = resolve_mcps_for_stack(registry, [])
        names = [name for name, _ in result]
        assert "arka-prompts" in names
        assert "context7" in names
        assert "laravel-boost" not in names
        assert "serena" not in names

    def test_laravel_stack_includes_laravel_and_base(self) -> None:
        registry = _SAMPLE_REGISTRY["mcpServers"]
        result = resolve_mcps_for_stack(registry, ["laravel", "php"])
        names = [name for name, _ in result]
        assert "arka-prompts" in names
        assert "context7" in names
        assert "laravel-boost" in names
        assert "serena" in names

    def test_php_alone_does_not_map_to_laravel_category(self) -> None:
        registry = _SAMPLE_REGISTRY["mcpServers"]
        result = resolve_mcps_for_stack(registry, ["php"])
        names = [name for name, _ in result]
        # "php" alone should NOT get laravel MCPs — only "laravel" in stack should
        assert "laravel-boost" not in names
        assert "arka-prompts" in names  # base MCPs are still included

    def test_nuxt_maps_to_nuxt_category(self) -> None:
        registry = {
            "nuxt-mcp": {"command": "npx", "args": ["nuxt-mcp"], "category": "nuxt"},
            "base-tool": {"command": "npx", "args": ["base"], "category": "base"},
        }
        result = resolve_mcps_for_stack(registry, ["nuxt"])
        names = [name for name, _ in result]
        assert "nuxt-mcp" in names
        assert "base-tool" in names

    def test_vue_maps_to_nuxt_category(self) -> None:
        registry = {
            "nuxt-mcp": {"command": "npx", "args": ["nuxt-mcp"], "category": "nuxt"},
        }
        result = resolve_mcps_for_stack(registry, ["vue"])
        names = [name for name, _ in result]
        assert "nuxt-mcp" in names

    def test_react_and_next_map_to_react_category(self) -> None:
        registry = {
            "react-tool": {"command": "npx", "args": ["react-tool"], "category": "react"},
        }
        assert "react-tool" in [n for n, _ in resolve_mcps_for_stack(registry, ["react"])]
        assert "react-tool" in [n for n, _ in resolve_mcps_for_stack(registry, ["next"])]

    def test_shopify_maps_to_ecommerce_category(self) -> None:
        registry = {
            "shop-mcp": {"command": "npx", "args": ["shop"], "category": "ecommerce"},
        }
        result = resolve_mcps_for_stack(registry, ["shopify"])
        names = [name for name, _ in result]
        assert "shop-mcp" in names

    def test_empty_registry_returns_empty(self) -> None:
        result = resolve_mcps_for_stack({}, ["laravel"])
        assert result == []


# ---------------------------------------------------------------------------
# TestSyncProjectMcp
# ---------------------------------------------------------------------------


class TestSyncProjectMcp:
    def test_creates_new_mcp_json_when_none_exists(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=["laravel"])
        registry = _SAMPLE_REGISTRY["mcpServers"]

        result = sync_project_mcp(project, registry, str(tmp_path / "home"))

        mcp_file = Path(project.path) / ".mcp.json"
        assert mcp_file.exists()
        data = json.loads(mcp_file.read_text())
        servers = data["mcpServers"]
        assert "arka-prompts" in servers
        assert "laravel-boost" in servers
        assert result.status in ("created", "updated")
        assert "arka-prompts" in result.final_mcp_list
        assert "laravel-boost" in result.final_mcp_list

    def test_preserves_custom_mcps_not_in_registry(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=[])
        mcp_file = Path(project.path) / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "my-custom-tool": {"command": "custom", "args": []},
            }
        }))
        registry = _SAMPLE_REGISTRY["mcpServers"]

        result = sync_project_mcp(project, registry, "/home/user")

        data = json.loads(mcp_file.read_text())
        assert "my-custom-tool" in data["mcpServers"]
        assert "my-custom-tool" in result.mcps_preserved
        assert "my-custom-tool" in result.final_mcp_list

    def test_updates_mcp_when_args_change(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=[])
        mcp_file = Path(project.path) / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "context7": {
                    "command": "npx",
                    "args": ["-y", "@upstash/context7-mcp", "--old-flag"],
                }
            }
        }))
        registry = _SAMPLE_REGISTRY["mcpServers"]

        result = sync_project_mcp(project, registry, "/home/user")

        assert "context7" in result.mcps_updated
        data = json.loads(mcp_file.read_text())
        assert "--old-flag" not in data["mcpServers"]["context7"]["args"]

    def test_serena_gets_project_path_injected(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=["laravel"])
        home = str(tmp_path / "home")
        registry = _SAMPLE_REGISTRY["mcpServers"]

        sync_project_mcp(project, registry, home)

        mcp_file = Path(project.path) / ".mcp.json"
        data = json.loads(mcp_file.read_text())
        serena_args = data["mcpServers"]["serena"]["args"]
        assert project.path in serena_args
        assert "{cwd}" not in " ".join(serena_args)

    def test_home_placeholder_resolved_in_arka_prompts(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=[])
        home = "/Users/testuser"
        registry = _SAMPLE_REGISTRY["mcpServers"]

        sync_project_mcp(project, registry, home)

        mcp_file = Path(project.path) / ".mcp.json"
        data = json.loads(mcp_file.read_text())
        arka_args = data["mcpServers"]["arka-prompts"]["args"]
        assert home in " ".join(arka_args)
        assert "{home}" not in " ".join(arka_args)

    def test_unchanged_when_already_correct(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=[])
        home = "/Users/testuser"
        registry = _SAMPLE_REGISTRY["mcpServers"]

        # First sync creates the file
        sync_project_mcp(project, registry, home)

        # Second sync should report unchanged
        result = sync_project_mcp(project, registry, home)

        assert result.status == "unchanged"
        assert result.mcps_added == []
        assert result.mcps_updated == []
        assert result.mcps_removed == []

    def test_removes_mcp_that_left_registry(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=[])
        mcp_file = Path(project.path) / ".mcp.json"
        # old-registry-tool was in registry but now is not in target for this stack
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "laravel-boost": {"command": "npx", "args": ["laravel-boost-mcp"]},
            }
        }))
        registry = _SAMPLE_REGISTRY["mcpServers"]

        # empty stack → laravel-boost is not in target
        result = sync_project_mcp(project, registry, "/home/user")

        assert "laravel-boost" in result.mcps_removed
        data = json.loads(mcp_file.read_text())
        assert "laravel-boost" not in data["mcpServers"]

    def test_registry_meta_keys_stripped_from_output(self, tmp_path: Path) -> None:
        project = _make_project(tmp_path, stack=["laravel"])
        registry = _SAMPLE_REGISTRY["mcpServers"]

        sync_project_mcp(project, registry, "/home/user")

        mcp_file = Path(project.path) / ".mcp.json"
        data = json.loads(mcp_file.read_text())
        for server_cfg in data["mcpServers"].values():
            assert "category" not in server_cfg
            assert "description" not in server_cfg
            assert "required_env" not in server_cfg

    def test_error_result_on_unwritable_path(self, tmp_path: Path) -> None:
        project = Project(path="/this/path/does/not/exist/at/all", name="ghost", stack=[])
        registry = _SAMPLE_REGISTRY["mcpServers"]

        result = sync_project_mcp(project, registry, "/home/user")

        assert result.status == "error"
        assert result.error is not None


# ---------------------------------------------------------------------------
# TestSyncAllMcps
# ---------------------------------------------------------------------------


class TestSyncAllMcps:
    def test_syncs_multiple_projects(self, tmp_path: Path) -> None:
        reg_file = _write_registry(tmp_path)
        p1 = _make_project(tmp_path, "app-one", stack=["laravel"])
        p2 = _make_project(tmp_path, "app-two", stack=[])
        home = str(tmp_path / "home")

        results = sync_all_mcps([p1, p2], reg_file, home)

        assert len(results) == 2
        paths = {r.path for r in results}
        assert p1.path in paths
        assert p2.path in paths

    def test_laravel_project_gets_laravel_mcps(self, tmp_path: Path) -> None:
        reg_file = _write_registry(tmp_path)
        project = _make_project(tmp_path, "laravel-app", stack=["laravel"])

        results = sync_all_mcps([project], reg_file, str(tmp_path / "home"))
        result = results[0]

        assert "laravel-boost" in result.final_mcp_list
        assert "serena" in result.final_mcp_list

    def test_non_laravel_project_lacks_laravel_mcps(self, tmp_path: Path) -> None:
        reg_file = _write_registry(tmp_path)
        project = _make_project(tmp_path, "plain-app", stack=[])

        results = sync_all_mcps([project], reg_file, str(tmp_path / "home"))
        result = results[0]

        assert "laravel-boost" not in result.final_mcp_list
        assert "serena" not in result.final_mcp_list
        assert "arka-prompts" in result.final_mcp_list

    def test_empty_project_list_returns_empty(self, tmp_path: Path) -> None:
        reg_file = _write_registry(tmp_path)
        results = sync_all_mcps([], reg_file, "/home/user")
        assert results == []
