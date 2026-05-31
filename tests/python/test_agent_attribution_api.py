"""Integration tests for the agent-attribution endpoints (PR3).

  GET  /api/knowledge/sources/{id}/agent-matches
  POST /api/knowledge/sources/{id}/agent-proposal

Uses a real tmp SourceRegistry and a monkeypatched embedder so the real
~/.arkaos and the real embedding model are never touched. Asserts the
propose-only file is written under a tmp proposals dir, contains the
PROPOSE-ONLY header + agent names, redacts a planted client identifier,
and that NO agent YAML under departments/ is ever written.
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
    from core.knowledge.sources import SourceRegistry
    return SourceRegistry(tmp_path / "knowledge.db")


@pytest.fixture
def fake_agents():
    return [
        {"id": "a1", "name": "Architect", "department": "dev", "role": "architect",
         "expertise_domains": ["architecture", "ADR"], "frameworks": ["DDD"]},
        {"id": "a2", "name": "Marketer", "department": "marketing", "role": "growth",
         "expertise_domains": ["funnels"], "frameworks": ["AARRR"]},
    ]


@pytest.fixture
def client(dashboard_module, registry, fake_agents, monkeypatch):
    monkeypatch.setattr(dashboard_module, "_get_source_registry", lambda: registry)
    monkeypatch.setattr(dashboard_module, "_get_vector_store", lambda: None)
    monkeypatch.setattr(dashboard_module, "_load_agents", lambda: fake_agents)
    return TestClient(dashboard_module.app)


def _patch_embedder(monkeypatch, *, available=True, source=None, batch=None):
    """Pin the embedder the agent_match module imports."""
    from core.knowledge import agent_match
    import core.knowledge.embedder as emb
    monkeypatch.setattr(emb, "is_available", lambda: available)
    if source is not None:
        monkeypatch.setattr(agent_match.embedder, "embed", lambda _t: source)
    if batch is not None:
        monkeypatch.setattr(agent_match.embedder, "embed_batch", lambda _ts: batch)


def test_agent_matches_sorted_with_known_transcript(client, registry, monkeypatch):
    _patch_embedder(monkeypatch, available=True, source=[1.0, 0.0],
                    batch=[[1.0, 0.0], [0.0, 1.0]])
    sid = registry.upsert(
        "https://example.com/adr",
        title="ADR: hexagonal architecture",
        transcript="this document describes the architecture and ADR decisions",
        status="ready",
    )
    res = client.get(f"/api/knowledge/sources/{sid}/agent-matches?top_n=5")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 2
    assert [m["id"] for m in body["matches"]] == ["a1", "a2"]
    scores = [m["score"] for m in body["matches"]]
    assert scores == sorted(scores, reverse=True)
    for key in ("id", "name", "department", "score", "matched_terms"):
        assert key in body["matches"][0]


def test_agent_matches_embedder_unavailable_is_200(client, registry, monkeypatch):
    _patch_embedder(monkeypatch, available=False)
    sid = registry.upsert("https://example.com/x", title="t",
                          transcript="some text", status="ready")
    res = client.get(f"/api/knowledge/sources/{sid}/agent-matches")
    assert res.status_code == 200
    body = res.json()
    assert body["matches"] == []
    assert body["reason"] == "embedder unavailable"


def test_agent_matches_no_source_text(client, registry, monkeypatch):
    _patch_embedder(monkeypatch, available=True, source=[1.0], batch=[[1.0]])
    res = client.get("/api/knowledge/sources/src-doesnotexist/agent-matches")
    assert res.status_code == 200
    assert res.json()["reason"] == "no source text"


def test_agent_proposal_writes_file_redacts_and_no_yaml(
    client, registry, monkeypatch, dashboard_module, tmp_path
):
    # Pin Path.home() to tmp so the proposal is NEVER written to real ~/.arkaos.
    home = tmp_path / "home"
    (home / ".arkaos").mkdir(parents=True)
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))

    # Configure redaction to catch a synthetic client identifier. Patch the
    # compiled regex directly (matches the test_reorganizer pattern) — no
    # reload, fully deterministic.
    import re
    monkeypatch.setattr("core.cognition.reorganizer._CLIENT_PATTERNS", ("acmecorp",))
    monkeypatch.setattr(
        "core.cognition.reorganizer._REDACT_RE",
        re.compile(r"(?<![a-z0-9])(acmecorp)(?![a-z0-9])", re.IGNORECASE),
    )

    _patch_embedder(monkeypatch, available=True, source=[1.0, 0.0],
                    batch=[[1.0, 0.0], [0.0, 1.0]])
    sid = registry.upsert(
        "https://example.com/secret",
        title="acmecorp architecture review",
        transcript="architecture and ADR notes for acmecorp",
        status="ready",
    )

    # Snapshot departments/ agent YAMLs to prove none are written.
    dept_dir = REPO_ROOT / "departments"
    before = {p: p.stat().st_mtime for p in dept_dir.rglob("agents/*.yaml")} if dept_dir.exists() else {}

    res = client.post(f"/api/knowledge/sources/{sid}/agent-proposal", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["agents"] >= 1
    proposal = Path(body["proposal_path"])
    assert proposal.exists()
    # Written under the tmp proposals dir, not real ~/.arkaos.
    assert (home / ".arkaos" / "reorganize-proposals") in proposal.parents

    content = proposal.read_text(encoding="utf-8")
    assert "PROPOSE-ONLY" in content
    assert "Architect" in content  # agent name present
    assert "acmecorp" not in content  # client identifier redacted
    assert "<redacted-client>" in content

    # NO agent YAML touched.
    after = {p: p.stat().st_mtime for p in dept_dir.rglob("agents/*.yaml")} if dept_dir.exists() else {}
    assert before == after


def test_agent_proposal_escapes_untrusted_title(
    client, registry, monkeypatch, dashboard_module, tmp_path
):
    """Untrusted title markdown control chars are neutralised via md_escape.

    The title comes from web-page <title> / YouTube / PDF metadata — fully
    attacker-influenceable. The .md proposal is opened in HTML-rendering
    viewers (Obsidian), so md_escape HTML-escapes <> to &lt;/&gt; (stored-XSS
    defence, CWE-79), escapes pipes/backslashes, and strips backticks.
    Redaction still runs (planted client below). Proposal otherwise intact.
    """
    home = tmp_path / "home-esc"
    (home / ".arkaos").mkdir(parents=True)
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))

    import re
    monkeypatch.setattr("core.cognition.reorganizer._CLIENT_PATTERNS", ("acmecorp",))
    monkeypatch.setattr(
        "core.cognition.reorganizer._REDACT_RE",
        re.compile(r"(?<![a-z0-9])(acmecorp)(?![a-z0-9])", re.IGNORECASE),
    )

    _patch_embedder(monkeypatch, available=True, source=[1.0, 0.0],
                    batch=[[1.0, 0.0], [0.0, 1.0]])
    sid = registry.upsert(
        "https://example.com/evil",
        title="acmecorp <script>alert(1)</script> | `rm -rf` review",
        transcript="architecture and ADR notes for acmecorp",
        status="ready",
    )

    res = client.post(f"/api/knowledge/sources/{sid}/agent-proposal", json={})
    assert res.status_code == 200
    content = Path(res.json()["proposal_path"]).read_text(encoding="utf-8")

    # Pipe escaped, backticks stripped (md_escape's real behavior).
    assert "\\|" in content
    assert "`rm -rf`" not in content
    assert "rm -rf" in content  # text kept, only the backticks removed
    # Stored-XSS defence: the <script> tag must be HTML-neutralised so it
    # renders as literal text, never as an executing tag, in Obsidian.
    assert "<script>" not in content
    assert "</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
    # Raw, unescaped pipe must NOT appear inside the heading.
    heading = next(l for l in content.splitlines() if l.startswith("# Agent"))
    assert " | " not in heading
    # Redaction still active; agent name intact; no agent YAML touched.
    assert "acmecorp" not in content
    assert "<redacted-client>" in content
    assert "Architect" in content


def test_agent_proposal_neutralises_img_onerror_title(
    client, registry, monkeypatch, dashboard_module, tmp_path
):
    """An <img onerror> title (Obsidian-executable) is written neutralised.

    Realistic stored-XSS payload: Obsidian strips <script> but renders
    <img onerror>. md_escape must HTML-escape the tag so it can never fire
    when the user opens the propose-only .md (CWE-79, OWASP A03).
    """
    home = tmp_path / "home-img"
    (home / ".arkaos").mkdir(parents=True)
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))
    _patch_embedder(monkeypatch, available=True, source=[1.0, 0.0],
                    batch=[[1.0, 0.0], [0.0, 1.0]])
    sid = registry.upsert(
        "https://example.com/img-evil",
        title='<img src=x onerror="alert(document.cookie)"> notes',
        transcript="architecture and ADR notes",
        status="ready",
    )

    res = client.post(f"/api/knowledge/sources/{sid}/agent-proposal", json={})
    assert res.status_code == 200
    content = Path(res.json()["proposal_path"]).read_text(encoding="utf-8")

    # No raw HTML tag survives; the angle brackets are entity-encoded.
    assert "<img" not in content
    assert "&lt;img src=x onerror=" in content


def test_agent_proposal_scoped_by_agent_ids(client, registry, monkeypatch, dashboard_module, tmp_path):
    home = tmp_path / "home2"
    (home / ".arkaos").mkdir(parents=True)
    monkeypatch.setattr(dashboard_module.Path, "home", staticmethod(lambda: home))
    _patch_embedder(monkeypatch, available=True, source=[1.0, 0.0],
                    batch=[[1.0, 0.0], [0.0, 1.0]])
    sid = registry.upsert("https://example.com/y", title="arch", transcript="architecture", status="ready")
    res = client.post(f"/api/knowledge/sources/{sid}/agent-proposal", json={"agent_ids": ["a2"]})
    assert res.status_code == 200
    assert res.json()["agents"] == 1
    content = Path(res.json()["proposal_path"]).read_text(encoding="utf-8")
    assert "Marketer" in content
    assert "Architect" not in content
