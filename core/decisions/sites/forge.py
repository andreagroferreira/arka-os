"""Forge sites — the inputs of the Forge complexity score.

* ``forge-departments`` — which departments a plan needs (read). Every
  department whose probability reaches :data:`DEPARTMENT_MIN_P` joins the
  set, most probable first, capped at :data:`MAX_DEPARTMENTS`.
* ``forge-complexity`` — the five dimensions of
  ``core/forge/complexity.py`` as 10-level scores, each mapped onto the
  heuristic's 0-100 scale; weights and ``determine_tier`` stay untouched.
  Each score is read with the shared ±1-level window (PR5 D6).

Level criteria mirror the heuristics in ``core/forge/complexity.py`` so
Jev and the regex score the same thing.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from core.decisions.models import Answer, Question, QuestionType
from core.decisions.site import (
    LANGUAGE_PREAMBLE,
    Site,
    interpret_choice,
    interpret_score,
    window_confidence,
)
from core.decisions.sites.prompt import NO_DEPARTMENT, route_options

DEPARTMENT_MIN_P = 0.20
MAX_DEPARTMENTS = 4
SCORE_LEVELS = 10
MAX_PROMPT_CHARS = 4000
MAX_FILES = 50


def forge_state(
    prompt: str, affected_files: Sequence[str], departments: Sequence[str]
) -> dict[str, Any]:
    """The state both Forge sites read: the request and its estimated reach."""
    return {
        "prompt": prompt[:MAX_PROMPT_CHARS],
        "affected_files": [str(f) for f in affected_files][:MAX_FILES],
        "departments": [str(d) for d in departments][:MAX_DEPARTMENTS * 4],
    }


def _instructions(body: str) -> str:
    return f"{LANGUAGE_PREAMBLE} {body}"


# --- forge-departments -------------------------------------------------------

def _departments_questions() -> dict[str, Question]:
    return {"departments": Question(type=QuestionType.CHOICE, instructions=_instructions(
        "The state holds a request for the ArkaOS Forge planner. Which departments "
        "does the plan need? Spread the probability across the departments that apply, "
        "in proportion to how much of the work each one owns (a launch may need dev, "
        "marketing and content at once); judge by intent, not keywords."
    ), criteria=route_options())}


def _departments_interpret(answers: dict[str, Answer], threshold: float) -> list[str] | None:
    # Departments with p ≥ 0.20, most probable first; "none" never counts.
    # A plan always needs a department, so "none" (or nothing above the
    # floor) abstains and the keyword estimate acts. Without probabilities
    # the single choice stands in when its confidence reaches the
    # threshold; with them, a stated confidence below it abstains.
    answer = answers.get("departments")
    if answer is None or (answer.confidence is not None and answer.confidence < threshold):
        return None
    if isinstance(answer.probabilities, dict):
        return _departments_from(answer.probabilities)
    chosen = interpret_choice(answer, threshold)
    return None if chosen in (None, NO_DEPARTMENT) else [str(chosen)]


def _departments_from(probs: dict[str, float]) -> list[str] | None:
    ranked = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))
    picked = [d for d, p in ranked if d != NO_DEPARTMENT and p >= DEPARTMENT_MIN_P]
    return picked[:MAX_DEPARTMENTS] or None


# Promoted shadow -> act by replay session jev-pr5-final (n=34, 3 s ceiling):
# Jev 60.7 % / 63.3 % vs heuristic 17.9 % / 16.7 %, abstain 17.6 % / 11.8 %.
FORGE_DEPARTMENTS = Site(
    name="forge-departments", questions=_departments_questions,
    interpret=_departments_interpret, risk="read", timeout_ms=3000,
    default_mode="act",
    state_class="prompt",
)


# --- forge-complexity --------------------------------------------------------

COMPLEXITY_LEVELS: dict[str, tuple[str, list[str]]] = {
    "scope": ("How broad is the change, judged by how many files and departments it "
              "touches?", [
        "One line or setting in a single file.",
        "A small edit to one or two files in one department.",
        "A handful of files in one module, one department.",
        "Several files across two modules, one department.",
        "Around ten files, or work shared by two departments.",
        "A feature spanning many files and two or three departments.",
        "A cross-cutting change across several modules and three departments.",
        "A large change touching dozens of files and four departments.",
        "Most of one system: dozens of files and five or more departments.",
        "The whole codebase and organisation: a sweeping, system-wide change.",
    ]),
    "dependencies": ("How much of the rest of the system depends on what changes?", [
        "Nothing depends on it: isolated docs, copy or a leaf script.",
        "A leaf file with one obvious caller.",
        "A module with a few callers inside one package.",
        "Shared helpers used by several modules.",
        "About half the touched files are shared core modules.",
        "Mostly shared core code with many downstream callers.",
        "Core modules plus public contracts other systems consume.",
        "Core engine code most features depend on.",
        "Foundational code plus external integrations that must stay in step.",
        "The system's foundations: everything downstream is affected.",
    ]),
    "ambiguity": ("How ambiguous is the request as written?", [
        "Exact: names the files, symbols and the expected result.",
        "Precise target and result; one small detail left open.",
        "Clear target and result; scope needs light interpretation.",
        "Clear intent; a few specifics must be inferred from the code.",
        "Target known, but the expected result is only implied.",
        "A general goal with no files named; several readings are plausible.",
        "Broad verbs such as improve, refactor or clean with little detail.",
        "A short wish with no target and no success criterion.",
        "Contradictory or open-ended: needs discovery before planning.",
        "Pure vagueness ('make it better'): nothing concrete to act on.",
    ]),
    "risk": ("How risky is the change if it goes wrong?", [
        "No risk: comments, docs or copy only.",
        "Cosmetic change with trivial rollback.",
        "Ordinary logic change covered by tests.",
        "Behaviour change in a user-facing flow.",
        "Touches configuration or one sensitive area (tokens, permissions).",
        "Touches auth, secrets or database schema in one place.",
        "Several sensitive areas: auth plus migrations, or deploy plus config.",
        "Production data, payments or billing at stake.",
        "Security-critical and production-wide, with hard rollback.",
        "Irreversible: production data loss, security breach or outage possible.",
    ]),
    "novelty": ("How new is this work for this codebase?", [
        "An exact repeat of an existing, well-trodden plan.",
        "A near copy of a previous plan with a known pattern.",
        "Familiar work: two or more reusable patterns apply.",
        "Mostly familiar; one known pattern applies.",
        "Some precedent exists, but the combination is new.",
        "Loosely related precedent; most of the design is fresh.",
        "Little precedent: a new capability for this codebase.",
        "No similar plan and no reusable pattern.",
        "New territory that needs research before design.",
        "Entirely new ground: no prior plan, pattern or precedent anywhere.",
    ]),
}
DIMENSIONS: tuple[str, ...] = tuple(COMPLEXITY_LEVELS)


def _complexity_questions() -> dict[str, Question]:
    prefix = ("The state holds a request for the ArkaOS Forge planner with its estimated "
              "affected files and departments. ")
    return {
        dim: Question(type=QuestionType.SCORE, instructions=_instructions(prefix + ask),
                      criteria=list(levels))
        for dim, (ask, levels) in COMPLEXITY_LEVELS.items()
    }


def level_to_percent(level: float) -> int:
    """A 0..9 level on the heuristic's 0-100 scale."""
    return round(level * 100 / (SCORE_LEVELS - 1))


