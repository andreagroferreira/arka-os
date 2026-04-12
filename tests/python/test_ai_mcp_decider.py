"""Tests for core.sync.ai_mcp_decider — AI fallback for ambiguous MCPs."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.sync.ai_mcp_decider import decide_ambiguous, AIUnavailable


@pytest.fixture
def cache_path(tmp_path: Path) -> Path:
    return tmp_path / "cache.json"


def test_empty_ambiguous_returns_empty(cache_path: Path) -> None:
    result = decide_ambiguous(
        ambiguous=[], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=None,
    )
    assert result == {}


def test_heuristic_fallback_defers_all_when_no_ai(cache_path: Path) -> None:
    result = decide_ambiguous(
        ambiguous=["firecrawl", "clickup"],
        stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=None,
    )
    assert result == {"firecrawl": "deferred", "clickup": "deferred"}


def test_ai_call_is_cached(cache_path: Path) -> None:
    call_count = {"n": 0}

    def fake_ai(name: str, stack: list[str], ecosystem: str | None) -> str:
        call_count["n"] += 1
        return "active"

    r1 = decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    r2 = decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    assert r1 == {"firecrawl": "active"}
    assert r2 == {"firecrawl": "active"}
    assert call_count["n"] == 1, "cache should prevent duplicate AI calls"


def test_ai_unavailable_falls_back_to_heuristic(cache_path: Path) -> None:
    def failing_ai(name: str, stack: list[str], ecosystem: str | None) -> str:
        raise AIUnavailable("rate limited")

    result = decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=failing_ai,
    )
    assert result == {"firecrawl": "deferred"}


def test_cache_key_differs_per_stack(cache_path: Path) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_ai(name: str, stack: list[str], ecosystem: str | None) -> str:
        calls.append((name, tuple(stack)))
        return "active"

    decide_ambiguous(
        ambiguous=["firecrawl"], stack=["laravel"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    decide_ambiguous(
        ambiguous=["firecrawl"], stack=["nuxt"], ecosystem=None,
        cache_path=cache_path, call_ai=fake_ai,
    )
    assert len(calls) == 2
