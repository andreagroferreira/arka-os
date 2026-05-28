"""Tests for core.synapse.pattern_library_layer (PR4 Squad Intelligence)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.knowledge import pattern_cards
from core.knowledge.pattern_cards import PatternCard, record_pattern
from core.synapse.pattern_library_layer import (
    PatternLibraryLayer,
    _extract_keywords,
    format_patterns,
)
from core.synapse.layers import PromptContext


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(pattern_cards, "PATTERNS_PATH", tmp_path / "cards.jsonl")
    return tmp_path / "cards.jsonl"


def _card(**kwargs) -> PatternCard:
    base = dict(
        id="auth-magic-link-1",
        name="Magic Link Auth",
        feature_keywords=["auth", "magic-link", "passwordless"],
        description="Passwordless authentication via emailed magic link",
        stack=["python", "fastapi"],
        files=["app/auth/magic_link.py"],
        acceptance_criteria=["Token expires after 15 minutes"],
        edge_cases=[],
        references=["https://example.com/pr/100"],
        projects_using=["arkaos"],
        created_at=datetime.now(timezone.utc).isoformat(),
        last_updated=datetime.now(timezone.utc).isoformat(),
    )
    base.update(kwargs)
    return PatternCard(**base)


# ─── Keyword extractor ─────────────────────────────────────────────────


class TestExtract:
    def test_extracts_words_above_3_chars(self):
        kw = _extract_keywords("Build a magic link auth flow for users")
        assert "magic" in kw
        assert "link" in kw
        assert "auth" in kw
        assert "flow" in kw

    def test_filters_stopwords(self):
        kw = _extract_keywords("I need this thing to have that flow")
        assert "this" not in kw
        assert "that" not in kw
        assert "need" not in kw
        assert "flow" in kw

    def test_deduplicates(self):
        kw = _extract_keywords("auth auth auth magic magic")
        assert kw.count("auth") == 1
        assert kw.count("magic") == 1

    def test_caps_at_max_n(self):
        text = " ".join(f"word{i}" for i in range(50))
        kw = _extract_keywords(text, max_n=5)
        assert len(kw) == 5

    def test_empty_input(self):
        assert _extract_keywords("") == []
        assert _extract_keywords(None) == []

    def test_pt_pt_accented_words_kept_whole(self):
        """PR4.5 v3.75.1 — Latin-1 Supplement chars must NOT truncate words."""
        kw = _extract_keywords("implementar autenticação com paginação no projeto")
        # Whole accented words preserved, not truncated to "autentica"/"pagina"
        assert "autenticação" in kw
        assert "paginação" in kw
        assert "projeto" in kw
        assert "implementar" in kw

    def test_pt_pt_mixed_with_english(self):
        kw = _extract_keywords("Build the autenticação flow with magic link")
        assert "build" in kw
        assert "autenticação" in kw
        assert "flow" in kw
        assert "magic" in kw
        assert "link" in kw


# ─── Layer compute path ────────────────────────────────────────────────


class TestLayer:
    def test_empty_user_input_returns_empty(self, tmp_store):
        layer = PatternLibraryLayer()
        result = layer.compute(PromptContext(user_input=""))
        assert result.content == ""
        assert result.tokens_est == 0

    def test_no_matching_card_returns_empty_with_none_tag(self, tmp_store):
        record_pattern(_card(feature_keywords=["totally-unrelated"]))
        layer = PatternLibraryLayer()
        result = layer.compute(
            PromptContext(user_input="build a chat system")
        )
        assert result.content == ""
        assert "none" in result.tag

    def test_matching_card_injects_context(self, tmp_store):
        record_pattern(_card())
        layer = PatternLibraryLayer()
        result = layer.compute(
            PromptContext(user_input="implement magic link login")
        )
        assert "Magic Link Auth" in result.content
        assert "magic_link.py" in result.content
        assert "Token expires" in result.content
        assert "1" in result.tag  # patterns:1

    def test_respects_limit(self, tmp_store):
        for i in range(10):
            record_pattern(
                _card(
                    id=f"auth-{i}",
                    feature_keywords=["auth", "passwordless"],
                )
            )
        layer = PatternLibraryLayer(limit=3)
        result = layer.compute(
            PromptContext(user_input="auth passwordless flow")
        )
        assert "patterns:3" in result.tag

    def test_layer_metadata(self, tmp_store):
        layer = PatternLibraryLayer()
        assert layer.id == "L7.5"
        assert layer.name == "PatternLibrary"
        assert layer.cache_ttl == 60
        assert layer.priority == 75


# ─── Format ────────────────────────────────────────────────────────────


def test_format_includes_name_files_ac_refs(tmp_store):
    cards = [
        _card(
            name="Magic Link Auth",
            description="Passwordless via email",
            stack=["python", "fastapi"],
            files=["app/auth/magic_link.py"],
            acceptance_criteria=["Token expires 15m"],
            references=["https://example.com/pr/100"],
        )
    ]
    out = format_patterns(cards)
    assert "Magic Link Auth" in out
    assert "auth-magic-link-1" in out
    assert "python, fastapi" in out
    assert "Passwordless via email" in out
    assert "magic_link.py" in out
    assert "Token expires 15m" in out
    assert "https://example.com/pr/100" in out
    assert "Pattern Library" in out
    assert "reuse or document divergence" in out


def test_format_truncates_long_lists(tmp_store):
    cards = [
        _card(
            files=[f"f{i}.py" for i in range(10)],
            acceptance_criteria=[f"AC{i}" for i in range(10)],
        )
    ]
    out = format_patterns(cards)
    # Should cap files at 3
    assert "f0.py" in out
    assert "f1.py" in out
    assert "f2.py" in out
    assert "f3.py" not in out
    # Should cap AC at 2
    assert "AC0" in out
    assert "AC1" in out
    assert "AC2" not in out
