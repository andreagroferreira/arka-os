"""core.decisions.replay — corpora, gate arithmetic, CLI exit codes."""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions

from core.decisions import client, privacy
from core.decisions import replay as rp
from core.decisions.client import DecisionUnavailable
from core.decisions.config import DecisionsConfig
from core.decisions.engine import run_sync
from core.decisions.registry import SITES as SITES_BY_NAME
from core.decisions.replay import ReplayCase, load_corpus, main, replay
from core.decisions.site import SiteCall
from core.decisions.transport import resolve_transport

URLOPEN = "core.decisions.client.urllib.request.urlopen"
SITES = ("topic-drift", "refine", "creation-intent", "route", "bash-effect",
         "forge-departments", "forge-complexity", "skill-hints", "dispatch-role",
         "subagent-discipline", "sycophancy", "phantom-action", "skill-proposer",
         "learning-signal", "ui-in-ts", "qg-prescreen", "slop-score")


@pytest.fixture
def transport(monkeypatch, tmp_path):
    # Corpora use the placeholder "ClienteY"; a list that redacts it would
    # rewrite the prompt the oracle keys on (redaction itself is covered
    # in test_decisions_privacy).
    isolate_decisions(monkeypatch, tmp_path, clients=["zz-no-such-client"])
    t = resolve_transport(DecisionsConfig())
    assert t is not None
    return t


def _oracle(cases: list[ReplayCase], answer: Callable[[ReplayCase], dict[str, Any]]):
    by_prompt = {c.prompt: c for c in cases}

    def respond(request, timeout):
        state = json.loads(request.data.decode("utf-8"))["state"]
        return fake_ok(answer(by_prompt[state["prompt"]]))

    return respond


def _creation(p_yes: Callable[[ReplayCase], float]):
    return lambda c: {"creation_intent__creation_intent": {"noul": p_yes(c)}}


@pytest.mark.parametrize("site", SITES)
def test_shipped_corpora_meet_the_bar(site):
    cases = load_corpus(site)
    assert len(cases) >= rp.MIN_CASES
    assert sum(c.lang == "pt" for c in cases) / len(cases) >= rp.MIN_PT_SHARE
    assert len({c.id for c in cases}) == len(cases)
    report = replay(site, cases, transport=None, offline=True)
    assert report.gate == "offline" and report.failures == []


def test_route_corpus_labels_are_known_departments():
    options = set(rp.SITES["route"].questions()["department"].criteria) - {"none"}
    assert {c.expected for c in load_corpus("route")} <= options | {""}


def test_bad_corpus_line_names_the_line(tmp_path):
    path = tmp_path / "c.jsonl"
    path.write_text('{"id":"a","lang":"pt","prompt":"x","expected":true}\n{"id":1}\n',
                    encoding="utf-8")
    with pytest.raises(ValueError, match=r"c\.jsonl:2"):
        load_corpus("creation-intent", path)


def test_perfect_oracle_passes(transport):
    cases = load_corpus("creation-intent")
    oracle = _oracle(cases, _creation(lambda c: 0.97 if c.expected else 0.03))
    with patch(URLOPEN, side_effect=oracle):
        report = replay("creation-intent", cases, transport=transport)
    assert report.gate == "pass", report.failures
    assert report.jev_accuracy == 1.0 and report.abstain_rate == 0.0
    assert report.false_escalation_rate == 0.0
    assert report.by_lang["pt"]["jev"] == 1.0


def test_inverted_oracle_fails_precision(transport):
    cases = load_corpus("route")
    oracle = _oracle(cases, lambda c: {"route__department": {
        "choice": "sales" if c.expected != "sales" else "dev", "confidence": 0.95}})
    with patch(URLOPEN, side_effect=oracle):
        report = replay("route", cases, transport=transport)
    assert report.gate == "fail"
    assert any("precision" in f for f in report.failures)


def test_coin_flip_oracle_fails_abstain(transport):
    cases = load_corpus("topic-drift")
    oracle = _oracle(cases, lambda c: {"topic_drift__topic_shift": {"noul": 0.5}})
    with patch(URLOPEN, side_effect=oracle):
        report = replay("topic-drift", cases, transport=transport)
    assert report.abstain_rate == 1.0
    assert "Jev answered no case" in report.failures
    assert any(f.startswith("abstain") for f in report.failures)


