"""Decision sites: what a call site asks and how an answer becomes a value.

A :class:`Site` owns its typed questions and an ``interpret`` function
mapping ``{question: Answer}`` plus the action threshold to a value of
the SAME type as the site's heuristic, or None (abstain). ``direction
="escalate_only"`` sites accept Jev only when ``is_escalation(jev,
heuristic)`` holds — governance checks may be tightened, never relaxed.

Every ``interpret`` is wrapped at construction so it only ever sees
choice answers that name an option the question offered (and whose
``probabilities`` keys are options too): the endpoint's free-text
``choice`` otherwise flowed raw into hook context (QG r1 B3). An
off-menu answer is dropped, so the site abstains and the heuristic acts.
The same pass (QG PR1 carry) drops answers to questions nobody asked,
answers whose ``probabilities`` are not a distribution (finite values in
[0, 1] summing to 1 ± :data:`PROB_SUM_TOLERANCE`), and clears the
``choice``/``score`` fields a question of another type never asked for.

A site whose questions depend on the call (a candidate menu) sets
``questions_for``: the engine asks ``questions_for(state)`` and validates
the answers against exactly those questions (:meth:`Site.judge`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Mapping, Sequence
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


Interpret = Callable[[dict[str, Answer], float], object | None]
Judge = Callable[[dict[str, Answer], float, object], object | None]
QuestionsFor = Callable[[object], dict[str, Question]]

PROB_SUM_TOLERANCE = 0.05


@dataclass(frozen=True)
class Site:
    """One decision point in ArkaOS."""

    name: str
    questions: Callable[[], dict[str, Question]]
    interpret: Interpret
    risk: Risk
    default_mode: Mode = "act"
    direction: Direction = "any"
    redact_default: bool = True
    timeout_ms: int = 1500
    is_escalation: Callable[[object, object], bool] | None = None
    # Questions built from the call's state (e.g. a candidate menu). None
    # keeps the static ``questions``; when set, ``questions`` is only the
    # stateless fallback a state-free ``interpret`` call validates against.
    questions_for: QuestionsFor | None = None
    # Required, no permissive default: a new site must say what its state
    # carries, or a diff site would silently egress as a prompt (QG r1 m1).
    state_class: StateClass = field(kw_only=True)
    # ``interpret`` with the answers validated against the questions the
    # call really asked; built in __post_init__, never passed in.
    judge: Judge = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        raw = getattr(self.interpret, "_arka_raw", self.interpret)
        judge = _guarded(self, raw)
        object.__setattr__(self, "judge", judge)
        object.__setattr__(self, "interpret", _stateless(judge, raw))

    def questions_of(self, state: object = None) -> dict[str, Question]:
        """The questions this call asks: ``questions_for(state)`` or the static set."""
        if self.questions_for is None:
            return self.questions()
        return self.questions_for(state)


def _guarded(site: Site, raw: Interpret) -> Judge:
    def judge(answers: dict[str, Answer], threshold: float, state: object = None) -> object | None:
        return raw(valid_answers(site.questions_of(state), answers), threshold)

    return judge


def _stateless(judge: Judge, raw: Interpret) -> Interpret:
    # Re-wrapping unwraps ``_arka_raw`` first, so ``dataclasses.replace``
    # never stacks guards and the guard always reads the NEW site.
    def interpret(answers: dict[str, Answer], threshold: float) -> object | None:
        return judge(answers, threshold, None)

    interpret._arka_guarded = True  # type: ignore[attr-defined]
    interpret._arka_raw = raw  # type: ignore[attr-defined]
    return interpret


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


def is_distribution(probs: Mapping[str, float] | Sequence[float] | None) -> bool:
    """None, or finite values in [0, 1] summing to 1 ± :data:`PROB_SUM_TOLERANCE`."""
    if probs is None:
        return True
    values = list(probs.values()) if isinstance(probs, Mapping) else list(probs)
    if not all(_is_unit(v) for v in values):
        return False
    return abs(math.fsum(values) - 1.0) <= PROB_SUM_TOLERANCE


def _is_unit(value: object) -> bool:
    # NaN and ±inf fail the range comparison itself (NaN compares False).
    return isinstance(value, int | float) and not isinstance(value, bool) and 0.0 <= value <= 1.0


def clean_answer(question: Question, answer: Answer) -> Answer | None:
    """``answer`` as ``question`` allows it, or None when it must be dropped."""
    if not is_distribution(answer.probabilities):
        return None
    options = choice_options(question)
    if options is not None:
        return answer if is_valid_choice(answer, options) else None
    update: dict[str, object] = {"choice": None}
    if question.type is not QuestionType.SCORE or not _is_number(answer.score):
        update["score"] = None
    if all(getattr(answer, k) is None for k in update):
        return answer
    return answer.model_copy(update=update)


def _is_number(value: object) -> bool:
    try:
        return value is not None and math.isfinite(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def valid_answers(
    questions: Mapping[str, Question], answers: Mapping[str, Answer]
) -> dict[str, Answer]:
    """The answers to asked questions, each cleaned by :func:`clean_answer`."""
    out: dict[str, Answer] = {}
    for name, answer in answers.items():
        question = questions.get(name)
        kept = clean_answer(question, answer) if question is not None else None
        if kept is not None:
            out[name] = kept
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
    # This site's raw answers (bare question names) when Jev answered;
    # empty on every fallback path. Lets a caller cite what Jev saw
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


def interpret_score(answer: Answer | None, threshold: float, levels: int) -> float | None:
    """The fractional level in ``[0, levels - 1]`` when its confidence reaches the threshold.

    Confidence is the answer's ``confidence``, else the probability of the
    nearest level; an answer with neither abstains.
    """
    if answer is None or not _is_number(answer.score):
        return None
    level = float(answer.score)  # type: ignore[arg-type]
    if not 0.0 <= level <= levels - 1:
        return None
    confidence = score_confidence(answer, level)
    if confidence is None or confidence < threshold:
        return None
    return level


def score_confidence(answer: Answer, level: float) -> float | None:
    """``confidence``, else the probability of the level nearest ``level``."""
    if answer.confidence is not None:
        return answer.confidence
    probs, nearest = answer.probabilities, round(level)
    if isinstance(probs, dict):
        value = probs.get(str(nearest))
        return None if value is None else float(value)
    if isinstance(probs, list) and 0 <= nearest < len(probs):
        return float(probs[nearest])
    return None


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
