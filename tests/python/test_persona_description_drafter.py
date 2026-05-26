"""Tests for the description-only persona drafter (PR83a v3.3.0)."""

from __future__ import annotations

import json

import pytest

from core.personas.description_drafter import (
    PersonaDraftError,
    PersonaDraftResult,
    draft_persona_from_description,
)
from core.runtime.llm_provider import LLMResponse, LLMUnavailable


_VALID_PAYLOAD = {
    "title": "Direct-response copywriter",
    "tagline": "Make the offer so good, only an idiot says no.",
    "disc": {
        "primary": "D",
        "secondary": "I",
        "communication_style": "Punchy",
        "under_pressure": "Doubles down",
        "motivator": "Conversion lift",
    },
    "enneagram": {
        "type": 3,
        "wing": 8,
        "core_motivation": "Win at offers",
        "core_fear": "Being unremarkable",
        "subtype": "self-preservation",
    },
    "big_five": {
        "openness": 75,
        "conscientiousness": 80,
        "extraversion": 70,
        "agreeableness": 40,
        "neuroticism": 30,
    },
    "mbti": "ENTJ",
    "mental_models": ["Grand Slam Offer", "Value Equation"],
    "expertise_domains": ["copywriting", "offers"],
    "frameworks": ["AIDA", "PAS"],
    "key_quotes": [],
    "communication": {
        "tone": "Direct",
        "vocabulary_level": "specialist",
        "preferred_format": "Short hooks",
        "avoid": ["fluff"],
    },
}


class _FakeProvider:
    def __init__(self, text: str, name: str = "fake") -> None:
        self._text = text
        self._name = name
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    def complete(self, prompt: str, *, max_tokens: int = 3000, system: str = "") -> LLMResponse:
        self.last_prompt = prompt
        self.last_system = system
        return LLMResponse(text=self._text, tokens_in=0, tokens_out=0, cached_tokens=0, model="")

    def is_available(self) -> bool:
        return True

    def name(self) -> str:
        return self._name


class _UnavailableProvider(_FakeProvider):
    def complete(self, *_args, **_kwargs) -> LLMResponse:
        raise LLMUnavailable("provider down")


def _provider_with_payload(payload: dict) -> _FakeProvider:
    return _FakeProvider(json.dumps(payload))


def test_returns_persona_from_clean_json():
    p = _provider_with_payload(_VALID_PAYLOAD)
    res = draft_persona_from_description(
        "A direct-response copywriter who treats offers as the only true growth lever.",
        name="Alex Carter",
        provider=p,
    )
    assert isinstance(res, PersonaDraftResult)
    assert res.persona.name == "Alex Carter"
    assert res.persona.mbti == "ENTJ"
    assert str(res.persona.disc.primary) == "D"
    assert res.provider_name == "fake"


def test_passes_description_into_prompt():
    p = _provider_with_payload(_VALID_PAYLOAD)
    draft_persona_from_description(
        "A risk-loving founder who ships before polish and iterates in public.",
        name="Riley Foster",
        provider=p,
    )
    assert "Riley Foster" in (p.last_prompt or "")
    assert "risk-loving founder" in (p.last_prompt or "")


def test_uses_system_prompt():
    p = _provider_with_payload(_VALID_PAYLOAD)
    draft_persona_from_description(
        "A direct-response copywriter who treats offers as the only true growth lever.",
        name="Alex Carter",
        provider=p,
    )
    assert "JSON" in (p.last_system or "")


def test_falls_back_to_name_for_source_label():
    p = _provider_with_payload(_VALID_PAYLOAD)
    res = draft_persona_from_description(
        "A direct-response copywriter who treats offers as the only true growth lever.",
        name="Alex Carter",
        provider=p,
    )
    assert res.persona.source == "Alex Carter"


def test_explicit_source_label_used():
    p = _provider_with_payload(_VALID_PAYLOAD)
    res = draft_persona_from_description(
        "A direct-response copywriter who treats offers as the only true growth lever.",
        name="Alex Carter",
        source_label="Alex Carter — Copywriting Coach",
        provider=p,
    )
    assert res.persona.source == "Alex Carter — Copywriting Coach"


def test_rejects_short_description():
    p = _provider_with_payload(_VALID_PAYLOAD)
    with pytest.raises(PersonaDraftError, match="at least"):
        draft_persona_from_description("too short", name="X", provider=p)


def test_rejects_empty_name():
    p = _provider_with_payload(_VALID_PAYLOAD)
    with pytest.raises(PersonaDraftError, match="name"):
        draft_persona_from_description(
            "A direct-response copywriter who treats offers as the only true growth lever.",
            name="",
            provider=p,
        )


def test_rejects_non_json_output():
    p = _FakeProvider("Sorry, here's a persona: looks great!")
    with pytest.raises(PersonaDraftError, match="JSON object"):
        draft_persona_from_description(
            "A direct-response copywriter who treats offers as the only true growth lever.",
            name="Alex",
            provider=p,
        )


def test_handles_schema_mismatch():
    bad = {**_VALID_PAYLOAD, "big_five": {"openness": "not-a-number"}}
    p = _provider_with_payload(bad)
    with pytest.raises(PersonaDraftError, match="schema mismatch"):
        draft_persona_from_description(
            "A direct-response copywriter who treats offers as the only true growth lever.",
            name="Alex",
            provider=p,
        )


def test_propagates_llm_unavailable():
    p = _UnavailableProvider("")
    with pytest.raises(PersonaDraftError, match="provider down"):
        draft_persona_from_description(
            "A direct-response copywriter who treats offers as the only true growth lever.",
            name="Alex",
            provider=p,
        )


def test_strips_code_fences_via_extract_json():
    fenced = "```json\n" + json.dumps(_VALID_PAYLOAD) + "\n```"
    p = _FakeProvider(fenced)
    res = draft_persona_from_description(
        "A direct-response copywriter who treats offers as the only true growth lever.",
        name="Alex",
        provider=p,
    )
    assert res.persona.mbti == "ENTJ"


def test_key_quotes_empty_when_no_quotes_in_description():
    p = _provider_with_payload(_VALID_PAYLOAD)
    res = draft_persona_from_description(
        "A direct-response copywriter who treats offers as the only true growth lever.",
        name="Alex",
        provider=p,
    )
    assert res.persona.key_quotes == []
