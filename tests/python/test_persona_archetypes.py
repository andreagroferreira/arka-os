"""Tests for the persona archetypes endpoint (PR93b v3.44.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_dashboard_api():
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "dashboard-api.py"
    spec = importlib.util.spec_from_file_location("dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_endpoint_returns_archetypes():
    api = _load_dashboard_api()
    res = api.personas_archetypes()
    assert "archetypes" in res
    assert "total" in res
    assert res["total"] == len(res["archetypes"])
    assert len(res["archetypes"]) >= 6


def test_archetype_shape():
    api = _load_dashboard_api()
    res = api.personas_archetypes()
    for a in res["archetypes"]:
        for key in ("id", "name", "title", "tagline", "mbti", "disc",
                    "enneagram", "big_five", "description"):
            assert key in a, f"missing {key} in {a.get('id')}"


def test_archetype_ids_unique():
    api = _load_dashboard_api()
    res = api.personas_archetypes()
    ids = [a["id"] for a in res["archetypes"]]
    assert len(ids) == len(set(ids))


def test_archetype_disc_primary_secondary_differ():
    api = _load_dashboard_api()
    res = api.personas_archetypes()
    for a in res["archetypes"]:
        d = a.get("disc") or {}
        assert d.get("primary") != d.get("secondary"), f"DISC clash in {a['id']}"


def test_archetype_big_five_in_range():
    api = _load_dashboard_api()
    res = api.personas_archetypes()
    for a in res["archetypes"]:
        bf = a.get("big_five") or {}
        for axis, value in bf.items():
            assert 0 <= int(value) <= 100, f"{a['id']}.{axis} out of range"


def test_archetype_descriptions_have_length():
    api = _load_dashboard_api()
    res = api.personas_archetypes()
    for a in res["archetypes"]:
        assert len(a["description"]) >= 50


def test_get_archetype_helper():
    from core.personas.archetypes import get_archetype
    assert get_archetype("the-coach") is not None
    assert get_archetype("definitely-not-a-real-id") is None
