"""Tests for runtime model catalog + role descriptions (Models page)."""

from __future__ import annotations

from core.runtime import runtime_models
from core.runtime.model_router import QUALITY_ROLES, ROLE_DESCRIPTIONS, role_description


class TestRuntimeModels:
    def test_claude_code_lists_the_current_models(self):
        models = runtime_models.models_for_runtime("claude-code")
        labels = {m["label"] for m in models}
        # Runtime Sync 2026-09-03: exactly these three lanes — the weakest
        # is Sonnet 5, and no previous-generation label survives.
        assert sorted(labels) == ["Fable 5.1", "Opus 5", "Sonnet 5"]

    def test_fable_is_the_full_id_and_flagged_most_capable(self):
        fable = next(
            m for m in runtime_models.CLAUDE_CODE_MODELS if m["label"] == "Fable 5.1"
        )
        assert fable["value"] == "claude-fable-5-1"
        assert fable["tier"] == "frontier"
        assert "most capable" in fable["note"]

    def test_every_model_has_value_label_tier_note(self):
        for m in runtime_models.CLAUDE_CODE_MODELS:
            assert m["value"] and m["label"] and m["tier"] and m["note"]

    def test_unknown_runtime_returns_empty(self):
        assert runtime_models.models_for_runtime("codex") == []
        assert runtime_models.models_for_runtime("nonexistent") == []

    def test_detect_returns_runtime_id_and_models(self):
        runtime_id, models = runtime_models.detect_runtime_models()
        assert isinstance(runtime_id, str) and runtime_id
        assert isinstance(models, list)


class TestRoleDescriptions:
    def test_every_configured_role_has_a_description(self):
        for role in QUALITY_ROLES | {"execution", "mechanical"}:
            assert role_description(role), f"{role} missing description"

    def test_execution_explains_what_it_does(self):
        # The operator specifically didn't know what "execution" meant.
        desc = role_description("execution")
        assert "Implementation" in desc
        assert "code" in desc.lower()

    def test_unknown_role_description_is_empty(self):
        assert role_description("no-such-role") == ""

    def test_descriptions_cover_all_default_roles(self):
        assert set(ROLE_DESCRIPTIONS) >= (QUALITY_ROLES | {"execution", "mechanical"})
