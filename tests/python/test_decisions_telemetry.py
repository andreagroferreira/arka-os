"""core.decisions.telemetry + telemetry_cli — writer, cost ledger, summary."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from _decisions_helpers import read_jsonl

from core.decisions import telemetry, telemetry_cli
from core.decisions.models import Usage
from core.decisions.telemetry import DecisionRecord, record, record_call_cost, summarise
from core.decisions.transport import Transport

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_DECISIONS_TELEMETRY_PATH", str(tmp_path / "d.jsonl"))
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(tmp_path / "cost.jsonl"))
    # The CLI's cost section also reads these two: never the operator's files.
    monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(tmp_path / "qg.jsonl"))
    monkeypatch.setattr("core.governance.activation_tracker.TELEMETRY_PATH", tmp_path / "act.jsonl")
    return tmp_path


def _t(model: str = "typesafe/jev-1.13") -> Transport:
    return Transport(name="openrouter", url="u", key="k", model=model)


def test_record_appends_every_field(paths):
    assert record(DecisionRecord(site="route", jev_result="dev", agree=True)) is True
    (line,) = read_jsonl(paths / "d.jsonl")
    assert line["site"] == "route" and line["agree"] is True
    for field in ("ts", "session_id", "mode", "call_id", "question_keys", "answers",
                  "confidence", "latency_ms", "input_tokens", "cost_usd", "transport",
                  "model", "fallback_used", "reason", "heuristic_result", "jev_result",
                  "acted_on", "state_sha16", "cache_hit"):
        assert field in line


def test_record_rotates_and_never_raises(paths, monkeypatch):
    with patch("core.shared.telemetry_rotate.rotate_if_oversized") as rot:
        record(DecisionRecord(site="x"))
    rot.assert_called_once_with(paths / "d.jsonl")
    monkeypatch.setenv("ARKA_DECISIONS_TELEMETRY_PATH", str(paths))  # a directory
    assert record(DecisionRecord(site="x")) is False


def test_telemetry_file_is_private(paths):
    """0600 at creation, and a looser pre-existing file is repaired."""
    record(DecisionRecord(site="x"))
    assert (paths / "d.jsonl").stat().st_mode & 0o777 == 0o600
    (paths / "d.jsonl").chmod(0o644)
    record(DecisionRecord(site="y"))
    assert (paths / "d.jsonl").stat().st_mode & 0o777 == 0o600


def test_state_sha16_is_keyed_by_the_install_salt(tmp_path, monkeypatch):
    import hashlib

    from core.decisions.telemetry import SALT_NAME, state_sha16

    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / "c1"))
    state = {"prompt": "sim", "recent_user_messages": []}
    first = state_sha16(state)
    salt = tmp_path / "c1" / SALT_NAME
    assert first == state_sha16(state), "stable within one install"
    assert salt.stat().st_mode & 0o777 == 0o600 and len(salt.read_bytes()) == 16
    blob = json.dumps(state, sort_keys=True, ensure_ascii=False).encode()
    assert first != hashlib.sha256(blob).hexdigest()[:16], "never the unsalted oracle"
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / "c2"))
    assert state_sha16(state) != first, "another install salt, another digest"


def test_call_cost_prefers_reported_cost(paths):
    record_call_cost("s1", _t(), Usage(input_tokens=749, output_tokens=118, cost=3.1458e-05))
    (row,) = read_jsonl(paths / "cost.jsonl")
    assert row["category"] == "decision" and row["model"] == "typesafe/jev-1.13"
    assert row["estimated_cost_usd"] == pytest.approx(3.1458e-05)
    assert "pricing_status" not in row


def test_call_cost_falls_back_to_pricing_then_unknown(paths):
    record_call_cost("s1", _t(), Usage(input_tokens=1_000_000))
    record_call_cost("s1", _t("typesafe/unknown"), Usage(input_tokens=10))
    priced, unknown = read_jsonl(paths / "cost.jsonl")
    assert priced["estimated_cost_usd"] == pytest.approx(0.042)
    assert unknown["estimated_cost_usd"] is None
    assert unknown["pricing_status"] == "unknown-model"


def _write(paths, rows, extra: str = ""):
    lines = [json.dumps(r) for r in rows]
    (paths / "d.jsonl").write_text("\n".join(lines) + "\n" + extra, encoding="utf-8")


def _row(site, **kw):
    base = {"ts": NOW.isoformat(), "site": site, "acted_on": "heuristic",
            "fallback_used": False, "cost_usd": 0.0}
    return {**base, **kw}


def test_summarise_aggregates(paths):
    _write(paths, [
        _row("route", agree=True, acted_on="jev", latency_ms=300, cost_usd=0.00001),
        _row("route", agree=False, acted_on="jev", latency_ms=500, cost_usd=0.00001),
        _row("route", fallback_used=True, reason="timeout", latency_ms=1500),
        _row("topic-drift", agree=True, cache_hit=True, latency_ms=0, acted_on="jev"),
        _row("topic-drift", ts=(NOW - timedelta(days=2)).isoformat()),
    ], extra="{broken\n[1]\n")
    s = summarise("today", path=paths / "d.jsonl", now=NOW)
    assert s.calls == 4 and s.corrupt_line_count == 2
    route = s.by_site["route"]
    assert (route.calls, route.agreement_pct, route.fallback_pct) == (3, 50.0, 33.3)
    assert route.p50_latency_ms == 400 and route.acted_jev_pct == 66.7
    assert route.cost_usd == pytest.approx(0.00002)
    assert s.cache_hit_pct == 25.0 and s.top_fallback_reasons == [("timeout", 1)]
    assert s.by_site["topic-drift"].p50_latency_ms is None
    assert summarise("week", path=paths / "d.jsonl", now=NOW).calls == 5


def test_record_call_cost_takes_the_replay_category(paths):
    record_call_cost("replay", _t(), Usage(input_tokens=1, cost=1e-06), category="decision-replay")
    (row,) = read_jsonl(paths / "cost.jsonl")
    assert (row["category"], row["session_id"]) == ("decision-replay", "replay")


def test_summarise_counts_effects_per_site(paths):
    _write(paths, [
        _row("route", acted_on="jev", jev_result="dev", reason="jev"),
        _row("route", jev_result="dev", reason="shadow"),
        _row("route", fallback_used=True, reason="abstain"),
        _row("route", fallback_used=True, reason="egress-denied:secret"),
        _row("route", fallback_used=True, reason="timeout"),
        _row("route", fallback_used=True, reason="timeout"),
        _row("refine", fallback_used=True, reason="timeout"),
    ])
    route = summarise("today", path=paths / "d.jsonl", now=NOW).by_site["route"]
    assert (route.acted_jev, route.fallback, route.abstain) == (1, 4, 1)
    # Only Jev's own abstain counts against it: 1 / (2 answered + 1 abstain).
    assert route.abstain_attributable_pct == 33.3
    assert route.top_fallback_reasons == (("timeout", 2), ("abstain", 1),
                                          ("egress-denied:secret", 1))
    refine = summarise("today", path=paths / "d.jsonl", now=NOW).by_site["refine"]
    assert refine.abstain_attributable_pct is None, "no answer and no abstain: not measured"


def test_summarise_edges(paths):
    empty = summarise("all", path=paths / "missing.jsonl")
    assert empty.calls == 0 and empty.by_site == {}
    with pytest.raises(ValueError):
        summarise("year")
    _write(paths, [_row("x", ts="garbage"), _row("x", ts="2026-09-23T10:00:00")])
    assert summarise("month", path=paths / "d.jsonl", now=NOW).calls == 1


class TestCli:
    def test_renders_markdown(self, paths, capsys):
        _write(paths, [_row("route", agree=True, acted_on="jev", latency_ms=282,
                            ts=datetime.now(UTC).isoformat())], extra="{x\n")
        assert telemetry_cli.main(["today"]) == 0
        out = capsys.readouterr().out
        assert out.startswith("# Decisions — today")
        assert "| `route` | 1 | 100.0% |" in out and "282 ms" in out
        assert "corrupt line" in out

    def test_empty_and_invalid(self, paths, capsys):
        assert telemetry_cli.main([]) == 0
        assert "No decisions recorded" in capsys.readouterr().out
        assert telemetry_cli.main(["year"]) == 2

    def test_render_fallback_reasons_sanitised(self):
        summary = telemetry.DecisionsSummary(
            period="all", calls=1, top_fallback_reasons=[("http-429`\n|x", 1)]
        )
        out = telemetry_cli._render(summary)
        assert "`http-429 /x` — 1" in out
