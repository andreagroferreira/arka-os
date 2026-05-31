"""Unit tests for core.knowledge.agent_match (PR3 agent attribution).

Pure matcher tests: cosine basics, profile-text composition, and ranking
with a monkeypatched deterministic fake embedder. No FastAPI, no I/O.
"""

from __future__ import annotations

import pytest

from core.knowledge import agent_match


def test_cosine_identical_is_one():
    assert agent_match.cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero():
    assert agent_match.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_empty_or_zero_norm_is_zero():
    assert agent_match.cosine([], [1.0]) == 0.0
    assert agent_match.cosine([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert agent_match.cosine([1.0], [1.0, 2.0]) == 0.0  # length mismatch


def test_agent_profile_text_includes_role_domains_frameworks():
    agent = {
        "name": "Andre",
        "role": "Senior Backend Developer",
        "expertise_domains": ["Laravel", "API design"],
        "frameworks": ["SOLID", "DDD"],
    }
    text = agent_match.agent_profile_text(agent)
    for token in ("Senior Backend Developer", "Laravel", "API design", "SOLID", "DDD", "Andre"):
        assert token in text


def _fake_agents() -> list[dict]:
    return [
        {"id": "a1", "name": "Architect", "department": "dev", "role": "architect",
         "expertise_domains": ["architecture", "ADR"], "frameworks": ["DDD"]},
        {"id": "a2", "name": "Marketer", "department": "marketing", "role": "growth",
         "expertise_domains": ["funnels"], "frameworks": ["AARRR"]},
    ]


def _install_fake_embedder(monkeypatch, source_vec, agent_vecs):
    """Pin deterministic vectors onto the embedder used by the matcher."""
    monkeypatch.setattr(agent_match.embedder, "embed", lambda _t: source_vec)
    monkeypatch.setattr(agent_match.embedder, "embed_batch", lambda _ts: agent_vecs)


def test_match_agents_ranks_closest_first(monkeypatch):
    # Source vector points at agent a1's vector → a1 ranks first.
    _install_fake_embedder(
        monkeypatch,
        source_vec=[1.0, 0.0],
        agent_vecs=[[1.0, 0.0], [0.0, 1.0]],
    )
    results = agent_match.match_agents("architecture ADR doc", _fake_agents())
    assert [r["id"] for r in results] == ["a1", "a2"]
    assert results[0]["score"] == pytest.approx(1.0)
    assert results[1]["score"] == pytest.approx(0.0)


def test_match_agents_top_n_respected(monkeypatch):
    _install_fake_embedder(monkeypatch, [1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]])
    results = agent_match.match_agents("architecture", _fake_agents(), top_n=1)
    assert len(results) == 1
    assert results[0]["id"] == "a1"


def test_match_agents_matched_terms_textual_overlap(monkeypatch):
    _install_fake_embedder(monkeypatch, [1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]])
    results = agent_match.match_agents("this ADR documents the architecture", _fake_agents())
    top = next(r for r in results if r["id"] == "a1")
    # "architecture" and "ADR" both appear in the source text.
    assert "architecture" in top["matched_terms"]
    assert "ADR" in top["matched_terms"]
    # has all required keys
    for key in ("id", "name", "department", "role", "score", "matched_terms"):
        assert key in top


def test_match_agents_embedder_unavailable_returns_empty(monkeypatch):
    monkeypatch.setattr(agent_match.embedder, "embed", lambda _t: None)
    assert agent_match.match_agents("anything", _fake_agents()) == []


def test_match_agents_empty_source_or_no_agents(monkeypatch):
    _install_fake_embedder(monkeypatch, [1.0], [[1.0]])
    assert agent_match.match_agents("   ", _fake_agents()) == []
    assert agent_match.match_agents("text", []) == []
