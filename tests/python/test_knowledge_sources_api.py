"""Integration tests for /api/knowledge/sources/* + upload traversal guard.

Covers the two P1 blockers fixed in feat/knowledge-video-pipeline:
  1. ``_get_source_registry`` was undefined -> every sources/* endpoint 500'd.
  2. upload-file used the raw client filename -> arbitrary file write.

Tests use a real (tmp) SourceRegistry so the endpoint<->registry wiring is
exercised end to end. The real ~/.arkaos is never touched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    """Load scripts/dashboard-api.py as an importable module (matches the
    loader pattern used by the other dashboard-api test files)."""
    if "dashboard_api" in sys.modules:
        return sys.modules["dashboard_api"]
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def registry(tmp_path):
    """A real SourceRegistry over a throwaway knowledge.db."""
    from core.knowledge.sources import SourceRegistry
    return SourceRegistry(tmp_path / "knowledge.db")


@pytest.fixture
def client(dashboard_module, registry, monkeypatch):
    """TestClient with the source registry pinned to the tmp registry so the
    real ~/.arkaos is never read or written."""
    monkeypatch.setattr(dashboard_module, "_get_source_registry", lambda: registry)
    return TestClient(dashboard_module.app)


def test_unknown_source_is_clean_not_found(client):
    """Unknown id must not 500 — the missing helper used to NameError here."""
    res = client.get("/api/knowledge/sources/src-doesnotexist")
    assert res.status_code != 500
    assert res.status_code == 404
    assert res.json().get("error") == "not found"


def test_source_detail_reads_registry_end_to_end(client, registry, monkeypatch, dashboard_module):
    """Insert a row directly, then prove GET returns 200 with its metadata.
    Proves the endpoint<->registry read path is wired correctly."""
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: None)
    sid = registry.upsert(
        "https://example.com/talk",
        title="A Real Talk",
        transcript="hello world transcript",
        status="ready",
    )
    res = client.get(f"/api/knowledge/sources/{sid}")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "A Real Talk"
    assert body["transcript"] == "hello world transcript"
    assert body["chunks"] == []


def test_source_transcript_reads_registry(client, registry):
    sid = registry.upsert("https://example.com/v2", transcript="full transcript text")
    res = client.get(f"/api/knowledge/sources/{sid}/transcript")
    assert res.status_code == 200
    assert res.json()["transcript"] == "full transcript text"


def test_upload_traversal_writes_nothing_outside_media(client, monkeypatch, dashboard_module, tmp_path):
    """filename='../../../../arkaos_pwn_test' must NOT write outside media_dir.
    The basename strip neutralizes the traversal: any write lands safely
    inside media_dir, and the escape targets stay non-existent."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))
    media_dir = home / ".arkaos" / "media"
    # Would-be escape targets at the levels the payload tried to reach.
    escapes = [home / "arkaos_pwn_test", home / ".arkaos" / "arkaos_pwn_test"]
    for target in escapes:
        assert not target.exists()

    res = client.post(
        "/api/knowledge/upload-file",
        files={"file": ("../../../../arkaos_pwn_test", b"pwned", "text/plain")},
    )
    assert res.status_code == 200
    # Critical invariant: nothing was written outside the media dir.
    for target in escapes:
        assert not target.exists()
    # If anything was written, it is confined to media_dir under the basename.
    stray = list(p for p in tmp_path.rglob("arkaos_pwn_test"))
    for p in stray:
        assert media_dir.resolve() in p.resolve().parents


def test_upload_rejects_empty_basename(client, monkeypatch, dashboard_module, tmp_path):
    """A filename that reduces to an empty basename is rejected outright."""
    home = tmp_path / "home2"
    home.mkdir()
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))
    res = client.post(
        "/api/knowledge/upload-file",
        files={"file": ("../../../", b"pwned", "text/plain")},
    )
    assert res.status_code == 200
    assert res.json().get("error") == "invalid filename"


def test_get_source_registry_returns_instance(dashboard_module, monkeypatch, tmp_path):
    """When knowledge.db is creatable, the helper yields a real registry."""
    from core.knowledge.sources import SourceRegistry
    monkeypatch.setattr(dashboard_module, "_source_registry_cache", None)
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: tmp_path))
    reg = dashboard_module._get_source_registry()
    assert reg is not None
    assert isinstance(reg, SourceRegistry)
