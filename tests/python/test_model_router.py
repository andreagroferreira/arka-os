"""Tests for the Model Fabric router (PR-A, Excellence Reform epic)."""

from pathlib import Path

import pytest
import yaml

from core.runtime import model_router
from core.runtime.model_router import (
    QUALITY_ROLES,
    RoleChoice,
    ensure_user_config,
    load_config,
    resolve,
    resolve_all,
    set_role,
)


@pytest.fixture
def user_path(tmp_path) -> Path:
    return tmp_path / "models.yaml"


class TestLoadProvenance:
    def test_missing_user_file_falls_back_to_packaged(self, user_path):
        config, source = load_config(user_path)
        assert source == "packaged"
        assert "review" in config.roles

    def test_user_file_wins(self, user_path):
        user_path.write_text(yaml.safe_dump({
            "version": 1,
            "aliases": {"ollama": {"best": "kimi-k2.6"}},
            "roles": {"review": {"provider": "ollama", "model": "best",
                                 "effort": "max"}},
        }), encoding="utf-8")
        config, source = load_config(user_path)
        assert source == "user"
        assert config.roles["review"].provider == "ollama"

    def test_corrupt_user_file_falls_back(self, user_path):
        user_path.write_text("{not yaml: [", encoding="utf-8")
        _, source = load_config(user_path)
        assert source == "packaged"

    def test_builtin_when_nothing_readable(self, user_path, monkeypatch):
        monkeypatch.setattr(
            model_router, "_packaged_config_path",
            lambda: Path("/nonexistent/models.yaml"),
        )
        config, source = load_config(user_path)
        assert source == "builtin"
        assert config.roles["review"].model == "best"


class TestQualityFirstPosture:
    def test_packaged_quality_roles_run_best_at_max(self, user_path):
        for role in QUALITY_ROLES:
            item = resolve(role, user_path)
            assert item.model == "fable", role
            assert item.effort == "max", role

    def test_mechanical_is_the_only_economy_tier(self, user_path):
        assert resolve("mechanical", user_path).model == "sonnet"
        assert resolve("execution", user_path).model == "sonnet"

    def test_unknown_role_never_lands_on_cheap_tier(self, user_path):
        item = resolve("some-new-role", user_path)
        assert item.model in ("fable", "opus", "sonnet")
        assert item.model != "haiku"

    def test_builtin_fallback_keeps_quality_posture(self, user_path, monkeypatch):
        monkeypatch.setattr(
            model_router, "_packaged_config_path",
            lambda: Path("/nonexistent/models.yaml"),
        )
        # Runtime Sync 2026-09-03: the builtin fallback's `best` is `fable`.
        assert resolve("design", user_path).model == "fable"


class TestAliasResolution:
    def test_alias_resolves_per_provider(self, user_path):
        user_path.write_text(yaml.safe_dump({
            "aliases": {"ollama": {"best": "kimi-k2.6"}},
            "roles": {"judge-x": {"provider": "ollama", "model": "best",
                                  "effort": "max"}},
        }), encoding="utf-8")
        assert resolve("judge-x", user_path).model == "kimi-k2.6"

    def test_literal_model_passes_through(self, user_path):
        user_path.write_text(yaml.safe_dump({
            "roles": {"review": {"provider": "openrouter",
                                 "model": "deepseek/deepseek-v4-pro",
                                 "effort": "max"}},
        }), encoding="utf-8")
        assert resolve("review", user_path).model == "deepseek/deepseek-v4-pro"

    def test_unmapped_alias_keeps_name_visible(self, user_path):
        user_path.write_text(yaml.safe_dump({
            "roles": {"review": {"provider": "mystery", "model": "best",
                                 "effort": "max"}},
        }), encoding="utf-8")
        # No aliases for "mystery" — surface the alias, never empty-string.
        assert resolve("review", user_path).model == "best"


