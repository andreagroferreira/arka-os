"""Tests for the Sync Engine schema models."""

import pytest

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


# --- FeatureSpec ---

class TestFeatureSpec:
    def test_create_minimal(self) -> None:
        spec = FeatureSpec(
            name="mcp-sync",
            added_in="2.14.0",
            mandatory=True,
            section_title="MCP Configuration",
            detection_pattern="mcpServers",
            content="## MCP\n...",
        )
        assert spec.name == "mcp-sync"
        assert spec.added_in == "2.14.0"
        assert spec.mandatory is True
        assert spec.deprecated_in is None

    def test_deprecated_in_optional(self) -> None:
        spec = FeatureSpec(
            name="legacy-skill",
            added_in="2.0.0",
            mandatory=False,
            section_title="Legacy",
            detection_pattern="legacy",
            content="content",
            deprecated_in="2.14.0",
        )
        assert spec.deprecated_in == "2.14.0"

    def test_non_mandatory_feature(self) -> None:
        spec = FeatureSpec(
            name="optional-feature",
            added_in="2.5.0",
            mandatory=False,
            section_title="Optional",
            detection_pattern="optional",
            content="optional content",
        )
        assert spec.mandatory is False


# --- ChangeManifest ---

class TestChangeManifest:
    def test_create_minimal(self) -> None:
        manifest = ChangeManifest(
            previous_version="2.13.0",
            current_version="2.14.0",
            is_first_sync=False,
        )
        assert manifest.previous_version == "2.13.0"
        assert manifest.current_version == "2.14.0"
        assert manifest.is_first_sync is False
        assert manifest.features == []
        assert manifest.new_features == []
        assert manifest.deprecated_features == []

    def test_first_sync_flag(self) -> None:
        manifest = ChangeManifest(
            previous_version="",
            current_version="2.14.0",
            is_first_sync=True,
        )
        assert manifest.is_first_sync is True

    def test_with_features_and_changes(self) -> None:
        spec = FeatureSpec(
            name="mcp-sync",
            added_in="2.14.0",
            mandatory=True,
            section_title="MCP",
            detection_pattern="mcpServers",
            content="content",
        )
        manifest = ChangeManifest(
            previous_version="2.13.0",
            current_version="2.14.0",
            is_first_sync=False,
            features=[spec],
            new_features=["mcp-sync"],
            deprecated_features=["old-skill"],
        )
        assert len(manifest.features) == 1
        assert "mcp-sync" in manifest.new_features
        assert "old-skill" in manifest.deprecated_features


# --- Project ---

class TestProject:
    def test_create_minimal(self) -> None:
        project = Project(path="/home/user/myapp", name="myapp")
        assert project.path == "/home/user/myapp"
        assert project.name == "myapp"
        assert project.ecosystem is None
        assert project.stack == []
        assert project.descriptor_path is None
        assert project.has_mcp_json is False
        assert project.has_settings is False

    def test_create_full(self) -> None:
        project = Project(
            path="/home/user/myapp",
            name="myapp",
            ecosystem="rockport",
            stack=["laravel", "nuxt"],
            descriptor_path="/home/user/myapp/.arkaos/descriptor.yaml",
            has_mcp_json=True,
            has_settings=True,
        )
        assert project.ecosystem == "rockport"
        assert "laravel" in project.stack
        assert project.has_mcp_json is True
        assert project.has_settings is True

    def test_stack_defaults_to_empty_list(self) -> None:
        project = Project(path="/p", name="p")
        assert isinstance(project.stack, list)
        assert len(project.stack) == 0


# --- McpSyncResult ---

class TestMcpSyncResult:
    def test_create_minimal(self) -> None:
        result = McpSyncResult(path="/p", status="ok")
        assert result.path == "/p"
        assert result.status == "ok"
        assert result.mcps_added == []
        assert result.mcps_removed == []
        assert result.mcps_updated == []
        assert result.mcps_preserved == []
        assert result.final_mcp_list == []
        assert result.error is None

    def test_create_with_changes(self) -> None:
        result = McpSyncResult(
            path="/project/.mcp.json",
            status="updated",
            mcps_added=["laravel-boost"],
            mcps_removed=["old-mcp"],
            mcps_updated=["nuxt-mcp"],
            mcps_preserved=["github"],
            final_mcp_list=["laravel-boost", "nuxt-mcp", "github"],
        )
        assert "laravel-boost" in result.mcps_added
        assert "old-mcp" in result.mcps_removed
        assert len(result.final_mcp_list) == 3

    def test_error_field(self) -> None:
        result = McpSyncResult(path="/p", status="error", error="File not found")
        assert result.error == "File not found"


