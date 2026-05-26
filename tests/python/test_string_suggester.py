"""Tests for the AI single-string suggester (PR83c v3.5.0)."""

from __future__ import annotations

import pytest

from core.agents.string_suggester import (
    StringSuggestionError,
    StringSuggestionResult,
    suggest_string_field,
)
from core.runtime.llm_provider import LLMResponse, LLMUnavailable


class _FakeProvider:
    def __init__(self, text: str = "", name: str = "fake") -> None:
        self._text = text
        self._name = name
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    def complete(self, prompt: str, *, max_tokens: int = 200, system: str = "") -> LLMResponse:
        self.last_prompt = prompt
        self.last_system = system
        return LLMResponse(
            text=self._text, tokens_in=0, tokens_out=0, cached_tokens=0, model="",
        )

    def is_available(self) -> bool:
        return True

    def name(self) -> str:
        return self._name


class _UnavailableProvider(_FakeProvider):
    def complete(self, *_args, **_kwargs) -> LLMResponse:
        raise LLMUnavailable("provider down")


def test_returns_string_result():
    p = _FakeProvider("Direct, analytical, crisp")
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert isinstance(res, StringSuggestionResult)
    assert res.value == "Direct, analytical, crisp"
    assert res.provider_name == "fake"


def test_strips_surrounding_double_quotes():
    p = _FakeProvider('"Direct, analytical"')
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert res.value == "Direct, analytical"


def test_strips_surrounding_single_quotes():
    p = _FakeProvider("'Crisp'")
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert res.value == "Crisp"


def test_strips_code_fences():
    p = _FakeProvider("```\nBriefs, tables\n```")
    res = suggest_string_field("preferred_format", {"name": "X"}, provider=p)
    assert res.value == "Briefs, tables"


def test_strips_leading_bullet():
    p = _FakeProvider("- Briefs, tables")
    res = suggest_string_field("preferred_format", {"name": "X"}, provider=p)
    assert res.value == "Briefs, tables"


def test_strips_leading_numbering():
    p = _FakeProvider("1. Direct, analytical")
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert res.value == "Direct, analytical"


def test_collapses_internal_whitespace():
    p = _FakeProvider("Direct,    analytical")
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert res.value == "Direct, analytical"


def test_truncates_at_field_max_for_tone():
    p = _FakeProvider("A" * 200)
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert len(res.value) == 60


def test_truncates_at_field_max_for_language():
    p = _FakeProvider("en-US, pt-PT, es-ES, fr-FR, de-DE, it-IT, ja-JP")
    res = suggest_string_field("language", {"name": "X"}, provider=p)
    assert len(res.value) <= 20


def test_rejects_unknown_field():
    p = _FakeProvider("X")
    with pytest.raises(StringSuggestionError, match="unknown field"):
        suggest_string_field("bogus", {}, provider=p)


def test_rejects_empty_output():
    p = _FakeProvider("")
    with pytest.raises(StringSuggestionError, match="empty"):
        suggest_string_field("tone", {"name": "X"}, provider=p)


def test_propagates_llm_unavailable():
    p = _UnavailableProvider()
    with pytest.raises(StringSuggestionError, match="provider down"):
        suggest_string_field("tone", {"name": "X"}, provider=p)


def test_prompt_includes_current_when_replacing():
    p = _FakeProvider("New tone")
    suggest_string_field(
        "tone", {"name": "X", "current": "old tone"}, provider=p,
    )
    assert "old tone" in (p.last_prompt or "")


def test_prompt_includes_role():
    p = _FakeProvider("X")
    suggest_string_field("tone", {"name": "Y", "role": "CFO"}, provider=p)
    assert "CFO" in (p.last_prompt or "")


def test_prompt_includes_department():
    p = _FakeProvider("X")
    suggest_string_field(
        "tone", {"name": "Y", "department": "finance"}, provider=p,
    )
    assert "finance" in (p.last_prompt or "")


def test_field_specific_hints_in_prompt():
    p = _FakeProvider("X")
    suggest_string_field("language", {"name": "Y"}, provider=p)
    assert "IETF" in (p.last_prompt or "")


def test_strips_trailing_period():
    p = _FakeProvider("Direct, analytical.")
    res = suggest_string_field("tone", {"name": "X"}, provider=p)
    assert res.value == "Direct, analytical"
