"""Stop hook x the four Jev Stop sites (JEV Decisions Layer PR3, lane 2A).

Spec decisions 1, 4 and 5: ONE bounded ``decide()`` per Stop, capped at
min(1200 ms, what the StopBudget has left); sycophancy and phantom-action
escalate-only; skill-proposer and learning-signal any direction; the new
learning-signal consumer emits ``[arka:learned-rule ...]`` and, when
high-leverage, Marta's confirmation line. Network is mocked at
``urlopen``; no test reaches OpenRouter.
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, read_jsonl, sent_payload

from core.hooks import stop as stop_hook
from core.hooks.stop_budget import StopBudget

URLOPEN = "core.decisions.client.urllib.request.urlopen"
REPO_ROOT = Path(__file__).resolve().parents[2]
SID = "sess-jev"
CLEAN_CLOSE = (
    "[arka:gate:4] The migration carries a risk: the index rebuild locks the"
    " orders table, so it runs in the maintenance window."
)
SYCOPHANTIC_CLOSE = "Tens razão. Vou implementar como pediste."
PHANTOM_CLOSE = "Criei o ficheiro core/x.py e corri os testes."
PLAIN_REQUEST = "migra a tabela de encomendas"
EXPLICIT_RULE = (
    "Nunca faças commit sem autorização. Regra permanente, NON-NEGOTIABLE,"
    " sempre em todos os projetos da equipa e de governance."
)
IMPLICIT_RULE = "prefiro que uses pytest em vez de unittest"


# ─── harness ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _anchor(tmp_path, monkeypatch):
    """Same isolation as test_stop_hook.TestMainInProcess, plus the
    enforcement log and the proposal dir pointed into tmp_path."""
    monkeypatch.chdir(tmp_path)
    from core.workflow import state as _st

    _st.reset_root_cache()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path(str(tmp_path / "home"))))
    monkeypatch.setenv("ARKAOS_ROOT", str(REPO_ROOT))
    monkeypatch.setenv("ARKA_STOP_LINT", "0")
    monkeypatch.setenv("ARKA_SESSION_MEMORY", "0")
    monkeypatch.setenv("ARKA_AUTO_DOC_QUEUE", str(tmp_path / "queue"))
    monkeypatch.setenv("ARKA_WF_REQUIRED_DIR", str(tmp_path / "wf"))
    monkeypatch.delenv("ARKA_STOP_BUDGET_MS", raising=False)
    monkeypatch.setattr(stop_hook, "arkaos_temp_dir", lambda name: tmp_path / name)
    monkeypatch.setattr(
        "core.workflow.flow_enforcer.TELEMETRY_PATH", tmp_path / "enforcement.jsonl")
    monkeypatch.setattr(
        "core.governance.skill_proposer._DEFAULT_OUTPUT_DIR", tmp_path / "proposals")
    monkeypatch.setattr("core.decisions.shadow.spawn_shadow", _no_shadow)
    monkeypatch.setattr("subprocess.Popen", _no_popen)
    (tmp_path / "wf").mkdir()


def _no_shadow(*_a: Any, **_k: Any) -> None:
    raise AssertionError("the Stop stage must never spawn a shadow worker here")


def _no_popen(*_a: Any, **_k: Any) -> None:
    raise AssertionError("no detached spawns from in-process tests")


@pytest.fixture
def jev(monkeypatch, tmp_path):
    home = isolate_decisions(monkeypatch, tmp_path)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


def _transcript(tmp_path: Path, user: str, close: str, *, tools: int = 0) -> Path:
    recs: list[dict[str, Any]] = [{"role": "user", "content": user}]
    for _ in range(tools):
        recs.append({"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]})
    recs.append({"role": "assistant", "content": close})
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    return path


def _stop(tmp_path: Path, transcript: Path, *, flagged: bool = True) -> int:
    if flagged:
        (tmp_path / "wf" / SID).write_text("1", encoding="utf-8")
    return stop_hook.main({
        "session_id": SID, "transcript_path": str(transcript),
        "stop_hook_active": "false", "cwd": str(tmp_path),
    })


def _entry(tmp_path: Path) -> dict[str, Any]:
    rows = read_jsonl(tmp_path / "enforcement.jsonl")
    assert len(rows) == 1, "one enforcement row per flagged Stop"
    return rows[0]


def _answers(**by_site: dict[str, Any]) -> object:
    return fake_ok(by_site)


def _noul(p: float) -> dict[str, Any]:
    return {"type": "noul", "noul": p}


def _learning(signal: str, high: float, conf: float = 0.95) -> dict[str, dict[str, Any]]:
    return {
        "learning_signal__signal": {"type": "choice", "choice": signal, "confidence": conf},
        "learning_signal__high_leverage": _noul(high),
    }


def _context(capsys) -> str:
    out = capsys.readouterr().out.strip()
    if not out:
        return ""
    lines = out.splitlines()
    assert len(lines) == 1, "a Stop hook prints one JSON object or none"
    return json.loads(lines[0])["hookSpecificOutput"]["additionalContext"]


# ─── budget: the Stop hook never waits past its deadline ─────────────────


def _sleeping(*_a: Any, **_k: Any) -> object:
    time.sleep(3.0)
    raise AssertionError("unreachable: the deadline abandons this thread")


def test_a_sleeping_endpoint_is_cut_at_the_budget(jev, tmp_path, monkeypatch):
    """Budget 900 ms - 500 reserve → the call gets ≈400 ms, not the 1200 ms
    site cap. Mutation (StopBudget.remaining_ms → ``cap``): the call waits
    the full 1.2 s and the elapsed assertion kills the test."""
    monkeypatch.setenv("ARKA_STOP_BUDGET_MS", "900")
    transcript = _transcript(tmp_path, PLAIN_REQUEST, SYCOPHANTIC_CLOSE)
    with patch(URLOPEN, side_effect=_sleeping) as net:
        start = time.monotonic()
        assert _stop(tmp_path, transcript) == 0
        elapsed = time.monotonic() - start
    assert net.call_count == 1
    assert elapsed < 1.0, f"the Stop call outlived its budget: {elapsed:.2f}s"
    entry = _entry(tmp_path)
    assert entry["decisions"]["fallback_used"] is True
    assert entry["decisions"]["reason"] == "timeout"
    assert entry["sycophancy_is_flagged"] is True  # the regex verdict stands
    rows = read_jsonl(tmp_path / "decisions.jsonl")
    assert {r["site"] for r in rows} == set(stop_hook.STOP_SITE_NAMES)
    assert all(r["fallback_used"] is True and r["reason"] == "timeout" for r in rows)


def test_an_exhausted_budget_never_reaches_the_wire(jev, tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_STOP_BUDGET_MS", "400")  # below the 500 ms reserve
    transcript = _transcript(tmp_path, PLAIN_REQUEST, PHANTOM_CLOSE)
    with patch(URLOPEN) as net:
        assert _stop(tmp_path, transcript) == 0
    net.assert_not_called()
    entry = _entry(tmp_path)
    assert entry["decisions"] == {
        "fallback_used": True, "reason": "deadline", "degraded": "budget",
        "acted_on": dict.fromkeys(stop_hook.STOP_SITE_NAMES, "heuristic"),
    }
    assert entry["phantom_check_passed"] is False  # heuristics ran
    degraded = read_jsonl(jev / ".arkaos" / "telemetry" / "hook-degraded.jsonl")
    assert [(d["hook"], d["reason"], d["detail"]) for d in degraded] == [
        ("stop", "decisions-unavailable", "deadline")]


def test_stop_budget_reserves_500_ms(monkeypatch):
    monkeypatch.setenv("ARKA_STOP_BUDGET_MS", "3000")
    budget = StopBudget(start=time.monotonic())
    assert 2400 <= budget.remaining_ms(10_000) <= 2500
    assert budget.remaining_ms(1200) == 1200
    monkeypatch.setenv("ARKA_STOP_BUDGET_MS", "junk")
    assert StopBudget(start=time.monotonic() - 10).remaining_ms(1200) == 0


# ─── one call, the right state, never the transcript ─────────────────────


def test_one_call_carries_four_sites_and_only_the_closing_text(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(sycophancy__is_sycophantic=_noul(0.02))) as net:
        _stop(tmp_path, transcript)
    assert net.call_count == 1
    payload = sent_payload(net)
    assert payload["state"] == {
        "response": CLEAN_CLOSE, "user_message": PLAIN_REQUEST, "tool_uses": 0}
    assert {k.split("__")[0] for k in payload["questions"]} == {
        "sycophancy", "phantom_action", "skill_proposer", "learning_signal"}
    assert net.call_args.kwargs["timeout"] <= 1.2


def test_tools_on_record_drop_the_phantom_question(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE, tools=2)
    with patch(URLOPEN, return_value=_answers()) as net:
        _stop(tmp_path, transcript)
    payload = sent_payload(net)
    assert payload["state"]["tool_uses"] == 2
    assert not any(k.startswith("phantom_action__") for k in payload["questions"])


def test_an_unflagged_turn_asks_learning_signal_only(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers()) as net:
        _stop(tmp_path, transcript, flagged=False)
    payload = sent_payload(net)
    assert payload["state"] == {
        "response": "", "user_message": PLAIN_REQUEST, "tool_uses": None}
    assert set(payload["questions"]) == {
        "learning_signal__signal", "learning_signal__high_leverage"}
    assert not (tmp_path / "enforcement.jsonl").exists()


# ─── escalate-only: sycophancy ───────────────────────────────────────────


def test_jev_flags_what_the_sycophancy_regex_missed(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(sycophancy__is_sycophantic=_noul(0.97))):
        _stop(tmp_path, transcript)
    entry = _entry(tmp_path)
    assert entry["sycophancy_is_flagged"] is True
    assert entry["sycophancy_signals"] == ["jev"]
    assert entry["sycophancy_confidence"] == pytest.approx(0.97)
    assert entry["decisions"]["acted_on"]["sycophancy"] == "jev"


def test_jev_never_clears_a_sycophancy_detection(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, SYCOPHANTIC_CLOSE)
    with patch(URLOPEN, return_value=_answers(sycophancy__is_sycophantic=_noul(0.01))):
        _stop(tmp_path, transcript)
    entry = _entry(tmp_path)
    assert entry["sycophancy_is_flagged"] is True
    assert "jev" not in entry["sycophancy_signals"]
    assert entry["decisions"]["acted_on"]["sycophancy"] == "heuristic"


def test_the_consumer_rechecks_escalate_only(monkeypatch):
    """Even an outcome that claims Jev cleared the flag cannot clear it:
    ``_sycophancy_verdict`` only ever adds (defence in depth over the engine)."""
    from core.decisions.site import Outcome
    from core.governance.sycophancy_detector import detect_sycophancy

    cleared = Outcome(False, True, False, 0.99, "act", "jev", "jev")
    verdicts = stop_hook.StopVerdicts({"sycophancy": cleared})
    flagged, _signals, _conf = stop_hook._sycophancy_verdict(
        detect_sycophancy(SYCOPHANTIC_CLOSE), verdicts)
    assert flagged is True


# ─── escalate-only: phantom-action ───────────────────────────────────────


def test_jev_flags_an_unbacked_effect_the_regex_missed(jev, tmp_path):
    close = "[arka:gate:4] Tudo pronto e publicado no ambiente de staging."
    transcript = _transcript(tmp_path, PLAIN_REQUEST, close)
    with patch(URLOPEN, return_value=_answers(
            phantom_action__claims_unbacked_effect=_noul(0.95))):
        _stop(tmp_path, transcript)
    entry = _entry(tmp_path)
    assert entry["phantom_check_passed"] is False
    assert entry["phantom_check_reason"] == "phantom-action-jev"
    state = json.loads((tmp_path / "arkaos-phantom" / f"{SID}.json").read_text())
    assert state["passed"] is False and "Jev" in state["suggestion"]


def test_jev_never_clears_a_phantom_detection(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, PHANTOM_CLOSE)
    with patch(URLOPEN, return_value=_answers(
            phantom_action__claims_unbacked_effect=_noul(0.01))):
        _stop(tmp_path, transcript)
    entry = _entry(tmp_path)
    assert entry["phantom_check_passed"] is False
    assert entry["phantom_check_reason"] == "phantom-action"


# ─── skill-proposer: any direction, bypass absolute ──────────────────────


def _skill_state(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "arkaos-skill-proposal" / f"{SID}.json").read_text())


def test_jev_proposes_a_skill_the_ladder_missed(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(
            skill_proposer__is_repeatable_capability=_noul(0.9))):
        _stop(tmp_path, transcript)
    state = _skill_state(tmp_path)
    assert (state["should_propose"], state["reason"]) == (True, "proposed")
    assert Path(state["proposal_path"]).is_file()


def test_jev_declines_a_skill_the_ladder_proposed(jev, tmp_path):
    close = (
        "[arka:gate:4] Shipped the four-phase release workflow: the checklist"
        " template and the rollback procedure are now a reusable playbook."
    )
    transcript = _transcript(tmp_path, PLAIN_REQUEST, close)
    with patch(URLOPEN, return_value=_answers(
            skill_proposer__is_repeatable_capability=_noul(0.05))):
        _stop(tmp_path, transcript)
    state = _skill_state(tmp_path)
    assert (state["should_propose"], state["reason"]) == (False, "jev-declined")
    assert not (tmp_path / "proposals").exists()


def test_a_bypass_marker_is_never_asked_about(jev, tmp_path):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, "[arka:trivial] typo fixed")
    with patch(URLOPEN, return_value=_answers()) as net:
        _stop(tmp_path, transcript)
    assert not any(
        k.startswith("skill_proposer__") for k in sent_payload(net)["questions"])
    assert _skill_state(tmp_path)["reason"] == "bypass-marker"


# ─── learning-signal consumer ────────────────────────────────────────────


@pytest.mark.parametrize(("user", "signal", "confirm"), [
    (EXPLICIT_RULE, "explicit", True),
    (IMPLICIT_RULE, "implicit", False),
])
def test_heuristic_learning_marker(tmp_path, capsys, user, signal, confirm):
    """Suite bypass on: the detector alone drives the marker."""
    transcript = _transcript(tmp_path, user, CLEAN_CLOSE)
    with patch(URLOPEN) as net:
        _stop(tmp_path, transcript, flagged=False)
    net.assert_not_called()
    context = _context(capsys)
    assert f"signal={signal}]" in context
    assert context.startswith("[arka:learned-rule confidence=")
    assert ("[arka:learned-rule:confirm] marta-cqo" in context) is confirm


def test_no_marker_without_a_signal(tmp_path, capsys):
    transcript = _transcript(tmp_path, "obrigado, está ótimo", CLEAN_CLOSE)
    _stop(tmp_path, transcript, flagged=False)
    assert _context(capsys) == ""


def test_jev_learning_signal_drives_the_marker(jev, tmp_path, capsys):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(**_learning("explicit", 0.96, 0.91))):
        _stop(tmp_path, transcript, flagged=False)
    assert _context(capsys) == (
        "[arka:learned-rule confidence=0.91 signal=explicit]\n"
        + stop_hook._MARTA_CONFIRM)


def test_the_marker_prints_the_signals_own_confidence(jev, tmp_path, capsys):
    """An unsure leverage (0.50) must not lower a confident signal's 0.90:
    ``Outcome.confidence`` is the minimum across answers, not the signal's."""
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(**_learning("explicit", 0.50, 0.90))):
        _stop(tmp_path, transcript, flagged=False)
    assert _context(capsys) == "[arka:learned-rule confidence=0.90 signal=explicit]"


