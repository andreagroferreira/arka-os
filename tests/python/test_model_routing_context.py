"""Tests for the Model Fabric → orchestrator consumption bridge."""

from __future__ import annotations

import pytest

from core.runtime import model_routing_context as mrc


@pytest.fixture
def user_models(tmp_path, monkeypatch):
    import yaml
    from core.runtime import model_router
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump({
        "aliases": {"runtime": {"best": "opus", "default": "sonnet", "fast": "haiku"}},
        "roles": {
            "review": {"provider": "runtime", "model": "best", "effort": "max"},
            "execution": {"provider": "runtime", "model": "default", "effort": "high"},
            "mechanical": {"provider": "runtime", "model": "fast", "effort": "low"},
        },
    }))
    monkeypatch.setattr(model_router, "USER_CONFIG_PATH", path)
    return path


class TestRoutingSummary:
    def test_summary_lists_resolved_models(self, user_models):
        summary = mrc.routing_summary()
        assert "review=runtime/opus@max" in summary
        assert "execution=runtime/sonnet@high" in summary
        assert "mechanical=runtime/haiku@low" in summary

    def test_summary_empty_when_config_unreadable(self, monkeypatch):
        from core.runtime import model_router
        monkeypatch.setattr(
            model_router, "resolve_all",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert mrc.routing_summary() == ""


class TestRoutingDirective:
    def test_directive_carries_the_summary_and_instruction(self, user_models):
        directive = mrc.routing_directive()
        assert "[ARKA:MODEL-FABRIC]" in directive
        assert "execution=runtime/sonnet@high" in directive
        assert "OVERRIDES" in directive
        assert "excellence-mandate" in directive

    def test_directive_has_no_backticks(self, user_models):
        # The SessionStart hook embeds this in $(echo -e "$MSG"); a
        # backtick would trigger shell command substitution.
        assert "`" not in mrc.routing_directive()

    def test_directive_empty_when_no_config(self, monkeypatch):
        monkeypatch.setattr(mrc, "routing_summary", lambda: "")
        assert mrc.routing_directive() == ""


class TestAgentRoleHints:
    def test_quality_agents_map_to_quality_roles(self):
        assert mrc.AGENT_ROLE_HINTS["architect"] == "architecture"
        assert mrc.AGENT_ROLE_HINTS["marta-cqo"] == "quality_gate"
        assert mrc.AGENT_ROLE_HINTS["frontend-dev"] == "design"

    def test_design_production_agents_map_to_design(self):
        # PR-D4: every agent that produces visual output routes via the
        # design role (QUALITY_ROLES → best model under Model Fabric).
        for slug in (
            "visual-designer",
            "ux-designer",
            "motion-designer",
            "creative-director",
            "scriptwriter",
            "video-producer",
        ):
            assert mrc.AGENT_ROLE_HINTS[slug] == "design"

    def test_mechanical_agent_maps_to_mechanical(self):
        assert mrc.AGENT_ROLE_HINTS["analyst"] == "mechanical"
