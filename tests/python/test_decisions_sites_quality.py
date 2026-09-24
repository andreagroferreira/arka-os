"""core.decisions.sites.quality — qg-prescreen and slop-score (JEV PR3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, write_config

from core.decisions import replay as rp
from core.decisions.client import DecisionUnavailable
from core.decisions.engine import decide
from core.decisions.models import Answer
from core.decisions.paths import repo_root
from core.decisions.privacy import prepare_state
from core.decisions.site import LANGUAGE_PREAMBLE, SiteCall
from core.decisions.sites import quality
from core.decisions.sites.quality import QG_PRESCREEN, QUALITY_SITES, SLOP_SCORE

URLOPEN = "core.decisions.client.urllib.request.urlopen"
SKILL = repo_root() / "arka" / "skills" / "human-writing" / "SKILL.md"


def test_policy_is_pinned():
    assert QUALITY_SITES == (QG_PRESCREEN, SLOP_SCORE)
    table = {s.name: (s.risk, s.direction, s.timeout_ms, s.state_class, s.default_mode)
             for s in QUALITY_SITES}
    assert table == {
        "qg-prescreen": ("write", "any", 5000, "diff", "shadow"),  # replay gate
        "slop-score": ("read", "any", 5000, "diff", "act"),
    }


# --- qg-prescreen -----------------------------------------------------------

def test_neutral_heuristic_is_pinned():
    # Kills: a prescreen baseline that predicts anything (e.g. "rejected").
    assert dict(quality.PRESCREEN_NEUTRAL) == {"verdict": "unknown", "blocker": "none"}
    fresh = quality.prescreen_heuristic()
    assert fresh == dict(quality.PRESCREEN_NEUTRAL) and fresh is not quality.PRESCREEN_NEUTRAL
    fresh["verdict"] = "rejected"
    assert quality.PRESCREEN_NEUTRAL["verdict"] == "unknown"
    with pytest.raises(TypeError):
        quality.PRESCREEN_NEUTRAL["verdict"] = "x"  # type: ignore[index]


def test_replay_baseline_is_neutral_on_every_case():
    for case in rp.load_corpus("qg-prescreen"):
        assert rp.HEURISTICS["qg-prescreen"](case) == {"verdict": "unknown", "blocker": "none"}
    report = rp.replay("qg-prescreen", rp.load_corpus("qg-prescreen"), transport=None)
    assert report.heuristic_accuracy == 0.0 and report.gate == "offline"


def test_prescreen_questions():
    questions = QG_PRESCREEN.questions()
    assert {k: q.instructions for k, q in questions.items()} == {
        "likely_verdict": f"{LANGUAGE_PREAMBLE} {quality.VERDICT_QUESTION}",
        "blocker_class": f"{LANGUAGE_PREAMBLE} {quality.BLOCKER_QUESTION}",
    }
    assert set(questions["likely_verdict"].criteria) == {"approved", "rejected"}
    assert set(questions["blocker_class"].criteria) == {
        "spellcheck", "tests", "diff-review", "security", "lint", "none"}


def _prescreen(verdict: str | None, blocker: str | None, conf: float = 0.9):
    answers = {}
    if verdict:
        answers["likely_verdict"] = Answer(choice=verdict, confidence=conf)
    if blocker:
        answers["blocker_class"] = Answer(choice=blocker, confidence=conf)
    return QG_PRESCREEN.judge(answers, 0.75, None)


def _rej(blocker: str, p: float | None) -> dict:
    return {"verdict": "rejected", "blocker": blocker, "blocker_p": p}


APPROVED = {"verdict": "approved", "blocker": "none", "blocker_p": None}


@pytest.mark.parametrize(("verdict", "blocker", "value"), [
    ("approved", None, APPROVED),
    ("approved", "tests", APPROVED),
    ("rejected", "security", _rej("security", 0.9)),
    ("rejected", "none", _rej("none", 0.9)),
    ("rejected", None, _rej("none", None)),
    ("rejected", "style", _rej("none", None)),  # off-menu → dropped by the guard
    (None, "tests", None),
    ("maybe", "tests", None),
])
def test_prescreen_interpretation(verdict, blocker, value):
    assert _prescreen(verdict, blocker) == value


def test_confident_rejection_survives_an_unsure_blocker():
    # Kills: restoring "rejected needs a confident real blocker, else abstain"
    # (r7: 43.8 % abstention). The unsure class is reported, never promoted.
    answers = {"likely_verdict": Answer(choice="rejected", confidence=0.9),
               "blocker_class": Answer(choice="tests", confidence=0.42)}
    assert QG_PRESCREEN.judge(answers, 0.75, None) == _rej("none", 0.42)
    answers["blocker_class"] = Answer(
        choice="tests", probabilities={"tests": 0.8, "lint": 0.15, "none": 0.05})
    assert QG_PRESCREEN.judge(answers, 0.75, None) == _rej("tests", 0.8)


def test_unsure_verdict_is_the_only_abstention():
    answers = {"likely_verdict": Answer(choice="rejected", confidence=0.74),
               "blocker_class": Answer(choice="security", confidence=0.99)}
    assert QG_PRESCREEN.judge(answers, 0.75, None) is None


def test_prescreen_below_write_threshold_abstains():
    assert _prescreen("approved", None, conf=0.7) is None


def test_diff_state_caps_on_a_line():
    diff = "\n".join(f"+linha {i}" for i in range(5000))
    capped = quality.diff_state(diff, "core/app.py")["diff"]
    assert len(capped) <= quality.MAX_DIFF_CHARS and capped.endswith("\n[truncated]")
    assert capped.split("\n")[-2].startswith("+linha ")


# --- slop-score -------------------------------------------------------------

def test_rubric_is_verbatim_from_human_writing():
    text = SKILL.read_text(encoding="utf-8")
    assert quality.SLOP_RUBRIC_INTRO.replace("Rate the draft 1", "Rate the draft\n1") in text
    for label, question in quality.SLOP_RUBRIC.values():
        assert f"| {label} | {question} |" in text
    for dim, question in SLOP_SCORE.questions().items():
        label, ask = quality.SLOP_RUBRIC[dim]
        assert question.instructions.endswith(f"Dimension: {label} — {ask}")
        assert quality.SLOP_RUBRIC_INTRO in question.instructions
        assert question.type.value == "score" and len(question.criteria) == 10


def test_slop_levels_run_worst_to_best():
    levels = quality.slop_levels("density")
    assert levels[0].startswith("1/10: ") and levels[-1].startswith("10/10: ")
    assert levels[0] == levels[1].replace("2/10", "1/10")
    assert levels[-1].endswith("every word carries weight.")


def _slop(levels: dict[str, float], conf: float = 0.9):
    answers = {d: Answer(score=v, confidence=conf) for d, v in levels.items()}
    return SLOP_SCORE.judge(answers, 0.6, None)


def test_slop_interpretation_maps_levels_to_scores():
    value = _slop({d: 6 for d in quality.SLOP_DIMENSIONS})
    assert value == {**{d: 7 for d in quality.SLOP_DIMENSIONS}, "total": 35}
    assert quality.slop_needs_revision(value) is False
    low = _slop({d: 0 for d in quality.SLOP_DIMENSIONS})
    assert low is not None and low["total"] == 5 and quality.slop_needs_revision(low) is True
    assert quality.slop_needs_revision(None) is None


def test_slop_abstains_on_any_missing_or_unsure_dimension():
    four = {d: 5 for d in quality.SLOP_DIMENSIONS[:4]}
    assert _slop(four) is None
    assert _slop({d: 5 for d in quality.SLOP_DIMENSIONS}, conf=0.5) is None
    assert _slop({**four, "density": 10}) is None  # 10 is past the 9.5 edge of 0..9


@pytest.mark.parametrize(("score", "level"), [
    (-0.3, 0), (0.5, 1), (1.49, 1), (2.5, 3), (9.4, 9), (-0.51, None), (9.5, None),
    (float("nan"), None), (True, None), (None, None),
])
def test_slop_level_rounds_half_up_within_half_a_level(score, level):
    assert quality.slop_level(score) == level


def _dist(**cells: float) -> dict[str, float]:
    probs = {str(i): 0.0 for i in range(10)}
    probs.update({k.removeprefix("p"): v for k, v in cells.items()})
    return probs


# The r7 diagnosis case (Paulo, reason ok, 463 ms): continuous scores and
# the single-cell ``confidence`` Jev returned. Directness's first three
# cells are the recorded ones; the remaining cells of every dimension are
# completed to a distribution whose top cell is the recorded confidence.
DIAGNOSIS = {
    "directness": Answer(score=1.58, confidence=0.37, probabilities=_dist(
        p0=0.28, p1=0.27, p2=0.24, p3=0.12, p4=0.05, p5=0.02, p6=0.01, p7=0.01)),
    "rhythm": Answer(score=2.29, confidence=0.82, probabilities=_dist(
        p0=0.03, p1=0.08, p2=0.82, p3=0.05, p4=0.02)),
    "trust": Answer(score=1.29, confidence=0.71, probabilities=_dist(
        p0=0.12, p1=0.71, p2=0.12, p3=0.03, p4=0.02)),
    "authenticity": Answer(score=0.50, confidence=0.80, probabilities=_dist(
        p0=0.80, p1=0.10, p2=0.04, p3=0.03, p4=0.03)),
    "density": Answer(score=0.76, confidence=0.70, probabilities=_dist(
        p0=0.20, p1=0.70, p2=0.07, p3=0.03)),
}
# A cached r7 answer (8a66f37a…): directness is spread flat over the whole
# scale (confidence 0.0); single-cell max mean 0.40, ``confidence`` mean
# 0.558, window mean 0.784.
R7_FLAT_DIMENSION = {
    "authenticity": Answer(score=1.19, confidence=0.68, probabilities=[
        0.3, 0.39, 0.21, 0.06, 0.01, 0.01, 0.01, 0.01, 0.0, 0.0]),
    "density": Answer(score=0.54, confidence=0.78, probabilities=[
        0.66, 0.26, 0.05, 0.02, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "directness": Answer(score=4.28, confidence=0.0, probabilities=[
        0.14, 0.09, 0.14, 0.13, 0.05, 0.06, 0.07, 0.07, 0.15, 0.1]),
    "rhythm": Answer(score=1.49, confidence=0.63, probabilities=[
        0.25, 0.24, 0.39, 0.11, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0]),
    "trust": Answer(score=1.06, confidence=0.7, probabilities=[
        0.35, 0.41, 0.17, 0.05, 0.01, 0.01, 0.0, 0.0, 0.0, 0.0]),
}


def test_diagnosis_case_scores_instead_of_abstaining():
    # Kills: the single-cell per-dimension rule (directness 0.37 < 0.6 abstained).
    value = SLOP_SCORE.judge(dict(DIAGNOSIS), 0.6, None)
    assert value == {"directness": 3, "rhythm": 3, "trust": 2, "authenticity": 2,
                     "density": 2, "total": 12}
    assert quality.slop_needs_revision(value) is True
    assert quality.slop_dimension(DIAGNOSIS["directness"]) == (3, pytest.approx(0.63))


def test_window_mass_not_the_single_cell_decides():
    # Kills: confidence from the top cell or from ``confidence`` (both mean < 0.6).
    value = SLOP_SCORE.judge(dict(R7_FLAT_DIMENSION), 0.6, None)
    assert value == {"authenticity": 2, "density": 2, "directness": 5, "rhythm": 2,
                     "trust": 2, "total": 13}
    assert quality.slop_dimension(R7_FLAT_DIMENSION["directness"]) == (
        5, pytest.approx(0.24))


def test_window_is_one_level_each_side_and_clipped_at_the_edges():
    probs = [0.5, 0.2, 0.1, 0.05, 0.05, 0.02, 0.02, 0.02, 0.02, 0.02]
    assert quality.window_mass(probs, 0) == pytest.approx(0.7)
    assert quality.window_mass(probs, 4) == pytest.approx(0.12)
    assert quality.window_mass({str(i): p for i, p in enumerate(probs)}, 9) == (
        pytest.approx(0.04))
    assert quality.window_mass(None, 3) is None


def test_mean_below_threshold_abstains():
    flat = [0.1] * 10  # window 0.3 inside the scale
    answers = {d: Answer(score=4.0, probabilities=flat) for d in quality.SLOP_DIMENSIONS}
    assert SLOP_SCORE.judge(answers, 0.6, None) is None
    answers["rhythm"] = Answer(score=4.0, probabilities=_dist(p3=0.1, p4=0.8, p5=0.1))
    assert SLOP_SCORE.judge(answers, 0.6, None) is None  # mean 0.44


# --- privacy: diff states are fail-closed -----------------------------------

@pytest.fixture
def home(monkeypatch, tmp_path) -> Path:
    return isolate_decisions(monkeypatch, tmp_path)


@pytest.mark.parametrize("state", [quality.diff_state("+x = 1", "core/app.py"),
                                   quality.prose_state("Olá.", "docs/guia.md")])
def test_quality_states_never_leave_without_a_client_list(home, state):
    (home / ".arkaos" / "redaction-clients.json").unlink()
    with pytest.raises(DecisionUnavailable, match="egress-denied"):
        prepare_state(state, redact=True, state_class="diff")
    with patch(URLOPEN) as net:
        out = decide([SiteCall(QG_PRESCREEN, quality.prescreen_heuristic())], state,
                     session_id="qg")
    net.assert_not_called()
    assert out["qg-prescreen"].value == {"verdict": "unknown", "blocker": "none"}


def test_prescreen_acts_with_a_client_list(home):
    write_config(home, {"sites": {"qg-prescreen": "act"}})  # default is shadow
    answers = {"qg_prescreen__likely_verdict": {"choice": "rejected", "confidence": 0.9},
               "qg_prescreen__blocker_class": {"choice": "tests", "confidence": 0.85}}
    with patch(URLOPEN, return_value=fake_ok(answers)):
        out = decide([SiteCall(QG_PRESCREEN, quality.prescreen_heuristic())],
                     quality.diff_state("-assert x\n+pass", "tests/test_app.py"), session_id="qg")
    assert out["qg-prescreen"].value == _rej("tests", 0.85)
    assert set(out["qg-prescreen"].answers) == {"likely_verdict", "blocker_class"}
