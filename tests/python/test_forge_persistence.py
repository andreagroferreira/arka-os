from pathlib import Path
import pytest
import yaml
from core.forge.schema import (
    ForgePlan, ForgeContext, ForgeStatus,
    ExplorerApproach, ExplorerLens, CriticVerdict, RejectedElement, IdentifiedRisk, RiskSeverity,
    PlanPhase, ExecutionPath, ExecutionPathType, ForgeTier, ComplexityScore, ComplexityDimensions,
)
from core.forge.persistence import (
    save_plan, load_plan, list_plans, get_active_plan, set_active_plan, clear_active_plan,
    export_to_obsidian, extract_patterns, load_patterns,
)

@pytest.fixture(autouse=True)
def _use_tmp_plans(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.forge.persistence._plans_dir", lambda: tmp_path / "plans")
    monkeypatch.setattr("core.forge.persistence._active_link", lambda: tmp_path / "plans" / "active.yaml")

def _make_plan(plan_id="forge-test-001", name="Test Plan"):
    return ForgePlan(
        id=plan_id, name=name,
        context=ForgeContext(repo="test", branch="main", commit_at_forge="abc", arkaos_version="2.14.0", prompt="test"),
    )

class TestSavePlan:
    def test_saves_yaml_file(self, tmp_path):
        save_plan(_make_plan())
        assert (tmp_path / "plans" / "forge-test-001.yaml").exists()

    def test_saved_file_is_valid_yaml(self, tmp_path):
        save_plan(_make_plan())
        data = yaml.safe_load((tmp_path / "plans" / "forge-test-001.yaml").read_text())
        assert data["id"] == "forge-test-001"

    def test_creates_plans_dir(self, tmp_path):
        save_plan(_make_plan())
        assert (tmp_path / "plans").is_dir()

class TestLoadPlan:
    def test_load_existing(self):
        save_plan(_make_plan())
        loaded = load_plan("forge-test-001")
        assert loaded is not None
        assert loaded.id == "forge-test-001"

    def test_load_nonexistent(self):
        assert load_plan("nope") is None

class TestListPlans:
    def test_empty(self):
        assert list_plans() == []

    def test_lists_saved(self):
        save_plan(_make_plan("a", "A"))
        save_plan(_make_plan("b", "B"))
        ids = [p["id"] for p in list_plans()]
        assert "a" in ids and "b" in ids

class TestActivePlan:
    def test_no_active_initially(self):
        assert get_active_plan() is None

    def test_set_and_get(self):
        save_plan(_make_plan())
        set_active_plan("forge-test-001")
        assert get_active_plan().id == "forge-test-001"

    def test_clear(self):
        save_plan(_make_plan())
        set_active_plan("forge-test-001")
        clear_active_plan()
        assert get_active_plan() is None


@pytest.fixture()
def _use_tmp_obsidian(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("core.forge.persistence._obsidian_forge_dir", lambda: tmp_path / "obsidian" / "Forge")
    return tmp_path / "obsidian" / "Forge"


class TestObsidianExport:
    def test_creates_plan_markdown(self, _use_tmp_obsidian):
        path = export_to_obsidian(_make_plan())
        assert path.exists() and path.suffix == ".md"

    def test_frontmatter_contains_tags(self, _use_tmp_obsidian):
        plan = _make_plan()
        plan.status = ForgeStatus.COMPLETED
        content = export_to_obsidian(plan).read_text()
        assert "tags:" in content and "forge" in content

    def test_contains_prompt(self, _use_tmp_obsidian):
        content = export_to_obsidian(_make_plan()).read_text()
        assert "test" in content

    def test_contains_approaches(self, _use_tmp_obsidian):
        plan = _make_plan()
        plan.approaches = [ExplorerApproach(explorer=ExplorerLens.PRAGMATIC, summary="Fast and simple")]
        content = export_to_obsidian(plan).read_text()
        assert "Pragmatic" in content and "Fast and simple" in content

    def test_contains_critic(self, _use_tmp_obsidian):
        plan = _make_plan()
        plan.critic = CriticVerdict(
            synthesis={"a": ["Good"]},
            rejected_elements=[RejectedElement(element="Bad", reason="Complex")],
            risks=[IdentifiedRisk(risk="Down", mitigation="Blue-green", severity=RiskSeverity.MEDIUM)],
            confidence=0.75,
        )
        content = export_to_obsidian(plan).read_text()
        assert "0.75" in content and "Bad" in content and "Down" in content


class TestPatternExtraction:
    def test_extracts_from_completed(self, _use_tmp_obsidian):
        plan = _make_plan()
        plan.status = ForgeStatus.COMPLETED
        plan.plan_phases = [PlanPhase(name="A", department="dev"), PlanPhase(name="B", department="ops")]
        assert len(extract_patterns(plan)) >= 1

    def test_no_patterns_from_draft(self, _use_tmp_obsidian):
        plan = _make_plan()
        plan.status = ForgeStatus.DRAFT
        assert extract_patterns(plan) == []

    def test_patterns_saved_to_obsidian(self, _use_tmp_obsidian):
        plan = _make_plan()
        plan.status = ForgeStatus.COMPLETED
        plan.plan_phases = [PlanPhase(name="A", department="dev"), PlanPhase(name="B", department="dev")]
        extract_patterns(plan)
        assert (_use_tmp_obsidian / "Patterns").exists()

    def test_load_patterns_empty(self, _use_tmp_obsidian):
        assert load_patterns() == []
