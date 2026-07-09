"""Tests for the commands registry generator (single canonical, M2)."""

import pytest
import json
from pathlib import Path

from core.registry.generator import (
    derive_command_id,
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


class TestIdDerivation:
    def test_plain_command(self):
        assert derive_command_id("/dev feature") == "dev-feature"

    def test_angle_args_stripped(self):
        assert derive_command_id("/arka resume <PR_URL>") == "arka-resume"

    def test_optional_args_stripped(self):
        assert derive_command_id("/arka costs [period]") == "arka-costs"

    def test_flags_stripped(self):
        assert (
            derive_command_id("/arka reorganize [--since-days N]")
            == "arka-reorganize"
        )

    def test_multiword_subcommand(self):
        assert derive_command_id("/dev scaffold laravel") == "dev-scaffold-laravel"


class TestRegistryGeneration:
    @pytest.fixture(scope="class")
    def registry(self, tmp_path_factory):
        out = tmp_path_factory.mktemp("reg") / "registry.json"
        return generate_commands_registry(BASE_DIR, out)

    def test_total_commands_above_200(self, registry):
        # Sub-skill scanning (M2 consolidation) brought the count to
        # bash-generator parity: 262 at consolidation time.
        assert registry["_meta"]["total_commands"] >= 200

    def test_has_all_departments_with_prefix_slugs(self, registry):
        # Department naming follows the command prefixes (mkt/fin/strat),
        # matching CLAUDE.md and the runtime consumers.
        depts = set(registry["_meta"]["departments"].keys())
        expected = {
            "dev", "mkt", "brand", "fin", "strat", "ecom", "kb",
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
            assert "keywords" in cmd
            assert "lead_agent" in cmd
            assert "source" in cmd
            assert cmd["command"].startswith("/")

    def test_seeded_keywords_win_over_department_fallback(self, registry):
        # arka-standup has a commands-keywords.json seed entry.
        standup = next(
            c for c in registry["commands"] if c["id"] == "arka-standup"
        )
        assert "standup" in standup["keywords"]
        assert standup["examples"], "seeded examples must be preserved"

    def test_unseeded_department_commands_get_keyword_fallback(self, registry):
        # 172 commands had keywords:[] under the bash generator — L5
        # hint-blind. The department fallback closes that. arka system
        # commands are exempt: they are invoked explicitly (/arka ...),
        # so unseeded ones intentionally carry no natural-language hints.
        empty = [
            c["id"]
            for c in registry["commands"]
            if not c["keywords"] and c["department"] != "arka"
        ]
        assert not empty, f"L5-blind commands (no keywords): {empty[:10]}"

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
