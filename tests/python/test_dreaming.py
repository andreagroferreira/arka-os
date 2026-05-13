"""Tests for core.cognition.dreaming — Dreaming v2 engine.

Mocks the LLM provider so the engine is exercised end-to-end without
needing Ollama or Claude Code running in CI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.cognition.dreaming import (
    Chunk,
    Cluster,
    Dreaming,
    Insight,
    _build_critic_prompt,
    _build_insight_prompt,
    _parse_insight,
    _slugify,
    _split_for_clustering,
)
from core.runtime.llm_provider import LLMResponse, LLMUnavailable


@pytest.fixture
def fake_provider():
    """A provider mock that returns scripted responses per call index."""
    provider = MagicMock()
    provider.complete = MagicMock()
    return provider


@pytest.fixture
def synthetic_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Projects").mkdir()
    fovory = vault / "Projects" / "Fovory.md"
    fovory.write_text(
        "# Fovory\n\n"
        "Decided to migrate Fovory to Inertia v3 this week, the supplier sync "
        "module was the main reason — the v2 React shell could not handle the "
        "pagination over 1000 rows that Fovory pricing screen needs.\n\n"
        "Pest browser tests fail on pagination over 1000 rows consistently in "
        "the Fovory batch_decisions screen — third occurrence this month and "
        "the pattern looks structural, not flaky.\n\n"
        "Fovory pricing tier B requires confirmation of 35 percent margin "
        "across the Sicily handbag line — Marta flagged the contradiction "
        "with the auditor evidence earlier in the week.\n\n"
        "Pest pagination bug recurs in Fovory batch_decisions screen again; "
        "shared helper paginatesLargeDataset would close this once and for "
        "all across three projects that share the pattern.\n",
        encoding="utf-8",
    )
    arka = vault / "Projects" / "ArkaOS.md"
    arka.write_text(
        "# ArkaOS notes\n\n"
        "PathResolver wraps profile.json paths and exposes ${VAULT_PATH} as "
        "the canonical token for SKILL.md substitution across the project; "
        "PathResolver shipped in v2.23.0 with 24 tests and 99 percent coverage.\n\n"
        "Cognitive layer is multi-backend after Conclave Phase 4 correction; "
        "Claude Code is the default backend, Ollama is opt-in, Anthropic API "
        "is supported for power users with API keys configured in env.\n\n"
        "PathResolver replaced hardcoded vault path in obsidian-config.json "
        "via the resolve_dict recursive substitution helper, see PR1 v2.23.0 "
        "release notes in the Knowledge Base for full diff metrics.\n",
        encoding="utf-8",
    )
    return vault


def test_split_for_clustering_filters_short_pieces():
    text = "short\n\nthis is a longer paragraph that definitely exceeds the minimum chunk size threshold we use for clustering today in the engine" * 1
    pieces = _split_for_clustering(text)
    assert len(pieces) == 1
    assert "longer paragraph" in pieces[0]


def test_split_for_clustering_caps_long_pieces():
    text = "x" * 5000
    pieces = _split_for_clustering(text)
    assert len(pieces) == 1
    assert len(pieces[0]) <= 1200


def test_slugify_handles_titles_with_punctuation():
    assert _slugify("Pest Pagination > 1000 rows: bug!") == "pest-pagination-1000-rows-bug"


def test_slugify_truncates_long_titles():
    long_title = "x" * 200
    assert len(_slugify(long_title)) <= 60


def test_parse_insight_returns_none_for_pass():
    resp = LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="x")
    cluster = Cluster(topic="Test", chunks=[])
    assert _parse_insight(resp, cluster) is None


def test_parse_insight_extracts_title_body_confidence():
    resp = LLMResponse(
        text="TITLE: Pest pagination recurring bug\nBODY: Three notes show pagination Pest tests fail. Add a shared helper.\nCONFIDENCE: high",
        tokens_in=20, tokens_out=20, cached_tokens=0, model="x",
    )
    cluster = Cluster(topic="Pest", chunks=[Chunk("Projects/Fovory.md", "...", "vault")])
    insight = _parse_insight(resp, cluster)
    assert insight is not None
    assert insight.title == "Pest pagination recurring bug"
    assert "shared helper" in insight.body
    assert insight.confidence == "high"
    assert insight.sources == ["Projects/Fovory.md"]
    assert insight.tags == ["pest"]


def test_parse_insight_defaults_confidence_when_missing():
    resp = LLMResponse(text="TITLE: Something\nBODY: Body here", tokens_in=1, tokens_out=1, cached_tokens=0, model="x")
    cluster = Cluster(topic="X", chunks=[])
    insight = _parse_insight(resp, cluster)
    assert insight is not None
    assert insight.confidence == "medium"


def test_parse_insight_clamps_invalid_confidence():
    resp = LLMResponse(text="TITLE: X\nBODY: y\nCONFIDENCE: nuclear", tokens_in=1, tokens_out=1, cached_tokens=0, model="x")
    cluster = Cluster(topic="X", chunks=[])
    insight = _parse_insight(resp, cluster)
    assert insight.confidence == "medium"


def test_build_insight_prompt_includes_sources_and_excerpts():
    cluster = Cluster(
        topic="Fovory",
        chunks=[
            Chunk("Projects/Fovory.md", "First excerpt about pagination.", "vault"),
            Chunk("Projects/Fovory.md", "Second excerpt about migration.", "vault"),
        ],
    )
    prompt = _build_insight_prompt(cluster)
    assert "Topic anchor: Fovory" in prompt
    assert "Projects/Fovory.md" in prompt
    assert "First excerpt about pagination" in prompt


def test_build_critic_prompt_asks_for_single_word_verdict():
    insight = Insight(title="X", body="Y", confidence="high")
    prompt = _build_critic_prompt(insight)
    assert "VALUABLE" in prompt
    assert "NOISE" in prompt
    assert "one word" in prompt.lower()


def test_dreaming_returns_empty_when_no_chunks(tmp_path, fake_provider):
    empty = tmp_path / "empty-vault"
    empty.mkdir()
    engine = Dreaming(vault_path=empty, output_dir=tmp_path / "out", provider=fake_provider)
    insights = engine.run()
    assert insights == []
    assert fake_provider.complete.call_count == 0


def test_dreaming_end_to_end_with_scripted_provider(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = [
        # First cluster — produce insight
        LLMResponse(
            text="TITLE: Pest pagination recurring\nBODY: Three Fovory notes mention pagination Pest tests failing. Consider a shared helper.\nCONFIDENCE: high",
            tokens_in=20, tokens_out=20, cached_tokens=0, model="test",
        ),
        # Critic — accept
        LLMResponse(text="VALUABLE", tokens_in=1, tokens_out=1, cached_tokens=0, model="test"),
    ] + [
        # Spare responses for any further clusters — all PASS
        LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="test"),
    ] * 20
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
        max_insights=3,
    )
    insights = engine.run()
    assert len(insights) >= 1
    assert insights[0].title == "Pest pagination recurring"
    # Verify a file was written
    written = list((tmp_path / "dreams").glob("*.md"))
    assert len(written) >= 1
    body = written[0].read_text(encoding="utf-8")
    assert "type: arkaos-insight" in body
    assert "Pest pagination recurring" in body


def test_dreaming_dry_run_does_not_write_files(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = [
        LLMResponse(
            text="TITLE: x\nBODY: y\nCONFIDENCE: medium",
            tokens_in=1, tokens_out=1, cached_tokens=0, model="t",
        ),
        LLMResponse(text="VALUABLE", tokens_in=1, tokens_out=1, cached_tokens=0, model="t"),
    ] + [LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="t")] * 20
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )
    insights = engine.run(dry_run=True)
    assert len(insights) >= 1
    # No files written despite insights generated
    if (tmp_path / "dreams").exists():
        assert list((tmp_path / "dreams").glob("*.md")) == []


def test_dreaming_critic_rejects_filter_noise(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = [
        # Insight draft passes parsing
        LLMResponse(
            text="TITLE: Noisy claim\nBODY: Generic statement about general patterns.\nCONFIDENCE: low",
            tokens_in=5, tokens_out=5, cached_tokens=0, model="t",
        ),
        # Critic rejects
        LLMResponse(text="NOISE", tokens_in=1, tokens_out=1, cached_tokens=0, model="t"),
    ] + [LLMResponse(text="PASS", tokens_in=1, tokens_out=1, cached_tokens=0, model="t")] * 20
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )
    insights = engine.run()
    assert insights == []


def test_dreaming_handles_provider_unavailable(synthetic_vault, tmp_path, fake_provider):
    fake_provider.complete.side_effect = LLMUnavailable("ollama down")
    engine = Dreaming(
        vault_path=synthetic_vault,
        output_dir=tmp_path / "dreams",
        provider=fake_provider,
    )
    insights = engine.run()
    assert insights == []  # zero insights, no crash
