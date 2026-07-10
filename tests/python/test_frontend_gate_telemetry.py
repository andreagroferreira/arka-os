"""Tests for the frontend-gate telemetry summarizer (PR-D2 flip evidence)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from core.workflow.frontend_gate_telemetry import summarise


def _entry(reason, marker_kind="none", mode="warn", ui_scope="suffix",
           ts=None):
    return {
        "ts": (ts or datetime.now(timezone.utc)).isoformat(),
        "session_id": "sess",
        "tool": "Edit",
        "allow": True,
        "reason": reason,
        "mode": mode,
        "target_file": "Hero.vue",
        "marker_found": None,
        "marker_kind": marker_kind,
        "ui_scope": ui_scope,
    }


def _write(path, entries, extra_lines=()):
    lines = [json.dumps(e) for e in entries]
    lines.extend(extra_lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestSummarise:
    def test_missing_file_yields_empty_summary(self, tmp_path):
        summary = summarise("all", path=tmp_path / "absent.jsonl")
        assert summary.total_events == 0
        assert summary.would_deny_rate == 0.0

    def test_invalid_period_raises(self, tmp_path):
        with pytest.raises(ValueError):
            summarise("yesterday", path=tmp_path / "fg.jsonl")

    def test_counts_and_would_deny_rate(self, tmp_path):
        path = tmp_path / "fg.jsonl"
        _write(path, [
            _entry("design-evidence", marker_kind="structured"),
            _entry("no-design-marker"),
            _entry("legacy-marker", marker_kind="legacy"),
            _entry("no-design-marker", ui_scope="heuristic"),
            _entry("not-ui-scope"),  # noise — excluded from gated totals
        ])
        summary = summarise("all", path=path)
        assert summary.total_events == 4
        # heuristic-scope misses never count toward the flip evidence
        assert summary.would_deny_events == 2
        assert summary.would_deny_rate == pytest.approx(0.5)
        assert ("no-design-marker", 2) in summary.by_reason
        assert ("structured", 1) in summary.by_marker_kind
        assert ("heuristic", 1) in summary.by_ui_scope

    def test_corrupt_lines_are_tolerated_and_counted(self, tmp_path):
        path = tmp_path / "fg.jsonl"
        _write(path, [_entry("no-design-marker")], extra_lines=["{broken"])
        summary = summarise("all", path=path)
        assert summary.total_events == 1
        assert summary.corrupt_line_count == 1

    def test_period_cutoff_filters_old_entries(self, tmp_path):
        path = tmp_path / "fg.jsonl"
        old = datetime.now(timezone.utc) - timedelta(days=40)
        _write(path, [
            _entry("no-design-marker", ts=old),
            _entry("no-design-marker"),
        ])
        assert summarise("month", path=path).total_events == 1
        assert summarise("all", path=path).total_events == 2