class TestUserConfigLifecycle:
    def test_ensure_creates_from_packaged(self, user_path):
        path = ensure_user_config(user_path)
        assert path.is_file()
        assert "Model Fabric" in path.read_text(encoding="utf-8")

    def test_ensure_is_idempotent(self, user_path):
        ensure_user_config(user_path)
        marker = "# custom-edit"
        user_path.write_text(
            user_path.read_text(encoding="utf-8") + f"\n{marker}\n", encoding="utf-8")
        ensure_user_config(user_path)
        assert marker in user_path.read_text(encoding="utf-8")

    def test_set_role_roundtrip(self, user_path):
        item = set_role("review", "anthropic/best", effort="max",
                        user_path=user_path)
        assert item.provider == "anthropic"
        assert item.model == "claude-fable-5-1"
        again, source = load_config(user_path)
        assert source == "user"
        assert again.roles["review"].provider == "anthropic"

    def test_set_role_rejects_malformed_target(self, user_path):
        with pytest.raises(ValueError, match="provider/model"):
            set_role("review", "just-a-model", user_path=user_path)

    def test_set_role_rejects_bad_effort_without_writing(self, user_path):
        with pytest.raises(ValueError):
            set_role("review", "runtime/best", effort="extreme",
                     user_path=user_path)

    def test_set_role_preserves_other_roles(self, user_path):
        set_role("mechanical", "ollama/qwen3:8b", effort="low",
                 user_path=user_path)
        assert resolve("review", user_path).model == "fable"


class TestValidation:
    def test_effort_is_validated(self):
        with pytest.raises(ValueError):
            RoleChoice(provider="runtime", model="best", effort="turbo")

    def test_resolve_all_covers_every_configured_role(self, user_path):
        roles = {item.role for item in resolve_all(user_path)}
        assert roles >= QUALITY_ROLES
        assert "mechanical" in roles


class TestLegacyModelIds:
    """Runtime Sync 2026-09-03: stale pins resolve to the current lane, the
    file is never rewritten, and the operator is told once per process."""

    def test_legacy_ids_resolve_to_current_lane(self, user_path, capsys, monkeypatch):
        import yaml as _yaml

        # The once-per-process notice set is module state; an earlier test
        # (or the operator's real models.yaml) may have consumed it (QG B2).
        monkeypatch.setattr(model_router, "_LEGACY_NOTICED", set())

        user_path.write_text(_yaml.safe_dump({
            "roles": {
                "review": {"provider": "anthropic", "model": "claude-opus-4-8", "effort": "max"},
                "strategy": {"provider": "runtime", "model": "claude-fable-5", "effort": "max"},
                "mechanical": {"provider": "runtime", "model": "haiku", "effort": "low"},
            },
        }), encoding="utf-8")
        before = user_path.read_bytes()
        assert resolve("review", user_path).model == "claude-opus-5"
        assert resolve("strategy", user_path).model == "claude-fable-5-1"
        assert resolve("mechanical", user_path).model == "sonnet"
        assert user_path.read_bytes() == before, "the operator's file is never rewritten"
        err = capsys.readouterr().err
        assert "legacy model 'claude-opus-4-8'" in err
        # one notice per id per process
        resolve("review", user_path)
        assert capsys.readouterr().err == ""

    def test_current_ids_pass_through(self):
        assert model_router.normalise_model_id("claude-fable-5-1") == "claude-fable-5-1"
        assert model_router.normalise_model_id("sonnet") == "sonnet"
        assert model_router.normalise_model_id("kimi-k2.7-code:cloud") == "kimi-k2.7-code:cloud"


class TestLegacyPinsSurface:
    def test_legacy_pins_lists_every_stale_role(self, user_path):
        import yaml as _yaml

        user_path.write_text(_yaml.safe_dump({
            "roles": {
                "review": {"provider": "anthropic", "model": "claude-opus-4-8", "effort": "max"},
                "execution": {"provider": "runtime", "model": "sonnet", "effort": "high"},
            },
        }), encoding="utf-8")
        assert model_router.legacy_pins(user_path) == [
            ("review", "claude-opus-4-8", "claude-opus-5"),
        ]
