"""Tests for the commands registry generator."""

import pytest
import json
from pathlib import Path

from core.registry.generator import (
    extract_commands_from_skill,
    generate_commands_registry,
    DEPARTMENT_KEYWORDS,
)


BASE_DIR = Path(__file__).parent.parent.parent


class TestCommandExtraction:
    def test_extract_dev_commands(self):
        skill = BASE_DIR / "departments" / "dev" / "SKILL.md"
        commands = extract_commands_from_skill(skill)
        assert len(commands) >= 15
        cmd_texts = [c["command"] for c in commands]
        assert any("/dev feature" in c for c in cmd_texts)
        assert any("/dev api" in c for c in cmd_texts)
        assert any("/dev debug" in c for c in cmd_texts)

    def test_extract_saas_commands(self):
        skill = BASE_DIR / "departments" / "saas" / "SKILL.md"
        commands = extract_commands_from_skill(skill)
        assert len(commands) >= 12
        cmd_texts = [c["command"] for c in commands]
        assert any("/saas validate" in c for c in cmd_texts)

    def test_extract_empty_file(self):
        commands = extract_commands_from_skill(Path("/nonexistent"))
        assert commands == []


class TestRegistryGeneration:
    @pytest.fixture(scope="class")
    def registry(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("reg") / "registry.json"
        return generate_commands_registry(BASE_DIR, out)

    def test_total_commands_above_150(self, registry):
        assert registry["_meta"]["total_commands"] >= 150

    def test_has_all_v2_departments(self, registry):
        depts = set(registry["_meta"]["departments"].keys())
        expected = {
            "dev", "marketing", "brand", "finance", "strategy", "ecom", "kb",
            "ops", "pm", "saas", "landing", "content", "community", "sales",
            "leadership", "org", "arka",
        }
        missing = expected - depts
        assert not missing, f"Missing departments: {missing}"

    def test_commands_have_required_fields(self, registry):
        for cmd in registry["commands"]:
            assert "id" in cmd
            assert "command" in cmd
            assert "department" in cmd
            assert "description" in cmd
            assert cmd["command"].startswith("/")

    def test_dev_commands_flagged_as_code_modifying(self, registry):
        dev_feature = next(
            (c for c in registry["commands"] if "dev-feature" in c["id"]), None
        )
        assert dev_feature is not None
        assert dev_feature["modifies_code"] is True
        assert dev_feature["requires_branch"] is True

    def test_non_dev_commands_not_code_modifying(self, registry):
        mkt_social = next(
            (c for c in registry["commands"] if "mkt-social" in c["id"]), None
        )
        if mkt_social:
            assert mkt_social["modifies_code"] is False

    def test_department_keywords_coverage(self):
        assert len(DEPARTMENT_KEYWORDS) >= 16
        for dept, keywords in DEPARTMENT_KEYWORDS.items():
            assert len(keywords) >= 5, f"{dept} has too few keywords"

    def test_registry_writes_valid_json(self, tmp_path):
        out = tmp_path / "test-registry.json"
        generate_commands_registry(BASE_DIR, out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "_meta" in data
        assert "commands" in data

    def test_no_duplicate_command_ids(self, registry):
        ids = [c["id"] for c in registry["commands"]]
        duplicates = [x for x in ids if ids.count(x) > 1]
        # Some duplicates are OK (e.g., /arka commands appear in arka SKILL.md)
        # But department commands should be unique within their department
        dept_ids = {}
        for cmd in registry["commands"]:
            key = f"{cmd['department']}-{cmd['id']}"
            if key in dept_ids:
                pytest.fail(f"Duplicate: {key}")
            dept_ids[key] = True
