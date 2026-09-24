"""core.decisions.sites.governance — Stop-hook sites and ui-in-ts (JEV PR3)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, sent_payload

from core.decisions import replay as rp
from core.decisions.config import DecisionsConfig, threshold_for
from core.decisions.engine import decide, resolve
from core.decisions.models import Answer, DecisionResponse
from core.decisions.site import LANGUAGE_PREAMBLE, Site, SiteCall
from core.decisions.sites import governance as gov
from core.decisions.sites.governance import (
    GOVERNANCE_SITES,
    LEARNING_SIGNAL,
    PHANTOM_ACTION,
    SKILL_PROPOSER,
    STOP_SITES,
    SYCOPHANCY,
    UI_IN_TS,
)

URLOPEN = "core.decisions.client.urllib.request.urlopen"
ESCALATE_ONLY = (SYCOPHANCY, PHANTOM_ACTION, UI_IN_TS)
NOUL_KEY = {
    "sycophancy": "is_sycophantic",
    "phantom-action": "claims_unbacked_effect",
    "ui-in-ts": "is_ui_code",
}
STATE = {
    "sycophancy": gov.stop_state("Tens razão.", user_message="apaga a base de dados"),
    "phantom-action": gov.stop_state("Criei o ficheiro.", tool_uses=0),
    "ui-in-ts": gov.ui_state("src/menu.ts", "el.classList.toggle('open')"),
}


def _resolve(site: Site, heuristic: object, answers: dict[str, Answer]):
    response = DecisionResponse(answers={
        f"{site.name.replace('-', '_')}__{k}": v for k, v in answers.items()})
    threshold = threshold_for(DecisionsConfig(), site)
    return resolve(SiteCall(site, heuristic), response, "act", threshold, state=STATE.get(
        site.name, gov.stop_state("x", tool_uses=0)))


# --- policy -----------------------------------------------------------------

def test_policy_is_pinned():
    assert GOVERNANCE_SITES == (SYCOPHANCY, PHANTOM_ACTION, SKILL_PROPOSER, LEARNING_SIGNAL,
                                UI_IN_TS)
    assert GOVERNANCE_SITES[:4] == STOP_SITES
    table = {s.name: (s.risk, s.direction, s.timeout_ms, s.state_class, s.default_mode)
             for s in GOVERNANCE_SITES}
    assert table == {
        "sycophancy": ("write", "escalate_only", 1200, "prompt", "act"),
        "phantom-action": ("write", "escalate_only", 1200, "prompt", "act"),
        "skill-proposer": ("read", "any", 1200, "prompt", "act"),
        "learning-signal": ("write", "any", 1200, "prompt", "act"),
        "ui-in-ts": ("write", "escalate_only", 600, "diff", "act"),
    }


def test_question_texts_are_the_approved_wording():
    expected = {
        "sycophancy": {"is_sycophantic": gov.IS_SYCOPHANTIC},
        "phantom-action": {"claims_unbacked_effect": gov.CLAIMS_UNBACKED_EFFECT},
        "skill-proposer": {"is_repeatable_capability": gov.IS_REPEATABLE_CAPABILITY},
        "learning-signal": {"signal": gov.SIGNAL_QUESTION, "high_leverage": gov.HIGH_LEVERAGE},
        "ui-in-ts": {"is_ui_code": gov.IS_UI_CODE},
    }
    for site in GOVERNANCE_SITES:
        questions = site.questions()
        assert {k: q.instructions for k, q in questions.items()} == {
            k: f"{LANGUAGE_PREAMBLE} {v}" for k, v in expected[site.name].items()}
    signal = LEARNING_SIGNAL.questions()["signal"]
    assert signal.type.value == "choice" and set(signal.criteria) == {
        "explicit", "implicit", "none"}


# --- escalate-only ----------------------------------------------------------

@pytest.mark.parametrize("site", ESCALATE_ONLY, ids=lambda s: s.name)
def test_jev_true_escalates_a_heuristic_miss(site):
    out = _resolve(site, False, {NOUL_KEY[site.name]: Answer(noul=0.97)})
    assert (out.value, out.acted_on, out.reason) == (True, "jev", "jev")


@pytest.mark.parametrize("site", ESCALATE_ONLY, ids=lambda s: s.name)
def test_jev_false_never_clears_a_detection(site):
    # Kills: direction="any" or an is_escalation accepting any change.
    out = _resolve(site, True, {NOUL_KEY[site.name]: Answer(noul=0.02)})
    assert (out.value, out.jev, out.reason) == (True, False, "downgrade-blocked")
    relaxed = dataclasses.replace(site, direction="any")
    loose = _resolve(relaxed, True, {NOUL_KEY[site.name]: Answer(noul=0.02)})
    assert loose.value is False


@pytest.mark.parametrize("site", ESCALATE_ONLY, ids=lambda s: s.name)
def test_escalation_predicate_only_accepts_false_to_true(site):
    esc = site.is_escalation
    assert esc is not None and esc(True, False) is True
    assert not any(esc(j, h) for j, h in ((False, True), (True, True), (None, False)))


def test_write_threshold_governs_the_stop_sites():
    # 0.70 acts at read (0.60) but not at write (0.75).
    out = _resolve(SYCOPHANCY, False, {"is_sycophantic": Answer(noul=0.70)})
    assert (out.value, out.reason) == (False, "abstain")


# --- state and questions_for ------------------------------------------------

def test_stop_state_shape_and_count_coercion():
    state = gov.stop_state("resposta", user_message="pedido", tool_uses=3)
    assert state == {"response": "resposta", "user_message": "pedido", "tool_uses": 3}
    for bad in (None, True, False, -1, "2", 1.0):
        assert gov.stop_state("r", tool_uses=bad)["tool_uses"] is None  # type: ignore[arg-type]


def test_long_text_is_capped_between_tokens():
    text = ("palavra " * 2000).strip()
    capped = gov.stop_state(text)["response"]
    assert len(capped) <= gov.MAX_TEXT_CHARS and capped.endswith(" [truncated]")
    assert capped[: -len(" [truncated]")].split(" ")[-1] == "palavra"
    assert gov.cap_between_tokens("x" * 7000, 100) == " [truncated]"


@pytest.mark.parametrize(("tool_uses", "asked"), [(0, True), (1, False), (None, False)])
def test_phantom_is_asked_only_with_zero_tool_calls(tool_uses, asked):
    state = gov.stop_state("Fiz commit.", tool_uses=tool_uses)
    assert bool(PHANTOM_ACTION.questions_of(state)) is asked
    yes = {"claims_unbacked_effect": Answer(noul=0.99)}
    assert PHANTOM_ACTION.judge(yes, 0.75, state) is (True if asked else None)


def test_phantom_questions_for_rejects_a_bool_count():
    assert PHANTOM_ACTION.questions_of({"tool_uses": False}) == {}


@pytest.mark.parametrize("marker", ["[arka:trivial]", "[arka:skill-skip]"])
def test_skill_proposer_never_asks_past_a_bypass_marker(marker):
    state = gov.stop_state(f"[arka:gate:4] workflow checklist template {marker}")
    assert SKILL_PROPOSER.questions_of(state) == {}
    assert SKILL_PROPOSER.questions_of(gov.stop_state("[arka:gate:4] done")) != {}


@pytest.mark.parametrize(("path", "asked"), [
    ("src/a.ts", True), ("bin/cli.js", True), ("x.MJS", True), ("x.cjs", True),
    ("src/App.tsx", False), ("src/App.vue", False), ("core/a.py", False), ("", False),
])
def test_ui_in_ts_asks_only_for_heuristic_suffixes(path, asked):
    assert bool(UI_IN_TS.questions_of(gov.ui_state(path, "x"))) is asked


def test_ui_suffixes_mirror_the_frontend_gate():
    from core.workflow.frontend_gate import _HEURISTIC_SUFFIXES

    assert frozenset(_HEURISTIC_SUFFIXES) == gov.UI_TS_SUFFIXES


# --- learning-signal --------------------------------------------------------

def _learning(signal: Answer | None, leverage: Answer | None):
    answers = {k: v for k, v in (("signal", signal), ("high_leverage", leverage)) if v}
    return LEARNING_SIGNAL.judge(answers, 0.75, None)


def test_signal_decides_and_leverage_is_optional():
    # Kills: restoring "both halves or neither" (r7: 32.4 % abstention).
    explicit = Answer(choice="explicit", confidence=0.9)
    assert _learning(explicit, Answer(noul=0.9)) == {"signal": "explicit", "high_leverage": True}
    assert _learning(explicit, None) == {"signal": "explicit", "high_leverage": False}
    assert _learning(explicit, Answer(noul=0.5)) == {"signal": "explicit", "high_leverage": False}
    assert _learning(explicit, Answer(noul=0.1)) == {"signal": "explicit", "high_leverage": False}
    assert _learning(None, Answer(noul=0.9)) is None


def test_no_signal_is_never_high_leverage():
    none = Answer(choice="none", confidence=0.9)
    assert _learning(none, Answer(noul=0.95)) == {"signal": "none", "high_leverage": False}


def test_learning_signal_rejects_off_menu_and_unsure_choices():
    assert _learning(Answer(choice="rule", confidence=0.99), Answer(noul=0.1)) is None
    assert _learning(Answer(choice="implicit", confidence=0.6), Answer(noul=0.1)) is None
    assert _learning(Answer(choice="none", confidence=0.8), Answer(noul=0.1)) == {
        "signal": "none", "high_leverage": False}


# --- heuristics mirror the governance detectors -----------------------------

def _transcript(tool_uses: int, text: str) -> str:
    blocks = [{"type": "tool_use", "id": f"t{i}", "name": "Read"} for i in range(tool_uses)]
    records = [{"role": "user", "content": "faz isto"},
               {"role": "assistant", "content": [*blocks, {"type": "text", "text": text}]}]
    return "\n".join(json.dumps(r) for r in records)


def test_sycophancy_heuristic_is_the_detector():
    from core.governance.sycophancy_detector import detect_sycophancy

    for case in rp.load_corpus("sycophancy"):
        assert gov.heuristic_sycophantic(case.prompt) is detect_sycophancy(
            case.prompt).is_sycophantic


def test_phantom_heuristic_matches_the_live_check():
    from core.governance.phantom_action_check import check_phantom_actions

    for case in rp.load_corpus("phantom-action"):
        n = int(case.context["tool_uses"])
        live = not check_phantom_actions(case.prompt, _transcript(n, case.prompt)).passed
        assert gov.heuristic_unbacked_effect(case.prompt, n) is live, case.id
    assert gov.heuristic_unbacked_effect("Fiz commit.", None) is False


def test_skill_heuristic_matches_evaluate_without_writing(tmp_path: Path):
    from core.governance.skill_proposer import evaluate

    for case in rp.load_corpus("skill-proposer"):
        live = evaluate(case.prompt, output_dir=tmp_path / case.id, today="2026-09-24")
        assert gov.heuristic_repeatable_capability(case.prompt) is live.should_propose, case.id
    before = sorted(tmp_path.rglob("*"))
    gov.heuristic_repeatable_capability(rp.load_corpus("skill-proposer")[0].prompt)
    assert sorted(tmp_path.rglob("*")) == before


def test_learning_heuristic_is_the_detector():
    from core.governance.learning_detector import detect_correction_signal

    for case in rp.load_corpus("learning-signal"):
        verdict = detect_correction_signal(case.prompt)
        assert gov.heuristic_learning_signal(case.prompt) == {
            "signal": verdict.mode, "high_leverage": verdict.is_high_leverage}


def test_ui_heuristic_is_the_gate_function():
    from core.workflow.frontend_gate import is_heuristic_ui_file

    for case in rp.load_corpus("ui-in-ts"):
        path = str(case.context["path"])
        assert gov.heuristic_ui_code(path, case.prompt) is is_heuristic_ui_file(
            path, "Write", {"content": case.prompt})


# --- one decide() call for the four Stop sites ------------------------------

@pytest.fixture
def home(monkeypatch, tmp_path):
    return isolate_decisions(monkeypatch, tmp_path)


def _stop_calls() -> list[SiteCall]:
    return [SiteCall(SYCOPHANCY, False), SiteCall(PHANTOM_ACTION, False),
            SiteCall(SKILL_PROPOSER, False),
            SiteCall(LEARNING_SIGNAL, {"signal": "none", "high_leverage": False})]


def test_stop_sites_share_one_request(home):
    answers = {
        "sycophancy__is_sycophantic": {"noul": 0.95},
        "phantom_action__claims_unbacked_effect": {"noul": 0.96},
        "skill_proposer__is_repeatable_capability": {"noul": 0.1},
        "learning_signal__signal": {"choice": "implicit", "confidence": 0.9},
        "learning_signal__high_leverage": {"noul": 0.1},
    }
    state = gov.stop_state("Boa ideia! Já ficou feito.", user_message="prefiro tabelas",
                           tool_uses=0)
    with patch(URLOPEN, return_value=fake_ok(answers)) as net:
        out = decide(_stop_calls(), state, session_id="stop")
    assert net.call_count == 1
    assert set(sent_payload(net)["questions"]) == set(answers)
    assert net.call_args.kwargs["timeout"] <= gov.STOP_TIMEOUT_MS / 1000
    assert out["sycophancy"].value is True and out["phantom-action"].value is True
    assert out["learning-signal"].value == {"signal": "implicit", "high_leverage": False}
    assert set(out["learning-signal"].answers) == {"signal", "high_leverage"}


def test_tool_calls_on_record_drop_the_phantom_question(home):
    answers = {"sycophancy__is_sycophantic": {"noul": 0.1}}
    state = gov.stop_state("Criei o ficheiro.", tool_uses=2)
    with patch(URLOPEN, return_value=fake_ok(answers)) as net:
        out = decide(_stop_calls(), state, session_id="stop")
    assert not any(k.startswith("phantom_action__") for k in sent_payload(net)["questions"])
    assert (out["phantom-action"].value, out["phantom-action"].acted_on) == (False, "heuristic")
