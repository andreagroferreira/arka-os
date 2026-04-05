"""Tests that all sub-skill SKILL.md files are valid and loadable."""

import pytest
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
SKILL_FILES = sorted(BASE_DIR.glob("departments/*/skills/*/SKILL.md"))
CORE_SKILLS = sorted(BASE_DIR.glob("arka/skills/*/SKILL.md"))
DEPT_SKILLS = sorted(BASE_DIR.glob("departments/*/SKILL.md"))


class TestSubSkillsValid:
    """Every sub-skill SKILL.md must have valid YAML frontmatter."""

    @pytest.mark.parametrize("skill_file", SKILL_FILES,
                             ids=lambda f: f"{f.parent.parent.name}/{f.parent.name}")
    def test_skill_has_frontmatter(self, skill_file):
        content = skill_file.read_text()
        assert content.startswith("---"), f"{skill_file} missing YAML frontmatter"
        # Must have closing ---
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{skill_file} incomplete frontmatter"

    @pytest.mark.parametrize("skill_file", SKILL_FILES,
                             ids=lambda f: f"{f.parent.parent.name}/{f.parent.name}")
    def test_skill_has_name(self, skill_file):
        content = skill_file.read_text()
        assert "name:" in content, f"{skill_file} missing name field"

    @pytest.mark.parametrize("skill_file", SKILL_FILES,
                             ids=lambda f: f"{f.parent.parent.name}/{f.parent.name}")
    def test_skill_has_description(self, skill_file):
        content = skill_file.read_text()
        assert "description:" in content, f"{skill_file} missing description"

    @pytest.mark.parametrize("skill_file", SKILL_FILES,
                             ids=lambda f: f"{f.parent.parent.name}/{f.parent.name}")
    def test_skill_has_content_after_frontmatter(self, skill_file):
        content = skill_file.read_text()
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""
        assert len(body) > 10, f"{skill_file} has no content body"


class TestSkillCoverage:
    def test_total_sub_skills_near_target(self):
        assert len(SKILL_FILES) >= 180, f"Expected 180+ sub-skills, found {len(SKILL_FILES)}"

    def test_all_departments_have_sub_skills(self):
        depts_with_skills = set()
        for f in SKILL_FILES:
            # path: departments/<dept>/skills/<skill>/SKILL.md
            dept = f.parts[-4]  # 4th from end = department name
            depts_with_skills.add(dept)
        expected = {
            "dev", "marketing", "brand", "finance", "strategy", "ecom", "kb",
            "ops", "pm", "saas", "landing", "content", "community", "sales",
            "leadership", "org",
        }
        missing = expected - depts_with_skills
        assert not missing, f"Departments without sub-skills: {missing}"

    def test_department_skills_exist(self):
        assert len(DEPT_SKILLS) >= 16, f"Expected 16+ dept SKILL.md, found {len(DEPT_SKILLS)}"

    def test_core_skills_exist(self):
        # human-writing + conclave
        assert len(CORE_SKILLS) >= 2, f"Expected 2+ core skills, found {len(CORE_SKILLS)}"

    def test_dev_has_most_skills(self):
        dev_skills = list(BASE_DIR.glob("departments/dev/skills/*/SKILL.md"))
        assert len(dev_skills) >= 12, f"Dev should have 12+ skills, found {len(dev_skills)}"

    def test_skill_names_are_kebab_case(self):
        for f in SKILL_FILES:
            dir_name = f.parent.name
            assert re.match(r'^[a-z0-9-]+$', dir_name), \
                f"Skill directory '{dir_name}' not kebab-case"


class TestCoreSkillsV2:
    """V1 core skills should be updated for v2."""

    def test_human_writing_has_v2_name(self):
        skill = BASE_DIR / "arka" / "skills" / "human-writing" / "SKILL.md"
        content = skill.read_text()
        assert "arka-human-writing" in content

    def test_spec_has_v2_name(self):
        skill = BASE_DIR / "departments" / "dev" / "skills" / "spec" / "SKILL.md"
        content = skill.read_text()
        assert "arka-dev-spec" in content

    def test_scaffold_has_v2_name(self):
        skill = BASE_DIR / "departments" / "dev" / "skills" / "scaffold" / "SKILL.md"
        content = skill.read_text()
        assert "arka-dev-scaffold" in content