def test_jev_can_lower_the_learning_signal(jev, tmp_path, capsys):
    """learning-signal is ``any`` direction: Jev's ``none`` silences the regex."""
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(**_learning("none", 0.02))):
        _stop(tmp_path, transcript, flagged=False)
    assert _context(capsys) == ""


def test_confirmation_only_with_high_leverage(jev, tmp_path, capsys):
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN, return_value=_answers(**_learning("implicit", 0.03, 0.8))):
        _stop(tmp_path, transcript, flagged=False)
    assert _context(capsys) == "[arka:learned-rule confidence=0.80 signal=implicit]"


def test_learning_lines_share_the_notice_emission(tmp_path, capsys):
    from core.governance import reviewer_ledger

    reviewer_ledger.queue_notice(SID, None, "[arka:subagent-qa] francisca-tech needs gating")
    transcript = _transcript(tmp_path, IMPLICIT_RULE, CLEAN_CLOSE)
    _stop(tmp_path, transcript, flagged=False)
    context = _context(capsys)  # asserts ONE JSON object
    assert context.splitlines()[0].startswith("[arka:subagent-qa]")
    assert context.splitlines()[1].startswith("[arka:learned-rule confidence=")
    assert reviewer_ledger.notices_context(SID) == ""


def test_the_hook_never_writes_memory(tmp_path):
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    _stop(tmp_path, transcript)
    home = tmp_path / "home"
    written = [p for p in home.rglob("*") if p.is_file() and "memory" in str(p).lower()]
    assert written == []


