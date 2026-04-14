"""Tests for ContextCompactor — rule-based subagent context summary."""

import pytest

from core.runtime.context_compactor import ContextCompactor, Turn


class TestContextCompactor:
    def test_empty_turns_returns_empty(self):
        compactor = ContextCompactor()
        assert compactor.build([]) == ""

    def test_single_user_turn_included(self):
        compactor = ContextCompactor()
        turns = [Turn(role="user", content="Build the auth module")]
        result = compactor.build(turns)
        assert "auth module" in result

    def test_includes_files_touched(self):
        compactor = ContextCompactor()
        turns = [
            Turn(role="user", content="Refactor service"),
            Turn(role="assistant", content="Done", files_touched=["core/auth.py", "core/db.py"]),
        ]
        result = compactor.build(turns)
        assert "core/auth.py" in result and "core/db.py" in result

    def test_respects_token_budget(self):
        compactor = ContextCompactor()
        turns = [Turn(role="user", content="word " * 5000)]
        result = compactor.build(turns, max_tokens=100)
        assert len(result.split()) <= 120  # small overhead for headers

    def test_keeps_recent_turns_priority(self):
        compactor = ContextCompactor()
        turns = [
            Turn(role="user", content="OLD_DECISION"),
            Turn(role="user", content="MIDDLE_DECISION"),
            Turn(role="user", content="RECENT_DECISION"),
        ]
        result = compactor.build(turns, max_tokens=20)
        assert "RECENT_DECISION" in result
