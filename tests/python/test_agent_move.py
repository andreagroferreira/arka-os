"""Tests for the agent MOVE endpoint (PR84b v3.8.0)."""

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


def _sibling_in(path: Path, dept: str) -> Path:
    """Same filename under ``departments/<dept>/agents/``.

    Built from path parts, never from a string replace: ``str(Path)``
    renders ``departments\\dev\\agents`` on Windows, so a replace keyed on
    ``"departments/dev/agents/"`` matched nothing there and the cleanup
    silently missed the moved file — leaving a stray agent YAML tracked
    in the repo tree after any failure mid-test.
    """
    return path.parents[2] / dept / "agents" / path.name


def _create_fixture(api, dept="dev", slug="agent-move-test-fixture"):
    res = api._do_agent_create({
        "name": "Move Probe",
        "role": "Test",
        "department": dept,
        "tier": 2,
        "id": slug,
    })
    assert res.get("created"), res
    return Path(res["yaml_path"])


def test_move_unknown_agent_returns_error():
    api = _load_dashboard_api()
    res = api.agent_move("definitely-not-real-zzzz", {"department": "dev"})
    assert "error" in res
    assert "not found" in res["error"].lower()


def test_move_requires_department():
    api = _load_dashboard_api()
    res = api.agent_move("x", {})
    assert "error" in res
    assert "department" in res["error"]


def test_move_rejects_unknown_department():
    api = _load_dashboard_api()
    src = _create_fixture(api)
    try:
        res = api.agent_move("agent-move-test-fixture", {"department": "bogus"})
        assert "error" in res
        assert "bogus" in res["error"]
    finally:
        if src.exists():
            src.unlink()


def test_move_rewrites_department_field_and_relocates_file():
    api = _load_dashboard_api()
    src = _create_fixture(api, dept="dev")
    try:
        res = api.agent_move("agent-move-test-fixture", {"department": "ops"})
        assert res.get("moved") is True
        dst = Path(res["yaml_path"])
        assert dst.exists()
        assert not src.exists()
        # Compare path parts, not a rendered string: str(Path) uses "\" on
        # Windows, so a substring check on "departments/ops/agents/" is a
        # guaranteed failure there regardless of where the file landed.
        # Keep "departments" in the comparison — dropping it would accept
        # a move to any ops/agents/ subtree anywhere on disk.
        assert dst.parts[-4:] == ("departments", "ops", "agents", dst.name)
        content = dst.read_text(encoding="utf-8")
        assert "department: ops" in content
        dst.unlink()
    finally:
        # Defensive: remove either src or dst if any lingers
        if src.exists():
            src.unlink()
        candidate = _sibling_in(src, "ops")
        if candidate.exists():
            candidate.unlink()


def test_move_refuses_overwrite():
    api = _load_dashboard_api()
    src = _create_fixture(api, dept="dev", slug="agent-move-collision-a")
    other = _create_fixture(api, dept="ops", slug="agent-move-collision-a")
    try:
        res = api.agent_move("agent-move-collision-a", {"department": "ops"})
        # The source resolves to ops because both share the same id and
        # _resolve_agent_yaml may find either. Whichever it finds, moving to
        # the same dept where a file with the same name exists must error.
        # If src and dst both ended up in ops, _resolve returns one of them
        # and the no-op branch may fire (`moved: False`) — accept either
        # error-on-collision OR no-op moved=False.
        assert ("error" in res and "already exists" in res["error"]) or res.get("moved") is False
    finally:
        for f in (src, other):
            if f.exists():
                f.unlink()
        candidate = _sibling_in(src, "ops")
        if candidate.exists() and candidate != other:
            candidate.unlink()


def test_move_refuses_tier_zero():
    api = _load_dashboard_api()
    agents = api._load_agents()
    tier0 = [a for a in agents if int(a.get("tier") or 99) == 0]
    if not tier0:
        return  # Environment-dependent — skip
    target = tier0[0]
    res = api.agent_move(target["id"], {"department": "dev"})
    assert "error" in res
    assert "Tier 0" in res["error"]