LevelReader = Callable[[Answer | None], float | None]


def _dimensions(answers: dict[str, Answer], read: LevelReader) -> dict[str, int] | None:
    # One unreadable or unsure dimension abstains the whole site.
    out: dict[str, int] = {}
    for dim in DIMENSIONS:
        level = read(answers.get(dim))
        if level is None:
            return None
        out[dim] = level_to_percent(level)
    return out


def window_level(answer: Answer | None, threshold: float) -> float | None:
    """The fractional level (clamped to ``0..9``) when its ±1 window is confident.

    D6 (PR5): the confidence is the window mass of
    :func:`~core.decisions.site.window_confidence`, as slop-score reads it,
    not one cell; the level keeps its fraction so the 0-100 mapping is as
    fine as before.
    """
    read = window_confidence(answer, SCORE_LEVELS)
    if answer is None or read is None or read[1] < threshold:
        return None
    return min(max(float(answer.score), 0.0), SCORE_LEVELS - 1)  # type: ignore[arg-type]


def _complexity_interpret(answers: dict[str, Answer], threshold: float) -> dict[str, int] | None:
    return _dimensions(answers, lambda answer: window_level(answer, threshold))


def single_cell_complexity(answers: dict[str, Answer], threshold: float) -> dict[str, int] | None:
    """The pre-D6 reading (one cell per dimension), kept only for the replay.

    The replay reports both readings on the same answers (spec D6: "regista
    ambas antes de qualquer proposta"); no live call site uses this one.
    """
    return _dimensions(answers, lambda answer: interpret_score(answer, threshold, SCORE_LEVELS))


# Demoted to shadow on 2026-09-23 by the online replay gate (n=32): abstain
# 90.6 % at the read threshold on the re-run (calibrated ``confidence`` < 0.60
# on at least one of the five dimensions), and at threshold 0 (first run) the
# tier matched only 43.8 % vs the heuristic's 37.5 %. Re-promote on a
# relabelled corpus.
FORGE_COMPLEXITY = Site(
    name="forge-complexity", questions=_complexity_questions,
    interpret=_complexity_interpret, risk="read", timeout_ms=3000,
    default_mode="shadow",
    state_class="prompt",
)

FORGE_SITES: tuple[Site, ...] = (FORGE_DEPARTMENTS, FORGE_COMPLEXITY)