# ─── learning-signal: once per user message, not once per Stop ───────────

LIVE_FALSE_POSITIVE = "conitnua ja tens tudo disponivel"


def _fresh_answers(**by_site: dict[str, Any]) -> Any:
    """A new response per call: a repeat Stop must not re-read a spent body."""
    return lambda *_a, **_k: _answers(**by_site)


def _learning_keys(payload: dict[str, Any]) -> set[str]:
    return {k for k in payload["questions"] if k.startswith("learning_signal__")}


def _digest_file(tmp_path: Path) -> Path:
    return tmp_path / "arkaos-learning-signal" / f"{SID}.json"


def test_a_repeat_stop_never_reasks_learning_signal(jev, tmp_path, capsys):
    """Live defect: 8 consecutive Stops on one operator message printed the
    marker 8 times. The second Stop asks the other three sites only, and
    prints no marker. Mutation (drop the digest check in ``_stop_verdicts``):
    the second payload carries the learning keys and this test dies."""
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    with patch(URLOPEN, side_effect=_fresh_answers(**_learning("explicit", 0.96, 0.91))) as net:
        _stop(tmp_path, transcript)
        first = _context(capsys)
        _stop(tmp_path, transcript)
        second = _context(capsys)
    assert net.call_count == 2
    assert _learning_keys(sent_payload(net, 0)) == {
        "learning_signal__signal", "learning_signal__high_leverage"}
    assert _learning_keys(sent_payload(net, 1)) == set()
    assert {k.split("__")[0] for k in sent_payload(net, 1)["questions"]} == {
        "sycophancy", "phantom_action", "skill_proposer"}
    assert sent_payload(net, 1)["state"]["user_message"] == EXPLICIT_RULE
    assert first.startswith("[arka:learned-rule confidence=0.91 signal=explicit]")
    assert second == ""


