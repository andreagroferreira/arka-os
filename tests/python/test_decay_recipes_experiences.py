"""Tests for F1-C2 — decay in recipe matching + agent experiences."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.governance.agent_experiences import Experience
from core.knowledge.recipes import Recipe, RecipeProvenance
from core.synapse import recipe_layer
from core.synapse.agent_experiences_layer import _split_by_decay, format_experiences

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def decay_on(monkeypatch, tmp_path):
    from core.shared import decay

    monkeypatch.setattr(decay, "_CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.delenv("ARKA_KNOWLEDGE_DECAY", raising=False)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def _recipe(slug: str, captured_days_ago: float, keywords: list[str]) -> Recipe:
    return Recipe(
        slug=slug, name=f"Recipe {slug}",
        problem="a validated build of this exact feature",
        stack=["laravel"], feature_keywords=keywords,
        provenance=RecipeProvenance(
            source_project="[CLIENT-1]", qg_verdict="APPROVED",
            qg_verdict_ts=_iso(captured_days_ago),
            captured_at=_iso(captured_days_ago),
        ),
        sanitized=True,
    )


def _exp(days_ago: float) -> Experience:
    return Experience(
        ts=_iso(days_ago), agent_id="frontend-dev", session_id="s",
        context=f"lesson from {days_ago:.0f}d ago", verdict="REJECTED",
        blockers=["B1"], patterns=["p"], fix_applied=None,
        references=[], tags=[],
    )


# ─── Recipe decay ──────────────────────────────────────────────────────


def test_stale_recipe_fades_from_matching(monkeypatch):
    monkeypatch.setattr(
        recipe_layer, "list_recipes",
        lambda: [_recipe("fresh", 2, ["payment"]),
                 _recipe("ancient", 400, ["payment"])],
    )
    matches = recipe_layer._match_recipes(["payment"], limit=3)
    assert [r.slug for r in matches] == ["fresh"]


def test_decayed_weight_breaks_overlap_ties(monkeypatch):
    """Same overlap: the fresher capture must rank first."""
    monkeypatch.setattr(
        recipe_layer, "list_recipes",
        lambda: [_recipe("older", 59, ["payment"]),
                 _recipe("newer", 1, ["payment"])],
    )
    matches = recipe_layer._match_recipes(["payment"], limit=3)
    assert [r.slug for r in matches] == ["newer", "older"]


def test_higher_overlap_still_beats_mild_age(monkeypatch):
    """Decay tempers ranking; it must not let one keyword of freshness
    beat two keywords of genuine match at moderate age."""
    monkeypatch.setattr(
        recipe_layer, "list_recipes",
        lambda: [_recipe("rich-match", 30, ["payment", "retry"]),
                 _recipe("thin-match", 1, ["payment"])],
    )
    matches = recipe_layer._match_recipes(["payment", "retry"], limit=3)
    assert matches[0].slug == "rich-match"  # 2*0.707 > 1*0.99


def test_recipe_decay_disabled_restores_old_ranking(monkeypatch):
    monkeypatch.setenv("ARKA_KNOWLEDGE_DECAY", "0")
    monkeypatch.setattr(
        recipe_layer, "list_recipes",
        lambda: [_recipe("ancient", 400, ["payment"])],
    )
    matches = recipe_layer._match_recipes(["payment"], limit=3)
    assert [r.slug for r in matches] == ["ancient"]


# ─── Experience decay ──────────────────────────────────────────────────


def test_split_partitions_fresh_and_faded(monkeypatch):
    fresh_exp, old_exp = _exp(2), _exp(400)
    fresh, faded = _split_by_decay([fresh_exp, old_exp])
    assert [e.context for e in fresh] == [fresh_exp.context]
    assert faded == 1


def test_split_disabled_keeps_everything(monkeypatch):
    monkeypatch.setenv("ARKA_KNOWLEDGE_DECAY", "0")
    fresh, faded = _split_by_decay([_exp(400)])
    assert len(fresh) == 1 and faded == 0


def test_format_appends_faded_count():
    text = format_experiences("frontend-dev", [_exp(1)], faded_count=7)
    assert "+7 older lesson(s) faded from injection" in text
    assert "history kept on disk" in text


def test_format_without_faded_has_no_counter():
    text = format_experiences("frontend-dev", [_exp(1)])
    assert "faded from injection" not in text


def test_layer_all_faded_emits_count_tag_only(monkeypatch, tmp_path):
    from core.governance import agent_experiences as ae
    from core.synapse.agent_experiences_layer import AgentExperiencesLayer
    from core.synapse.layers import PromptContext

    monkeypatch.setattr(ae, "AGENTS_ROOT", tmp_path / "agents")
    ae.record_experience(_exp(400))
    result = AgentExperiencesLayer().compute(
        PromptContext(user_input="[arka:dispatch] paulo -> frontend-dev")
    )
    assert result.content == ""
    assert "faded:1" in result.tag  # history acknowledged, zero token rent
