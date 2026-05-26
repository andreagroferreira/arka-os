"""Tests for the AI list-field suggester (PR81 v2.99.0)."""

from __future__ import annotations

import pytest

from core.agents.field_suggester import (
    SuggestionError,
    SuggestionResult,
    suggest_field,
)
from core.runtime.llm_provider import LLMResponse, LLMUnavailable


class _FakeProvider:
    def __init__(self, text: str = "[]", name: str = "fake") -> None:
        self._text = text
        self._name = name
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 600,
        system: str = "",
    ) -> LLMResponse:
        self.last_prompt = prompt
        self.last_system = system
        return LLMResponse(
            text=self._text,
            tokens_in=0,
            tokens_out=0,
            cached_tokens=0,
            model="",
        )

    def is_available(self) -> bool:
        return True

    def name(self) -> str:
        return self._name


class _UnavailableProvider(_FakeProvider):
    def complete(self, *_args, **_kwargs) -> LLMResponse:
        raise LLMUnavailable("provider down")


def test_returns_suggestions_from_clean_json():
    p = _FakeProvider('["Option A", "Option B", "Option C"]')
    res = suggest_field("frameworks", {"name": "Test"}, count=3, provider=p)
    assert isinstance(res, SuggestionResult)
    assert res.suggestions == ["Option A", "Option B", "Option C"]
    assert res.provider_name == "fake"


def test_strips_json_fences():
    p = _FakeProvider('```json\n["A", "B"]\n```')
    res = suggest_field("mental_models", {"name": "X"}, provider=p)
    assert res.suggestions == ["A", "B"]


def test_truncates_to_count():
    p = _FakeProvider('["one","two","three","four","five"]')
    res = suggest_field("mental_models", {"name": "X"}, count=2, provider=p)
    assert res.suggestions == ["one", "two"]


def test_count_clamped_above_max():
    p = _FakeProvider('["a","b","c","d","e","f","g","h","i","j","k","l","m","n"]')
    res = suggest_field("frameworks", {"name": "X"}, count=999, provider=p)
    assert len(res.suggestions) == 12  # _MAX_COUNT


def test_count_clamped_below_one():
    p = _FakeProvider('["a","b"]')
    res = suggest_field("frameworks", {"name": "X"}, count=0, provider=p)
    assert len(res.suggestions) == 1


def test_rejects_unknown_field():
    p = _FakeProvider("[]")
    with pytest.raises(SuggestionError, match="unknown field"):
        suggest_field("bogus", {}, provider=p)


def test_falls_back_to_line_split_when_not_json():
    p = _FakeProvider("- Pattern A\n- Pattern B\n- Pattern C")
    res = suggest_field("frameworks", {"name": "X"}, provider=p)
    assert res.suggestions == ["Pattern A", "Pattern B", "Pattern C"]


def test_passes_current_into_prompt():
    p = _FakeProvider('["X"]')
    suggest_field(
        "expertise_domains",
        {"name": "Y", "current": ["already-have"]},
        provider=p,
    )
    assert "already-have" in (p.last_prompt or "")


def test_dedupes_against_current_case_insensitive():
    p = _FakeProvider('["First", "second"]')
    res = suggest_field(
        "mental_models",
        {"name": "X", "current": ["FIRST"]},
        provider=p,
    )
    assert "First" not in res.suggestions
    assert "second" in res.suggestions


def test_dedupes_within_response():
    p = _FakeProvider('["dup", "dup", "unique"]')
    res = suggest_field("frameworks", {"name": "X"}, provider=p)
    assert res.suggestions == ["dup", "unique"]


def test_passes_role_into_prompt():
    p = _FakeProvider('["X"]')
    suggest_field(
        "frameworks",
        {"name": "Y", "role": "Senior backend engineer"},
        provider=p,
    )
    assert "Senior backend engineer" in (p.last_prompt or "")


def test_passes_department_into_prompt():
    p = _FakeProvider('["X"]')
    suggest_field(
        "expertise_domains",
        {"name": "Y", "department": "dev"},
        provider=p,
    )
    assert "dev" in (p.last_prompt or "")


def test_uses_title_when_no_role():
    p = _FakeProvider('["X"]')
    suggest_field(
        "mental_models",
        {"name": "Y", "title": "Negotiation Coach"},
        provider=p,
    )
    assert "Negotiation Coach" in (p.last_prompt or "")


def test_field_label_in_prompt():
    p = _FakeProvider('["X"]')
    suggest_field("expertise_domains", {"name": "Y"}, provider=p)
    assert "expertise domains" in (p.last_prompt or "")


def test_returns_empty_when_llm_returns_empty_array():
    p = _FakeProvider("[]")
    res = suggest_field("frameworks", {"name": "X"}, provider=p)
    assert res.suggestions == []


def test_handles_non_list_json():
    p = _FakeProvider('{"not": "a list"}')
    res = suggest_field("frameworks", {"name": "X"}, provider=p)
    # Falls through to line-split fallback on the JSON text itself.
    assert isinstance(res.suggestions, list)


def test_propagates_llm_unavailable_as_suggestion_error():
    p = _UnavailableProvider()
    with pytest.raises(SuggestionError, match="provider down"):
        suggest_field("frameworks", {"name": "X"}, provider=p)


def test_strips_bullet_prefixes_in_fallback():
    p = _FakeProvider("• Item one\n* Item two\n- Item three\n1. Item four")
    res = suggest_field("frameworks", {"name": "X"}, provider=p)
    assert res.suggestions == ["Item one", "Item two", "Item three", "Item four"]


# --- PR82c v3.2.0: extended fields ---

def test_accepts_communication_avoid_field():
    p = _FakeProvider('["fluff", "synergy", "circle back"]')
    res = suggest_field("communication_avoid", {"name": "X"}, provider=p)
    assert res.suggestions == ["fluff", "synergy", "circle back"]


def test_accepts_key_quotes_field():
    p = _FakeProvider('["You can\'t cheat physics.", "Speed is a moat."]')
    res = suggest_field("key_quotes", {"name": "X"}, provider=p)
    assert len(res.suggestions) == 2
    assert "physics" in res.suggestions[0]


def test_communication_avoid_prompt_explains_avoid_semantic():
    p = _FakeProvider('["X"]')
    suggest_field("communication_avoid", {"name": "Y"}, provider=p)
    assert "AVOID" in (p.last_prompt or "")


def test_key_quotes_prompt_asks_for_full_sentences():
    p = _FakeProvider('["X"]')
    suggest_field("key_quotes", {"name": "Y"}, provider=p)
    assert "sentences" in (p.last_prompt or "").lower()


def test_other_field_length_hints_unchanged():
    p = _FakeProvider('["X"]')
    suggest_field("mental_models", {"name": "Y"}, provider=p)
    assert "2-5 words" in (p.last_prompt or "")
