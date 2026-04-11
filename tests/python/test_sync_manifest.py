"""Tests for the Change Manifest Builder (core/sync/manifest.py)."""

from pathlib import Path

import pytest

from core.sync.manifest import build_manifest, load_features
from core.sync.schema import FeatureSpec


# --- Helpers ---

def _write_feature_yaml(directory: Path, filename: str, content: str) -> None:
    (directory / filename).write_text(content)


_BASIC_FEATURE_YAML = """\
name: mcp-sync
added_in: "2.14.0"
mandatory: true
section_title: "MCP Configuration"
detection_pattern: "mcpServers"
deprecated_in: null
content: |
  ## MCP Sync
  Syncs .mcp.json for every project.
"""

_DEPRECATED_FEATURE_YAML = """\
name: legacy-skill
added_in: "2.0.0"
mandatory: false
section_title: "Legacy Skill"
detection_pattern: "legacy"
deprecated_in: "2.14.0"
content: |
  ## Legacy Skill
  No longer used.
"""


# --- TestLoadFeatures ---

class TestLoadFeatures:
    def test_load_from_directory(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        features = load_features(tmp_path)

        assert len(features) == 1
        spec = features[0]
        assert isinstance(spec, FeatureSpec)
        assert spec.name == "mcp-sync"
        assert spec.added_in == "2.14.0"
        assert spec.mandatory is True
        assert spec.section_title == "MCP Configuration"
        assert spec.detection_pattern == "mcpServers"
        assert spec.deprecated_in is None

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        features = load_features(tmp_path)
        assert features == []

    def test_skip_non_yaml_files(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)
        (tmp_path / "readme.txt").write_text("not a feature")
        (tmp_path / "notes.md").write_text("# Notes")

        features = load_features(tmp_path)

        assert len(features) == 1
        assert features[0].name == "mcp-sync"

    def test_load_deprecated_feature(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "legacy-skill.yaml", _DEPRECATED_FEATURE_YAML)

        features = load_features(tmp_path)

        assert len(features) == 1
        spec = features[0]
        assert spec.name == "legacy-skill"
        assert spec.deprecated_in == "2.14.0"
        assert spec.mandatory is False

    def test_returns_empty_list_when_dir_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        features = load_features(missing)
        assert features == []


# --- TestBuildManifest ---

class TestBuildManifest:
    def test_first_sync(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        manifest = build_manifest("pending-sync", "2.14.0", tmp_path)

        assert manifest.is_first_sync is True
        assert manifest.previous_version == "pending-sync"
        assert manifest.current_version == "2.14.0"
        assert "mcp-sync" in manifest.new_features
        assert manifest.deprecated_features == []

    def test_first_sync_none_marker(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        manifest = build_manifest("none", "2.14.0", tmp_path)

        assert manifest.is_first_sync is True

    def test_first_sync_empty_string_marker(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        manifest = build_manifest("", "2.14.0", tmp_path)

        assert manifest.is_first_sync is True

    def test_first_sync_excludes_deprecated_features(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)
        _write_feature_yaml(tmp_path, "legacy-skill.yaml", _DEPRECATED_FEATURE_YAML)

        manifest = build_manifest("pending-sync", "2.14.0", tmp_path)

        assert "mcp-sync" in manifest.new_features
        assert "legacy-skill" not in manifest.new_features

    def test_incremental_sync_new_feature(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        manifest = build_manifest("2.13.0", "2.14.0", tmp_path)

        assert manifest.is_first_sync is False
        assert "mcp-sync" in manifest.new_features
        assert manifest.deprecated_features == []

    def test_incremental_sync_feature_already_present(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        # Syncing from 2.14.0 → 2.15.0: feature was added in 2.14.0, not new
        manifest = build_manifest("2.14.0", "2.15.0", tmp_path)

        assert "mcp-sync" not in manifest.new_features

    def test_incremental_sync_deprecated_feature(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "legacy-skill.yaml", _DEPRECATED_FEATURE_YAML)

        manifest = build_manifest("2.13.0", "2.14.0", tmp_path)

        assert manifest.is_first_sync is False
        assert "legacy-skill" in manifest.deprecated_features
        assert "legacy-skill" not in manifest.new_features

    def test_incremental_sync_no_changes(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)

        # Feature added_in 2.14.0, syncing 2.14.0 → 2.15.0 = no new features
        manifest = build_manifest("2.14.0", "2.15.0", tmp_path)

        assert manifest.new_features == []
        assert manifest.deprecated_features == []

    def test_manifest_contains_all_features(self, tmp_path: Path) -> None:
        _write_feature_yaml(tmp_path, "mcp-sync.yaml", _BASIC_FEATURE_YAML)
        _write_feature_yaml(tmp_path, "legacy-skill.yaml", _DEPRECATED_FEATURE_YAML)

        manifest = build_manifest("2.13.0", "2.14.0", tmp_path)

        assert len(manifest.features) == 2
