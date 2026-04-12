"""End-to-end integration test for the ArkaOS Sync Engine.

Creates a complete mock environment and exercises the full run_sync pipeline,
verifying MCP merging, user-custom preservation, version writing, and report output.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.sync.engine import run_sync
from core.sync.reporter import format_report


# ---------------------------------------------------------------------------
# Environment builder
# ---------------------------------------------------------------------------


def _make_feature_yaml(features_dir: Path) -> None:
    features_dir.mkdir(parents=True, exist_ok=True)
    (features_dir / "forge.yaml").write_text(
        "name: forge-integration\n"
        'added_in: "2.14.0"\n'
        "mandatory: true\n"
        'section_title: "Forge Integration"\n'
        'detection_pattern: "arka-forge"\n'
        "deprecated_in: null\n"
        "content: |\n"
        "  Forge integration content.\n"
    )


def _write_registry(mcps_dir: Path) -> None:
    registry = {
        "mcpServers": {
            "arka-prompts": {
                "category": "base",
                "command": "npx",
                "args": ["-y", "arka-prompts"],
                "description": "ArkaOS prompts",
            },
            "context7": {
                "category": "base",
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp"],
                "description": "Context7 docs",
            },
            "laravel-boost": {
                "category": "laravel",
                "command": "npx",
                "args": ["-y", "laravel-boost"],
                "description": "Laravel MCP",
            },
        }
    }
    (mcps_dir / "registry.json").write_text(json.dumps(registry, indent=2))


def _write_crm_mcp_json(crm_app: Path) -> None:
    """Write an existing .mcp.json with old arka-prompts config and a custom MCP."""
    existing = {
        "mcpServers": {
            "arka-prompts": {
                "command": "npx",
                "args": ["-y", "arka-prompts@old"],
            },
            "my-custom": {
                "command": "node",
                "args": ["/usr/local/custom-mcp/index.js"],
            },
        }
    }
    (crm_app / ".mcp.json").write_text(json.dumps(existing, indent=2))


def _write_crm_descriptor(projects_dir: Path, crm_path: Path) -> None:
    content = (
        "---\n"
        f"name: crm-app\n"
        f"path: {crm_path}\n"
        "status: active\n"
        "stack: [php, laravel]\n"
        "---\n"
        "\n"
        "CRM application descriptor.\n"
    )
    (projects_dir / "crm-app.md").write_text(content)


def _build_environment(tmp_path: Path) -> dict:
    """Create a complete mock sync environment under tmp_path."""
    # 1. arkaos_home
    arkaos_home = tmp_path / ".arkaos"
    arkaos_home.mkdir()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "VERSION").write_text("2.14.0")

    features_dir = repo / "core" / "sync" / "features"
    _make_feature_yaml(features_dir)

    (arkaos_home / ".repo-path").write_text(str(repo))
    (arkaos_home / "sync-state.json").write_text(
        json.dumps({"version": "pending-sync"})
    )

    herd_dir = tmp_path / "herd"
    herd_dir.mkdir()
    (arkaos_home / "profile.json").write_text(
        json.dumps({"projectsDir": str(herd_dir)})
    )

    # 2. skills_dir
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    mcps_dir = skills_dir / "arka" / "mcps"
    mcps_dir.mkdir(parents=True)
    _write_registry(mcps_dir)

    projects_dir = skills_dir / "arka" / "projects"
    projects_dir.mkdir(parents=True)

    knowledge_dir = skills_dir / "arka" / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "ecosystems.json").write_text(json.dumps({"ecosystems": {}}))

    # 3. Projects
    crm_app = herd_dir / "crm-app"
    crm_app.mkdir()
    (crm_app / "composer.json").write_text(
        json.dumps({"require": {"laravel/framework": "^11.0"}})
    )
    _write_crm_mcp_json(crm_app)
    _write_crm_descriptor(projects_dir, crm_app)

    web_app = herd_dir / "web-app"
    web_app.mkdir()
    (web_app / "package.json").write_text(
        json.dumps({"dependencies": {"nuxt": "^3.0.0"}})
    )
    # Add a .mcp.json marker so filesystem discovery picks up this project
    (web_app / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))

    return {
        "arkaos_home": arkaos_home,
        "skills_dir": skills_dir,
        "home_path": str(tmp_path),
        "crm_app": crm_app,
        "web_app": web_app,
    }


# ---------------------------------------------------------------------------
# TestFullSyncIntegration
# ---------------------------------------------------------------------------


def _build_content_core_repo(root: Path) -> None:
    """Create a minimal fake ArkaOS core repo for content sync."""
    (root / "config" / "standards" / "claude-md-overlays").mkdir(parents=True)
    (root / "config" / "hooks").mkdir(parents=True)
    (root / "config" / "user-claude.md").write_text("# ArkaOS CLAUDE Template\n")
    (root / "config" / "standards" / "claude-md-overlays" / "python.md").write_text(
        "## Python Rules\n"
    )
    (root / "config" / "standards" / "communication.md").write_text("# Communication\n")
    (root / "config" / "hooks" / "session-start.sh").write_text("#!/bin/bash\necho start\n")
    (root / "config" / "constitution.yaml").write_text(
        "rules:\n  - name: squad-routing\n    level: NON-NEGOTIABLE\n"
    )
    (root / "VERSION").write_text("2.14.0\n")


def _build_content_sync_environment(tmp_path: Path) -> dict:
    """Create a mock environment with a python project for content sync tests."""
    arkaos_home = tmp_path / ".arkaos"
    arkaos_home.mkdir()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "VERSION").write_text("2.14.0")

    features_dir = repo / "core" / "sync" / "features"
    _make_feature_yaml(features_dir)

    (arkaos_home / ".repo-path").write_text(str(repo))
    (arkaos_home / "sync-state.json").write_text(json.dumps({"version": "pending-sync"}))

    herd_dir = tmp_path / "herd"
    herd_dir.mkdir()
    (arkaos_home / "profile.json").write_text(json.dumps({"projectsDir": str(herd_dir)}))

    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    mcps_dir = skills_dir / "arka" / "mcps"
    mcps_dir.mkdir(parents=True)
    _write_registry(mcps_dir)

    projects_dir = skills_dir / "arka" / "projects"
    projects_dir.mkdir(parents=True)

    knowledge_dir = skills_dir / "arka" / "knowledge"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "ecosystems.json").write_text(json.dumps({"ecosystems": {}}))

    py_app = herd_dir / "py-app"
    py_app.mkdir()
    (py_app / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))
    (projects_dir / "py-app.md").write_text(
        f"---\nname: py-app\npath: {py_app}\nstatus: active\nstack: [python]\n---\n\nPython app.\n"
    )

    core_repo = tmp_path / "core-repo"
    core_repo.mkdir()
    _build_content_core_repo(core_repo)

    return {
        "arkaos_home": arkaos_home,
        "skills_dir": skills_dir,
        "home_path": str(tmp_path),
        "py_app": py_app,
        "core_repo": core_repo,
    }


class TestFullSyncIntegration:
    def test_full_first_sync(self, tmp_path: Path) -> None:
        env = _build_environment(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=5
        ):
            report = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        assert report.current_version == "2.14.0"

        crm_result = next(
            (r for r in report.mcp_results if "crm-app" in r.path), None
        )
        assert crm_result is not None, "Expected MCP result for crm-app"
        # After optimizer: laravel policy activates context7; laravel-boost and
        # my-custom are ambiguous with no AI available so they are deferred.
        assert "context7" in crm_result.final_mcp_list

        state_path = env["arkaos_home"] / "sync-state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["version"] == "2.14.0"

    def test_report_output(self, tmp_path: Path) -> None:
        env = _build_environment(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=5
        ):
            report = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        output = format_report(report)

        assert "2.14.0" in output
        assert "MCPs" in output
        assert "Errors: 0" in output

    def test_content_sync_idempotent_across_two_runs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _build_content_sync_environment(tmp_path)
        monkeypatch.setenv("ARKAOS_CORE_ROOT", str(env["core_repo"]))

        with patch("core.sync.descriptor_syncer._get_last_commit_days", return_value=5):
            report1 = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        py_result1 = next(
            (r for r in report1.content_results if "py-app" in r.path), None
        )
        assert py_result1 is not None, "Expected content_result for py-app on first run"
        assert py_result1.status == "updated"

        with patch("core.sync.descriptor_syncer._get_last_commit_days", return_value=5):
            report2 = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        py_result2 = next(
            (r for r in report2.content_results if "py-app" in r.path), None
        )
        assert py_result2 is not None, "Expected content_result for py-app on second run"
        assert py_result2.status == "unchanged"

    def test_nuxt_project_gets_base_mcps_only(self, tmp_path: Path) -> None:
        env = _build_environment(tmp_path)

        with patch(
            "core.sync.descriptor_syncer._get_last_commit_days", return_value=5
        ):
            report = run_sync(
                arkaos_home=env["arkaos_home"],
                skills_dir=env["skills_dir"],
                home_path=env["home_path"],
            )

        web_result = next(
            (r for r in report.mcp_results if "web-app" in r.path), None
        )
        assert web_result is not None, "Expected MCP result for web-app"
        assert "laravel-boost" not in web_result.final_mcp_list
        # After optimizer: nuxt policy activates context7; arka-prompts is
        # ambiguous with no AI available so it is deferred.
        assert "context7" in web_result.final_mcp_list