def test_an_unflagged_repeat_stop_makes_no_call(jev, tmp_path, capsys):
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    with patch(URLOPEN, side_effect=_fresh_answers(**_learning("explicit", 0.96))) as net:
        _stop(tmp_path, transcript, flagged=False)
        _stop(tmp_path, transcript, flagged=False)
    assert net.call_count == 1
    out = capsys.readouterr().out
    assert out.count("[arka:learned-rule confidence=") == 1


def test_a_new_user_message_is_classified_again(jev, tmp_path, capsys):
    with patch(URLOPEN, side_effect=_fresh_answers(**_learning("implicit", 0.03, 0.8))) as net:
        _stop(tmp_path, _transcript(tmp_path, IMPLICIT_RULE, CLEAN_CLOSE), flagged=False)
        assert _context(capsys).startswith("[arka:learned-rule")
        _stop(tmp_path, _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE), flagged=False)
        assert _context(capsys).startswith("[arka:learned-rule")
    assert net.call_count == 2
    assert all(_learning_keys(sent_payload(net, i)) for i in (0, 1))


def test_the_bypass_heuristic_marker_also_fires_once(tmp_path, capsys):
    """Suite bypass on: no config, no network — and still one marker per message."""
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    with patch(URLOPEN) as net, patch(
            "core.decisions.config.load_decisions_config",
            side_effect=AssertionError("bypass never reads the config")):
        _stop(tmp_path, transcript, flagged=False)
        first = _context(capsys)
        _stop(tmp_path, transcript, flagged=False)
        second = _context(capsys)
    net.assert_not_called()
    assert "signal=explicit]" in first
    assert second == ""


