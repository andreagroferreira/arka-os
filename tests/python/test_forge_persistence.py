from pathlib import Path
import pytest
import yaml
from core.forge.schema import ForgePlan, ForgeContext, ForgeStatus
from core.forge.persistence import save_plan, load_plan, list_plans, get_active_plan, set_active_plan, clear_active_plan

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
