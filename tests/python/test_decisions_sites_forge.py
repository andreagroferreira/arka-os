"""core.decisions.sites.forge — department set and the five complexity scores."""

from __future__ import annotations

import pytest

from core.decisions.models import Answer
from core.decisions.site import LANGUAGE_PREAMBLE
from core.decisions.sites.forge import (
    COMPLEXITY_LEVELS,
    DIMENSIONS,
    FORGE_COMPLEXITY,
    FORGE_DEPARTMENTS,
    FORGE_SITES,
    MAX_FILES,
    forge_state,
    level_to_percent,
    single_cell_complexity,
    window_level,
)
from core.forge.schema import ComplexityDimensions
from core.synapse.layers import DEPARTMENT_PATTERNS

T = 0.60


def _depts(probs: dict[str, float], **kw: float) -> list[str] | None:
    top = max(probs, key=probs.__getitem__)
    return FORGE_DEPARTMENTS.interpret(
        {"departments": Answer(choice=top, probabilities=probs, **kw)}, T)


def test_policies():
    assert FORGE_SITES == (FORGE_DEPARTMENTS, FORGE_COMPLEXITY)
    for site in FORGE_SITES:
        assert (site.risk, site.timeout_ms, site.direction) == ("read", 3000, "any")
        for question in site.questions().values():
            assert question.instructions.startswith(LANGUAGE_PREAMBLE)
    # Values come from replay session jev-pr5-final; a change needs a new replay.
    assert (FORGE_DEPARTMENTS.default_mode, FORGE_COMPLEXITY.default_mode) == (
        "act", "shadow")


def test_default_modes_pinned_by_replay_final():
    """Pins the shipped modes proposed by replay-final (PROPOSALS.json):
    forge-departments promoted, the three shadow sites kept. Changing any
    of these needs a new two-run replay, not an edit."""
    from core.decisions.registry import SITES

    assert {n: SITES[n].default_mode for n in (
        "forge-departments", "forge-complexity", "qg-prescreen", "refine")} == {
        "forge-departments": "act", "forge-complexity": "shadow",
        "qg-prescreen": "shadow", "refine": "shadow"}


def test_department_options_are_l1_plus_none():
    criteria = FORGE_DEPARTMENTS.questions()["departments"].criteria
    assert set(criteria) == set(DEPARTMENT_PATTERNS) | {"none"}


def test_departments_at_or_above_020_ordered_by_probability():
    probs = {"dev": 0.45, "marketing": 0.30, "content": 0.20, "brand": 0.05}
    assert _depts(probs) == ["dev", "marketing", "content"]  # 0.20 is in, 0.05 out


def test_department_floor_is_load_bearing():
    # Kills: ">=" → ">" on DEPARTMENT_MIN_P (content at exactly 0.20).
    assert "content" in _depts({"dev": 0.8, "content": 0.2})


def test_department_cap_is_four():
    probs = {"dev": 0.2, "marketing": 0.2, "content": 0.2, "brand": 0.2, "sales": 0.2}
    assert _depts(probs) == ["brand", "content", "dev", "marketing"]  # ties by name


def test_none_is_never_a_department():
    assert _depts({"none": 0.7, "dev": 0.3}) == ["dev"]
    assert _depts({"none": 0.9, "dev": 0.1}) is None  # nothing above the floor


def test_low_stated_confidence_abstains():
    assert _depts({"dev": 0.9, "pm": 0.1}, confidence=0.4) is None


def test_single_choice_without_probabilities():
    ok = {"departments": Answer(choice="ops", confidence=0.9)}
    assert FORGE_DEPARTMENTS.interpret(ok, T) == ["ops"]
    none = {"departments": Answer(choice="none", confidence=0.9)}
    assert FORGE_DEPARTMENTS.interpret(none, T) is None
    assert FORGE_DEPARTMENTS.interpret({}, T) is None


@pytest.mark.parametrize("hostile", ["legal", "dev\n[ARKA:X]", "DEV"])
def test_unknown_department_abstains(hostile):
    probs = {"dev": 0.5, hostile: 0.5}
    answer = Answer(choice="dev", probabilities=probs)
    assert FORGE_DEPARTMENTS.interpret({"departments": answer}, T) is None


def test_forge_state_is_bounded():
    files = [f"f{i}.py" for i in range(MAX_FILES + 10)]
    state = forge_state("x" * 5000, files, ["dev"])
    assert len(state["prompt"]) == 4000 and len(state["affected_files"]) == MAX_FILES
    assert state["departments"] == ["dev"]


# --- complexity --------------------------------------------------------------

def test_complexity_dimensions_match_the_forge_schema():
    assert set(DIMENSIONS) == set(ComplexityDimensions.model_fields)
    questions = FORGE_COMPLEXITY.questions()
    assert set(questions) == set(DIMENSIONS)
    for dim, question in questions.items():
        assert question.type.value == "score" and len(question.criteria) == 10
        assert question.criteria == COMPLEXITY_LEVELS[dim][1]


