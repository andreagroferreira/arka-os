"""Tests for Obsidian vault integration."""

import json
from pathlib import Path

import pytest

from core.obsidian.writer import ObsidianWriter
from core.obsidian.templates import build_frontmatter, resolve_template_vars


class TestFrontmatter:
    def test_basic_frontmatter(self):
        fm = build_frontmatter(department="dev", agent="paulo")
        assert "---" in fm
        assert "department: dev" in fm
        assert "agent: paulo" in fm
        assert "source: arkaos" in fm

    def test_tags(self):
        fm = build_frontmatter(department="marketing", tags=["campaign", "q3"])
        assert "- arkaos" in fm
        assert "- dept/marketing" in fm
        assert "- campaign" in fm
        assert "- q3" in fm

    def test_extra_fields(self):
        fm = build_frontmatter(extra={"project": "client_retail", "status": "draft"})
        assert "project: client_retail" in fm
        assert "status: draft" in fm

    def test_workflow_field(self):
        fm = build_frontmatter(workflow="dev-feature")
        assert "workflow: dev-feature" in fm

    def test_created_date(self):
        fm = build_frontmatter()
        assert "created:" in fm


class TestTemplateVars:
    def test_resolve_project(self):
        result = resolve_template_vars("Projects/{project}/docs/", {"project": "ArkaOS"})
        assert result == "Projects/ArkaOS/docs/"

    def test_resolve_department(self):
        result = resolve_template_vars("{department}/output.md", {"department": "dev"})
        assert result == "dev/output.md"

    def test_resolve_multiple(self):
        result = resolve_template_vars(
            "Projects/{project}/ADR-{number}.md",
            {"project": "MyApp", "number": "042"},
        )
        assert result == "Projects/MyApp/ADR-042.md"

    def test_defaults_applied(self):
        result = resolve_template_vars("{date}/output.md")
        assert "output.md" in result
        # Date should be ISO format
        assert len(result.split("/")[0]) == 10  # YYYY-MM-DD

    def test_no_vars(self):
        result = resolve_template_vars("simple/path.md")
        assert result == "simple/path.md"


class TestObsidianWriter:
    @pytest.fixture
    def writer(self, tmp_path):
        return ObsidianWriter(vault_path=tmp_path)

    def test_save_basic(self, writer, tmp_path):
        path = writer.save(
            obsidian_path="test/output.md",
            content="# Hello\n\nThis is a test.",
            department="dev",
        )
        assert path.exists()
        content = path.read_text()
        assert "source: arkaos" in content
        assert "department: dev" in content
        assert "# Hello" in content

    def test_save_creates_directories(self, writer, tmp_path):
        path = writer.save(
            obsidian_path="deep/nested/dir/output.md",
            content="Test content",
        )
        assert path.exists()
        assert "deep/nested/dir" in str(path)

    def test_save_directory_path_generates_filename(self, writer, tmp_path):
        path = writer.save(
            obsidian_path="WizardingCode/Strategy/",
            content="Strategy report",
            department="strategy",
        )
        assert path.exists()
        assert path.suffix == ".md"
        assert "strategy-" in path.name

    def test_save_with_template_vars(self, writer, tmp_path):
        path = writer.save(
            obsidian_path="Projects/{project}/report.md",
            content="Project report",
            template_vars={"project": "ArkaOS"},
        )
        assert path.exists()
        assert "ArkaOS" in str(path)

    def test_save_with_tags(self, writer, tmp_path):
        path = writer.save(
            obsidian_path="test.md",
            content="Tagged content",
            department="dev",
            tags=["security", "audit"],
        )
        content = path.read_text()
        assert "- security" in content
        assert "- audit" in content

    def test_duplicate_gets_timestamp(self, writer, tmp_path):
        path1 = writer.save(obsidian_path="test/same.md", content="First")
        path2 = writer.save(obsidian_path="test/same.md", content="Second")
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()

    def test_ensure_vault(self, writer, tmp_path):
        assert writer.ensure_vault()

    def test_ensure_vault_missing(self):
        writer = ObsidianWriter(vault_path="/nonexistent/vault")
        assert not writer.ensure_vault()

    def test_vault_path_property(self, writer, tmp_path):
        assert writer.vault_path == tmp_path

    def test_list_outputs_empty(self, writer):
        assert writer.list_outputs() == []

    def test_list_outputs_finds_arkaos_files(self, writer, tmp_path):
        writer.save(obsidian_path="test/a.md", content="Content A", department="dev")
        writer.save(obsidian_path="test/b.md", content="Content B", department="marketing")

        all_outputs = writer.list_outputs()
        assert len(all_outputs) == 2

        dev_outputs = writer.list_outputs(department="dev")
        assert len(dev_outputs) == 1

    def test_save_with_extra_frontmatter(self, writer, tmp_path):
        path = writer.save(
            obsidian_path="test.md",
            content="Content",
            extra_frontmatter={"status": "final", "reviewed": True},
        )
        content = path.read_text()
        assert "status: final" in content
        assert "reviewed: true" in content


class TestVaultPathResolution:
    def test_explicit_path(self, tmp_path):
        writer = ObsidianWriter(vault_path=tmp_path)
        assert writer.vault_path == tmp_path

    def test_fallback_creates_directory(self):
        writer = ObsidianWriter(vault_path=None, arkaos_root="/nonexistent")
        # Should fall back to ~/.arkaos/vault/
        assert "vault" in str(writer.vault_path)

    def test_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ARKAOS_VAULT", str(tmp_path))
        writer = ObsidianWriter(vault_path=None, arkaos_root="/nonexistent")
        assert writer.vault_path == tmp_path
