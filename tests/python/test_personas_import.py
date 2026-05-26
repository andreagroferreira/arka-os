"""Tests for the persona Markdown import endpoint (PR87b v3.20.0)."""

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


_VALID_MD = """---
type: persona
name: Import Test
title: Tester
mbti: INTJ
disc:
  primary: D
  secondary: C
enneagram:
  type: 5
  wing: 4
big_five:
  openness: 80
  conscientiousness: 70
  extraversion: 50
  agreeableness: 60
  neuroticism: 30
mental_models:
  - First Principles
expertise_domains:
  - testing
frameworks:
  - pytest
---

# Body content here.
"""


def test_empty_body_returns_empty_results():
    api = _load_dashboard_api()
    res = api.personas_import({"files": []})
    assert res["imported"] == 0
    assert res["failed"] == 0
    assert res["results"] == []


def test_non_list_files_returns_error():
    api = _load_dashboard_api()
    res = api.personas_import({"files": "not a list"})
    assert "error" in res


def test_rejects_files_without_frontmatter():
    api = _load_dashboard_api()
    res = api.personas_import({"files": [{"name": "bad.md", "content": "no frontmatter here"}]})
    assert res["imported"] == 0
    assert res["failed"] == 1
    assert res["results"][0]["status"] == "failed"
    assert "frontmatter" in res["results"][0]["error"]


def test_rejects_files_with_wrong_type():
    api = _load_dashboard_api()
    body = _VALID_MD.replace("type: persona", "type: agent")
    res = api.personas_import({"files": [{"name": "x.md", "content": body}]})
    assert res["failed"] == 1


def test_rejects_empty_content():
    api = _load_dashboard_api()
    res = api.personas_import({"files": [{"name": "empty.md", "content": ""}]})
    assert res["failed"] == 1
    assert "empty" in res["results"][0]["error"]


def test_rejects_non_object_entry():
    api = _load_dashboard_api()
    res = api.personas_import({"files": ["not an object"]})
    assert res["failed"] == 1


def test_imports_valid_markdown():
    api = _load_dashboard_api()
    # The persona manager must be available — if not, skip
    if api._get_persona_manager() is None:
        return
    res = api.personas_import({"files": [{"name": "Import Test.md", "content": _VALID_MD}]})
    assert res["imported"] == 1
    assert res["failed"] == 0
    new_id = res["results"][0]["id"]
    assert new_id
    # Cleanup
    mgr = api._get_persona_manager()
    try:
        mgr.delete(new_id)
    except Exception:
        pass


def test_mixed_batch_partial_success():
    api = _load_dashboard_api()
    if api._get_persona_manager() is None:
        return
    res = api.personas_import({
        "files": [
            {"name": "good.md", "content": _VALID_MD},
            {"name": "bad.md", "content": "no frontmatter"},
        ],
    })
    assert res["imported"] == 1
    assert res["failed"] == 1
    # Cleanup
    new_id = next(
        (r["id"] for r in res["results"] if r["status"] == "ok"),
        None,
    )
    if new_id:
        try:
            api._get_persona_manager().delete(new_id)
        except Exception:
            pass