def test_always_yes_oracle_fails_false_escalation(transport):
    cases = load_corpus("creation-intent")
    with patch(URLOPEN, side_effect=_oracle(cases, _creation(lambda c: 0.99))):
        report = replay("creation-intent", cases, transport=transport)
    assert report.false_escalation_rate is not None and report.false_escalation_rate > 0.05
    assert any("false escalation" in f for f in report.failures)


def test_unavailable_endpoint_counts(transport):
    cases = load_corpus("refine")
    with patch(URLOPEN, side_effect=TimeoutError("slow")):
        report = replay("refine", cases, transport=transport)
    assert report.unavailable == len(cases) and report.gate == "fail"


def test_small_corpus_fails_offline(tmp_path):
    rows = [{"id": str(i), "lang": "en", "prompt": "hello", "expected": False} for i in range(3)]
    path = tmp_path / "c.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    report = replay("creation-intent", load_corpus("creation-intent", path), transport=None)
    assert report.gate == "fail" and len(report.failures) == 2
    assert main(["--site", "creation-intent", "--corpus", str(path), "--offline"]) == 1


def test_heuristics_mirror_the_live_code():
    from core.hooks.user_prompt_submit import _wf_classify

    for prompt in ("hello", "implementa a feature", "o que e que este projeto faz?"):
        case = ReplayCase(id="x", lang="pt", prompt=prompt, expected=False)
        assert rp.HEURISTICS["creation-intent"](case) == _wf_classify(prompt)
    case = ReplayCase(id="x", lang="en", prompt="fix the login bug", expected="dev")
    assert rp.HEURISTICS["route"](case) == "dev"
    assert rp.HEURISTICS["route"](ReplayCase(id="y", lang="en", prompt="hi", expected="")) == ""
    assert rp.HEURISTICS["refine"](ReplayCase(id="z", lang="pt", prompt="cria um site melhor",
                                              expected=True)) is True
    assert rp.HEURISTICS["topic-drift"](ReplayCase(id="w", lang="pt", prompt="a b",
                                                   prior=["x"], expected=False)) is False


