"""Tests for the agent-create helpers in dashboard-api.py (PR82 v3.0.0).

Verifies the YAML payload composition and slug rules. The FastAPI
endpoint itself is exercised by the dashboard E2E suite; this file
focuses on the pure helpers so failures point at a specific function.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_dashboard_api():
    """Load scripts/dashboard-api.py as a module despite the hyphenated name."""
    repo = Path(__file__).resolve().parents[2]
    path = repo / "scripts" / "dashboard-api.py"
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    spec = importlib.util.spec_from_file_location("dashboard_api", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_slugify_lowercases_and_replaces_spaces():
    api = _load_dashboard_api()
    assert api._agent_slugify("Market Analyst Lucas") == "market-analyst-lucas"


def test_slugify_collapses_separators():
    api = _load_dashboard_api()
    assert api._agent_slugify("Foo___Bar---Baz") == "foo-bar-baz"


def test_slugify_strips_punctuation():
    api = _load_dashboard_api()
    assert api._agent_slugify("Hi, World!") == "hi-world"


def test_slugify_falls_back_to_default_for_empty():
    api = _load_dashboard_api()
    assert api._agent_slugify("") == "agent"
    assert api._agent_slugify("!!!") == "agent"


def test_build_agent_yaml_applies_defaults():
    api = _load_dashboard_api()
    payload = api._build_agent_yaml(
        slug="test-agent",
        name="Test",
        role="Tester",
        department="dev",
        tier=2,
        body={},
    )
    assert payload["id"] == "test-agent"
    assert payload["model"] == "sonnet"
    assert payload["behavioral_dna"]["mbti"]["type"] == "INTJ"
    assert payload["expertise"]["depth"] == "advanced"
    assert payload["communication"]["language"] == "en"


def test_build_agent_yaml_tier_zero_uses_opus():
    api = _load_dashboard_api()
    payload = api._build_agent_yaml(
        slug="cto", name="CTO", role="Chief", department="dev", tier=0, body={},
    )
    assert payload["model"] == "opus"


def test_build_agent_yaml_respects_disc():
    api = _load_dashboard_api()
    body = {"behavioral_dna": {"disc": {"primary": "d", "secondary": "c"}}}
    payload = api._build_agent_yaml(
        slug="x", name="X", role="Y", department="dev", tier=2, body=body,
    )
    assert payload["behavioral_dna"]["disc"]["primary"] == "D"
    assert payload["behavioral_dna"]["disc"]["secondary"] == "C"


def test_build_agent_yaml_normalises_mbti_from_string():
    api = _load_dashboard_api()
    body = {"behavioral_dna": {"mbti": "entj"}}
    payload = api._build_agent_yaml(
        slug="x", name="X", role="Y", department="dev", tier=2, body=body,
    )
    assert payload["behavioral_dna"]["mbti"]["type"] == "ENTJ"


def test_build_agent_yaml_normalises_mbti_from_dict():
    api = _load_dashboard_api()
    body = {"behavioral_dna": {"mbti": {"type": "infp"}}}
    payload = api._build_agent_yaml(
        slug="x", name="X", role="Y", department="dev", tier=2, body=body,
    )
    assert payload["behavioral_dna"]["mbti"]["type"] == "INFP"


def test_build_agent_yaml_lists_passed_through():
    api = _load_dashboard_api()
    body = {
        "expertise": {"domains": ["A", "B"], "frameworks": ["F"]},
        "mental_models": {"primary": ["MM"]},
        "linked_personas": ["p1", "p2"],
    }
    payload = api._build_agent_yaml(
        slug="x", name="X", role="Y", department="dev", tier=2, body=body,
    )
    assert payload["expertise"]["domains"] == ["A", "B"]
    assert payload["expertise"]["frameworks"] == ["F"]
    assert payload["mental_models"]["primary"] == ["MM"]
    assert payload["linked_personas"] == ["p1", "p2"]


def test_create_rejects_missing_name():
    api = _load_dashboard_api()
    res = api._do_agent_create({"role": "X", "department": "dev"})
    assert "error" in res
    assert "required" in res["error"]


def test_create_rejects_missing_department():
    api = _load_dashboard_api()
    res = api._do_agent_create({"name": "X", "role": "Y"})
    assert "error" in res


def test_create_rejects_unknown_department():
    api = _load_dashboard_api()
    res = api._do_agent_create({"name": "X", "role": "Y", "department": "bogus"})
    assert "error" in res
    assert "bogus" in res["error"]


def test_create_rejects_invalid_tier():
    api = _load_dashboard_api()
    res = api._do_agent_create(
        {"name": "X", "role": "Y", "department": "dev", "tier": "not-a-number"},
    )
    assert "error" in res


def test_create_writes_yaml_file(tmp_path, monkeypatch):
    """Full create + cleanup. Writes into the real departments/dev dir
    because the helper resolves ARKAOS_ROOT at module-load time."""
    api = _load_dashboard_api()
    res = api._do_agent_create({
        "name": "Pytest Probe",
        "role": "Test Agent",
        "department": "dev",
        "tier": 2,
        "expertise": {"domains": ["pytest"], "frameworks": ["unittest"]},
    })
    assert res.get("created") is True
    yaml_path = Path(res["yaml_path"])
    try:
        assert yaml_path.exists()
        content = yaml_path.read_text(encoding="utf-8")
        assert "Pytest Probe" in content
        assert "department: dev" in content
        assert "model: sonnet" in content
    finally:
        if yaml_path.exists():
            yaml_path.unlink()


def test_create_refuses_to_overwrite_existing(tmp_path):
    """Use an explicit id that already exists in departments/dev/."""
    api = _load_dashboard_api()
    # First create
    res1 = api._do_agent_create({
        "name": "Probe Two",
        "role": "Tester",
        "department": "dev",
        "tier": 2,
        "id": "agent-create-collision-probe",
    })
    assert res1.get("created") is True
    yaml_path = Path(res1["yaml_path"])
    try:
        # Second create with same id must fail
        res2 = api._do_agent_create({
            "name": "Probe Two",
            "role": "Tester",
            "department": "dev",
            "tier": 2,
            "id": "agent-create-collision-probe",
        })
        assert "error" in res2
        assert "already exists" in res2["error"]
    finally:
        if yaml_path.exists():
            yaml_path.unlink()
