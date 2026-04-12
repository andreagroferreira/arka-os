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

    env_example = proj / ".env.arkaos.example"
    assert env_example.exists()
    text = env_example.read_text()
    assert "PG_HOST" in text
    assert "PG_PASSWORD" in text


def test_override_collision_force_active_wins(tmp_path: Path, policy_file: Path) -> None:
    proj = tmp_path / "p"
    (proj / ".arkaos").mkdir(parents=True)
    _make_mcp_json(proj, {"canva": {}})
    (proj / ".arkaos" / "mcp-override.yaml").write_text(
        "force_active: [canva]\n"
        "force_deferred: [canva]\n"
        "reason: conflicting\n"
    )

    mcp_result = McpSyncResult(
        path=str(proj), status="updated", final_mcp_list=["canva"],
    )
    project = Project(path=str(proj), name="p", stack=["laravel"])

    result = optimize_project_mcps(
        project, mcp_result, policy_file,
        vault_path=None, cache_path=tmp_path / "cache.json",
    )

    assert "canva" in result.final_mcp_list
    assert "canva" not in result.mcps_deferred
    assert any("collision" in w for w in result.optimizer_warnings)


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
