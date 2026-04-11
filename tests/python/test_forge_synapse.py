import pytest
from core.synapse.layers import ForgeContextLayer, PromptContext

@pytest.fixture(autouse=True)
def _use_tmp_plans(tmp_path, monkeypatch):
    monkeypatch.setattr("core.forge.persistence._plans_dir", lambda: tmp_path / "plans")
    monkeypatch.setattr("core.forge.persistence._active_link", lambda: tmp_path / "plans" / "active.yaml")

class TestForgeContextLayer:
    def test_layer_id(self):
        assert ForgeContextLayer().id == "L8"
    def test_layer_name(self):
        assert ForgeContextLayer().name == "ForgeContext"
    def test_no_cache(self):
        assert ForgeContextLayer().cache_ttl == 0
    def test_priority(self):
        assert ForgeContextLayer().priority == 80
    def test_empty_no_active(self):
        result = ForgeContextLayer().compute(PromptContext(user_input="test"))
        assert result.tag == "" and result.content == ""
    def test_returns_context_with_active_plan(self, tmp_path):
        from core.forge.schema import ForgePlan, ForgeContext as FCtx, CriticVerdict, RejectedElement, IdentifiedRisk, RiskSeverity
        from core.forge.persistence import save_plan, set_active_plan
        plan = ForgePlan(id="forge-syn", name="Syn Test",
            context=FCtx(repo="t", branch="m", commit_at_forge="a", arkaos_version="2.14.0", prompt="t"),
            critic=CriticVerdict(synthesis={"a": ["dec-1"]}, rejected_elements=[RejectedElement(element="bad", reason="no")],
                risks=[IdentifiedRisk(risk="risk-1", mitigation="m", severity=RiskSeverity.LOW)], confidence=0.8))
        save_plan(plan)
        set_active_plan("forge-syn")
        result = ForgeContextLayer().compute(PromptContext(user_input="test"))
        assert "forge-syn" in result.tag and result.content != ""
