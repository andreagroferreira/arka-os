"""core.decisions.backoff — shared circuit breaker, never raises."""

from __future__ import annotations

import pytest

from core.decisions import backoff


@pytest.fixture(autouse=True)
def _root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(tmp_path / "c"))
    return tmp_path / "c"


def test_closed_by_default():
    assert backoff.blocked() is None


def test_trip_then_expire():
    backoff.trip("http-529", 120, now=1000.0)
    assert backoff.blocked(now=1100.0) == "http-529"
    assert backoff.blocked(now=1120.0) is None


def test_longer_deadline_is_kept():
    backoff.trip("http-401", 3600, now=0.0)
    backoff.trip("http-429", 60, now=0.0)
    assert backoff.blocked(now=100.0) == "http-401"


def test_corrupt_state_is_closed(_root):
    _root.mkdir(parents=True)
    (_root / "backoff.json").write_text("{nope", encoding="utf-8")
    assert backoff.blocked() is None
    (_root / "backoff.json").write_text('{"until": "later"}', encoding="utf-8")
    assert backoff.blocked() is None
    (_root / "backoff.json").write_text("[1]", encoding="utf-8")
    assert backoff.blocked() is None


def test_unwritable_root_never_raises(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(blocker / "sub"))
    backoff.trip("http-529", 10)
    assert backoff.blocked() is None


def test_planted_far_future_deadline_neither_blocks_nor_sticks(_root):
    # Kills: dropping the MAX_BLOCK_S clamp in blocked() or in trip().
    _root.mkdir(parents=True)
    (_root / "backoff.json").write_text('{"reason": "x", "until": 1e12}', encoding="utf-8")
    assert backoff.blocked(now=1000.0) is None
    backoff.trip("http-529", 120, now=1000.0)
    assert backoff.blocked(now=1100.0) == "http-529"


def test_trip_is_capped_at_an_hour():
    backoff.trip("http-429", 10 * 3600, now=0.0)
    assert backoff.blocked(now=3599.0) == "http-429"
    assert backoff.blocked(now=3601.0) is None


def test_state_file_is_private(_root):
    import stat

    backoff.trip("http-401", 60)
    assert stat.S_IMODE((_root / "backoff.json").stat().st_mode) == 0o600


def test_three_transport_failures_trip_and_success_resets():
    # Kills: dropping the trip in record_failure, or record_success's reset.
    assert backoff.record_failure("timeout", now=0.0) == 1
    assert backoff.record_failure("timeout", now=1.0) == 2
    backoff.record_success()
    assert backoff.record_failure("timeout", now=2.0) == 1
    assert backoff.record_failure("network", now=3.0) == 2
    assert backoff.blocked(now=3.5) is None
    assert backoff.record_failure("network", now=4.0) == 3
    assert backoff.blocked(now=5.0) == "network"
    assert backoff.blocked(now=4.0 + backoff.FAILURE_BACKOFF_S + 1) is None


def test_stale_failures_start_over():
    backoff.record_failure("timeout", now=0.0)
    backoff.record_failure("timeout", now=1.0)
    assert backoff.record_failure("timeout", now=1.0 + backoff.FAILURE_WINDOW_S + 1) == 1


def test_corrupt_failure_count_starts_over(_root):
    _root.mkdir(parents=True)
    (_root / "failures.json").write_text("{nope", encoding="utf-8")
    assert backoff.record_failure("timeout", now=0.0) == 1


def test_created_directory_chain_is_private(tmp_path, monkeypatch):
    # Kills: ensure_private_dir → mkdir(parents=True) (parents 0755 by umask).
    import os
    import stat

    root = tmp_path / "a" / "b" / "c"
    monkeypatch.setenv("ARKA_DECISIONS_CACHE_DIR", str(root))
    old = os.umask(0o022)
    try:
        backoff.trip("http-529", 10)
    finally:
        os.umask(old)
    for d in (tmp_path / "a", tmp_path / "a" / "b", root):
        assert stat.S_IMODE(d.stat().st_mode) == 0o700, d
