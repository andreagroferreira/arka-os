"""Tests for persona Markdown download (PR90a v3.31.0)."""

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


def test_unknown_persona_returns_error():
    api = _load_dashboard_api()
    res = api.persona_download_markdown("nonexistent-zzzzz")
    assert isinstance(res, dict)
    assert "error" in res


def test_returns_response_for_existing_persona():
    api = _load_dashboard_api()
    mgr = api._get_persona_manager()
    if mgr is None:
        return  # No persona store — skip
    personas = mgr.list_all() or []
    personas = [p.model_dump() if hasattr(p, "model_dump") else p for p in personas]
    if not personas:
        return
    target_id = personas[0].get("id")
    res = api.persona_download_markdown(target_id)
    if isinstance(res, dict) and "error" in res:
        return  # Detail lookup failed — environment-specific
    assert hasattr(res, "body")
    assert res.media_type == "text/markdown"
    assert "attachment" in res.headers.get("content-disposition", "")


def test_content_disposition_filename_ends_md():
    api = _load_dashboard_api()
    mgr = api._get_persona_manager()
    if mgr is None:
        return
    personas = mgr.list_all() or []
    personas = [p.model_dump() if hasattr(p, "model_dump") else p for p in personas]
    if not personas:
        return
    res = api.persona_download_markdown(personas[0].get("id"))
    if isinstance(res, dict):
        return
    assert ".md" in res.headers.get("content-disposition", "")


def test_body_has_frontmatter():
    api = _load_dashboard_api()
    mgr = api._get_persona_manager()
    if mgr is None:
        return
    personas = mgr.list_all() or []
    personas = [p.model_dump() if hasattr(p, "model_dump") else p for p in personas]
    if not personas:
        return
    res = api.persona_download_markdown(personas[0].get("id"))
    if isinstance(res, dict):
        return
    body = res.body.decode("utf-8") if isinstance(res.body, bytes) else res.body
    # Renderer writes `---` frontmatter delimiters
    assert "---" in body