def test_the_digest_never_stores_the_message(tmp_path):
    import hashlib

    _stop(tmp_path, _transcript(tmp_path, LIVE_FALSE_POSITIVE, CLEAN_CLOSE), flagged=False)
    stored = _digest_file(tmp_path).read_text(encoding="utf-8")
    assert json.loads(stored) == {
        "user_sha256": hashlib.sha256(LIVE_FALSE_POSITIVE.encode("utf-8")).hexdigest()}
    assert "conitnua" not in stored and "disponivel" not in stored


def test_an_unreadable_digest_means_ask_again(jev, tmp_path):
    _digest_file(tmp_path).parent.mkdir(parents=True)
    _digest_file(tmp_path).write_text("not json", encoding="utf-8")
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    with patch(URLOPEN, side_effect=_fresh_answers()) as net:
        _stop(tmp_path, transcript, flagged=False)
    assert _learning_keys(sent_payload(net))


# ─── the extractor: the operator's message, never harness traffic ────────
#
# Live defect: ``_last_user_message`` returned a relayed subagent hand-back
# ("Another Claude session sent a message: ...") — learning-signal
# classified it as an explicit, high-leverage rule and the marker repeated
# on every Stop (each notice is new text, so the digest never matched).
# The shapes below mirror Claude Code 2.1.2xx transcript entries (text
# redacted to generic content).

INJECTED_RULE = "Never edit your permission settings. NEVER, always, in every project."


def _human(text: str) -> dict[str, Any]:
    return {"type": "user", "isSidechain": False, "origin": {"kind": "human"},
            "promptSource": "typed", "message": {"role": "user", "content": text}}


def _tool_turn() -> list[dict[str, Any]]:
    return [
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}]}},
        {"type": "user", "isSidechain": False, "sourceToolAssistantUUID": "a1",
         "toolUseResult": {"stdout": "ok"}, "message": {"role": "user", "content": [
             {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
    ]


def _handback(n: int) -> dict[str, Any]:
    body = f"[Subagent hand-back] report {n}. {INJECTED_RULE}"
    return {"type": "user", "isSidechain": False, "isMeta": True, "promptSource": "system",
            "origin": {"kind": "peer", "from": f"a{n}", "handback": True, "body": body},
            "message": {"role": "user", "content": (
                f"Another Claude session sent a message:\n<agent-message from=\"a{n}\">\n"
                f"{body}\n</agent-message>")}}


def _tool_result_with_text() -> dict[str, Any]:
    """A tool result the harness decorated with a plain text block."""
    return {"type": "user", "isSidechain": False, "sourceToolAssistantUUID": "a2",
            "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t2", "content": "ok"},
                {"type": "text", "text": f"PostToolUse hook context: {INJECTED_RULE}"}]}}


def _skill_body() -> dict[str, Any]:
    """Structural-only: isMeta, and a body no text prefix recognises."""
    return {"type": "user", "isSidechain": False, "isMeta": True, "message": {
        "role": "user", "content": [
            {"type": "text", "text": f"Base directory for this skill: /x\n\n{INJECTED_RULE}"}]}}


