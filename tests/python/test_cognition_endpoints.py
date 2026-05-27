"""HTTP-level tests for the cognition endpoints in scripts/dashboard-api.py.

v3.72.0 — surfaces existing Dreaming insights (read-only) to the dashboard.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_insight(dreams_dir: Path, date: str, title: str, confidence: str,
                   tags: list[str], sources: list[str], body: str) -> None:
    fm = ["---", "type: arkaos-insight", f"date: {date}", f"confidence: {confidence}"]
    if sources:
        fm.append("sources:")
        fm += [f"  - {s}" for s in sources]
    if tags:
        fm.append("tags:")
        fm += [f"  - {t}" for t in tags]
    fm.append("---")
    text = "\n".join(fm) + f"\n\n# {title}\n\n{body}\n"
    (dreams_dir / f"{date}-{title.lower().replace(' ', '-')}.md").write_text(
        text, encoding="utf-8"
    )


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    dreams = tmp_path / "vault" / "Projects" / "ArkaOS" / "Dreams"
    dreams.mkdir(parents=True)
    today = datetime.now(timezone.utc).date()
    old = today - timedelta(days=20)
    _write_insight(dreams, today.isoformat(), "Fresh Insight", "high",
                   ["dev"], ["[[note-a]]"], "A high-confidence insight.")
    _write_insight(dreams, today.isoformat(), "Second Today", "medium",
                   ["ui"], [], "Another one today.")
    _write_insight(dreams, old.isoformat(), "Old Insight", "low",
                   ["ops"], [], "From three weeks ago.")

    # Point load_profile at the temp vault.
    import core.runtime.path_resolver as pr
    monkeypatch.setattr(pr, "load_profile",
                        lambda: SimpleNamespace(vault_path=str(tmp_path / "vault")))

    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        f"dashboard_api_cog_{tmp_path.name}",
        REPO_ROOT / "scripts" / "dashboard-api.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_insights_today_only(api):
    client = TestClient(api.app)
    r = client.get("/api/cognition/insights?days=1")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    titles = [i["title"] for i in body["insights"]]
    assert "Fresh Insight" in titles
    assert "Second Today" in titles
    assert "Old Insight" not in titles


def test_insights_window_includes_old(api):
    client = TestClient(api.app)
    body = client.get("/api/cognition/insights?days=30").json()
    titles = [i["title"] for i in body["insights"]]
    assert "Old Insight" in titles
    assert len(body["insights"]) == 3


def test_insight_shape(api):
    client = TestClient(api.app)
    fresh = next(i for i in client.get("/api/cognition/insights?days=1").json()["insights"]
                 if i["title"] == "Fresh Insight")
    assert set(fresh.keys()) >= {"date", "title", "confidence", "sources", "tags", "body"}
    assert fresh["confidence"] == "high"
    assert fresh["tags"] == ["dev"]
    assert fresh["sources"] == ["[[note-a]]"]
    assert "path" not in fresh  # internal Path not leaked


def test_status_counts_and_confidence(api):
    client = TestClient(api.app)
    s = client.get("/api/cognition/status").json()
    assert s["vault_configured"] is True
    assert s["today"] == 2
    assert s["total"] == 3
    assert s["by_confidence"]["high"] == 1
    assert s["by_confidence"]["medium"] == 1
    assert s["by_confidence"]["low"] == 1
    assert s["last_date"] == datetime.now(timezone.utc).date().isoformat()


def test_no_vault_is_graceful(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKAOS_HOME", str(tmp_path))
    import core.runtime.path_resolver as pr

    class _Missing(Exception):
        pass

    def _raise():
        raise pr.ProfileMissingError("no profile")

    monkeypatch.setattr(pr, "load_profile", _raise)
    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        f"dashboard_api_novault_{tmp_path.name}",
        REPO_ROOT / "scripts" / "dashboard-api.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client = TestClient(module.app)

    insights = client.get("/api/cognition/insights")
    assert insights.status_code == 200
    assert insights.json()["available"] is False
    status = client.get("/api/cognition/status")
    assert status.status_code == 200
    assert status.json()["vault_configured"] is False
