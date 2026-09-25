"""core.decisions.cost_effect + telemetry_cli cost section (spec PR5, D5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from core.decisions import cost_effect as ce
from core.decisions import telemetry_cli
from core.decisions.telemetry import summarise

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
TS = "2026-09-25T10:00:00+00:00"
SHALLOW = {"scope": 0, "dependencies": 0, "ambiguity": 0, "risk": 0, "novelty": 0}
DEEP = dict.fromkeys(SHALLOW, 100)


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps({"ts": TS, **r}) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture
def src(tmp_path, monkeypatch) -> ce.Sources:
    sources = ce.Sources(tmp_path / "d.jsonl", tmp_path / "cost.jsonl",
                         tmp_path / "qg.jsonl", tmp_path / "act.jsonl")
    monkeypatch.setenv("ARKA_DECISIONS_TELEMETRY_PATH", str(sources.decisions))
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(sources.ledger))
    monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(sources.verdicts))
    monkeypatch.setattr("core.governance.activation_tracker.TELEMETRY_PATH", sources.activations)
    return sources


def test_default_sources_follow_each_env_override(src):
    assert ce.default_sources() == src


def test_ledger_split_separates_replay_from_production():
    ledger = [
        {"category": "decision", "session_id": "live-1", "estimated_cost_usd": 0.01},
        {"category": "decision", "session_id": "replay", "estimated_cost_usd": 0.02},  # older
        {"category": "decision-replay", "session_id": "replay", "estimated_cost_usd": 0.04},
        {"category": "subagent:marta-cqo", "session_id": "live-1", "estimated_cost_usd": 9.0},
    ]
    split = ce.ledger_split(ledger)
    assert (split.production_usd, split.production_calls) == (0.01, 1)
    assert (split.replay_usd, split.replay_calls) == (pytest.approx(0.06), 2)


def test_forge_complexity_counts_tier_changes_by_direction():
    rows = [
        {"site": "forge-complexity", "heuristic_result": SHALLOW, "jev_result": DEEP},
        {"site": "forge-complexity", "heuristic_result": DEEP, "jev_result": SHALLOW},
        {"site": "forge-complexity", "heuristic_result": DEEP, "jev_result": DEEP},
        {"site": "forge-complexity", "heuristic_result": DEEP, "jev_result": None},
        {"site": "forge-complexity", "heuristic_result": {"bad": 1}, "jev_result": DEEP},
        {"site": "forge-complexity", "heuristic_result": {**SHALLOW, "novelty": "x"},
         "jev_result": DEEP},
        {"site": "route", "heuristic_result": SHALLOW, "jev_result": DEEP},
    ]
    c = ce.forge_complexity(rows)
    assert (c.count, c.detail, c.saving, c.ceiling_usd) == (2, {"up": 1, "down": 1}, "—", None)


def test_dispatch_role_counts_acted_escalations_and_never_saves():
    rows = [
        {"site": "dispatch-role", "acted_on": "jev", "jev_result": "review",
         "heuristic_result": "execution"},
        {"site": "dispatch-role", "acted_on": "jev", "jev_result": "execution",
         "heuristic_result": "execution"},
        {"site": "dispatch-role", "acted_on": "heuristic", "reason": "downgrade-blocked",
         "jev_result": "mechanical", "heuristic_result": "execution"},
    ]
    c = ce.dispatch_role(rows)
    assert (c.count, c.detail) == (1, {"downgrade_blocked": 1})
    assert "never saves by construction" in c.saving and c.ceiling_usd is None


def test_qg_prescreen_ceiling_is_reviewer_cost_of_correctly_predicted_rejections():
    verdicts = [
        {"session_id": "s1", "verdict": "REJECTED", "prescreen": {"verdict": "rejected"}},
        {"session_id": "s1", "verdict": "APPROVED", "prescreen": {"verdict": "approved"}},
        {"session_id": "s2", "verdict": "APPROVED", "prescreen": {"verdict": "rejected"}},
        {"session_id": "s3", "verdict": "REJECTED", "prescreen": None},
    ]
    ledger = [
        {"category": "subagent:eduardo-copy", "session_id": "s1", "estimated_cost_usd": 1.0},
        {"category": "subagent:francisca-tech", "session_id": "s1", "estimated_cost_usd": 2.0},
        {"category": "subagent:marta-cqo", "session_id": "s1", "estimated_cost_usd": 3.0},
        {"category": "subagent:eduardo-copy", "session_id": "s2", "estimated_cost_usd": 5.0},
    ]
    c = ce.qg_prescreen(verdicts, ledger)
    assert c.count == 3 and c.detail == {"agree_with_final": 2, "sessions_rejected_as_predicted": 1}
    assert (c.saving, c.ceiling_usd) == (ce.COUNTERFACTUAL, 3.0)


def test_subagent_discipline_correlates_by_session_only():
    rows = [
        {"site": "subagent-discipline", "session_id": "s1", "acted_on": "jev",
         "jev_result": False, "heuristic_result": True},
        {"site": "subagent-discipline", "session_id": "s2", "acted_on": "heuristic",
         "jev_result": None, "heuristic_result": False},
        {"site": "subagent-discipline", "session_id": "s3", "acted_on": "jev",
         "jev_result": True, "heuristic_result": False},
    ]
    c = ce.subagent_discipline(rows, [{"session_id": "s1"}, {"session_id": "s3"}])
    assert (c.count, c.detail) == (2, {"sessions": 2, "sessions_with_a_subagent": 1})
    assert "not attribution" in c.saving


def test_cost_effect_filters_by_period_and_rejects_bad_periods(src):
    _write(src.ledger, [{"category": "decision", "session_id": "x", "estimated_cost_usd": 0.5}])
    src.decisions.write_text(json.dumps({"ts": "2026-09-01T00:00:00+00:00", "site": "route"})
                             + "\n", encoding="utf-8")
    today = ce.cost_effect("today", sources=src, now=NOW)
    assert today.has_data and today.ledger.production_calls == 1
    assert [c.number for c in today.counterfactuals] == [7, 10, 11, 22]
    assert ce.cost_effect("all", sources=src, now=NOW).has_data
    with pytest.raises(ValueError, match="invalid period"):
        ce.cost_effect("year", sources=src)


def _cli(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = telemetry_cli.main(args)
    return code, capsys.readouterr().out


def test_cli_without_data_is_the_old_output_plus_an_empty_cost_section(src, capsys):
    code, out = _cli(["all"], capsys)
    old = telemetry_cli._render(summarise("all"))
    assert code == 0 and out == old + "\n\n## Cost and effect\n\n" \
        "_No cost or effect data for this period._\n"


def test_cli_is_byte_identical_under_bypass(src, capsys, monkeypatch):
    _write(src.decisions, [{"site": "route", "acted_on": "jev", "jev_result": "dev",
                            "heuristic_result": "dev", "agree": True, "cost_usd": 0.001}])
    _write(src.ledger, [{"category": "decision", "session_id": "x", "estimated_cost_usd": 0.001}])
    monkeypatch.delenv("ARKA_BYPASS_DECISIONS", raising=False)
    plain = _cli(["all", "--by-site"], capsys)
    monkeypatch.setenv("ARKA_BYPASS_DECISIONS", "1")
    assert _cli(["all", "--by-site"], capsys) == plain


def test_cli_never_calls_a_counterfactual_a_saving(src, capsys):
    _write(src.verdicts, [{"session_id": "s1", "verdict": "REJECTED",
                           "prescreen": {"verdict": "rejected"}}])
    _write(src.ledger, [
        {"category": "subagent:eduardo-copy", "session_id": "s1", "estimated_cost_usd": 1.25},
        {"category": "decision", "session_id": "live", "estimated_cost_usd": 0.002},
        {"category": "decision-replay", "session_id": "replay", "estimated_cost_usd": 0.003},
    ])
    code, out = _cli(["all"], capsys)
    assert code == 0 and ce.NO_MEASURED_SAVING in out
    assert "counterfactual (ceiling): $1.250000" in out
    assert "**$0.002000** over 1 call(s)" in out and "$0.003000 over 1 call(s)" in out
    lowered = out.lower()
    assert "saved" not in lowered and "poupado" not in lowered and "poupança" not in lowered


def test_cli_by_site_adds_the_effect_table(src, capsys):
    _write(src.decisions, [
        {"site": "route", "acted_on": "jev", "jev_result": "dev", "cost_usd": 0.001},
        {"site": "route", "fallback_used": True, "reason": "abstain", "cost_usd": 0.001},
        {"site": "route", "fallback_used": True, "reason": "timeout"},
    ])
    _, plain = _cli(["all"], capsys)
    _, by_site = _cli(["all", "--by-site"], capsys)
    assert "## Effect by site" not in plain
    assert "| `route` | $0.002000 | 1 | 2 | 1 | 50.0% | abstain 1, timeout 1 |" in by_site


@pytest.mark.parametrize("args", [["--nope"], ["today", "week"], ["year"]])
def test_cli_rejects_bad_arguments(src, capsys, args):
    assert telemetry_cli.main(args) == 2
    assert "error:" in capsys.readouterr().err
