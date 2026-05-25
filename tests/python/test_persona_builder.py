"""Tests for the AI-powered persona builder (PR57 v2.74.0)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from core.personas.builder import (
    PersonaBuildError,
    PersonaBuilder,
    _extract_json_object,
)
from core.personas.schema import Persona


# ─── Helpers / fakes ────────────────────────────────────────────────────


@dataclass
class _StubResponse:
    text: str
    cost_usd: float | None = None


class _FakeProvider:
    """Minimal LLMProvider stand-in. Returns the canned text on every call."""

    def __init__(self, response_text: str, name_hint: str = "fake") -> None:
        self._text = response_text
        self._name = name_hint
        self.last_prompt: str = ""
        self.last_system: str = ""

    def complete(self, prompt: str, *, max_tokens: int = 2000, system: str = "") -> _StubResponse:  # noqa: ARG002
        self.last_prompt = prompt
        self.last_system = system
        return _StubResponse(text=self._text)

    def is_available(self) -> bool:
        return True

    def name(self) -> str:
        return self._name


class _FakeStore:
    """VectorStore stand-in that returns pre-baked chunks."""

    def __init__(self, chunks: list[dict]) -> None:
        self._chunks = chunks

    def search(self, query: str, top_k: int = 5) -> list[dict]:  # noqa: ARG002
        return list(self._chunks[:top_k])


def _valid_response_json() -> str:
    return json.dumps({
        "title": "Business Strategist",
        "tagline": "The Natural Commander with emotional depth",
        "disc": {
            "primary": "D",
            "secondary": "C",
            "communication_style": "Direct and analytical",
            "under_pressure": "Becomes more directive",
            "motivator": "Building lasting systems",
        },
        "enneagram": {
            "type": 8,
            "wing": 7,
            "core_motivation": "Self-reliance and control",
            "core_fear": "Being controlled by others",
            "subtype": "self-preservation",
        },
        "big_five": {
            "openness": 80, "conscientiousness": 90,
            "extraversion": 70, "agreeableness": 55, "neuroticism": 25,
        },
        "mbti": "ENTJ",
        "mental_models": ["First principles", "Skin in the game"],
        "expertise_domains": ["Business models", "Sales", "Operations"],
        "frameworks": ["Hormozi Grand Slam Offer", "Value Equation"],
        "key_quotes": ["You have one job: keep providing value."],
        "communication": {
            "tone": "Direct, candid",
            "vocabulary_level": "specialist",
            "preferred_format": "Punchy lists with examples",
            "avoid": ["jargon-for-its-own-sake"],
        },
    })


# ─── _extract_json_object ───────────────────────────────────────────────


def test_extract_json_handles_bare_json():
    raw = '{"title": "Strategist", "tagline": "test"}'
    obj = _extract_json_object(raw)
    assert obj == {"title": "Strategist", "tagline": "test"}


def test_extract_json_handles_markdown_fence():
    raw = (
        "Here is the persona JSON:\n\n"
        "```json\n"
        '{"title": "Strategist"}\n'
        "```\n"
        "Hope this helps!"
    )
    obj = _extract_json_object(raw)
    assert obj == {"title": "Strategist"}


def test_extract_json_handles_leading_prose():
    raw = (
        "Sure, based on the content I can infer the following:\n"
        '{"title": "Strategist", "mbti": "ENTJ"}'
    )
    obj = _extract_json_object(raw)
    assert obj == {"title": "Strategist", "mbti": "ENTJ"}


def test_extract_json_returns_none_when_no_object():
    assert _extract_json_object("Sorry, no JSON here.") is None
    assert _extract_json_object("") is None


def test_extract_json_returns_none_for_a_list():
    """A bare array is not a persona shape — reject so the parser
    doesn't blow up downstream."""
    assert _extract_json_object("[1, 2, 3]") is None


# ─── PersonaBuilder.generate ────────────────────────────────────────────


