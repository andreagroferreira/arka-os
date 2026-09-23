"""UserPromptSubmit x the Jev dispatch sites (JEV Decisions Layer PR2).

Three sites join the hook's single ``decisions`` stage:

* ``dispatch-role`` — which Model Fabric role the work is. Heuristic
  (:func:`keyword_dispatch_role`): the first role whose keywords match,
  else ``execution``. The site is escalate-only with a bespoke predicate
  (never quality → economy), so a keyword-matched quality role can only
  move to another quality role, and ``execution`` anywhere.
* ``subagent-discipline`` — does the request need an isolated agent?
  Heuristic (:func:`keyword_needs_isolation`): the prompt names breadth.
  Quality dispatches (:func:`is_quality_dispatch`) are exempt and ask
  nothing.
* ``skill-hints`` — which command of the pre-filtered menu fits.
  Heuristic: the live L5 top-1 keyword command, or "" (none).

Both keyword baselines were the replay's (each right in 27 of 32 corpus
cases, 84.4 %); they live here so the replay scores the heuristic that
ships.

Everything here is pure except :func:`load_commands` (one cached read of
``knowledge/commands-registry.json``). Markers carry allowlisted fields
only: a Jev answer is untrusted text (QG PR1 B3).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.decisions.site import Outcome, SiteCall

DISPATCH_SITE_NAMES: tuple[str, ...] = ("dispatch-role", "subagent-discipline", "skill-hints")
# Prompts that are already an explicit command or a shell escape: they
# carry their own workflow, so no dispatch site is asked about them.
EXPLICIT_PREFIXES = ("/", "!")
ROLES: frozenset[str] = frozenset({
    "design", "review", "architecture", "strategy", "quality_gate", "execution", "mechanical",
})
# A prompt aimed at the Quality Gate or an adversarial review: exempt
# from subagent-discipline (constitution: QG dispatches are never suppressed).
_QUALITY_DISPATCH_RE = re.compile(
    r"quality[ -]gate|\bqg\b|\bcqo\b|arka-quality|adversarial|advers[áa]ri[ao]",
    re.IGNORECASE,
)
_SKILL_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


_ROLE_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (role, re.compile(pattern, re.IGNORECASE)) for role, pattern in (
        ("quality_gate", r"quality gate|\bqg\b|veredicto|verdict"),
        ("review", r"\breview|\brev[êe]\b|\brever\b|revis[ãa]o|audit"),
        ("architecture",
         r"architect|arquitetura|\badr\b|system design|contrato de api|api contract"),
        ("design", r"\bui\b|\bux\b|layout|typograph|tipografia|mockup|paleta|palette|visual"),
        ("strategy",
         r"strateg|estrat[ée]gi|mercado|market|roadmap|pricing|posicionamento|positioning"),
        ("mechanical",
         r"commit message|mensagem de commit|changelog|formata|format\b|renomeia|rename"),
    )
)
_ISOLATION_RE = re.compile(
    r"\b(whole|entire|every|across|codebase|all (the )?files|audit|investigate|research|"
    r"tod[oa]s? [oa]s?|repo(sit[óo]rio)?|auditoria|investiga|pesquisa|varre|percorre)\b",
    re.IGNORECASE,
)


def keyword_dispatch_role(prompt: str) -> str:
    """First role whose keywords match, else ``execution``."""
    return next((role for role, rx in _ROLE_KEYWORDS if rx.search(prompt)), "execution")


def keyword_needs_isolation(prompt: str) -> bool:
    """True when the prompt names breadth (whole repo, audit, research)."""
    return bool(_ISOLATION_RE.search(prompt))


def is_quality_dispatch(prompt: str) -> bool:
    """True when the prompt asks for the Quality Gate or an adversarial review."""
    return bool(_QUALITY_DISPATCH_RE.search(prompt))


def dispatch_site_calls(prompt: str) -> list[SiteCall]:
    """The dispatch-role and subagent-discipline calls with their heuristics."""
    from core.decisions.site import SiteCall
    from core.decisions.sites.dispatch import DISPATCH_ROLE, SUBAGENT_DISCIPLINE

    return [
        SiteCall(DISPATCH_ROLE, keyword_dispatch_role(prompt)),
        SiteCall(SUBAGENT_DISCIPLINE, keyword_needs_isolation(prompt)),
    ]


@lru_cache(maxsize=8)
def load_commands(root: str) -> tuple[dict[str, Any], ...]:
    """The registry commands under ``root`` (read once per root); () on any failure."""
    try:
        path = Path(root) / "knowledge" / "commands-registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        commands = data.get("commands", []) if isinstance(data, dict) else []
        return tuple(c for c in commands if isinstance(c, dict))
    except (OSError, ValueError, TypeError):
        return ()


@dataclass(frozen=True)
class SkillMenu:
    """What the skill-hints site needs for one prompt."""

    prompt: str
    commands: tuple[dict[str, Any], ...]
    keyword_dept: str
    candidates: list[dict[str, str]] = field(default_factory=list)
    heuristic: str = ""

    def for_dept(self, dept: str) -> list[dict[str, str]]:
        """The menu this prompt gets when routed to ``dept``."""
        from core.synapse.command_menu import skill_hint_candidates

        return skill_hint_candidates(self.commands, self.prompt, dept)


def build_skill_menu(prompt: str, root: str) -> SkillMenu | None:
    """The menu for the L1 keyword route, or None (explicit command, no registry)."""
    if prompt.lstrip()[:1] in EXPLICIT_PREFIXES:
        return None
    commands = load_commands(root)
    if not commands:
        return None
    from core.synapse.command_menu import skill_hint_candidates
    from core.synapse.layers import keyword_department

    dept = keyword_department(prompt) or ""
    return SkillMenu(prompt, commands, dept, skill_hint_candidates(commands, prompt, dept),
                     skill_heuristic(commands, prompt))


def skill_heuristic(commands: Sequence[dict[str, Any]], prompt: str) -> str:
    """The id of L5's top-1 keyword command, or "" when no keyword matches."""
    from core.synapse.layers import _score_commands

    top = _score_commands(list(commands), prompt.lower())
    if not top:
        return ""
    ids = {str(c.get("command", "")): str(c.get("id", "")) for c in reversed(commands)}
    return ids.get(top[0][1], "")


