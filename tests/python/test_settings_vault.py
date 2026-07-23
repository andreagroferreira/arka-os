"""Tests for the settings vault test endpoint (PR89c v3.29.0)."""

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


def test_returns_payload_shape():
    api = _load_dashboard_api()
    res = api.settings_vault()
    for key in ("configured", "vault_path", "exists", "personas", "agents"):
        assert key in res


def test_personas_subdir_shape():
    api = _load_dashboard_api()
    res = api.settings_vault()
    assert "dir" in res["personas"]
    assert "count" in res["personas"]
    assert isinstance(res["personas"]["count"], int)
    assert res["personas"]["count"] >= 0


def test_agents_subdir_shape():
    api = _load_dashboard_api()
    res = api.settings_vault()
    assert "dir" in res["agents"]
    assert "count" in res["agents"]
    assert isinstance(res["agents"]["count"], int)


def test_unconfigured_vault(monkeypatch):
    """When profile has no vaultPath, exists must be False."""
    from core.profile import ProfileManager

    class _NoVault:
        vaultPath = ""

    monkeypatch.setattr(ProfileManager, "read", lambda self: _NoVault())
    api = _load_dashboard_api()
    res = api.settings_vault()
    assert res["configured"] is False
    assert res["exists"] is False
    assert res["personas"]["count"] == 0
    assert res["agents"]["count"] == 0


def test_configured_but_missing_vault(monkeypatch, tmp_path):
    """When vaultPath points to a non-existent dir, exists is False."""
    from core.profile import ProfileManager

    class _Bogus:
        vaultPath = str(tmp_path / "definitely-not-real")

    monkeypatch.setattr(ProfileManager, "read", lambda self: _Bogus())
    api = _load_dashboard_api()
    res = api.settings_vault()
    assert res["configured"] is True
    assert res["exists"] is False


def test_configured_vault_with_subdirs(monkeypatch, tmp_path):
    """Real vault with Personas and Agents subdirs reports counts."""
    vault = tmp_path / "vault"
    (vault / "Personas").mkdir(parents=True)
    (vault / "Agents").mkdir(parents=True)
    (vault / "Personas" / "a.md").write_text("---\ntype: persona\n---\n", encoding="utf-8")
    (vault / "Personas" / "b.md").write_text("---\ntype: persona\n---\n", encoding="utf-8")
    (vault / "Agents" / "x.md").write_text("---\ntype: agent\n---\n", encoding="utf-8")

    from core.profile import ProfileManager

    class _Real:
        vaultPath = str(vault)

    monkeypatch.setattr(ProfileManager, "read", lambda self: _Real())
    api = _load_dashboard_api()
    res = api.settings_vault()
    assert res["configured"] is True
    assert res["exists"] is True
    assert res["personas"]["count"] == 2
    assert res["agents"]["count"] == 1
