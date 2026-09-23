"""Command sites — decisions about a shell command before it runs.

* ``bash-effect`` — does this Bash command change anything? (destructive,
  escalate-only: Jev may gate a command the discovery regex let
  through, never un-gate one the regex caught)

The state is ``state_class="command"``: privacy refuses secrets in it
like a prompt, and the command is capped at :data:`MAX_COMMAND_CHARS`
on a whitespace boundary (R-C1): the cap runs BEFORE privacy, so a cut
inside a token would ship a client-name or key fragment no check knows.
"""

from __future__ import annotations

from typing import Any

from core.decisions.models import Answer, Question, QuestionType
from core.decisions.site import LANGUAGE_PREAMBLE, Site, interpret_noul

MAX_COMMAND_CHARS = 4000
_TRUNCATED = " [truncated]"

REQUIRES_GATING = (
    "Does running this shell command modify files, git state, packages, services, "
    "or anything outside reading? Answer YES for any write, delete, install, network "
    "mutation, or privilege escalation, including via pipes, redirects, subshells or "
    "flags such as -delete/--force; NO for pure reads, listings, searches and dry-runs."
)


def command_state(command: str) -> dict[str, Any]:
    """The state the command sites read: the command, capped between tokens."""
    if len(command) <= MAX_COMMAND_CHARS:
        return {"command": command}
    head = command[: MAX_COMMAND_CHARS - len(_TRUNCATED)]
    cut = max(head.rfind(" "), head.rfind("\n"), head.rfind("\t"))
    return {"command": (head[:cut] if cut > 0 else "") + _TRUNCATED}


def _bash_effect_questions() -> dict[str, Question]:
    return {"requires_gating": Question(
        type=QuestionType.NOUL, instructions=f"{LANGUAGE_PREAMBLE} {REQUIRES_GATING}",
    )}


def _bash_effect_interpret(answers: dict[str, Answer], threshold: float) -> bool | None:
    return interpret_noul(answers.get("requires_gating"), threshold)


BASH_EFFECT = Site(
    name="bash-effect", questions=_bash_effect_questions,
    interpret=_bash_effect_interpret, risk="destructive", direction="escalate_only",
    is_escalation=lambda jev, heur: jev is True and heur is False,
    timeout_ms=1000, default_mode="act",
    state_class="command",
)

COMMAND_SITES: tuple[Site, ...] = (BASH_EFFECT,)
