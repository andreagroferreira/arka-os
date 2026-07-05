"""Tests for the QG redo-loop counter (excellence-mandate, PR-D)."""

from __future__ import annotations

import pytest

from core.governance.redo_counter import (
    REDO_CAP,
    current,
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
        state.write_text("{corrupt")
        result = record_rejected("sess-1", path=state)
        assert result.count == 1
