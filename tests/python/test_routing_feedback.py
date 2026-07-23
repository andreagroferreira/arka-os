"""Tests for core.governance.routing_feedback (F1-B1)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.governance.routing_feedback import (
    RoutingScores,
    load_scores,
    rebuild,
    stale,
)
from core.governance.routing_feedback_cli import main as cli_main

NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def corpora(tmp_path, monkeypatch):
    """Isolated label corpora + scores file via the supported env overrides."""
    qg = tmp_path / "qg-verdicts.jsonl"
    judge = tmp_path / "judge-verdicts.jsonl"
    scores = tmp_path / "routing-scores.json"
    qg.touch()
    judge.touch()
    monkeypatch.setenv("ARKA_QG_LABELS_PATH", str(qg))
    monkeypatch.setenv("ARKA_JUDGE_LABELS_PATH", str(judge))
    monkeypatch.setenv("ARKA_ROUTING_SCORES_PATH", str(scores))
    return {"qg": qg, "judge": judge, "scores": scores}


def _qg_line(department: str, verdict: str, *, days_ago: float = 1.0,
             deliverable: str = "", blockers: list[str] | None = None) -> str:
    return json.dumps({
        "ts": (NOW - timedelta(days=days_ago)).isoformat(),
        "department": department,
        "deliverable": deliverable,
        "verdict": verdict,
        "blockers": [{"check": c, "detail": "x"} for c in (blockers or [])],
    })


def _judge_line(department: str, verdict: str, days_ago: float = 1.0) -> str:
    return json.dumps({
        "ts": (NOW - timedelta(days=days_ago)).isoformat(),
        "department": department,
        "verdict": verdict,
        "gate": "G4",
    })


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ─── rebuild() aggregation ─────────────────────────────────────────────


def test_rebuild_counts_and_smoothing(corpora):
    _write(corpora["qg"], [
        _qg_line("dev", "APPROVED"),
        _qg_line("dev", "APPROVED"),
        _qg_line("dev", "REJECTED", blockers=["function-length"]),
        _qg_line("frontend", "REJECTED", blockers=["missing-tests"]),
    ])
    result = rebuild(now=NOW)
    by_dept = {s.department: s for s in result.scores}
    dev = by_dept["dev"]
    assert (dev.approvals, dev.rejections, dev.samples) == (2, 1, 3)
    assert 0.5 < dev.smoothed_approval < 1.0  # Laplace keeps it citable, not 1.0
    frontend = by_dept["frontend"]
    assert frontend.smoothed_approval < 0.5
    assert frontend.top_blocker_patterns == ["missing-tests"]


def test_recency_weighting_forgets_old_failures(corpora):
    """An old rejection storm must weigh less than recent approvals."""
    _write(corpora["qg"], [
        _qg_line("dev", "REJECTED", days_ago=85.0),
        _qg_line("dev", "REJECTED", days_ago=84.0),
        _qg_line("dev", "APPROVED", days_ago=1.0),
        _qg_line("dev", "APPROVED", days_ago=2.0),
    ])
    result = rebuild(now=NOW)
    dev = result.scores[0]
    assert dev.approvals == 2 and dev.rejections == 2  # raw counts stay honest
    assert dev.smoothed_approval > 0.6  # weights favour the recent record


def test_window_excludes_ancient_records(corpora):
    _write(corpora["qg"], [
        _qg_line("dev", "REJECTED", days_ago=200.0),
        _qg_line("dev", "APPROVED", days_ago=1.0),
    ])
    result = rebuild(now=NOW)
    assert result.scores[0].rejections == 0
    assert result.scores[0].samples == 1


def test_unattributable_records_skipped(corpora):
    _write(corpora["qg"], [
        _qg_line("", "REJECTED"),
        json.dumps({"ts": "not-a-date", "department": "dev", "verdict": "APPROVED"}),
        _qg_line("dev", "APPROVED"),
    ])
    result = rebuild(now=NOW)
    assert len(result.scores) == 1
    assert result.scores[0].samples == 1


def test_redo_detection_same_deliverable_within_window(corpora):
    _write(corpora["qg"], [
        _qg_line("dev", "REJECTED", days_ago=3.0, deliverable="feature-x"),
        _qg_line("dev", "REJECTED", days_ago=2.5, deliverable="feature-x"),
        _qg_line("dev", "REJECTED", days_ago=40.0, deliverable="feature-y"),
        _qg_line("dev", "REJECTED", days_ago=20.0, deliverable="feature-y"),
    ])
    result = rebuild(now=NOW)
    dev = result.scores[0]
    assert dev.redo_count == 1  # feature-x pair inside 7d; feature-y pair outside


def test_redo_ignores_empty_deliverable(corpora):
    """QG blocker B2: the live pipeline defaults deliverable to '' —
    two UNRELATED rejections must never count as a redo."""
    _write(corpora["qg"], [
        _qg_line("dev", "REJECTED", days_ago=3.0, deliverable=""),
        _qg_line("dev", "REJECTED", days_ago=2.5, deliverable=""),
    ])
    result = rebuild(now=NOW)
    assert result.scores[0].redo_count == 0
    assert result.scores[0].rejections == 2  # raw counts stay honest


def test_mixed_naive_and_aware_timestamps_never_crash(corpora):
    """QG blocker B1: a naive ts in the same redo bucket crashed
    stamps.sort() with TypeError, killing every detached rebuild."""
    naive = (NOW - timedelta(days=2.0)).replace(tzinfo=None).isoformat()
    _write(corpora["qg"], [
        json.dumps({"ts": naive, "department": "dev",
                    "deliverable": "feature-x", "verdict": "REJECTED"}),
        _qg_line("dev", "REJECTED", days_ago=1.5, deliverable="feature-x"),
    ])
    result = rebuild(now=NOW)  # must not raise
    assert result.scores[0].redo_count == 1  # naive normalized to UTC, pair counted
    assert corpora["scores"].exists()  # the file LANDS — stale() can go False


def test_judge_signal_kept_separate(corpora):
    _write(corpora["judge"], [
        _judge_line("dev", "PASS"),
        _judge_line("dev", "REVISE"),
        _judge_line("dev", "REVISE"),
    ])
    result = rebuild(now=NOW)
    dev = result.scores[0]
    assert (dev.judge_passes, dev.judge_revises) == (1, 2)
    assert dev.samples == 0  # judge verdicts never inflate QG sample count
    assert dev.smoothed_approval == 0.5  # neutral prior without QG data


def test_top_blockers_ranked(corpora):
    _write(corpora["qg"], [
        _qg_line("dev", "REJECTED", blockers=["a", "b"]),
        _qg_line("dev", "REJECTED", blockers=["b"]),
        _qg_line("dev", "REJECTED", blockers=["b", "c", "d"]),
    ])
    result = rebuild(now=NOW)
    assert result.scores[0].top_blocker_patterns[0] == "b"
    assert len(result.scores[0].top_blocker_patterns) == 3


# ─── persistence + staleness ───────────────────────────────────────────


def test_atomic_write_and_load_roundtrip(corpora):
    _write(corpora["qg"], [_qg_line("dev", "APPROVED")])
    rebuild(now=NOW)
    loaded = load_scores()
    assert isinstance(loaded, RoutingScores)
    assert loaded.scores[0].department == "dev"
    assert not list(corpora["scores"].parent.glob("*.tmp"))


def test_load_rejects_unknown_version(corpora):
    corpora["scores"].write_text(json.dumps({"version": 99, "scores": []}), encoding="utf-8")
    assert load_scores() is None


def test_load_missing_file_is_none(corpora):
    assert load_scores() is None


def test_stale_semantics(corpora):
    assert stale() is True  # missing file
    rebuild(now=NOW)
    assert stale(max_age_seconds=3600) is False
    assert stale(max_age_seconds=0) is True


# ─── CLI ───────────────────────────────────────────────────────────────


def test_cli_rebuild_and_show(corpora, capsys):
    _write(corpora["qg"], [_qg_line("dev", "APPROVED")])
    assert cli_main(["rebuild"]) == 0
    assert cli_main(["show"]) == 0
    out = capsys.readouterr().out
    assert "dev: 1/1 approved" in out


def test_cli_show_without_file(corpora, capsys):
    assert cli_main(["show"]) == 1
    assert "run: rebuild" in capsys.readouterr().out


def test_cli_usage(corpora):
    assert cli_main(["bogus"]) == 2


# ─── Stop hook wiring ──────────────────────────────────────────────────


def test_stop_hook_enqueues_rebuild_when_stale(monkeypatch, tmp_path, corpora):
    from core.hooks import stop

    calls = []
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **k: calls.append((a, k)) or None
    )
    monkeypatch.setattr(stop, "repo_path", lambda: str(Path(__file__).parents[2]))
    stop._enqueue_routing_rebuild()
    assert len(calls) == 1
    assert "core.governance.routing_feedback_cli" in calls[0][0][0]


def test_stop_hook_skips_rebuild_when_fresh(monkeypatch, corpora):
    from core.hooks import stop

    rebuild(now=NOW)  # fresh file
    called = []
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: called.append(1))
    stop._enqueue_routing_rebuild()
    assert not called
