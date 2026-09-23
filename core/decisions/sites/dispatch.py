"""Dispatch sites — how a request is handed to agents and skills.

* ``dispatch-role`` — which Model Fabric role the work is (write,
  escalate-only with a bespoke predicate: see :func:`is_not_quality_demotion`).
* ``subagent-discipline`` — does the request need an isolated agent? (read,
  advisory). Quality dispatches are exempt: for them the question is
  never asked, so Jev cannot even suggest inlining a review.
* ``skill-hints`` — which of the pre-filtered candidate commands fits the
  prompt (read). The menu is built per call from ``state["candidates"]``
  (``Site.questions_for``), so an id outside it is never accepted.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from core.decisions.models import Answer, Question, QuestionType
from core.decisions.site import LANGUAGE_PREAMBLE, Site, interpret_choice, interpret_noul
from core.runtime.model_router import ROLE_DESCRIPTIONS
from core.synapse.command_menu import MENU_CAP

QUALITY_ROLES = frozenset({"design", "review", "architecture", "strategy", "quality_gate"})
ECONOMY_ROLES = frozenset({"execution", "mechanical"})
# One cap for the menu builder and the site (PR2: dept + top-20 keyword,
# capped at 60 + ``none``; the endpoint's own ceiling is 255 options).
MAX_CANDIDATES = MENU_CAP
MAX_OPTION_CHARS = 240
NO_SKILL = "none"
SKILL_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _instructions(body: str) -> str:
    return f"{LANGUAGE_PREAMBLE} {body}"


# --- dispatch-role -----------------------------------------------------------

def is_not_quality_demotion(jev: object, heuristic: object) -> bool:
    """The escalation predicate of ``dispatch-role``.

    True unless Jev would move quality-critical work (design, review,
    architecture, strategy, quality_gate) down to an economy role
    (execution, mechanical): the Model Routing rule says cost never
    downgrades a quality phase. Every other change is accepted, including
    economy → quality (an upgrade) and quality → quality (same tier).
    """
    return not (heuristic in QUALITY_ROLES and jev in ECONOMY_ROLES)


def _role_questions() -> dict[str, Question]:
    return {"role": Question(type=QuestionType.CHOICE, instructions=_instructions(
        "Which kind of work does this request ask for? The answer picks the model "
        "tier of the agent that does it: quality-critical work (design, review, "
        "architecture, strategy, the Quality Gate) runs the best model; execution "
        "and mechanical work may run cheaper ones."
    ), criteria=dict(ROLE_DESCRIPTIONS))}


def _role_interpret(answers: dict[str, Answer], threshold: float) -> str | None:
    return interpret_choice(answers.get("role"), threshold)


DISPATCH_ROLE = Site(
    name="dispatch-role", questions=_role_questions, interpret=_role_interpret,
    risk="write", timeout_ms=1500, direction="escalate_only",
    is_escalation=is_not_quality_demotion,
    state_class="prompt",
)


# --- subagent-discipline -----------------------------------------------------

def _discipline_questions() -> dict[str, Question]:
    return {"needs_isolated_context": Question(type=QuestionType.NOUL, instructions=_instructions(
        "Would a careful tech lead hand this request to a separate agent because it "
        "needs more than 3 file reads or 5 searches, or an isolated context, rather "
        "than doing it inline?"
    ))}


def _discipline_questions_for(state: object) -> dict[str, Question]:
    # Quality dispatches (QG reviewers, adversarial verification) are
    # exempt from subagent-discipline: nothing is asked, nothing answers.
    if isinstance(state, dict) and state.get("quality_dispatch") is True:
        return {}
    return _discipline_questions()


def _discipline_interpret(answers: dict[str, Answer], threshold: float) -> bool | None:
    return interpret_noul(answers.get("needs_isolated_context"), threshold)


SUBAGENT_DISCIPLINE = Site(
    name="subagent-discipline", questions=_discipline_questions,
    questions_for=_discipline_questions_for, interpret=_discipline_interpret,
    risk="read", timeout_ms=1500,
    state_class="prompt",
)


# --- skill-hints -------------------------------------------------------------

def skill_state(
    prompt: str, candidates: Sequence[dict[str, Any]], *, quality_dispatch: bool = False
) -> dict[str, Any]:
    """The state the dispatch sites read: the prompt plus the candidate menu."""
    menu = [
        {k: str(c.get(k, "")) for k in ("id", "command", "description")}
        for c in list(candidates)[:MAX_CANDIDATES]
    ]
    return {"prompt": prompt, "candidates": menu, "quality_dispatch": quality_dispatch}


def skill_candidates(state: object) -> dict[str, str]:
    """Candidate id → option text from ``state["candidates"]``; malformed entries skipped."""
    raw = state.get("candidates") if isinstance(state, dict) else None
    out: dict[str, str] = {}
    for item in raw[:MAX_CANDIDATES] if isinstance(raw, list) else []:
        option = _candidate_option(item)
        if option is not None:
            out.setdefault(*option)
    return out


def _candidate_option(item: object) -> tuple[str, str] | None:
    if not isinstance(item, dict):
        return None
    cid = item.get("id")
    if not isinstance(cid, str) or cid == NO_SKILL or not SKILL_ID_RE.fullmatch(cid):
        return None
    text = f"{item.get('command', '')} — {item.get('description', '')}"
    return cid, text[:MAX_OPTION_CHARS]


def _skill_questions_for(state: object) -> dict[str, Question]:
    options = {**skill_candidates(state),
               NO_SKILL: "No candidate fits; the prompt needs no specific command."}
    return {"command": Question(type=QuestionType.CHOICE, instructions=_instructions(
        "The state holds a user prompt and ArkaOS commands shortlisted for it. Which "
        "candidate command should handle the prompt? Judge by intent, not shared "
        "words; pick 'none' when no candidate fits."
    ), criteria=options)}


def _skill_interpret(answers: dict[str, Answer], threshold: float) -> str | None:
    choice = interpret_choice(answers.get("command"), threshold)
    if choice is None:
        return None
    return "" if choice == NO_SKILL else choice


SKILL_HINT = Site(
    name="skill-hints", questions=lambda: _skill_questions_for(None),
    questions_for=_skill_questions_for, interpret=_skill_interpret,
    risk="read", timeout_ms=1500,
    state_class="prompt",
)

DISPATCH_SITES: tuple[Site, ...] = (DISPATCH_ROLE, SUBAGENT_DISCIPLINE, SKILL_HINT)