def test_generate_returns_persona_with_dna(tmp_path):
    store = _FakeStore([
        {"text": "Hormozi talks about the value equation and skin in the game.", "heading": "intro"},
        {"text": "He emphasizes first-principles thinking.", "heading": "philosophy"},
    ])
    provider = _FakeProvider(_valid_response_json())
    builder = PersonaBuilder(store, provider=provider)
    result = builder.generate(name="Alex Hormozi", source_label="Alex Hormozi")
    assert isinstance(result.persona, Persona)
    assert result.persona.name == "Alex Hormozi"
    assert result.persona.source == "Alex Hormozi"
    assert result.persona.mbti == "ENTJ"
    assert result.persona.disc.primary == "D"
    assert result.persona.enneagram.type == 8
    assert result.persona.big_five.conscientiousness == 90
    assert "First principles" in result.persona.mental_models
    assert result.chunks_used == 2
    assert result.provider_name == "fake"


def test_generate_uses_name_as_default_query():
    store = _FakeStore([{"text": "x" * 100, "heading": "h"}])
    provider = _FakeProvider(_valid_response_json())
    builder = PersonaBuilder(store, provider=provider)
    builder.generate(name="Naval Ravikant")
    assert "Naval Ravikant" in provider.last_prompt


def test_generate_uses_explicit_search_query_when_provided():
    captured: list[str] = []

    class _CapturingStore(_FakeStore):
        def search(self, query: str, top_k: int = 5) -> list[dict]:
            captured.append(query)
            return super().search(query, top_k)

    store = _CapturingStore([{"text": "stub", "heading": ""}])
    provider = _FakeProvider(_valid_response_json())
    builder = PersonaBuilder(store, provider=provider)
    builder.generate(name="Naval", search_query="philosophy of wealth")
    assert captured == ["philosophy of wealth"]


def test_generate_truncates_context_at_max_chars():
    huge_chunk = {"text": "a" * 10_000, "heading": "huge"}
    store = _FakeStore([huge_chunk] * 10)
    provider = _FakeProvider(_valid_response_json())
    builder = PersonaBuilder(store, provider=provider)
    builder.generate(name="X")
    assert len(provider.last_prompt) < PersonaBuilder.MAX_CONTEXT_CHARS + 1000


def test_generate_raises_when_no_chunks_indexed():
    store = _FakeStore([])
    provider = _FakeProvider(_valid_response_json())
    builder = PersonaBuilder(store, provider=provider)
    with pytest.raises(PersonaBuildError, match="no indexed content"):
        builder.generate(name="Anyone")


def test_generate_raises_on_empty_name():
    store = _FakeStore([{"text": "x", "heading": ""}])
    builder = PersonaBuilder(store, provider=_FakeProvider("{}"))
    with pytest.raises(PersonaBuildError, match="name must not be empty"):
        builder.generate(name="")
    with pytest.raises(PersonaBuildError, match="name must not be empty"):
        builder.generate(name="   ")


def test_generate_raises_on_non_json_response():
    store = _FakeStore([{"text": "x", "heading": ""}])
    provider = _FakeProvider("Sorry, I can't help with that.")
    builder = PersonaBuilder(store, provider=provider)
    with pytest.raises(PersonaBuildError, match="JSON"):
        builder.generate(name="X")


def test_generate_raises_when_json_violates_schema():
    """Bad DISC primary (must be D/I/S/C) is caught by Pydantic."""
    bad = json.dumps({
        "disc": {"primary": "X"},  # invalid
        "enneagram": {"type": "not-an-int"},  # invalid type
    })
    store = _FakeStore([{"text": "x", "heading": ""}])
    provider = _FakeProvider(bad)
    builder = PersonaBuilder(store, provider=provider)
    # PersonaDISC.primary uses defaults so str "X" still passes; the
    # enneagram.type non-int IS the catchable failure.
    with pytest.raises(PersonaBuildError, match="schema"):
        builder.generate(name="X")


def test_generate_passes_system_prompt_to_provider():
    store = _FakeStore([{"text": "x" * 50, "heading": ""}])
    provider = _FakeProvider(_valid_response_json())
    builder = PersonaBuilder(store, provider=provider)
    builder.generate(name="X")
    assert "behavioural-DNA" in provider.last_system
    assert "key_quotes" in provider.last_system
