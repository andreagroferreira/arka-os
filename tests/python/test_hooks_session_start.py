"""Tests for core.hooks.session_start memory recap (F1-A3)."""

from __future__ import annotations

import pytest

from core.hooks.session_start import build_recap, main
from core.memory.semantic_store import SessionMemoryStore, TurnRecord


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("ARKA_SESSION_MEMORY_DB", str(tmp_path / "sm.db"))
    return tmp_path


def _seed(project: str, n: int = 3) -> None:
    store = SessionMemoryStore()
    for i in range(n):
        store.save(TurnRecord(
            id=f"t{i}", ts=f"2026-07-0{i + 1}T00:00:00+00:00",
            session_id=f"s{i}", project_name=project,
            summary=f"turn {i}: shipped feature {i}",
            importance=0.5 + i * 0.1,
            embedding_backend="fastembed" if i else "none",
        ))


def test_empty_store_is_silent():
    assert build_recap("/repo/proj") == ""


def test_recap_ranks_by_importance_and_labels_honestly(tmp_path):
    _seed("proj")
    recap = build_recap("/repo/proj")
    assert recap.startswith("[SESSION-MEMORY] Prior turns (importance+recency")
    assert "not semantic" in recap  # no prompt exists yet — never faked
    lines = recap.splitlines()
    assert "turn 2" in lines[1]  # highest importance first
    assert "store: 3 turns" in lines[-1]
    assert "backends=fastembed,none" in lines[-1]


def test_recap_scopes_to_project(tmp_path):
    _seed("other-project")
    assert build_recap("/repo/proj") == ""


def test_budget_exceeded_returns_empty(tmp_path, monkeypatch):
    _seed("proj")
    assert build_recap("/repo/proj", budget_ms=-1) == ""


def test_main_prints_recap(tmp_path, capsys):
    _seed("proj")
    assert main(["/repo/proj"]) == 0
    out = capsys.readouterr().out
    assert "[SESSION-MEMORY]" in out


def test_main_silent_without_store(capsys):
    assert main(["/repo/none"]) == 0
    assert capsys.readouterr().out == ""