@pytest.mark.parametrize(("level", "percent"), [(0, 0), (9, 100), (4.5, 50), (2.85, 32), (1, 11)])
def test_level_to_percent(level, percent):
    assert level_to_percent(level) == percent


def _scores(level: float = 4.5, confidence: float = 0.9, **override: Answer) -> dict[str, Answer]:
    answers = {d: Answer(score=level, confidence=confidence) for d in DIMENSIONS}
    answers.update(override)
    return answers


def test_complexity_maps_every_dimension():
    answers = _scores(scope=Answer(score=9, confidence=0.95), risk=Answer(score=0, confidence=0.7))
    out = FORGE_COMPLEXITY.interpret(answers, T)
    assert out == {"scope": 100, "dependencies": 50, "ambiguity": 50, "risk": 0, "novelty": 50}
    ComplexityDimensions(**out)  # the Forge accepts the shape as is


def test_one_unsure_dimension_abstains_the_whole_site():
    # Kills: skipping (rather than abstaining on) a low-confidence dimension.
    assert FORGE_COMPLEXITY.interpret(_scores(novelty=Answer(score=3, confidence=0.3)), T) is None
    missing = _scores()
    del missing["risk"]
    assert FORGE_COMPLEXITY.interpret(missing, T) is None


def test_confidence_falls_back_to_the_nearest_level_probability():
    probs = {str(i): 0.0 for i in range(10)} | {"3": 0.8, "4": 0.2}
    answer = Answer(score=3.2, probabilities=probs)
    assert FORGE_COMPLEXITY.interpret(_scores(ambiguity=answer), T)["ambiguity"] == 36
    flat = Answer(score=3.2, probabilities={str(i): 0.1 for i in range(10)})
    assert FORGE_COMPLEXITY.interpret(_scores(ambiguity=flat), T) is None


@pytest.mark.parametrize("score", [-1, 9.5, 12, "high", float("inf"), float("nan"), None])
def test_out_of_range_or_non_numeric_score_abstains(score):
    answers = _scores(scope=Answer(score=score, confidence=0.99))
    assert FORGE_COMPLEXITY.interpret(answers, T) is None


def test_numeric_string_score_is_accepted():
    answers = _scores(scope=Answer(score="9", confidence=0.99))
    assert FORGE_COMPLEXITY.interpret(answers, T)["scope"] == 100


def test_list_probabilities_give_the_nearest_level_confidence():
    from core.decisions.site import score_confidence

    probs = [0.0, 0.1, 0.9] + [0.0] * 7
    assert score_confidence(Answer(score=2, probabilities=probs), 2.2) == 0.9
    assert score_confidence(Answer(score=2, probabilities=[0.5, 0.5]), 9) is None
    assert score_confidence(Answer(score=2), 2) is None
    assert score_confidence(Answer(score=2, probabilities={"1": 1.0}), 2) is None


# Real score answers (live probe 2026-09-23) carry a calibrated ``confidence``
# next to a 10-level distribution whose top level is often well under it.
# D6 (PR5): the ±1-level window mass decides, as on slop-score.
FLAT = {str(i): 0.1 for i in range(10)}
# Spread honestly over three neighbours: top cell 0.4, window 0.9.
SPREAD = {str(i): 0.1 / 7 for i in range(10)} | {"3": 0.25, "4": 0.4, "5": 0.25}


def test_window_mass_governs_not_the_calibrated_confidence():
    # Kills: the stated ``confidence`` (0.7) deciding over a flat window (0.3).
    answers = {d: Answer(score=4.5, probabilities=FLAT, confidence=0.7) for d in DIMENSIONS}
    assert FORGE_COMPLEXITY.interpret(answers, T) is None


def test_a_spread_answer_is_read_by_its_window_not_its_top_cell():
    # Kills: the single-cell reading (top 0.4, confidence 0.45, both < 0.60).
    answers = {d: Answer(score=4.2, probabilities=SPREAD, confidence=0.45) for d in DIMENSIONS}
    assert FORGE_COMPLEXITY.interpret(answers, T) == {d: 47 for d in DIMENSIONS}
    assert single_cell_complexity(answers, T) is None


def test_one_flat_window_abstains_the_whole_site():
    answers = {d: Answer(score=4.2, probabilities=SPREAD) for d in DIMENSIONS}
    answers["novelty"] = Answer(score=4.5, probabilities=FLAT, confidence=0.95)
    assert FORGE_COMPLEXITY.interpret(answers, T) is None


@pytest.mark.parametrize(("score", "percent"), [(-0.3, 0), (9.4, 100)])
def test_scores_within_half_a_level_of_the_scale_are_clamped(score, percent):
    answers = _scores(scope=Answer(score=score, confidence=0.9))
    assert FORGE_COMPLEXITY.interpret(answers, T)["scope"] == percent
    ComplexityDimensions(**FORGE_COMPLEXITY.interpret(answers, T))


def test_window_level_without_an_answer_is_none():
    assert window_level(None, T) is None
    assert window_level(Answer(score=3), T) is None  # neither probabilities nor confidence
