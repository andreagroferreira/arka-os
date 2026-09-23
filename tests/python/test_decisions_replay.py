"""core.decisions.replay — corpora, gate arithmetic, CLI exit codes."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions

from core.decisions import replay as rp
from core.decisions.config import DecisionsConfig
from core.decisions.replay import ReplayCase, load_corpus, main, replay
from core.decisions.transport import resolve_transport

URLOPEN = "core.decisions.client.urllib.request.urlopen"
SITES = ("topic-drift", "refine", "creation-intent", "route")


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
        load_corpus("route", path)


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
    assert "JEV answered no case" in report.failures
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
        assert "JEV precision (answered): 100.0%" in out and "false escalation: 0.0%" in out


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
