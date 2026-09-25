"""core.decisions.replay_report — measured runs, cache off, real ceilings, artefacts."""

from __future__ import annotations

import hashlib
import json
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from _decisions_helpers import fake_ok, isolate_decisions, read_jsonl, write_config

from core.decisions import replay as rp
from core.decisions import replay_report as rr
from core.decisions.registry import SITES
from core.decisions.replay import ReplayReport, load_corpus
from core.decisions.telemetry import REPLAY_COST_CATEGORY, SiteSummary

URLOPEN = "core.decisions.client.urllib.request.urlopen"


@pytest.fixture
def home(monkeypatch, tmp_path) -> Path:
    # Corpora use the placeholder "ClienteY" (see test_decisions_replay).
    return isolate_decisions(monkeypatch, tmp_path, clients=["zz-no-such-client"])


def _empty(request: Any, timeout: float) -> Any:
    return fake_ok({})  # every site abstains: measured, gate fail


def _out(home: Path, session: str = "s1") -> Path:
    return home / ".arkaos" / "quality-gate" / session / "replay-final"


def _summary(home: Path, session: str = "s1") -> dict[str, Any]:
    return json.loads((_out(home, session) / "SUMMARY.json").read_text(encoding="utf-8"))


def _run(argv: list[str], side_effect: Any = _empty) -> tuple[int, int]:
    with patch(URLOPEN, side_effect=side_effect) as mock:
        code = rr.main(argv)
    return code, mock.call_count


def test_all_seventeen_sites_write_every_artefact(home):
    code, calls = _run(["--all", "--session", "s1", "--runs", "1"])
    out = _out(home)
    assert code == 0
    assert {"REPORT.md", "SUMMARY.json", "PROPOSALS.json"} <= {p.name for p in out.iterdir()}
    summary = _summary(home)
    assert list(summary["sites"]) == list(SITES) and summary["all_measured"] is True
    reached = 0
    for site, entry in summary["sites"].items():
        run = json.loads((out / f"{site}-run1.json").read_text(encoding="utf-8"))
        assert run["measured_gate"] == "fail" and run["cost_category"] == REPLAY_COST_CATEGORY
        corpus = rp.default_corpus_path(site).read_bytes()
        assert entry["corpus_sha256"] == run["corpus_sha256"] == hashlib.sha256(corpus).hexdigest()
        reached += run["reached"]
    assert calls == reached, "one POST per reached case, nothing hidden"
    proposals = json.loads((out / "PROPOSALS.json").read_text(encoding="utf-8"))
    assert [p["site"] for p in proposals] == list(SITES)
    report = (out / "REPORT.md").read_text(encoding="utf-8")
    assert "informational, never decides a mode" in report and "`slop-score`" in report


def test_second_run_asks_the_endpoint_as_often_as_the_first(home):
    """Cache off: a mutant that keeps the TTL turns run 2 into cache hits."""
    _, first = _run(["--sites", "route", "--session", "a", "--runs", "1"])
    _, both = _run(["--sites", "route", "--session", "b", "--runs", "2"])
    assert first == len(load_corpus("route")) and both == 2 * first
    runs = [json.loads((_out(home, "b") / f"route-run{k}.json").read_text()) for k in (1, 2)]
    assert runs[0]["reached"] == runs[1]["reached"] == first


def test_no_cache_config_only_turns_the_cache_off():
    from core.decisions.config import DecisionsConfig

    cfg = DecisionsConfig.model_validate({"hookTimeoutMs": 900, "sites": {"route": "shadow"}})
    copy = rr.no_cache_config(cfg)
    assert copy.cache_ttl_seconds == 0 and cfg.cache_ttl_seconds == 86400
    assert copy.hook_timeout_ms == 900 and copy.sites == cfg.sites


def test_each_call_uses_the_site_ceiling_and_the_replay_category(home):
    write_config(home, {"sites": {"route": {"mode": "act", "timeoutMs": 777}}})
    seen: list[tuple[float, str]] = []
    real = rp.run_sync

    def spy(*args: Any, **kwargs: Any) -> Any:
        seen.append((kwargs["timeout_s"], kwargs["cost_category"]))
        return real(*args, **kwargs)

    with patch("core.decisions.replay.run_sync", side_effect=spy):
        _run(["--sites", "route,topic-drift", "--session", "s1", "--runs", "1"])
    n_route, n_drift = len(load_corpus("route")), len(load_corpus("topic-drift"))
    assert seen[:n_route] == [(0.777, REPLAY_COST_CATEGORY)] * n_route
    drift = SITES["topic-drift"].timeout_ms / 1000
    assert seen[n_route:] == [(drift, REPLAY_COST_CATEGORY)] * n_drift


