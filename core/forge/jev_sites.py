"""Forge step 3 x the Jev decisions layer (JEV Decisions Layer PR2).

Two sites refine the complexity inputs, in sequence and under one
:class:`~core.forge.budget.ForgeBudget` (3 s per call, 5 s in total —
never a call without a deadline):

1. ``forge-departments`` — the departments the plan needs; the keyword
   estimate is the heuristic.
2. ``forge-complexity`` — the five dimensions, asked with the departments
   step 1 settled on; ``score_dimensions`` is the heuristic. Weights and
   ``determine_tier`` stay untouched.

Jev's value is used only when the site acted on it (``acted_on ==
"jev"``); every other path — off, shadow, no key, abstain, timeout, an
internal error — keeps the heuristic, so the Forge behaves as before.
"""

from __future__ import annotations

from typing import Any

from core.forge.budget import FORGE_CALL_MS, ForgeBudget
from core.forge.complexity import score_dimensions
from core.forge.schema import ComplexityDimensions

FORGE_SESSION = "forge"


def _acted_value(
    site: Any, heuristic: object, state: dict[str, Any], budget: ForgeBudget
) -> object:
    """The site's Jev value when it acted, else ``heuristic``. Never raises."""
    try:
        from core.decisions.engine import decide
        from core.decisions.site import SiteCall
        from core.decisions.transport import configured_model

        outcomes = decide(
            [SiteCall(site, heuristic)], state, session_id=FORGE_SESSION,
            timeout_ms=budget.remaining_ms(FORGE_CALL_MS), model=configured_model(),
        )
        outcome = outcomes[site.name]
        return outcome.value if outcome.acted_on == "jev" else heuristic
    except Exception:
        return heuristic


def decide_departments(
    prompt: str, affected_files: list[str], heuristic: list[str], budget: ForgeBudget
) -> list[str]:
    """The plan's departments: the Jev set when it acted, else the keyword estimate."""
    from core.decisions.sites.forge import FORGE_DEPARTMENTS, forge_state

    state = forge_state(prompt, affected_files, heuristic)
    value = _acted_value(FORGE_DEPARTMENTS, heuristic, state, budget)
    if isinstance(value, list) and value and all(isinstance(d, str) for d in value):
        return list(value)
    return heuristic


def decide_dimensions(
    prompt: str,
    affected_files: list[str],
    departments: list[str],
    history: tuple[list[str], list[str]],
    budget: ForgeBudget,
) -> ComplexityDimensions:
    """The five dimensions: Jev scores when it acted, else ``score_dimensions``.

    ``history`` is ``(similar_plans, reused_patterns)``, the novelty inputs.
    """
    from core.decisions.sites.forge import FORGE_COMPLEXITY, forge_state

    heuristic = score_dimensions(prompt, affected_files, departments, *history)
    state = forge_state(prompt, affected_files, departments)
    value = _acted_value(FORGE_COMPLEXITY, heuristic.model_dump(), state, budget)
    try:
        return ComplexityDimensions(**value) if isinstance(value, dict) else heuristic
    except (TypeError, ValueError):
        return heuristic
