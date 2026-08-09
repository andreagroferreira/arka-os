"""Tests for the QG redo-loop counter (excellence-mandate, PR-D)."""

from __future__ import annotations

import json

import pytest

from core.governance.redo_counter import (
    REDO_CAP,
    current,
    escalation_marker,
    record_rejected,
    reset,
)


@pytest.fixture
def state(tmp_path):
    return tmp_path / "redo-counters.json"


class TestRedoCounter:
    def test_first_two_rejections_loop_back(self, state):
        first = record_rejected("sess-1", path=state)
        second = record_rejected("sess-1", path=state)
        assert (first.count, first.escalate) == (1, False)
        assert (second.count, second.escalate) == (2, False)
        assert f"1/{REDO_CAP}" in first.to_message()

    def test_third_rejection_escalates_to_operator(self, state):
        for _ in range(2):
            record_rejected("sess-1", path=state)
        third = record_rejected("sess-1", path=state)
        assert third.escalate is True
        message = third.to_message()
        assert "[arka:qg:escalate]" in message
        assert "Do not retry silently" in message

    def test_sessions_are_independent(self, state):
        record_rejected("sess-1", path=state)
        assert current("sess-2", path=state).count == 0

    def test_approved_resets_counter(self, state):
        record_rejected("sess-1", path=state)
        record_rejected("sess-1", path=state)
        reset("sess-1", path=state)
        assert current("sess-1", path=state).count == 0
        assert record_rejected("sess-1", path=state).count == 1

    def test_corrupt_state_file_degrades_to_zero(self, state):
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("{corrupt", encoding="utf-8")
        result = record_rejected("sess-1", path=state)
        assert result.count == 1


class TestEscalationMarker:
    """Gate Economy: the cap drops an on-disk ESCALATE marker — the
    actionable half of the escalation, testable before any dispatch."""

    @pytest.fixture
    def home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        return tmp_path

    def _marker(self, home, session):
        return home / ".arkaos" / "quality-gate" / session / "ESCALATE"

    def test_marker_dropped_when_cap_crossed(self, home, state):
        for _ in range(REDO_CAP):
            record_rejected("sess-esc", path=state)
        assert not self._marker(home, "sess-esc").exists()
        third = record_rejected("sess-esc", path=state)
        assert third.escalate is True
        marker = self._marker(home, "sess-esc")
        assert marker.exists()
        payload = json.loads(marker.read_text(encoding="utf-8"))
        assert payload["count"] == REDO_CAP + 1
        assert "[arka:qg:escalate]" in payload["message"]

    def test_reset_clears_marker(self, home, state):
        for _ in range(REDO_CAP + 1):
            record_rejected("sess-esc2", path=state)
        assert self._marker(home, "sess-esc2").exists()
        reset("sess-esc2", path=state)
        assert not self._marker(home, "sess-esc2").exists()
        assert current("sess-esc2", path=state).count == 0

    def test_hostile_session_id_writes_no_marker(self, home, state):
        third = None
        for _ in range(REDO_CAP + 1):
            third = record_rejected("../evil", path=state)
        assert third is not None and third.escalate is True
        assert escalation_marker("../evil") is None
        assert not (home / ".arkaos" / "quality-gate" / ".." ).exists()
