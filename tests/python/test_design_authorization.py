"""design_authorization — persist-on-observe state for the frontend gate."""

from __future__ import annotations

import time

import pytest

from core.workflow import design_authorization as da

MARKER = "[arka:design] benchmark=Vercel skills=frontend-design tokens=x.css"


@pytest.fixture(autouse=True)
def _isolated_auth_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_DESIGN_AUTH_DIR", str(tmp_path / "design-auth"))


def test_confirm_then_is_confirmed() -> None:
    da.confirm("sess-1", MARKER)
    assert da.is_confirmed("sess-1")
    assert da.confirmed_marker("sess-1") == MARKER


def test_unconfirmed_session_is_not_confirmed() -> None:
    assert not da.is_confirmed("sess-never")
    assert da.confirmed_marker("sess-never") is None


def test_sessions_are_isolated() -> None:
    da.confirm("sess-a", MARKER)
    assert da.is_confirmed("sess-a")
    assert not da.is_confirmed("sess-b")


def test_ttl_expiry(monkeypatch) -> None:
    da.confirm("sess-ttl", MARKER)
    real_time = time.time()
    monkeypatch.setattr(time, "time", lambda: real_time + da.DEFAULT_TTL_SECONDS + 1)
    assert not da.is_confirmed("sess-ttl")


def test_clear_removes_state() -> None:
    da.confirm("sess-clear", MARKER)
    da.clear("sess-clear")
    assert not da.is_confirmed("sess-clear")


def test_unsafe_session_id_is_noop() -> None:
    da.confirm("../../etc/passwd", MARKER)
    assert not da.is_confirmed("../../etc/passwd")


def test_empty_marker_never_confirms() -> None:
    da.confirm("sess-empty", "")
    assert da.confirmed_marker("sess-empty") is None
