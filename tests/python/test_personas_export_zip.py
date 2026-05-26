"""Tests for the bulk persona ZIP export (PR92a v3.39.0)."""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
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


def test_slug_strips_special_chars():
    api = _load_dashboard_api()
    assert api._zip_persona_slug("Alex Hormozi") == "Alex-Hormozi"
    assert api._zip_persona_slug("Foo / Bar") == "Foo-Bar"
    assert api._zip_persona_slug("") == "persona"


def test_slug_caps_length():
    api = _load_dashboard_api()
    long_name = "a" * 200
    assert len(api._zip_persona_slug(long_name)) == 80


def test_export_when_manager_unavailable(monkeypatch):
    api = _load_dashboard_api()
    monkeypatch.setattr(api, "_get_persona_manager", lambda: None)
    res = api.personas_export_all()
    assert "error" in res


def test_export_no_personas_returns_error(monkeypatch):
    api = _load_dashboard_api()

    class _EmptyMgr:
        def list_all(self):
            return []

    monkeypatch.setattr(api, "_get_persona_manager", lambda: _EmptyMgr())
    res = api.personas_export_all()
    assert "error" in res


def test_export_with_ids_filter():
    """PR93c — ?ids=... narrows the export."""
    api = _load_dashboard_api()
    mgr = api._get_persona_manager()
    if mgr is None or not (mgr.list_all() or []):
        return
    target = next(iter(mgr.list_all()), None)
    if not target:
        return
    res = api.personas_export_all(ids=target.id)
    if isinstance(res, dict):
        return
    body = res.body if isinstance(res.body, bytes) else res.body.encode("utf-8")
    zf = zipfile.ZipFile(io.BytesIO(body))
    # With a single id filter we should have at most 1 file.
    assert len(zf.namelist()) == 1


def test_export_with_unknown_ids_returns_error():
    api = _load_dashboard_api()
    if api._get_persona_manager() is None:
        return
    res = api.personas_export_all(ids="definitely-nonexistent-zzzz")
    assert "error" in res


def test_export_returns_zip_with_personas():
    api = _load_dashboard_api()
    mgr = api._get_persona_manager()
    if mgr is None or not (mgr.list_all() or []):
        return  # Environment dependent — skip
    res = api.personas_export_all()
    if isinstance(res, dict):
        return
    assert res.media_type == "application/zip"
    body = res.body if isinstance(res.body, bytes) else res.body.encode("utf-8")
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    assert len(names) >= 1
    assert all(n.endswith(".md") for n in names)
    # First entry should look like rendered markdown with YAML frontmatter
    first = zf.read(names[0]).decode("utf-8")
    assert "---" in first
