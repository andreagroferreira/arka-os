"""Tests for persistent flow authorization (enforcer resilience fix)."""

from __future__ import annotations

import pytest

from core.workflow import flow_authorization as fa


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_FLOW_AUTH_DIR", str(tmp_path / "auth"))
    yield


SID = "sess-abc"


class TestConfirmed:
    def test_confirm_then_is_confirmed(self):
        assert fa.is_confirmed(SID) is False
        fa.confirm(SID, "routing")
        assert fa.is_confirmed(SID) is True

    def test_confirmed_record_carries_type(self):
        fa.confirm(SID, "gate")
        record = fa.confirmed_record(SID)
        assert record is not None
        assert record["marker_type"] == "gate"

    def test_confirmed_expires_after_ttl(self):
        fa.confirm(SID, "routing")
        # A zero TTL makes any record instantly stale.
        assert fa.is_confirmed(SID, ttl_seconds=0) is False

    def test_confirm_resets_grace_count(self):
        fa.register_grace(SID)
        fa.register_grace(SID)
        assert fa.grace_count(SID) == 2
        fa.confirm(SID, "routing")
        assert fa.grace_count(SID) == 0

    def test_unsafe_session_id_is_ignored(self):
        fa.confirm("../etc/passwd", "routing")
        assert fa.is_confirmed("../etc/passwd") is False


class TestTurnGrace:
    def test_grace_absent_until_granted(self):
        assert fa.has_turn_grace(SID) is False

    def test_grant_and_read_turn_grace(self):
        fa.grant_turn_grace(SID)
        assert fa.has_turn_grace(SID) is True

    def test_reset_turn_clears_grace(self):
        fa.grant_turn_grace(SID)
        fa.reset_turn(SID)
        assert fa.has_turn_grace(SID) is False

    def test_reset_turn_keeps_confirmed_auth(self):
        fa.confirm(SID, "routing")
        fa.grant_turn_grace(SID)
        fa.reset_turn(SID)
        assert fa.has_turn_grace(SID) is False
        assert fa.is_confirmed(SID) is True


class TestGraceEscalation:
    def test_grace_count_increments(self):
        assert fa.grace_count(SID) == 0
        fa.register_grace(SID)
        fa.register_grace(SID)
        assert fa.grace_count(SID) == 2

    def test_should_escalate_after_cap(self):
        for _ in range(fa.GRACE_CAP):
            assert fa.register_grace(SID).escalate is False
        # One past the cap escalates to a hard block.
        assert fa.register_grace(SID).escalate is True

    def test_normal_routing_never_escalates(self):
        # A session that confirms by turn 2 resets before hitting the cap.
        fa.register_grace(SID)          # turn 1 grace
        fa.confirm(SID, "routing")      # turn 2 marker observed
        assert fa.grace_count(SID) == 0
        assert fa.register_grace(SID).escalate is False