def test_replay_cost_is_its_own_ledger_category_and_skips_live_telemetry(home, tmp_path):
    _run(["--sites", "route", "--session", "s1", "--runs", "1"])
    rows = read_jsonl(tmp_path / "llm-cost.jsonl")
    assert len(rows) == len(load_corpus("route"))
    assert {(r["category"], r["session_id"]) for r in rows} == {(REPLAY_COST_CATEGORY, "replay")}
    assert read_jsonl(tmp_path / "decisions.jsonl") == [], "the live column stays live"


def test_unreachable_endpoint_is_not_measured_and_exits_1(home):
    def down(request: Any, timeout: float) -> Any:
        raise urllib.error.URLError("down")

    code, _ = _run(["--sites", "route", "--session", "s1", "--runs", "1"], down)
    entry = _summary(home)["sites"]["route"]
    assert code == 1 and entry["gates"] == ["not-measured"]
    assert entry["proposal"]["action"] == "keep" and entry["proposal"]["runs_considered"] == 0


def _report(**kw: Any) -> ReplayReport:
    base: dict[str, Any] = {"site": "route", "cases": 40, "pt_share": 0.6,
                            "heuristic_accuracy": 0.5, "gate": "pass", "asked": 40, "reached": 40}
    return ReplayReport(**{**base, **kw})


@pytest.mark.parametrize(("kw", "want"), [
    ({}, "pass"),
    ({"gate": "fail"}, "fail"),
    ({"reached": 36}, "pass"),  # exactly 90 %
    ({"reached": 35}, "not-measured"),
    ({"unavailable": 4}, "pass"),  # exactly 10 %
    ({"unavailable": 5}, "not-measured"),
    ({"asked": 0, "reached": 0}, "not-measured"),
    ({"asked": None, "reached": None, "gate": "offline"}, "not-measured"),
])
def test_measure_floors(kw, want):
    gate, why = rr.measure(_report(**kw))
    assert gate == want and (why == "") == (want != "not-measured")


@pytest.mark.parametrize("argv", [
    ["--all"],
    ["--all", "--session", "../escape"],
    ["--all", "--session", "a..b"],
    ["--sites", "nope", "--session", "s1"],
    ["--sites", "", "--session", "s1"],
    ["--all", "--session", "s1", "--runs", "0"],
    ["--all", "--sites", "route", "--session", "s1"],
])
def test_usage_errors_exit_2_before_any_call(home, argv):
    assert _run(argv) == (2, 0)


def test_bypass_and_missing_key_exit_2_before_any_call(home, monkeypatch):
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    assert _run(["--all", "--session", "s1"]) == (2, 0)
    monkeypatch.delenv("ARKA_BYPASS_DECISIONS")
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert _run(["--all", "--session", "s1"]) == (2, 0)
    assert not _out(home).exists()


def test_operator_override_is_reported_not_proposed_on(home):
    write_config(home, {"sites": {"refine": "act"}})
    _run(["--sites", "refine", "--session", "s1", "--runs", "1"])
    entry = _summary(home)["sites"]["refine"]
    assert (entry["default_mode"], entry["effective_mode"], entry["operator_override"]) == (
        "shadow", "act", True)
    assert entry["proposal"]["current"] == "shadow"
    report = (_out(home) / "REPORT.md").read_text(encoding="utf-8")
    assert "shadow (operator override: act)" in report


def test_two_passing_runs_reach_the_rule(home):
    cases = {c.prompt: c for c in load_corpus("creation-intent")}

    def oracle(request: Any, timeout: float) -> Any:
        prompt = json.loads(request.data.decode("utf-8"))["state"]["prompt"]
        p = 0.97 if cases[prompt].expected else 0.03
        return fake_ok({"creation_intent__creation_intent": {"noul": p}})

    code, _ = _run(["--sites", "creation-intent", "--session", "s1", "--runs", "2"], oracle)
    entry = _summary(home)["sites"]["creation-intent"]
    assert code == 0 and entry["gates"] == ["pass", "pass"]
    assert (entry["proposal"]["action"], entry["proposal"]["proposed"]) == ("keep", "act")


def _live(calls: int, pct: float | None) -> SiteSummary:
    return SiteSummary(calls=calls, agreement_pct=None, fallback_pct=0.0, p50_latency_ms=None,
                       cost_usd=0.0, acted_jev_pct=0.0, abstain_attributable_pct=pct)


@pytest.mark.parametrize(("calls", "pct", "period", "drift"), [
    (60, 30.0, "week", True),
    (60, 30.0, "today", False),  # window under 7 days
    (49, 30.0, "week", False),
    (60, 25.0, "month", False),
    (60, None, "all", False),
])
def test_live_drift_flag(calls, pct, period, drift):
    view = rr.live_view(_live(calls, pct), period)
    assert view is not None and view.live_drift is drift
    assert rr.live_view(None, "week") is None