def skill_calls(menu: SkillMenu | None) -> list[SiteCall]:
    """The skill-hints call, or none when the menu is empty."""
    if menu is None or not menu.candidates:
        return []
    from core.decisions.site import SiteCall
    from core.decisions.sites.dispatch import SKILL_HINT

    return [SiteCall(SKILL_HINT, menu.heuristic)]


def turn_state(
    base: dict[str, Any], prompt: str, candidates: Sequence[dict[str, str]]
) -> dict[str, Any]:
    """The prompt state plus what the dispatch sites read (one state per call)."""
    from core.decisions.sites.dispatch import skill_state

    extra = skill_state(prompt, candidates, quality_dispatch=is_quality_dispatch(prompt))
    return {**base, "candidates": extra["candidates"],
            "quality_dispatch": extra["quality_dispatch"]}


def repair_dept(
    outcomes: Mapping[str, Outcome], menu: SkillMenu | None, skill_act: bool
) -> str | None:
    """The department to re-ask skill-hints for, or None (no second call).

    One call per turn is the rule; the exception is when the Jev route
    moved the prompt to a department whose commands the keyword-routed
    menu lacked AND that menu did not yield a command (not asked, "none",
    or an unsure answer), with the skill-hints site in ``act``. A skill
    question the endpoint left unanswered is not repaired.
    """
    route, skill = outcomes.get("route"), outcomes.get("skill-hints")
    if not skill_act or menu is None or route is None or route.acted_on != "jev":
        return None
    dept = route.value if isinstance(route.value, str) else ""
    if not dept or dept == menu.keyword_dept:
        return None
    if skill is not None and (not skill.answers or (skill.acted_on == "jev" and skill.value)):
        return None
    return dept


def skill_hint_payload(
    outcomes: Mapping[str, Outcome], commands: Sequence[dict[str, Any]]
) -> dict[str, Any] | None:
    """The bridge's ``skill_hint`` when the site acted on a registry id."""
    skill = outcomes.get("skill-hints")
    if skill is None or skill.acted_on != "jev":
        return None
    cmd_id = skill.value
    if not isinstance(cmd_id, str) or not _SKILL_ID_RE.fullmatch(cmd_id):
        return None
    if not any(c.get("id") == cmd_id for c in commands):
        return None
    return {"id": cmd_id, "p": skill.confidence, "source": "jev"}


def dispatch_role_marker(outcomes: Mapping[str, Outcome], fmt_p: Any) -> str:
    """``[arka:dispatch-role]`` once Jev answered an ``act`` site; "" otherwise.

    ``source=heuristic`` means Jev was overruled (a blocked demotion);
    an abstention or an unavailable endpoint adds nothing to the turn.
    """
    out = outcomes.get("dispatch-role")
    if out is None or out.mode != "act" or out.jev is None:
        return ""
    source = "jev" if out.acted_on == "jev" else "heuristic"
    role = out.value if out.value in ROLES else None
    if role is None:
        return ""
    p = fmt_p(out.confidence) if source == "jev" else "n/a"
    return f"[arka:dispatch-role] role={role} p={p} source={source}"


def discipline_marker(outcomes: Mapping[str, Outcome], fmt_p: Any) -> str:
    """``[arka:subagent-discipline]`` when the ``act`` site decided; "" when it abstained.

    The line exists only when Jev acted, so ``source`` is the literal
    ``jev``; it is spelled out so every decision marker carries the field.
    """
    out = outcomes.get("subagent-discipline")
    if out is None or out.mode != "act" or out.acted_on != "jev":
        return ""
    if out.value is not True and out.value is not False:
        return ""
    isolate = "yes" if out.value else "no"
    return f"[arka:subagent-discipline] isolate={isolate} p={fmt_p(out.confidence)} source=jev"
