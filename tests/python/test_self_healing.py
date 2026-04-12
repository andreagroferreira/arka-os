"""Tests for core.sync.self_healing — retry wrapper."""

from __future__ import annotations

import pytest

from core.sync.self_healing import RetryExhausted, run_with_retry


def test_success_on_first_try_returns_result() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        return "ok"

    result = run_with_retry(fn, max_retries=3)
    assert result == "ok"
    assert calls["n"] == 1


def test_retries_until_success() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        return "ok"

    result = run_with_retry(fn, max_retries=3, base_delay=0.0)
    assert result == "ok"
    assert calls["n"] == 3


def test_raises_retry_exhausted_after_max() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise ValueError("always fails")

    with pytest.raises(RetryExhausted) as exc_info:
        run_with_retry(fn, max_retries=2, base_delay=0.0)

    assert calls["n"] == 3  # initial + 2 retries
    assert "always fails" in str(exc_info.value)


def test_zero_retries_means_one_attempt() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        raise ValueError("boom")

    with pytest.raises(RetryExhausted):
        run_with_retry(fn, max_retries=0, base_delay=0.0)

    assert calls["n"] == 1
