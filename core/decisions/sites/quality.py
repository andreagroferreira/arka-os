"""Quality sites — advisory reads of a change before its reviewers see it (PR3).

* ``qg-prescreen`` — the verdict a strict Quality Gate would likely give a
  diff, and the blocker class when it would reject (write, advisory: it
  never skips a reviewer; ``shadow`` by default since the PR3 replay). No
  heuristic exists: the baseline is the neutral :data:`PRESCREEN_NEUTRAL`,
  so without Jev nothing is predicted. The verdict decides; the blocker
  only annotates it (see :func:`_prescreen_interpret`).
* ``slop-score`` — the human-writing Slop Score of changed prose: five
  1-10 scores and their total (read; the ADR's "minor"). No heuristic in
  code: the baseline is None (no score). Confidence is read as the mass
  of a level window, not one cell (see :func:`slop_dimension`).

Both states are ``state_class="diff"``: without the operator's redaction
list they never leave the machine (``privacy.DEGRADABLE`` excludes diff),
and each names the file it comes from (``path``): privacy sends a diff
state only for a file whose suffix is in ``DIFF_SOURCE_SUFFIXES``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from core.decisions.models import Answer, Question, QuestionType
from core.decisions.site import (
    LANGUAGE_PREAMBLE,
    Site,
    choice_confidence,
    interpret_choice,
)

MAX_DIFF_CHARS = 24_000
MAX_PROSE_CHARS = 12_000
QUALITY_TIMEOUT_MS = 5000
SLOP_LEVELS = 10
SLOP_PASS_TOTAL = 35  # human-writing: "below 35/50, revise before delivering"
# Levels either side of the rounded level whose probability counts as
# agreement: ±1 of a 10-level rubric (so 3 cells, 2 at an edge).
SLOP_WINDOW = 1
_TRUNCATED = "\n[truncated]"

VERDICTS: dict[str, str] = {
    "approved": (
        "No blocker: behaviour changes carry tests, no secret or unsafe code, no "
        "misspelling in user-facing text, no lint-level defect, and the change does "
        "what it claims."
    ),
    "rejected": "At least one blocker a strict reviewer would reject the change on.",
}
BLOCKERS: dict[str, str] = {
    "spellcheck": "Misspelled words, wrong accentuation or broken grammar in "
                  "user-facing prose, docs or strings.",
    "tests": "Behaviour added or changed without a test, or a test weakened, skipped "
             "or deleted, or an assertion that cannot fail.",
    "diff-review": "A logic defect, dead code, wrong API use, a broken contract, an "
                   "unfinished edge, or code breaking the Clean Code limits.",
    "security": "A hard-coded secret, injection, unsafe deserialisation, disabled "
                "verification, over-broad permission or a data leak.",
    "lint": "Static-analysis or style defects: unused imports, undefined names, "
            "formatting, type errors.",
    "none": "No blocker.",
}
NO_BLOCKER = "none"
# The neutral baseline: read-only, so no consumer can mutate the shared value.
PRESCREEN_NEUTRAL: MappingProxyType[str, str] = MappingProxyType(
    {"verdict": "unknown", "blocker": NO_BLOCKER})


def prescreen_heuristic() -> dict[str, str]:
    """A fresh copy of :data:`PRESCREEN_NEUTRAL` — there is no regex to run."""
    return dict(PRESCREEN_NEUTRAL)


def _cap_lines(text: str, limit: int) -> str:
    """``text`` capped on a line boundary (never mid-token, privacy runs after)."""
    if len(text) <= limit:
        return text
    head = text[: limit - len(_TRUNCATED)]
    cut = head.rfind("\n")
    return (head[:cut] if cut > 0 else "") + _TRUNCATED


def diff_state(diff: str, path: str) -> dict[str, Any]:
    """The state ``qg-prescreen`` reads: the file and its unified diff, capped between lines."""
    return {"path": path, "diff": _cap_lines(diff or "", MAX_DIFF_CHARS)}


def prose_state(prose: str, path: str) -> dict[str, Any]:
    """The state ``slop-score`` reads: the file and its changed prose, capped between lines."""
    return {"path": path, "prose": _cap_lines(prose or "", MAX_PROSE_CHARS)}


def _instructions(body: str) -> str:
    return f"{LANGUAGE_PREAMBLE} {body}"


# --- qg-prescreen ------------------------------------------------------------

VERDICT_QUESTION = (
    "The state holds a diff about to go to the ArkaOS Quality Gate (binary "
    "APPROVED/REJECTED, absolute veto, zero tolerance for unfinished work). Predict "
    "the verdict a strict reviewer would give this diff."
)
BLOCKER_QUESTION = (
    "The state holds a diff about to go to the ArkaOS Quality Gate. Which class of "
    "blocker would a strict reviewer reject it on first? Pick 'none' when there is "
    "no blocker."
)


def _prescreen_questions() -> dict[str, Question]:
    return {
        "likely_verdict": Question(type=QuestionType.CHOICE, instructions=_instructions(
            VERDICT_QUESTION), criteria=dict(VERDICTS)),
        "blocker_class": Question(type=QuestionType.CHOICE, instructions=_instructions(
            BLOCKER_QUESTION), criteria=dict(BLOCKERS)),
    }


def _prescreen_interpret(
    answers: dict[str, Answer], threshold: float
) -> dict[str, Any] | None:
    """A confident ``likely_verdict`` decides; the blocker only annotates it.

    * verdict unconfident or missing → abstain (the only abstention);
    * ``approved`` → blocker ``none`` whatever was said, ``blocker_p`` None;
    * ``rejected`` → the blocker class when it clears the threshold, else
      ``none``; either way ``blocker_p`` is the blocker answer's own
      confidence (None without one), so a consumer can print
      ``blocker=none p=0.42`` instead of hiding an unsure class.
    """
    verdict = interpret_choice(answers.get("likely_verdict"), threshold)
    if verdict == "approved":
        return {"verdict": "approved", "blocker": NO_BLOCKER, "blocker_p": None}
    if verdict != "rejected":
        return None
    answer = answers.get("blocker_class")
    blocker = interpret_choice(answer, threshold) or NO_BLOCKER
    return {"verdict": "rejected", "blocker": blocker, "blocker_p": _blocker_p(answer)}


def _blocker_p(answer: Answer | None) -> float | None:
    confidence = None if answer is None else choice_confidence(answer)
    return None if confidence is None else round(float(confidence), 4)


# shadow by the replay gate (2026-09-24): in the deciding run, r10 (46 cases),
# the verdict abstained on 28.3 % of the corpus at the 0.75 write threshold
# and was right on 72.7 % of the answered cases; five of six runs sat above
# the 25 % abstain limit. It runs in ``act`` only by operator override
# (``decisions.sites.qg-prescreen: act``).
QG_PRESCREEN = Site(
    name="qg-prescreen", questions=_prescreen_questions, interpret=_prescreen_interpret,
    risk="write", timeout_ms=QUALITY_TIMEOUT_MS, state_class="diff",
    default_mode="shadow",
)


# --- slop-score --------------------------------------------------------------

# Verbatim from arka/skills/human-writing/SKILL.md, "### Slop Score".
SLOP_RUBRIC_INTRO = (
    "A fast quantitative gate, complement to the Seven Sweeps. Rate the draft "
    "1 to 10 on each dimension; below 35/50, revise before delivering."
)
SLOP_RUBRIC: dict[str, tuple[str, str]] = {
    "directness": ("Directness", "Statements or announcements?"),
    "rhythm": ("Rhythm", "Varied or metronomic?"),
    "trust": ("Trust", "Respects reader intelligence?"),
    "authenticity": ("Authenticity", "Sounds human?"),
    "density": ("Density", "Anything cuttable?"),
}
# Five bands per dimension, two levels each (1-2 … 9-10), worst first.
SLOP_BANDS: dict[str, tuple[str, str, str, str, str]] = {
    "directness": (
        "Announces instead of saying: throat-clearing, 'let's dive in', signposting.",
        "Mostly announcements; the point arrives late and hedged.",
        "Mixed: some plain statements, some preamble.",
        "Mostly direct statements; rare signposting.",
        "Every sentence states something; no preamble at all.",
    ),
    "rhythm": (
        "Metronomic: every sentence the same length and shape; rule-of-three lists and "
        "punchy closers throughout.",
        "Mostly uniform length; rule-of-three lists and punchy closers recur.",
        "Some variation, but patterns repeat paragraph after paragraph.",
        "Varied length and structure with occasional repetition.",
        "Natural, varied rhythm that follows the content.",
    ),
    "trust": (
        "Condescending: over-explains, repeats itself, tells the reader what to feel.",
        "Frequent hand-holding and restated conclusions.",
        "Some over-explanation or needless summaries.",
        "Mostly trusts the reader; a rare redundant recap.",
        "Treats the reader as intelligent throughout.",
    ),
    "authenticity": (
        "Unmistakably machine-written: stock phrases, false enthusiasm, empty hype.",
        "Many AI tells: buzzwords, forced metaphors, generic claims.",
        "Some AI tells mixed with genuine voice.",
        "Sounds human, with one or two stock phrases.",
        "Sounds like a specific person who knows the subject.",
    ),
    "density": (
        "More than half could be cut: filler, padding, repeated points.",
        "A third to a half could be cut without loss.",
        "Some filler sentences and redundant qualifiers.",
        "Tight, with a few cuttable words.",
        "Nothing to cut: every word carries weight.",
    ),
}
SLOP_DIMENSIONS: tuple[str, ...] = tuple(SLOP_RUBRIC)


def slop_levels(dimension: str) -> list[str]:
    """The ten level criteria of one dimension, ``1/10`` first."""
    bands = SLOP_BANDS[dimension]
    return [f"{level + 1}/10: {bands[level // 2]}" for level in range(SLOP_LEVELS)]


def _slop_questions() -> dict[str, Question]:
    prefix = ("The state holds prose written for a human reader. Apply the ArkaOS Slop "
              f"Score rubric: {SLOP_RUBRIC_INTRO} ")
    return {
        dim: Question(type=QuestionType.SCORE, instructions=_instructions(
            f"{prefix}Dimension: {label} — {question}"), criteria=slop_levels(dim))
        for dim, (label, question) in SLOP_RUBRIC.items()
    }


def slop_level(score: object) -> int | None:
    """The 0-based level of a continuous score: half-up rounding into 0..9.

    Jev answers a score question with a fractional level (1.58 = between
    2/10 and 3/10). Scores within half a level of the scale round into it
    (-0.3 → 0, 9.4 → 9); anything further out is malformed → None.
    """
    if isinstance(score, bool) or not isinstance(score, int | float):
        return None
    if not math.isfinite(score) or not -0.5 <= score < SLOP_LEVELS - 0.5:
        return None
    return math.floor(score + 0.5)


def window_mass(probs: Mapping[str, float] | Sequence[float] | None, level: int) -> float | None:
    """Probability of the levels within :data:`SLOP_WINDOW` of ``level``; None without probs."""
    cells = range(max(0, level - SLOP_WINDOW), min(SLOP_LEVELS, level + SLOP_WINDOW + 1))
    if isinstance(probs, Mapping):
        return math.fsum(float(probs.get(str(i), 0.0)) for i in cells)
    if isinstance(probs, Sequence) and not isinstance(probs, str):
        return math.fsum(float(probs[i]) for i in cells if i < len(probs))
    return None


def slop_dimension(answer: Answer | None) -> tuple[int, float] | None:
    """``(score 1..10, confidence)`` of one dimension, or None.

    Confidence is the probability mass within ±1 level of the rounded
    level, NOT the single most likely cell: a 10-level rubric spreads soft
    prose over neighbouring levels ({'0': 0.28, '1': 0.27, '2': 0.24, …}),
    and "the answer is 2/10 give or take one" is what the score claims.
    Without ``probabilities`` the answer's own ``confidence`` stands in.
    """
    if answer is None:
        return None
    level = slop_level(answer.score)
    if level is None:
        return None
    mass = window_mass(answer.probabilities, level)
    confidence = answer.confidence if mass is None else mass
    return None if confidence is None else (level + 1, confidence)


def _slop_interpret(answers: dict[str, Answer], threshold: float) -> dict[str, int] | None:
    """Five scores and their total, or None.

    Abstains when any dimension is missing or malformed, or when the MEAN
    of the five window confidences is below the threshold. No
    per-dimension floor: rhythm is spread flat on most texts, and a 0.3
    floor abstained on 13 of 33 cached r7 answers.
    """
    read: dict[str, tuple[int, float]] = {}
    for dim in SLOP_DIMENSIONS:
        scored = slop_dimension(answers.get(dim))
        if scored is None:
            return None
        read[dim] = scored
    if math.fsum(conf for _, conf in read.values()) / len(read) < threshold:
        return None
    out = {dim: score for dim, (score, _) in read.items()}
    out["total"] = sum(out.values())
    return out


def slop_needs_revision(value: object) -> bool | None:
    """True below 35/50, False at or above, None without a score."""
    total = value.get("total") if isinstance(value, dict) else None
    if not isinstance(total, int):
        return None
    return total < SLOP_PASS_TOTAL


SLOP_SCORE = Site(
    name="slop-score", questions=_slop_questions, interpret=_slop_interpret,
    risk="read", timeout_ms=QUALITY_TIMEOUT_MS, state_class="diff",
)

QUALITY_SITES: tuple[Site, ...] = (QG_PRESCREEN, SLOP_SCORE)
