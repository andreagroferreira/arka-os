"""Tests for core.synapse.recipe_layer (Interaction Reform PR8, L7.6)."""

from __future__ import annotations

import json

import pytest

from core.knowledge.recipes import capture_recipe, Recipe, RecipeProvenance
from core.synapse.layers import PromptContext
from core.synapse.recipe_layer import RecipeLayer, _match_recipes


@pytest.fixture(autouse=True)
def _isolated_recipes(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_RECIPES_DIR", str(tmp_path / "recipes"))
    config = tmp_path / "redaction.json"
    config.write_text(json.dumps({"clients": []}), encoding="utf-8")
    # Empty client list: sanitizer would refuse (fail-closed). Seed one
    # so capture can run in the test; it just never matches.
    config.write_text(json.dumps({"clients": ["zzz-never"]}), encoding="utf-8")
    self_config = config
    monkeypatch.setattr(
        "core.governance.leak_scanner._DEFAULT_CONFIG_PATH", self_config
    )


def _seed(slug: str, keywords: list[str], stack: list[str]) -> None:
    recipe = Recipe(
        slug=slug,
        name=f"{slug} recipe",
        problem="A validated build worth reusing across projects.",
        stack=stack,
        feature_keywords=keywords,
        provenance=RecipeProvenance(
            source_project="arkaos",
            qg_verdict="APPROVED",
            qg_verdict_ts="2026-07-09T00:00:00+00:00",
            captured_at="2026-07-09T00:00:00+00:00",
        ),
    )
    capture_recipe(recipe, narrative="how to apply", reference_files={})


class TestMatching:
    def test_no_recipes_returns_empty(self):
        assert _match_recipes(["auth", "login"], 3) == []

    def test_keyword_overlap_matches(self):
        _seed("laravel-auth", ["auth", "login", "token"], ["laravel"])
        matches = _match_recipes(["preciso", "auth", "flow"], 3)
        assert [r.slug for r in matches] == ["laravel-auth"]

    def test_stack_counts_toward_overlap(self):
        _seed("nuxt-dash", ["dashboard"], ["nuxt", "vue"])
        matches = _match_recipes(["nuxt", "widget"], 3)
        assert [r.slug for r in matches] == ["nuxt-dash"]

    def test_ranks_by_overlap_then_slug(self):
        _seed("aaa", ["auth"], ["laravel"])
        _seed("bbb", ["auth", "login", "token"], ["laravel"])
        matches = _match_recipes(["auth", "login", "token", "laravel"], 3)
        assert [r.slug for r in matches] == ["bbb", "aaa"]

    def test_equal_overlap_ties_break_on_slug(self):
        # Same overlap (1 keyword each) → deterministic slug order.
        _seed("zzz-recipe", ["auth"], ["laravel"])
        _seed("aaa-recipe", ["auth"], ["laravel"])
        matches = _match_recipes(["auth"], 3)
        assert [r.slug for r in matches] == ["aaa-recipe", "zzz-recipe"]

    def test_limit_respected(self):
        for i in range(5):
            _seed(f"r{i}", ["auth"], ["laravel"])
        assert len(_match_recipes(["auth"], 2)) == 2


class TestLayer:
    def test_layer_identity(self):
        layer = RecipeLayer()
        assert layer.id == "L7.6"
        assert layer.priority == 76
        assert layer.input_sensitive is True

    def test_empty_prompt_no_tag(self):
        result = RecipeLayer().compute(PromptContext(user_input=""))
        assert result.tag == ""

    def test_no_match_emits_recipes_none(self):
        _seed("x", ["auth"], ["laravel"])
        result = RecipeLayer().compute(
            PromptContext(user_input="something about frontend widgets")
        )
        assert result.tag == "[recipes:none]"

    def test_match_injects_recipes_tag_and_paths(self):
        _seed("laravel-auth", ["auth", "login"], ["laravel"])
        result = RecipeLayer().compute(
            PromptContext(user_input="preciso de auth login no projeto")
        )
        assert result.tag == "[recipes:1]"
        assert "~/.arkaos/recipes/laravel-auth/" in result.content
        assert "adapt via the normal flow" in result.content
