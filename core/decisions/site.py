"""Decision sites: what a call site asks and how an answer becomes a value.

A :class:`Site` owns its typed questions and an ``interpret`` function
mapping ``{question: Answer}`` plus the action threshold to a value of
the SAME type as the site's heuristic, or None (abstain). ``direction
="escalate_only"`` sites accept the JEV only when ``is_escalation(jev,
heuristic)`` holds — governance checks may be tightened, never relaxed.

Every ``interpret`` is wrapped at construction so it only ever sees
choice answers that name an option the question offered (and whose
``probabilities`` keys are options too): the endpoint's free-text
``choice`` otherwise flowed raw into hook context (QG r1 B3). An
off-menu answer is dropped, so the site abstains and the heuristic acts.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Literal

from core.decisions.config import Mode
from core.decisions.models import Answer, Question, QuestionType

Risk = Literal["read", "write", "destructive"]
Direction = Literal["any", "escalate_only"]
# What the state of a site carries — privacy.py decides egress by it
# (prompt/command may leave without a client list; diff/transcript never).
StateClass = Literal["prompt", "command", "diff", "transcript"]
ActedOn = Literal["jev", "heuristic"]

# Contract pinned by the 2026-09-23 smoke test: ``noul`` is P(yes).
# "agora prepara o email de lançamento" after "corrige o bug do login"
# → topic_shift 0.96; "porque é que o teste falha?" → 0.06.
NOUL_IS_P_YES = True

LANGUAGE_PREAMBLE = (
    "Messages may be in Portuguese (pt-PT) or English; judge meaning, not language."
)


@dataclass(frozen=True)
class Site:
    """One decision point in ArkaOS."""

    name: str
    questions: Callable[[], dict[str, Question]]
    interpret: Callable[[dict[str, Answer], float], object | None]
    risk: Risk
    default_mode: Mode = "act"
    direction: Direction = "any"
    redact_default: bool = True
    timeout_ms: int = 1500
    is_escalation: Callable[[object, object], bool] | None = None
    # Required, no permissive default: a new site must say what its state
    # carries, or a diff site would silently egress as a prompt (QG r1 m1).
    state_class: StateClass = field(kw_only=True)

    def __post_init__(self) -> None:
        if getattr(self.interpret, "_arka_guarded", False):
            return
        object.__setattr__(self, "interpret", _guarded(self.questions, self.interpret))


def _guarded(
    questions: Callable[[], dict[str, Question]],
    interpret: Callable[[dict[str, Answer], float], object | None],
) -> Callable[[dict[str, Answer], float], object | None]:
    def guarded(answers: dict[str, Answer], threshold: float) -> object | None:
        return interpret(valid_answers(questions(), answers), threshold)

    guarded._arka_guarded = True  # type: ignore[attr-defined]
    return guarded


def choice_options(question: Question) -> frozenset[str] | None:
    """The option keys of a CHOICE question; None for other types."""
    if question.type is not QuestionType.CHOICE:
        return None
    criteria = question.criteria
    return frozenset(criteria) if isinstance(criteria, dict | list) else frozenset()


def is_valid_choice(answer: Answer, options: Collection[str]) -> bool:
    """``choice`` and every ``probabilities`` key are offered options."""
    if answer.choice is not None and answer.choice not in options:
        return False
    probs = answer.probabilities
    return not (isinstance(probs, dict) and not set(probs) <= set(options))


def valid_answers(
    questions: Mapping[str, Question], answers: Mapping[str, Answer]
) -> dict[str, Answer]:
    """``answers`` minus choice answers that step outside their options."""
    out: dict[str, Answer] = {}
    for name, answer in answers.items():
        question = questions.get(name)
        options = choice_options(question) if question is not None else None
        if options is None or is_valid_choice(answer, options):
            out[name] = answer
    return out


@dataclass(frozen=True)
class SiteCall:
    """A site plus the heuristic value computed for this turn."""

    site: Site
    heuristic: object


@dataclass(frozen=True)
class Outcome:
    """What the caller acts on, and why."""

    value: object
    heuristic: object
    jev: object | None
    confidence: float | None
    mode: Mode
    acted_on: ActedOn
    reason: str
    # This site's raw answers (bare question names) when the JEV answered;
    # empty on every fallback path. Lets a caller cite what the JEV saw
    # (e.g. the refine hint's ``missing=<choice>``) without a second call.
    answers: Mapping[str, Answer] = field(default_factory=dict)


def interpret_noul(answer: Answer | None, threshold: float) -> bool | None:
    """P(yes) ≥ t → True; P(yes) ≤ 1 - t → False; in between → None."""
    if answer is None or answer.noul is None:
        return None
    p_yes = answer.noul if NOUL_IS_P_YES else 1.0 - answer.noul
    if p_yes >= threshold:
        return True
    if p_yes <= 1.0 - threshold:
        return False
    return None


def interpret_choice(
    answer: Answer | None, threshold: float, options: Collection[str] | None = None
) -> str | None:
    """The chosen option when its confidence reaches the threshold.

    With ``options``, an answer outside them abstains. Sites get this
    check for free (``Site`` wraps ``interpret``); pass ``options`` when
    calling outside a site.
    """
    if answer is None or not answer.choice:
        return None
    if options is not None and not is_valid_choice(answer, options):
        return None
    confidence = choice_confidence(answer)
    if confidence is None or confidence < threshold:
        return None
    return answer.choice


def choice_confidence(answer: Answer) -> float | None:
    """``confidence``, else the chosen option's probability."""
    if answer.confidence is not None:
        return answer.confidence
    probs = answer.probabilities
    if isinstance(probs, dict) and answer.choice in probs:
        return float(probs[answer.choice])
    return None


def answer_confidence(answer: Answer) -> float | None:
    """Comparable certainty for telemetry: noul → max(p, 1 - p)."""
    if answer.noul is not None and answer.confidence is None:
        return max(answer.noul, 1.0 - answer.noul)
    return choice_confidence(answer)