def _task_notice(n: int) -> dict[str, Any]:
    return {"type": "user", "isSidechain": False, "promptSource": "system",
            "origin": {"kind": "task-notification"}, "message": {"role": "user", "content": (
                f"<task-notification>\n<task-id>b{n}</task-id>\n<status>completed</status>\n"
                f"<summary>{INJECTED_RULE}</summary>\n</task-notification>")}}


def _reminder(n: int) -> dict[str, Any]:
    """Text-only: no structural flag, recognised by its prefix alone."""
    return {"type": "user", "isSidechain": False, "message": {"role": "user", "content": (
        f"<system-reminder>\n{INJECTED_RULE} ({n})\n</system-reminder>")}}


def _injected(n: int) -> list[dict[str, Any]]:
    return [_handback(n), _skill_body(), _task_notice(n), _reminder(n)]


def _close(text: str = CLEAN_CLOSE) -> dict[str, Any]:
    return {"type": "assistant", "message": {"role": "assistant", "content": text}}


def _write(tmp_path: Path, recs: list[dict[str, Any]]) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    return path


def _raw(recs: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r) for r in recs)


def test_the_extractor_returns_the_operator_not_the_harness():
    recs = [_human(EXPLICIT_RULE), *_tool_turn(), *_injected(1), _close()]
    assert stop_hook._last_user_message(_raw(recs)) == EXPLICIT_RULE


@pytest.mark.parametrize(
    "entry", [_handback(1), _skill_body(), _task_notice(1), _reminder(1), _tool_result_with_text()],
    ids=["peer-handback", "meta-skill-body", "task-notification", "system-reminder",
         "decorated-tool-result"])
def test_each_injected_shape_alone_is_skipped(entry):
    """One shape per filter layer: a structural-only (skill body) and a
    text-only (reminder) entry each die when their layer is removed."""
    assert stop_hook._last_user_message(_raw([_human(PLAIN_REQUEST), entry])) == PLAIN_REQUEST


def test_injected_blocks_are_dropped_from_a_human_message():
    entry = _human(PLAIN_REQUEST)
    entry["message"]["content"] = [
        {"type": "text", "text": PLAIN_REQUEST},
        {"type": "text", "text": f"<system-reminder>{INJECTED_RULE}</system-reminder>"}]
    assert stop_hook._last_user_message(_raw([entry])) == PLAIN_REQUEST


def test_an_injected_only_transcript_asks_nothing(jev, tmp_path, capsys):
    recs = [*_tool_turn(), *_injected(1), *_injected(2), _close()]
    assert stop_hook._last_user_message(_raw(recs)) == ""
    with patch(URLOPEN, side_effect=_fresh_answers(**_learning("explicit", 0.96))) as net:
        _stop(tmp_path, _write(tmp_path, recs), flagged=False)
    net.assert_not_called()
    assert _context(capsys) == ""


def test_notices_after_one_message_never_repeat_the_marker(jev, tmp_path, capsys):
    """The live repeat: one operator message, then three Stops whose only new
    user entries are harness notices. One call, one marker."""
    recs: list[dict[str, Any]] = [_human(EXPLICIT_RULE), _close()]
    out: list[str] = []
    with patch(URLOPEN, side_effect=_fresh_answers(**_learning("explicit", 0.96, 0.91))) as net:
        for n in range(4):
            if n:
                recs[-1:-1] = _injected(n)
            _stop(tmp_path, _write(tmp_path, recs), flagged=False)
            out.append(_context(capsys))
    assert net.call_count == 1
    assert sent_payload(net, 0)["state"]["user_message"] == EXPLICIT_RULE
    assert out[0].startswith("[arka:learned-rule confidence=0.91 signal=explicit]")
    assert out[1:] == ["", "", ""]


def test_sycophancy_judges_against_the_operator_message(jev, tmp_path):
    recs = [_human(PLAIN_REQUEST), *_tool_turn(), *_injected(1), _close(SYCOPHANTIC_CLOSE)]
    with patch(URLOPEN, side_effect=_fresh_answers()) as net:
        _stop(tmp_path, _write(tmp_path, recs))
    payload = sent_payload(net, 0)
    assert any(k.startswith("sycophancy__") for k in payload["questions"])
    assert payload["state"]["user_message"] == PLAIN_REQUEST


# ─── bypass: byte-identical to the pre-layer path ────────────────────────


def _pre_layer_context(session_id, transcript_path, raw, budget):
    """What main() did at this point before PR3: drain notices, no verdicts."""
    stop_hook._emit_subagent_notices(session_id)
    return stop_hook.StopVerdicts()


def _fixture_run(tmp_path: Path, recs: list[dict[str, Any]], name: str) -> tuple:
    run_dir = tmp_path / name
    run_dir.mkdir()
    path = run_dir / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    log = tmp_path / "enforcement.jsonl"
    log.unlink(missing_ok=True)
    rc = _stop(tmp_path, path)
    rows = [{k: v for k, v in r.items() if k != "ts"} for r in read_jsonl(log)]
    return rc, rows


