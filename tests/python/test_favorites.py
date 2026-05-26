"""Tests for the favourites store (PR86a v3.15.0)."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def fav(tmp_path, monkeypatch):
    """Isolated favourites dir per test."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    import core.favorites as f
    importlib.reload(f)
    return f


def test_list_empty_initially(fav):
    state = fav.list_favorites()
    assert state == {"agents": [], "personas": []}


def test_toggle_adds_then_removes(fav):
    r1 = fav.toggle("agents", "a1")
    assert r1["favorited"] is True
    state = fav.list_favorites()
    assert state["agents"] == ["a1"]
    r2 = fav.toggle("agents", "a1")
    assert r2["favorited"] is False
    state = fav.list_favorites()
    assert state["agents"] == []


def test_separate_buckets(fav):
    fav.toggle("agents", "a1")
    fav.toggle("personas", "p1")
    state = fav.list_favorites()
    assert state == {"agents": ["a1"], "personas": ["p1"]}


def test_unknown_kind_returns_error(fav):
    r = fav.toggle("bogus", "x")
    assert "error" in r


def test_empty_id_returns_error(fav):
    r = fav.toggle("agents", "")
    assert "error" in r


def test_is_favorite_reflects_state(fav):
    assert fav.is_favorite("agents", "a1") is False
    fav.toggle("agents", "a1")
    assert fav.is_favorite("agents", "a1") is True


def test_set_favorite_idempotent_add(fav):
    fav.set_favorite("agents", "a1", True)
    fav.set_favorite("agents", "a1", True)
    assert fav.list_favorites()["agents"] == ["a1"]


def test_set_favorite_idempotent_remove(fav):
    fav.set_favorite("agents", "a1", True)
    fav.set_favorite("agents", "a1", False)
    fav.set_favorite("agents", "a1", False)
    assert fav.list_favorites()["agents"] == []


def test_survives_reload(fav):
    fav.toggle("agents", "a1")
    fav.toggle("personas", "p1")
    # Reload module — should re-read the same file
    importlib.reload(fav)
    state = fav.list_favorites()
    assert "a1" in state["agents"]
    assert "p1" in state["personas"]


def test_corrupt_json_falls_back_to_empty(fav):
    fav._store_path().parent.mkdir(parents=True, exist_ok=True)
    fav._store_path().write_text("not json {{{", encoding="utf-8")
    state = fav.list_favorites()
    assert state == {"agents": [], "personas": []}