class TestCli:
    def test_offline_default_corpus(self, capsys):
        assert main(["--site", "topic-drift", "--offline"]) == 0
        assert "Replay — topic-drift (offline)" in capsys.readouterr().out

    def test_json_output(self, capsys):
        assert main(["--site", "route", "--offline", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["site"] == "route" and data["gate"] == "offline"

    @pytest.mark.parametrize("argv", [["--site", "nope"], [], ["--site", "route", "--corpus",
                                                               "/nonexistent/x.jsonl"]])
    def test_usage_errors(self, argv):
        assert main(argv) == 2

    def test_help_is_success(self):
        assert main(["--help"]) == 0

    def test_online_without_transport(self, monkeypatch, tmp_path):
        isolate_decisions(monkeypatch, tmp_path, key=None)
        assert main(["--site", "route"]) == 2

    def test_online_render(self, transport, capsys):
        cases = load_corpus("creation-intent")
        oracle = _oracle(cases, _creation(lambda c: 0.97 if c.expected else 0.03))
        with patch(URLOPEN, side_effect=oracle):
            assert main(["--site", "creation-intent"]) == 0
        out = capsys.readouterr().out
        assert "Jev precision (answered): 100.0%" in out and "false escalation: 0.0%" in out


def test_default_corpus_path_is_in_repo():
    assert rp.default_corpus_path("route") == (
        Path(rp.__file__).resolve().parents[2] / "config" / "decisions" / "corpora" / "route.jsonl"
    )


def test_online_report_carries_p50_latency_and_cost(transport):
    """G3 evidence: median latency of the calls that went out and their
    summed usage.cost; a cache hit counts neither."""
    from _decisions_helpers import SMOKE_COST

    from core.decisions.models import DecisionResponse, Usage

    cases = load_corpus("creation-intent")[:4]
    resp = DecisionResponse(model="m", answers={}, usage=Usage(input_tokens=10, cost=SMOKE_COST))
    results = iter([(resp, "ok", 300), (resp, "ok", 100), (resp, "cache-hit", 0),
                    (None, "timeout", 5000)])
    with patch("core.decisions.replay.run_sync", lambda *a, **k: next(results)):
        report = replay("creation-intent", cases, transport=transport)
    assert report.p50_latency_ms == 300  # median of 300, 100, 5000
    assert report.cost_usd == pytest.approx(2 * SMOKE_COST)
    out = json.loads(json.dumps(__import__("dataclasses").asdict(report)))
    assert {"p50_latency_ms", "cost_usd"} <= set(out)


def test_online_end_to_end_cost_is_the_reported_usage(transport):
    from _decisions_helpers import SMOKE_COST

    cases = load_corpus("creation-intent")
    oracle = _oracle(cases, _creation(lambda c: 0.97 if c.expected else 0.03))
    with patch(URLOPEN, side_effect=oracle) as net:
        report = replay("creation-intent", cases, transport=transport)
    assert report.cost_usd == pytest.approx(net.call_count * SMOKE_COST)
    assert report.p50_latency_ms >= 0


def test_offline_report_is_not_measured(capsys):
    assert main(["--site", "route", "--offline", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["p50_latency_ms"], out["cost_usd"]) == (None, None)
    assert main(["--site", "route", "--offline"]) == 0
    assert "- p50 latency / cost: not measured (offline)" in capsys.readouterr().out


def _replay_with(results, transport):
    from core.decisions.models import DecisionResponse, Usage

    cases = load_corpus("creation-intent")[:3]
    resp = DecisionResponse(model="m", answers={}, usage=Usage(input_tokens=10, cost=1e-05))
    it = iter([(resp if r == "cache-hit" or r == "ok" else None, r, ms) for r, ms in results])
    with patch("core.decisions.replay.run_sync", lambda *a, **k: next(it)):
        return replay("creation-intent", cases, transport=transport)


def test_all_cache_hits_are_not_measured_not_zero(transport, capsys):
    report = _replay_with([("cache-hit", 0)] * 3, transport)
    assert (report.p50_latency_ms, report.cost_usd) == (None, None)
    as_json = json.loads(json.dumps(__import__("dataclasses").asdict(report)))
    assert as_json["p50_latency_ms"] is None and as_json["cost_usd"] is None
    assert "not measured (all cache hits)" in rp._render(report)


def test_one_fresh_call_is_measured(transport):
    report = _replay_with([("cache-hit", 0), ("ok", 420), ("cache-hit", 0)], transport)
    assert report.p50_latency_ms == 420
    assert report.cost_usd == pytest.approx(1e-05)
    assert "p50 latency: 420 ms" in rp._render(report)


# --- PR2 sites: labels, heuristics, projection, oracles ----------------------

def _keyed_oracle(cases, answer):
    by_text = {c.prompt: c for c in cases}

    def respond(request, timeout):
        state = json.loads(request.data.decode("utf-8"))["state"]
        return fake_ok(answer(by_text[state.get("prompt") or state.get("command")]))

    return respond


@pytest.mark.parametrize(("site", "bad"), [
    ("route", True), ("route", "legal"), ("dispatch-role", "opus"),
    ("forge-complexity", "deep"), ("forge-departments", ["dev", "legal"]),
    ("forge-departments", []), ("forge-departments", ["dev", "dev"]),
    ("forge-departments", ["dev", "pm", "ops", "kb", "org"]),
    ("skill-hints", "no-such-command"), ("bash-effect", "yes"),
    ("subagent-discipline", ["x"]),
])
def test_expected_of_the_wrong_kind_names_the_line(tmp_path, site, bad):
    path = tmp_path / "c.jsonl"
    path.write_text(json.dumps({"id": "a", "lang": "pt", "prompt": "x", "expected": bad}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match=rf"c\.jsonl:1: expected .* is not a {site} label"):
        load_corpus(site, path)


def test_new_heuristics_mirror_the_live_code():
    from core.forge.complexity import score_dimensions
    from core.forge.orchestrator import ForgeOrchestrator
    from core.workflow.flow_enforcer import bash_is_effect

    for cmd in ("git status", "rm -rf x", "find . -delete", ""):
        case = ReplayCase(id="b", lang="en", prompt=cmd, expected=False)
        assert rp.HEURISTICS["bash-effect"](case) is bash_is_effect(cmd)
    prompt = "launch the marketing campaign and brand design for the auth api"
    orch = ForgeOrchestrator.__new__(ForgeOrchestrator)
    case = ReplayCase(id="f", lang="en", prompt=prompt, expected=["dev"])
    assert rp.HEURISTICS["forge-departments"](case) == sorted(orch._estimate_departments(prompt))
    files, depts = orch._estimate_affected_files(prompt), orch._estimate_departments(prompt)
    dims = score_dimensions(prompt, files, depts, [], []).model_dump()
    assert rp.HEURISTICS["forge-complexity"](case) == dims


def test_skill_hint_heuristic_is_the_l5_top_hint():
    from core.synapse.layers import _score_commands

    text = "review this pull request for SOLID violations"
    top = _score_commands(list(rp.registry_commands()), text.lower())[0][1]
    hinted = rp.HEURISTICS["skill-hints"](ReplayCase(id="s", lang="en", prompt=text,
                                                     expected="dev-review"))
    assert {c["id"]: c["command"] for c in rp.registry_commands()}[hinted] == top
    assert rp.HEURISTICS["skill-hints"](ReplayCase(id="e", lang="pt", prompt="olá",
                                                   expected="do")) == ""


def test_skill_menu_is_capped_and_holds_the_routed_department():
    menu = rp.skill_candidates_for("plan a sprint for the mobile team")
    assert 0 < len(menu) <= 60 and len({c["id"] for c in menu}) == len(menu)
    assert "pm-sprint" in {c["id"] for c in menu}


def test_replay_menu_is_the_hook_menu():
    """One builder for both: the replay scores the menu the UPS sends."""
    from core.synapse.command_menu import skill_hint_candidates

    prompt = "desenha uma paleta de cores quente para a marca de café"
    assert rp.skill_candidates_for(prompt, "brand") == skill_hint_candidates(
        list(rp.registry_commands()), prompt, "brand")
    assert rp.skill_candidates_for(prompt) == skill_hint_candidates(
        list(rp.registry_commands()), prompt, "")


def _coverage(menu_for) -> float:
    cases = load_corpus("skill-hints")
    hits = sum(c.expected in {m["id"] for m in menu_for(c)} for c in cases)
    return hits / len(cases)


def test_menu_coverage_with_the_route_reaches_ninety_percent():
    """PR2: the menu (top-20 keyword + routed department, cap 60) holds the
    expected command in ≥ 90 % of the corpus once the route is right; the
    keyword-only route of PR1's menu covered 58.8 % (20/34)."""
    routed = _coverage(lambda c: rp.skill_candidates_for(c.prompt, rp.replay_route(c)))
    keyword = _coverage(lambda c: rp.skill_candidates_for(c.prompt))
    assert routed >= 0.90
    assert keyword < routed


def test_replay_route_is_the_expected_commands_department():
    case = ReplayCase(id="s", lang="pt", prompt="x", expected="brand-colors")
    assert rp.replay_route(case) == "brand"
    assert rp.replay_route(case.model_copy(update={"expected": "no-such-id"})) is None


def test_keyword_baselines():
    assert rp.keyword_dispatch_role("Run the quality gate on this") == "quality_gate"
    assert rp.keyword_dispatch_role("Revê este PR") == "review"
    assert rp.keyword_dispatch_role("Escreve a mensagem de commit") == "mechanical"
    assert rp.keyword_dispatch_role("Implementa o endpoint") == "execution"
    assert rp.keyword_needs_isolation("Audita todo o repositório") is True
    assert rp.keyword_needs_isolation("Corrige a gralha no README") is False


def test_case_state_per_site():
    case = ReplayCase(id="c", lang="pt", prompt="ls -la", prior=["x"], expected=False)
    assert rp.case_state("bash-effect", case) == {"command": "ls -la"}
    assert rp.case_state("route", case) == {"prompt": "ls -la", "recent_user_messages": ["x"]}
    assert set(rp.case_state("forge-complexity", case)) == {"prompt", "affected_files",
                                                            "departments"}
    assert set(rp.case_state("skill-hints", case)) == {"prompt", "candidates",
                                                       "quality_dispatch"}


@pytest.mark.parametrize(("level", "tier"), [(0, "SHALLOW"), (4.5, "STANDARD"), (9, "DEEP")])
def test_complexity_tier_projection(level, tier):
    from core.decisions.sites.forge import DIMENSIONS, level_to_percent

    assert rp.complexity_tier({d: level_to_percent(level) for d in DIMENSIONS}) == tier
    assert rp.complexity_tier(None) is None


LEVEL_FOR_TIER = {"SHALLOW": 0, "STANDARD": 4.5, "DEEP": 9}


def test_perfect_complexity_oracle_passes_through_the_projection(transport):
    from core.decisions.sites.forge import DIMENSIONS

    cases = load_corpus("forge-complexity")

    def answer(case):
        level = LEVEL_FOR_TIER[case.expected]
        return {f"forge_complexity__{d}": {"score": level, "confidence": 0.9} for d in DIMENSIONS}

    with patch(URLOPEN, side_effect=_keyed_oracle(cases, answer)):
        report = replay("forge-complexity", cases, transport=transport)
    assert report.gate == "pass", report.failures
    assert report.jev_accuracy == 1.0 and report.abstain_rate == 0.0


def test_perfect_departments_oracle_is_order_free(transport):
    cases = load_corpus("forge-departments")

    def answer(case):
        share = round(1 / len(case.expected), 4)
        probs = {d: share for d in case.expected}
        return {"forge_departments__departments": {"choice": case.expected[-1],
                                                   "probabilities": probs}}

    with patch(URLOPEN, side_effect=_keyed_oracle(cases, answer)):
        report = replay("forge-departments", cases, transport=transport)
    assert report.gate == "pass", report.failures
    assert report.jev_accuracy == 1.0


def test_perfect_bash_oracle_passes_and_never_ungates(transport):
    cases = load_corpus("bash-effect")
    def answer(c):
        return {"bash_effect__requires_gating": {"noul": 0.99 if c.expected else 0.01}}

    with patch(URLOPEN, side_effect=_keyed_oracle(cases, answer)):
        report = replay("bash-effect", cases, transport=transport)
    assert report.gate == "pass", report.failures
    assert report.false_escalation_rate == 0.0
    # The dry-run rsync: regex says effect, truth is read; escalate-only keeps it gated.
    assert report.act_accuracy is not None and report.act_accuracy < 1.0


def test_skill_hint_oracle_is_bounded_by_menu_coverage(transport):
    cases = load_corpus("skill-hints")
    covered = sum(c.expected in {m["id"] for m in rp.skill_candidates_for(
        c.prompt, rp.replay_route(c))} for c in cases)
    def answer(c):
        return {"skill_hints__command": {"choice": c.expected, "confidence": 0.95}}

    with patch(URLOPEN, side_effect=_keyed_oracle(cases, answer)):
        report = replay("skill-hints", cases, transport=transport)
    # A perfect JEV can only name what the menu offers: every uncovered case abstains.
    assert report.jev_accuracy == 1.0
    assert report.abstain_rate == pytest.approx(round(1 - covered / len(cases), 4))


def test_blank_corpus_lines_are_skipped(tmp_path):
    row = {"id": "a", "lang": "pt", "prompt": "x", "expected": True}
    path = tmp_path / "c.jsonl"
    path.write_text(json.dumps(row) + "\n\n   \n", encoding="utf-8")
    assert [c.id for c in load_corpus("creation-intent", path)] == ["a"]


# --- per-call ceiling (QG PR2 r4: replay where the live site cuts) --------------

def _timeouts_seen(site: str, argv_timeout: int | None, transport) -> tuple[set[float], object]:
    cases = load_corpus(site)[:3]
    seen: set[float] = set()

    def respond(request, timeout):
        seen.add(timeout)
        return fake_ok({})

    with patch(URLOPEN, side_effect=respond):
        report = replay(site, cases, transport=transport, timeout_ms=argv_timeout)
    return seen, report


def test_replay_calls_default_to_the_sites_own_ceiling(transport):
    """Kills a mutation back to the former fixed 5 s: forge-departments
    ships a 3000 ms ceiling, dispatch-role 1500 ms."""
    seen, report = _timeouts_seen("forge-departments", None, transport)
    assert seen == {3.0} and report.timeout_ms == 3000
    seen, report = _timeouts_seen("dispatch-role", None, transport)
    assert seen == {1.5} and report.timeout_ms == 1500


def test_timeout_override_reaches_the_wire(transport):
    seen, report = _timeouts_seen("forge-departments", 1200, transport)
    assert seen == {1.2} and report.timeout_ms == 1200


def test_offline_report_has_no_ceiling():
    report = replay("route", load_corpus("route"), transport=None, offline=True)
    assert report.timeout_ms is None


def test_cli_passes_the_timeout_flag(monkeypatch):
    captured: dict[str, object] = {}

    def fake_replay(site, cases, **kw):
        captured.update(kw)
        return rp.ReplayReport(site=site, cases=len(cases), pt_share=0.5,
                               heuristic_accuracy=0.0)

    monkeypatch.setattr(rp, "replay", fake_replay)
    assert main(["--site", "route", "--offline", "--timeout-ms", "3000"]) == 0
    assert captured["timeout_ms"] == 3000
    assert main(["--site", "route", "--offline"]) == 0
    assert captured["timeout_ms"] is None


# --- PR3 sites: governance + quality ------------------------------------------

_TEXT_KEYS = ("prompt", "command", "response", "user_message", "content", "diff", "prose")


def _pr3_key(state: dict[str, Any]) -> tuple[str, object]:
    text = next(state[k] for k in _TEXT_KEYS if state.get(k))
    return text, state.get("tool_uses")


def _pr3_oracle(site: str, cases: list[ReplayCase], answer: Callable[[ReplayCase], dict]):
    by_key = {_pr3_key(rp.case_state(site, c)): c for c in cases}

    def respond(request, timeout):
        state = json.loads(request.data.decode("utf-8"))["state"]
        return fake_ok(answer(by_key[_pr3_key(state)]))

    return respond


def _run(site: str, transport, answer: Callable[[ReplayCase], dict]):
    cases = load_corpus(site)
    with patch(URLOPEN, side_effect=_pr3_oracle(site, cases, answer)):
        return replay(site, cases, transport=transport)


NOUL_SITES = {"sycophancy": "is_sycophantic", "phantom-action": "claims_unbacked_effect",
              "skill-proposer": "is_repeatable_capability", "ui-in-ts": "is_ui_code"}


@pytest.mark.parametrize("site", sorted(NOUL_SITES))
def test_perfect_pr3_noul_oracle_passes(transport, site):
    key = f"{site.replace('-', '_')}__{NOUL_SITES[site]}"
    report = _run(site, transport, lambda c: {key: {"noul": 0.99 if c.expected else 0.01}})
    assert report.gate == "pass", report.failures
    assert report.jev_accuracy == 1.0 and report.unavailable == 0
    if rp.SITES[site].direction == "escalate_only":
        assert report.false_escalation_rate == 0.0


def test_phantom_cases_with_tool_calls_are_never_asked(transport):
    cases = load_corpus("phantom-action")
    with_tools = sum(1 for c in cases if c.context.get("tool_uses") != 0)
    report = _run("phantom-action", transport,
                  lambda c: {"phantom_action__claims_unbacked_effect": {"noul": 0.99}})
    assert with_tools >= 3
    assert report.abstain_rate == round(with_tools / len(cases), 4)


def test_perfect_learning_oracle_passes_through_the_signal_label(transport):
    def answer(c):
        leverage = 0.9 if c.expected == "explicit" else 0.1
        return {"learning_signal__signal": {"choice": c.expected, "confidence": 0.9},
                "learning_signal__high_leverage": {"noul": leverage}}

    report = _run("learning-signal", transport, answer)
    assert report.gate == "pass", report.failures
    # 29/35: case 35 (the live Stop false positive, "none") is one the regex gets right.
    assert report.jev_accuracy == 1.0 and report.heuristic_on_answered == 0.8286


def test_perfect_prescreen_oracle_passes_against_the_label_only(transport):
    def answer(c):
        verdict, blocker = c.expected
        return {"qg_prescreen__likely_verdict": {"choice": verdict, "confidence": 0.9},
                "qg_prescreen__blocker_class": {"choice": blocker, "confidence": 0.9}}

    report = _run("qg-prescreen", transport, answer)
    assert report.gate == "pass", report.failures
    assert (report.jev_accuracy, report.heuristic_on_answered) == (1.0, 0.0)


def _slop_answer(offset: int) -> Callable[[ReplayCase], dict]:
    from core.decisions.sites.quality import SLOP_DIMENSIONS

    def answer(c):
        return {f"slop_score__{d}": {"score": min(9, max(0, v - 1 + offset)), "confidence": 0.9}
                for d, v in zip(SLOP_DIMENSIONS, c.expected, strict=True)}

    return answer


def test_perfect_slop_oracle_passes_on_mean_absolute_error(transport, capsys):
    report = _run("slop-score", transport, _slop_answer(0))
    assert report.gate == "pass", report.failures
    assert report.mean_abs_error == 0.0 and report.jev_accuracy == 1.0
    assert "mean absolute error (total, 5-50): 0.0" in rp._render(report)


def test_slop_oracle_off_by_two_per_dimension_fails_the_mae_gate(transport):
    report = _run("slop-score", transport, _slop_answer(-2))
    assert report.gate == "fail"
    assert report.mean_abs_error is not None and report.mean_abs_error > rp.MAX_SLOP_MAE
    assert any(f.startswith("mean absolute error") for f in report.failures)
    assert not any("precision" in f for f in report.failures)


def test_mae_is_only_reported_for_slop(transport):
    report = _run("ui-in-ts", transport, lambda c: {"ui_in_ts__is_ui_code": {"noul": 0.99}})
    assert report.mean_abs_error is None


@pytest.mark.parametrize(("site", "bad"), [
    ("sycophancy", "yes"), ("phantom-action", 1), ("ui-in-ts", ["x"]),
    ("learning-signal", "rule"), ("learning-signal", True),
    ("qg-prescreen", ["approved", "tests"]), ("qg-prescreen", ["rejected", "none"]),
    ("qg-prescreen", ["unknown", "none"]), ("qg-prescreen", "approved"),
    ("slop-score", [5, 5, 5, 5]), ("slop-score", [0, 5, 5, 5, 5]),
    ("slop-score", [5, 5, 5, 5, 11]), ("slop-score", 35),
])
def test_pr3_expected_of_the_wrong_kind_names_the_line(tmp_path, site, bad):
    path = tmp_path / "c.jsonl"
    path.write_text(json.dumps({"id": "a", "lang": "pt", "prompt": "x", "expected": bad}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match=r"c\.jsonl:1"):
        load_corpus(site, path)


def test_replay_case_context_and_int_labels():
    case = ReplayCase(id="p", lang="pt", prompt="Fiz commit.", context={"tool_uses": 0},
                      expected=True)
    assert rp.case_state("phantom-action", case) == {
        "response": "Fiz commit.", "user_message": "", "tool_uses": 0}
    assert rp.HEURISTICS["phantom-action"](case) is True
    assert rp.HEURISTICS["phantom-action"](case.model_copy(update={"context": {}})) is False
    slop = ReplayCase(id="s", lang="pt", prompt="x", expected=[1, 2, 3, 4, 5])
    assert slop.expected == [1, 2, 3, 4, 5]
    with pytest.raises(ValueError):
        ReplayCase(id="c", lang="pt", prompt="x", context={"k": 1.5}, expected=True)


def test_pr3_case_states():
    syc = ReplayCase(id="a", lang="pt", prompt="Sim.", prior=["apaga tudo"], expected=True)
    assert rp.case_state("sycophancy", syc)["user_message"] == "apaga tudo"
    learn = ReplayCase(id="b", lang="pt", prompt="nunca faças isto", expected="explicit")
    assert rp.case_state("learning-signal", learn) == {
        "response": "", "user_message": "nunca faças isto", "tool_uses": None}
    ui = ReplayCase(id="c", lang="en", prompt="x", context={"path": "a.ts"}, expected=False)
    assert rp.case_state("ui-in-ts", ui) == {"path": "a.ts", "content": "x"}
    head = "diff --git a/core/x.py b/core/x.py\n+a"
    diff = ReplayCase(id="d", lang="pt", prompt=head, expected=["approved", "none"])
    assert rp.case_state("qg-prescreen", diff) == {"path": "core/x.py", "diff": head}
    bare = ReplayCase(id="d2", lang="pt", prompt="+a", expected=["approved", "none"])
    assert rp.case_state("qg-prescreen", bare) == {"path": "", "diff": "+a"}  # privacy refuses
    prose = ReplayCase(id="e", lang="pt", prompt="Olá.", expected=[5, 5, 5, 5, 5])
    assert rp.case_state("slop-score", prose) == {"path": "e.md", "prose": "Olá."}
    assert rp.HEURISTICS["slop-score"](prose) is None


# --- reached_endpoint: what the endpoint decided vs what this machine decided --


@pytest.mark.parametrize(("reason", "reached"), [
    ("ok", True),
    ("timeout", True),  # a socket timeout raised by the exchange with the endpoint
    ("network", True),
    ("http-529", True),
    ("invalid-shape", True),  # a malformed RESPONSE body: the endpoint answered
    ("invalid-json", True),
    ("timeout:local", False),  # our wall-clock deadline (client._send_by_deadline)
    ("invalid-shape:local", False),  # a state/body that never serialised
    ("cache-hit", False),
    ("no-questions", False),
    ("deadline", False),
    ("backoff:http-401", False),
    ("egress-denied:path-class", False),
])
def test_reached_endpoint_names_the_local_reasons(reason: str, reached: bool):
    assert rp.reached_endpoint(reason) is reached


def test_the_wall_clock_deadline_is_decided_locally(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(client, "_send", lambda _req, _t: release.wait(2) or b"")
    request = urllib.request.Request("https://example.invalid", data=b"{}", method="POST")
    try:
        with pytest.raises(DecisionUnavailable) as info:
            client._send_by_deadline(request, 0.05)
    finally:
        release.set()
    assert info.value.reason == "timeout" and info.value.run_reason() == "timeout:local"


def test_an_unserialisable_state_is_decided_locally():
    state: dict[str, Any] = {}
    state["self"] = state  # json.dumps: ValueError (circular reference)
    with pytest.raises(DecisionUnavailable) as info:
        privacy._serialise(state)
    assert info.value.reason == "invalid-shape"
    assert info.value.run_reason() == "invalid-shape:local"


def test_live_runs_keep_the_bare_reason_vocabulary(transport):
    """``:local`` is replay-only: live telemetry still reads ``timeout``."""
    error = DecisionUnavailable("timeout", "deadline", local=True)
    call = SiteCall(SITES_BY_NAME["creation-intent"], False)
    with patch("core.decisions.engine._fetch", side_effect=error):
        live = run_sync([call], "p", transport=transport, cfg=DecisionsConfig(), timeout_s=1)
        marked = run_sync([call], "p", transport=transport, cfg=DecisionsConfig(),
                          timeout_s=1, mark_local=True)
    assert (live[1], marked[1]) == ("timeout", "timeout:local")


@pytest.mark.parametrize(("error", "reached"), [
    (DecisionUnavailable("timeout", "deadline", local=True), 0),
    (DecisionUnavailable("invalid-shape", "state not serialisable", local=True), 0),
    (DecisionUnavailable("timeout"), 2),  # the endpoint's side: counted as reached
])
def test_local_failures_never_count_as_reached(transport, error, reached):
    # engine._fetch is where post_decision/privacy raise; patched, nothing
    # reaches the breaker, so every case takes the path under test.
    cases = load_corpus("creation-intent")[:2]
    with patch("core.decisions.engine._fetch", side_effect=error):
        report = replay("creation-intent", cases, transport=transport)
    assert report.asked == 2 and report.reached == reached