# The fixtures of tests/python/test_stop_hook.py.
_STOP_HOOK_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "external": [
        {"role": "user", "content": "implement a Laravel OrderService"},
        {"role": "assistant", "content": "[arka:routing] dev -> paulo"},
        {"role": "assistant", "content": [{"type": "tool_use", "name": "WebFetch",
                                           "input": {"url": "https://laravel.com/docs"}}]},
        {"role": "assistant", "content": "[arka:qg:approved]\n[arka:phase:13] done"},
    ],
    "no-external": [
        {"role": "user", "content": "implement a Laravel OrderService"},
        {"role": "assistant", "content": "[arka:routing] dev -> paulo"},
        {"role": "assistant", "content": "[arka:qg:approved]\n[arka:phase:13] done"},
    ],
    "skill": [
        {"role": "user", "content": "ship the release flow"},
        {"role": "assistant", "content": (
            "[arka:gate:4] Shipped the four-phase release workflow: the "
            "checklist template and the rollback procedure are now a "
            "reusable skill with its own playbook and evidence gates.")},
    ],
    "trivial": [{"role": "assistant", "content": "[arka:gate:4] done"}],
    "empty": [],
}


def _all_fixtures(tmp_path: Path, capsys, prefix: str) -> list[tuple]:
    results = []
    for name, recs in _STOP_HOOK_FIXTURES.items():
        rc, rows = _fixture_run(tmp_path, recs, f"{prefix}-{name}")
        results.append((name, rc, capsys.readouterr().out, rows))
    return results


def test_bypass_is_byte_identical_to_the_pre_layer_path(tmp_path, monkeypatch, capsys):
    """``ARKA_BYPASS_DECISIONS=1``: zero urlopen, zero shadow spawn, zero
    Popen (both patched to raise), and stdout + the enforcement row equal
    to main() with the Stop stage swapped for what it replaced."""
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    with patch(URLOPEN) as net:
        with_layer = _all_fixtures(tmp_path, capsys, "layer")
        monkeypatch.setattr(stop_hook, "_stop_context", _pre_layer_context)
        without = _all_fixtures(tmp_path, capsys, "pre")
    net.assert_not_called()
    assert [r[:3] for r in with_layer] == [r[:3] for r in without]
    strip = [[{k: v for k, v in row.items() if k != "cwd"} for row in r[3]]
             for r in (*with_layer, *without)]
    assert strip[: len(with_layer)] == strip[len(with_layer):]
    assert all("decisions" not in row for rows in strip for row in rows), (
        "an inactive layer adds no telemetry key")


def test_bypass_reads_no_decisions_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    monkeypatch.setattr(
        "core.decisions.config.load_decisions_config",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("config read under bypass")))
    assert stop_hook._stop_decisions_cfg() is None


