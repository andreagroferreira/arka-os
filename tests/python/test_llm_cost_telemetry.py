"""Tests for the LLM cost telemetry JSONL writer and aggregator."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.runtime import llm_cost_telemetry
from core.runtime.llm_cost_telemetry import (
    CostSummary,
    list_expensive_sessions,
    read_entries,
    record_cost,
    summarise,
)


@pytest.fixture()
def tmp_telemetry(tmp_path, monkeypatch):
    path = tmp_path / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(path))
    yield path


# ---------------------------------------------------------------------------
# Task #12 — writer tests (unchanged)
# ---------------------------------------------------------------------------


def test_record_cost_appends_jsonl(tmp_telemetry: Path):
    record_cost(
        session_id="sess-1",
        provider="stub",
        model="claude-opus-4-7",
        tokens_in=100,
        tokens_out=50,
        cached_tokens=0,
        estimated_cost_usd=0.0125,
    )
    entries = read_entries(tmp_telemetry)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["session_id"] == "sess-1"
    assert entry["provider"] == "stub"
    assert entry["model"] == "claude-opus-4-7"
    assert entry["tokens_in"] == 100
    assert entry["tokens_out"] == 50
    assert entry["estimated_cost_usd"] == 0.0125
    assert "ts" in entry


def test_record_cost_creates_dir_if_missing(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "tree" / "llm-cost.jsonl"
    monkeypatch.setenv("ARKA_LLM_COST_PATH", str(nested))
    record_cost("s", "stub", "m", 1, 1, 0, None)
    assert nested.exists()
    assert nested.parent.is_dir()


def test_record_cost_handles_unknown_model_as_null(tmp_telemetry: Path):
    record_cost("s", "p", "unknown-m", 1, 1, 0, None)
    entries = read_entries(tmp_telemetry)
    assert entries[0]["estimated_cost_usd"] is None


def test_record_cost_never_raises_on_bad_path(monkeypatch):
    monkeypatch.setenv("ARKA_LLM_COST_PATH", "/proc/1/forbidden/llm-cost.jsonl")
    record_cost("s", "p", "m", 1, 1, 0, None)  # should not raise


def test_record_cost_never_raises_on_bad_inputs(tmp_telemetry: Path):
    record_cost("s", "p", "m", "10", "20", "0", "0.5")  # type: ignore[arg-type]
    entries = read_entries(tmp_telemetry)
    assert entries[0]["tokens_in"] == 10
    assert entries[0]["estimated_cost_usd"] == 0.5


def test_record_cost_concurrent_safe(tmp_telemetry: Path):
    threads: list[threading.Thread] = []
    for i in range(5):
        t = threading.Thread(
            target=lambda idx=i: [
                record_cost(f"sess-{idx}", "stub", "m", 1, 1, 0, 0.0)
                for _ in range(20)
            ]
        )
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    lines = tmp_telemetry.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 100
    for line in lines:
        assert json.loads(line)["provider"] == "stub"


def test_read_entries_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "nope.jsonl"
    assert read_entries(missing) == []


def test_read_entries_skips_malformed_lines(tmp_telemetry: Path):
    tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
    tmp_telemetry.write_text(
        '{"ok": 1}\nnot json\n{"ok": 2}\n',
        encoding="utf-8",
    )
    entries = read_entries(tmp_telemetry)
    assert entries == [{"ok": 1}, {"ok": 2}]


def test_record_cost_unicode_session_id(tmp_telemetry: Path):
    record_cost("sess-ção-🚀", "stub", "m", 1, 1, 0, 0.0)
    entries = read_entries(tmp_telemetry)
    assert entries[0]["session_id"] == "sess-ção-🚀"


def test_record_cost_large_numbers(tmp_telemetry: Path):
    record_cost("s", "p", "m", 10_000_000, 10_000_000, 0, 1_000.5)
    entries = read_entries(tmp_telemetry)
    assert entries[0]["tokens_in"] == 10_000_000
    assert entries[0]["estimated_cost_usd"] == 1_000.5


def test_record_cost_empty_strings(tmp_telemetry: Path):
    record_cost("", "", "", 0, 0, 0, None)
    entries = read_entries(tmp_telemetry)
    assert entries[0]["session_id"] == ""
    assert entries[0]["tokens_in"] == 0


def test_default_path_is_under_arkaos_telemetry(monkeypatch):
    monkeypatch.delenv("ARKA_LLM_COST_PATH", raising=False)
    path = llm_cost_telemetry._telemetry_path()
    assert path.name == "llm-cost.jsonl"
    assert path.parent.name == "telemetry"


# ---------------------------------------------------------------------------
# Task #14 — aggregation tests
# ---------------------------------------------------------------------------


def _write_entries(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _entry(
    ts: datetime,
    session_id: str = "s",
    provider: str = "anthropic",
    model: str = "claude-opus-4-7",
    tokens_in: int = 1000,
    tokens_out: int = 200,
    cached_tokens: int = 0,
    cost: float | None = 0.01,
) -> dict:
    return {
        "ts": ts.isoformat(),
        "session_id": session_id,
        "provider": provider,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cached_tokens": cached_tokens,
        "estimated_cost_usd": cost,
    }


def test_summarise_today_filters_by_utc_midnight(tmp_telemetry: Path):
    now = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
    yesterday = now - timedelta(days=1)
    just_after_midnight = now.replace(hour=0, minute=1)
    _write_entries(
        tmp_telemetry,
        [
            _entry(yesterday, cost=0.50),  # excluded
            _entry(just_after_midnight, cost=0.10),  # included
            _entry(now, cost=0.20),  # included
        ],
    )
    summary = summarise(period="today", path=tmp_telemetry, now=now)
    assert summary.call_count == 2
    assert summary.total_cost_usd == pytest.approx(0.30, rel=1e-6)


def test_summarise_week_rolling_7_days(tmp_telemetry: Path):
    now = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now - timedelta(days=8), cost=1.0),  # out
            _entry(now - timedelta(days=6), cost=2.0),  # in
            _entry(now - timedelta(hours=1), cost=3.0),  # in
        ],
    )
    summary = summarise(period="week", path=tmp_telemetry, now=now)
    assert summary.call_count == 2
    assert summary.total_cost_usd == pytest.approx(5.0, rel=1e-6)


def test_summarise_month_rolling_30_days(tmp_telemetry: Path):
    now = datetime(2026, 4, 20, 14, 0, tzinfo=timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now - timedelta(days=31), cost=9.0),  # out
            _entry(now - timedelta(days=15), cost=1.0),  # in
            _entry(now, cost=0.5),  # in
        ],
    )
    summary = summarise(period="month", path=tmp_telemetry, now=now)
    assert summary.call_count == 2
    assert summary.total_cost_usd == pytest.approx(1.5, rel=1e-6)


def test_summarise_all_includes_every_entry(tmp_telemetry: Path):
    now = datetime(2026, 4, 20, tzinfo=timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now - timedelta(days=400), cost=4.0),
            _entry(now - timedelta(days=200), cost=2.0),
            _entry(now, cost=0.5),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry, now=now)
    assert summary.call_count == 3
    assert summary.total_cost_usd == pytest.approx(6.5, rel=1e-6)


def test_summarise_empty_file_returns_zero_summary(tmp_telemetry: Path):
    tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
    tmp_telemetry.write_text("", encoding="utf-8")
    summary = summarise(period="today", path=tmp_telemetry)
    assert isinstance(summary, CostSummary)
    assert summary.call_count == 0
    assert summary.total_cost_usd is None
    assert summary.total_tokens_in == 0
    assert summary.cache_hit_rate == 0.0
    assert summary.by_provider == {}
    assert summary.by_model == {}
    assert summary.by_session == []
    assert summary.advisories == []


def test_summarise_missing_file_returns_zero_summary(tmp_path):
    missing = tmp_path / "nope.jsonl"
    summary = summarise(period="week", path=missing)
    assert summary.call_count == 0
    assert summary.total_cost_usd is None
    assert summary.corrupt_line_count == 0


def test_summarise_corrupt_jsonl_skips_and_counts(tmp_telemetry: Path):
    tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    tmp_telemetry.write_text(
        "\n".join(
            [
                json.dumps(_entry(now, cost=0.10)),
                "not json",
                "{broken",
                json.dumps(_entry(now, cost=0.20)),
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert summary.call_count == 2
    assert summary.corrupt_line_count == 2
    assert summary.total_cost_usd == pytest.approx(0.30, rel=1e-6)


def test_summarise_groups_by_provider(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, provider="anthropic", cost=1.0),
            _entry(now, provider="anthropic", cost=2.0),
            _entry(now, provider="openai", cost=0.5),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert set(summary.by_provider.keys()) == {"anthropic", "openai"}
    assert summary.by_provider["anthropic"]["call_count"] == 2
    assert summary.by_provider["anthropic"]["total_cost_usd"] == pytest.approx(3.0)
    assert summary.by_provider["openai"]["call_count"] == 1


def test_summarise_groups_by_model_unknown_bucketed(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, model="claude-opus-4-7", cost=1.0),
            _entry(now, model="", cost=None),
            _entry(now, model="", cost=None),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert "claude-opus-4-7" in summary.by_model
    assert "" in summary.by_model  # unknown bucket
    assert summary.by_model[""]["call_count"] == 2
    assert summary.by_model[""]["total_cost_usd"] is None


def test_summarise_top_sessions_sorted_desc_by_cost(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, session_id="cheap", cost=0.01),
            _entry(now, session_id="mid", cost=1.0),
            _entry(now, session_id="expensive", cost=10.0),
            _entry(now, session_id="mid", cost=0.5),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    ids = [row["session_id"] for row in summary.by_session]
    assert ids[:3] == ["expensive", "mid", "cheap"]
    assert summary.by_session[1]["total_cost_usd"] == pytest.approx(1.5)


def test_summarise_cache_hit_rate_calculation(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, tokens_in=1000, cached_tokens=250, cost=0.1),
            _entry(now, tokens_in=3000, cached_tokens=750, cost=0.3),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert summary.total_tokens_in == 4000
    assert summary.total_cached_tokens == 1000
    assert summary.cache_hit_rate == pytest.approx(0.25)


def test_summarise_advisories_triggered_over_threshold(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, session_id="quiet", cost=0.10),
            _entry(now, session_id="spender", cost=6.50),
        ],
    )
    summary = summarise(
        period="all", path=tmp_telemetry, advisory_threshold_usd=5.0
    )
    assert len(summary.advisories) == 1
    assert "spender" in summary.advisories[0]
    assert "$5.00" in summary.advisories[0]


def test_summarise_advisories_empty_when_under_threshold(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [_entry(now, session_id="quiet", cost=0.10)],
    )
    summary = summarise(
        period="all", path=tmp_telemetry, advisory_threshold_usd=5.0
    )
    assert summary.advisories == []


def test_summarise_invalid_period_raises(tmp_telemetry: Path):
    with pytest.raises(ValueError):
        summarise(period="yearly", path=tmp_telemetry)


def test_list_expensive_sessions_limit_respected(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    rows = [
        _entry(now, session_id=f"s{i}", cost=float(i)) for i in range(1, 16)
    ]
    _write_entries(tmp_telemetry, rows)
    top = list_expensive_sessions(path=tmp_telemetry, top_n=5)
    assert len(top) == 5
    assert [r["session_id"] for r in top] == ["s15", "s14", "s13", "s12", "s11"]


def test_list_expensive_sessions_missing_file(tmp_path):
    missing = tmp_path / "nope.jsonl"
    assert list_expensive_sessions(path=missing, top_n=10) == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_summarise_all_null_costs_totals_none(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, model="unpriced-m", cost=None),
            _entry(now, model="unpriced-m", cost=None),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert summary.call_count == 2
    assert summary.total_cost_usd is None
    # Group bucket also surfaces None because no cost ever known.
    assert summary.by_model["unpriced-m"]["total_cost_usd"] is None


def test_summarise_huge_numbers(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(
                now,
                tokens_in=10_000_000_000,
                tokens_out=5_000_000_000,
                cached_tokens=1_000_000_000,
                cost=99_999.50,
            ),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert summary.total_tokens_in == 10_000_000_000
    assert summary.total_tokens_out == 5_000_000_000
    assert summary.total_cost_usd == pytest.approx(99_999.50)
    assert summary.cache_hit_rate == pytest.approx(0.1, rel=1e-4)


def test_summarise_unicode_session_ids(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, session_id="sess-ção-🚀", cost=2.0),
            _entry(now, session_id="普通のセッション", cost=0.5),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    ids = {row["session_id"] for row in summary.by_session}
    assert ids == {"sess-ção-🚀", "普通のセッション"}


def test_summarise_mixed_costs_sum_known_only(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    _write_entries(
        tmp_telemetry,
        [
            _entry(now, cost=1.0),
            _entry(now, cost=None),
            _entry(now, cost=2.5),
        ],
    )
    summary = summarise(period="all", path=tmp_telemetry)
    assert summary.call_count == 3
    assert summary.total_cost_usd == pytest.approx(3.5)


def test_summarise_handles_entries_without_ts(tmp_telemetry: Path):
    # "all" period must include entries even when ts is missing/unparseable.
    tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
    tmp_telemetry.write_text(
        json.dumps(
            {
                "session_id": "s",
                "provider": "p",
                "model": "m",
                "tokens_in": 10,
                "tokens_out": 5,
                "cached_tokens": 0,
                "estimated_cost_usd": 0.2,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_all = summarise(period="all", path=tmp_telemetry)
    assert summary_all.call_count == 1
    # Period-filtered views skip entries that can't be dated.
    summary_today = summarise(period="today", path=tmp_telemetry)
    assert summary_today.call_count == 0


def test_summarise_handles_z_suffix_ts(tmp_telemetry: Path):
    now = datetime.now(timezone.utc)
    z_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    tmp_telemetry.parent.mkdir(parents=True, exist_ok=True)
    tmp_telemetry.write_text(
        json.dumps(
            {
                "ts": z_ts,
                "session_id": "s",
                "provider": "p",
                "model": "m",
                "tokens_in": 100,
                "tokens_out": 50,
                "cached_tokens": 0,
                "estimated_cost_usd": 0.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary = summarise(period="today", path=tmp_telemetry, now=now)
    assert summary.call_count == 1
