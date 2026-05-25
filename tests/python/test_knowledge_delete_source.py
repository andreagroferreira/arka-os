"""Tests for DELETE /api/knowledge/sources (PR71 v2.88.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    spec = importlib.util.spec_from_file_location("dashboard_api", DASHBOARD_API_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


class _FakeStore:
    """Stand-in vector store with the surface this endpoint uses."""

    def __init__(self, deleted: int = 0, raises: bool = False):
        self._deleted = deleted
        self._raises = raises
        self.last_source: str | None = None

    def remove_file(self, source: str) -> int:
        if self._raises:
            raise RuntimeError("simulated DB failure")
        self.last_source = source
        return self._deleted


class TestDeleteSource:
    def test_rejects_empty_source(self, dashboard_module):
        result = dashboard_module.knowledge_delete_source(source="")
        assert "error" in result
        assert "required" in result["error"]

    def test_rejects_whitespace_source(self, dashboard_module):
        result = dashboard_module.knowledge_delete_source(source="   ")
        assert "error" in result

    def test_returns_zero_when_store_missing(self, dashboard_module, monkeypatch):
        monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: None)
        result = dashboard_module.knowledge_delete_source(
            source="/path/to/source.md"
        )
        assert result.get("error")
        assert result.get("deleted") == 0

    def test_deletes_and_returns_count(self, dashboard_module, monkeypatch):
        fake = _FakeStore(deleted=3)
        monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: fake)
        result = dashboard_module.knowledge_delete_source(
            source="/path/to/source.md"
        )
        assert result.get("deleted") == 3
        assert result.get("source") == "/path/to/source.md"
        assert fake.last_source == "/path/to/source.md"

    def test_strips_whitespace_from_source(self, dashboard_module, monkeypatch):
        fake = _FakeStore(deleted=1)
        monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: fake)
        dashboard_module.knowledge_delete_source(source="  /path/to/x.md  ")
        assert fake.last_source == "/path/to/x.md"

    def test_swallows_store_exception(self, dashboard_module, monkeypatch):
        fake = _FakeStore(raises=True)
        monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: fake)
        result = dashboard_module.knowledge_delete_source(
            source="/path/to/source.md"
        )
        # Must not raise; reports the failure inline.
        assert "error" in result
        assert result.get("deleted") == 0

    def test_idempotent_when_nothing_to_delete(self, dashboard_module, monkeypatch):
        """remove_file returning 0 is a valid "nothing matched"; not an error."""
        fake = _FakeStore(deleted=0)
        monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: fake)
        result = dashboard_module.knowledge_delete_source(
            source="/does/not/exist.md"
        )
        assert result.get("deleted") == 0
        assert result.get("source") == "/does/not/exist.md"
        assert "error" not in result