def test_no_key_means_no_network(jev, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    with patch(URLOPEN) as net:
        _stop(tmp_path, transcript)
    net.assert_not_called()
    assert "decisions" not in _entry(tmp_path)


def test_a_failing_stage_still_delivers_notices(tmp_path, monkeypatch, capsys):
    from core.governance import reviewer_ledger

    def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("stage exploded")

    monkeypatch.setattr(stop_hook, "_stop_verdicts", _boom)
    reviewer_ledger.queue_notice(SID, None, "[arka:subagent-qa] pending")
    transcript = _transcript(tmp_path, PLAIN_REQUEST, CLEAN_CLOSE)
    assert _stop(tmp_path, transcript) == 0
    assert _context(capsys) == "[arka:subagent-qa] pending"


# ─── operator_message: one fixture per structural filter (QG r1 M4) ──────
#
# Each entry below carries NO text prefix INJECTED_PREFIXES recognises, so
# exactly one structural field keeps it out; removing that field from the
# filter makes its row return the harness text as the operator's.

COMPACT_TEXT = (
    "This session is being continued from a previous conversation that ran out"
    f" of context. The summary below covers the earlier portion. {INJECTED_RULE}"
)


def _harness_user(text: str, **fields: Any) -> dict[str, Any]:
    return {"type": "user", "isSidechain": False, **fields,
            "message": {"role": "user", "content": text}}


def _compact_summary() -> dict[str, Any]:
    """The real shape (this session's compact-summary entry, 2.1.280): no
    ``origin``, no ``promptSource``, a plain string body, two flags."""
    return _harness_user(COMPACT_TEXT, isVisibleInTranscriptOnly=True, isCompactSummary=True,
                         turnOrigin="peer", userType="external", entrypoint="cli")


STRUCTURAL_ONLY = {
    "compact-summary-real": _compact_summary(),
    "isCompactSummary": _harness_user(COMPACT_TEXT, isCompactSummary=True),
    "isVisibleInTranscriptOnly": _harness_user(INJECTED_RULE, isVisibleInTranscriptOnly=True),
    "isSidechain": {**_harness_user(INJECTED_RULE), "isSidechain": True,
                    "origin": {"kind": "human"}, "promptSource": "typed"},
    "promptSource-system": _harness_user(INJECTED_RULE, promptSource="system"),
    "origin-auto-continuation": _harness_user(
        INJECTED_RULE, origin={"kind": "auto-continuation"}),
}


@pytest.mark.parametrize("name", list(STRUCTURAL_ONLY))
def test_each_structural_filter_alone_skips_its_entry(name):
    entry = STRUCTURAL_ONLY[name]
    assert stop_hook._last_user_message(_raw([_human(PLAIN_REQUEST), entry])) == PLAIN_REQUEST


def test_no_structural_row_is_caught_by_a_text_prefix():
    """The rows above prove the structural layer only if the text layer
    alone would let each through."""
    from core.hooks.operator_message import _injected

    assert not any(_injected(e["message"]["content"]) for e in STRUCTURAL_ONLY.values())


# ─── operator_message: a slash command's arguments are the operator's ────


def _slash(args: str, **fields: Any) -> dict[str, Any]:
    body = (f"<command-message>arka</command-message>\n<command-name>/arka</command-name>\n"
            f"<command-args>{args}</command-args>")
    return {"type": "user", "isSidechain": False, **fields,
            "message": {"role": "user", "content": body}}


def test_human_slash_command_args_are_the_operator_message():
    entry = _slash(f"  {EXPLICIT_RULE}\n", origin={"kind": "human"}, promptSource="typed")
    assert stop_hook._last_user_message(_raw([_human(PLAIN_REQUEST), entry])) == EXPLICIT_RULE


@pytest.mark.parametrize("fields", [{}, {"origin": {"kind": "peer"}}], ids=["no-origin", "peer"])
def test_a_command_echo_without_human_origin_is_dropped(fields):
    entry = _slash(EXPLICIT_RULE, **fields)
    assert stop_hook._last_user_message(_raw([_human(PLAIN_REQUEST), entry])) == PLAIN_REQUEST


def test_a_human_command_without_args_is_not_an_operator_message():
    entry = _harness_user("<command-name>/clear</command-name>", origin={"kind": "human"})
    assert stop_hook._last_user_message(_raw([_human(PLAIN_REQUEST), entry])) == PLAIN_REQUEST


# ─── escalate-only: the phantom-action consumer never passes a failure ───


def test_the_phantom_consumer_rechecks_escalate_only():
    """A Jev False that claims to clear the check cannot pass it:
    ``_phantom_verdict`` only ever fails (defence in depth over the engine)."""
    from core.decisions.site import Outcome
    from core.governance.phantom_action_check import PhantomActionResult

    failed = PhantomActionResult(passed=False, reason="phantom-action", suggestion="s")
    cleared = Outcome(False, True, False, 0.99, "act", "jev", "jev")
    verdicts = stop_hook.StopVerdicts({"phantom-action": cleared})
    assert stop_hook._phantom_verdict(failed, verdicts) is failed
    passed = replace(failed, passed=True, reason="ok")
    assert stop_hook._phantom_verdict(passed, verdicts) is passed


def test_the_consumers_escalate_on_a_jev_true():
    """The positive half, so a consumer that ignores Jev entirely dies too."""
    from core.decisions.site import Outcome
    from core.governance.phantom_action_check import PhantomActionResult
    from core.governance.sycophancy_detector import detect_sycophancy

    flagged = Outcome(True, False, True, 0.9, "act", "jev", "jev")
    verdicts = stop_hook.StopVerdicts({"phantom-action": flagged, "sycophancy": flagged})
    passed = PhantomActionResult(passed=True, reason="ok", suggestion="")
    assert stop_hook._phantom_verdict(passed, verdicts).passed is False
    assert stop_hook._sycophancy_verdict(detect_sycophancy(CLEAN_CLOSE), verdicts)[0] is True


# ─── a failing Jev stage keeps the heuristic learning marker (QG r1 m5) ──


def test_a_config_failure_keeps_the_heuristic_marker(jev, tmp_path, monkeypatch, capsys):
    def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("config exploded")

    monkeypatch.setattr("core.decisions.config.load_decisions_config", _boom)
    transcript = _transcript(tmp_path, EXPLICIT_RULE, CLEAN_CLOSE)
    with patch(URLOPEN) as net:
        assert _stop(tmp_path, transcript, flagged=False) == 0
    net.assert_not_called()
    context = _context(capsys)
    assert context.startswith("[arka:learned-rule confidence=") and "signal=explicit]" in context
