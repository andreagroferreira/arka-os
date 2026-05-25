"""Tests for the /api/knowledge/ingest-bulk endpoint (PR56 v2.73.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_API_PATH = REPO_ROOT / "scripts" / "dashboard-api.py"


@pytest.fixture(scope="module")
def dashboard_module():
    """Load scripts/dashboard-api.py as an importable module.

    scripts/ is not a Python package, so we use importlib.util.spec_from_file_location
    to bring the module into the test process.
    """
    spec = importlib.util.spec_from_file_location(
        "dashboard_api", DASHBOARD_API_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["dashboard_api"] = module
    spec.loader.exec_module(module)
    return module


def test_bulk_rejects_non_list_sources(dashboard_module):
    result = dashboard_module.knowledge_ingest_bulk({"sources": "not-a-list"})
    assert result.get("error") == "sources must be a list"


def test_bulk_rejects_empty_list(dashboard_module):
    result = dashboard_module.knowledge_ingest_bulk({"sources": []})
    assert result.get("error") == "no valid sources provided"


def test_bulk_rejects_only_whitespace_sources(dashboard_module):
    result = dashboard_module.knowledge_ingest_bulk(
        {"sources": ["", "   ", "\n", "\t"]}
    )
    assert result.get("error") == "no valid sources provided"


def test_bulk_caps_at_50_sources(dashboard_module):
    too_many = [f"https://example.com/{i}" for i in range(51)]
    result = dashboard_module.knowledge_ingest_bulk({"sources": too_many})
    assert "capped at 50" in result.get("error", "")


def test_bulk_dedupes_sources(monkeypatch, dashboard_module):
    """Sending the same URL twice should produce one job, not two."""
    seen_sources: list[str] = []

    def fake_ingest(body):
        seen_sources.append(body["source"])
        return {"job_id": f"job-{len(seen_sources)}", "source_type": "web", "status": "queued"}

    monkeypatch.setattr(dashboard_module, "knowledge_ingest", fake_ingest)
    result = dashboard_module.knowledge_ingest_bulk({
        "sources": [
            "https://example.com/a",
            "https://example.com/a",  # duplicate
            "https://example.com/b",
        ],
    })
    assert result["count"] == 2
    assert seen_sources == ["https://example.com/a", "https://example.com/b"]


def test_bulk_strips_whitespace_around_sources(monkeypatch, dashboard_module):
    seen_sources: list[str] = []

    def fake_ingest(body):
        seen_sources.append(body["source"])
        return {"job_id": "j", "source_type": "web", "status": "queued"}

    monkeypatch.setattr(dashboard_module, "knowledge_ingest", fake_ingest)
    dashboard_module.knowledge_ingest_bulk({
        "sources": ["  https://example.com/x  ", "\nhttps://example.com/y\n"],
    })
    assert seen_sources == ["https://example.com/x", "https://example.com/y"]


def test_bulk_aggregates_job_results(monkeypatch, dashboard_module):
    """Returned jobs array carries one entry per source with its job_id."""
    def fake_ingest(body):
        return {"job_id": f"id-for-{body['source']}", "source_type": "web", "status": "queued"}

    monkeypatch.setattr(dashboard_module, "knowledge_ingest", fake_ingest)
    result = dashboard_module.knowledge_ingest_bulk({
        "sources": ["https://a", "https://b", "https://c"],
    })
    assert result["count"] == 3
    assert {j["job_id"] for j in result["jobs"]} == {
        "id-for-https://a", "id-for-https://b", "id-for-https://c"
    }


def test_bulk_per_source_error_does_not_abort_batch(
    monkeypatch, dashboard_module
):
    """If one source fails (e.g. validation), other sources still get queued."""
    def fake_ingest(body):
        if "bad" in body["source"]:
            return {"error": "source is required"}
        return {"job_id": f"ok-{body['source']}", "source_type": "web", "status": "queued"}

    monkeypatch.setattr(dashboard_module, "knowledge_ingest", fake_ingest)
    result = dashboard_module.knowledge_ingest_bulk({
        "sources": ["https://good-1", "bad-source", "https://good-2"],
    })
    assert result["count"] == 3
    statuses = {j.get("source"): ("error" if "error" in j else "ok") for j in result["jobs"]}
    assert statuses == {
        "https://good-1": "ok",
        "bad-source": "error",
        "https://good-2": "ok",
    }


def test_bulk_skips_non_string_entries(monkeypatch, dashboard_module):
    seen: list[str] = []

    def fake_ingest(body):
        seen.append(body["source"])
        return {"job_id": "j", "source_type": "web", "status": "queued"}

    monkeypatch.setattr(dashboard_module, "knowledge_ingest", fake_ingest)
    result = dashboard_module.knowledge_ingest_bulk({
        "sources": [
            "https://example.com/a",
            None,
            42,
            {"not": "a string"},
            "https://example.com/b",
        ],
    })
    assert result["count"] == 2
    assert seen == ["https://example.com/a", "https://example.com/b"]