# --- SettingsSyncResult ---

class TestSettingsSyncResult:
    def test_create_minimal(self) -> None:
        result = SettingsSyncResult(path="/p/.claude/settings.local.json", status="ok")
        assert result.status == "ok"
        assert result.servers_added == []
        assert result.servers_removed == []
        assert result.error is None

    def test_create_with_changes(self) -> None:
        result = SettingsSyncResult(
            path="/p/.claude/settings.local.json",
            status="updated",
            servers_added=["mcp-server-a"],
            servers_removed=["mcp-server-b"],
        )
        assert "mcp-server-a" in result.servers_added
        assert "mcp-server-b" in result.servers_removed

    def test_error_optional(self) -> None:
        result = SettingsSyncResult(path="/p", status="error", error="Permission denied")
        assert result.error == "Permission denied"


# --- DescriptorSyncResult ---

class TestDescriptorSyncResult:
    def test_create_minimal(self) -> None:
        result = DescriptorSyncResult(path="/p/descriptor.yaml", status="ok")
        assert result.path == "/p/descriptor.yaml"
        assert result.status == "ok"
        assert result.changes == []
        assert result.error is None

    def test_create_with_changes(self) -> None:
        result = DescriptorSyncResult(
            path="/p/descriptor.yaml",
            status="updated",
            changes=["updated stack", "added ecosystem"],
        )
        assert len(result.changes) == 2
        assert "updated stack" in result.changes

    def test_error_optional(self) -> None:
        result = DescriptorSyncResult(path="/p", status="error", error="YAML parse error")
        assert result.error == "YAML parse error"


# --- SkillSyncResult ---

class TestSkillSyncResult:
    def test_create_minimal(self) -> None:
        result = SkillSyncResult(skill_name="arka-dev", status="ok")
        assert result.skill_name == "arka-dev"
        assert result.status == "ok"
        assert result.features_added == []
        assert result.features_removed == []
        assert result.error is None

    def test_create_with_changes(self) -> None:
        result = SkillSyncResult(
            skill_name="arka-update",
            status="updated",
            features_added=["mcp-sync-section"],
            features_removed=["deprecated-section"],
        )
        assert "mcp-sync-section" in result.features_added
        assert "deprecated-section" in result.features_removed

    def test_error_optional(self) -> None:
        result = SkillSyncResult(skill_name="arka-dev", status="error", error="Skill not found")
        assert result.error == "Skill not found"


# --- SyncReport ---

class TestSyncReport:
    def test_create_minimal(self) -> None:
        report = SyncReport(previous_version="2.13.0", current_version="2.14.0")
        assert report.previous_version == "2.13.0"
        assert report.current_version == "2.14.0"
        assert report.mcp_results == []
        assert report.settings_results == []
        assert report.descriptor_results == []
        assert report.skill_results == []
        assert report.errors == []

    def test_create_full_report(self) -> None:
        report = SyncReport(
            previous_version="2.13.0",
            current_version="2.14.0",
            mcp_results=[McpSyncResult(path="/p1", status="ok")],
            settings_results=[SettingsSyncResult(path="/p1", status="ok")],
            descriptor_results=[DescriptorSyncResult(path="/p1/descriptor.yaml", status="ok")],
            skill_results=[SkillSyncResult(skill_name="arka-dev", status="ok")],
            errors=["Some non-fatal error"],
        )
        assert len(report.mcp_results) == 1
        assert len(report.settings_results) == 1
        assert len(report.descriptor_results) == 1
        assert len(report.skill_results) == 1
        assert len(report.errors) == 1

    def test_errors_accumulate(self) -> None:
        report = SyncReport(
            previous_version="2.13.0",
            current_version="2.14.0",
            errors=["error A", "error B", "error C"],
        )
        assert len(report.errors) == 3
        assert "error A" in report.errors

    def test_version_fields_stored_as_strings(self) -> None:
        report = SyncReport(previous_version="2.0.0-alpha.1", current_version="2.14.0")
        assert isinstance(report.previous_version, str)
        assert isinstance(report.current_version, str)
