"""Tests for the AI agent draft builder (PR82b v3.1.0)."""

from __future__ import annotations

import json

import pytest

from core.agents.draft_builder import DraftError, DraftResult, draft_agent
from core.runtime.llm_provider import LLMResponse, LLMUnavailable


_VALID_PAYLOAD = {
    "behavioral_dna": {
        "disc": {
            "primary": "D",
            "secondary": "C",
            "communication_style": "Direct",
            "under_pressure": "Decisive",
            "motivator": "Impact",
        },
        "enneagram": {
            "type": 8,
            "wing": 7,
            "core_motivation": "Control",
            "core_fear": "Vulnerability",
            "subtype": "self-preservation",
        },
        "big_five": {
            "openness": 80,
            "conscientiousness": 85,
            "extraversion": 60,
            "agreeableness": 40,
            "neuroticism": 25,
        },
        "mbti": "ENTJ",
    },
    "expertise": {
        "domains": ["strategy", "operations"],
        "frameworks": ["BCG Matrix", "OKRs"],
        "depth": "expert",
        "years_equivalent": 10,
    },
    "mental_models": {"primary": ["First Principles"], "secondary": []},
    "communication": {
        "tone": "Crisp",
        "vocabulary_level": "expert",
        "preferred_format": "Executive memos",
        "language": "en",
        "avoid": ["fluff"],
    },
}


class _FakeProvider:
    def __init__(self, text: str, name: str = "fake") -> None:
        self._text = text
        self._name = name
        self.last_prompt: str | None = None
        self.last_system: str | None = None

    def complete(self, prompt: str, *, max_tokens: int = 2000, system: str = "") -> LLMResponse:
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


def _provider_with_payload(payload: dict) -> _FakeProvider:
    return _FakeProvider(json.dumps(payload))


def test_returns_draft_from_clean_json():
    p = _provider_with_payload(_VALID_PAYLOAD)
    res = draft_agent(
        "A senior strategist who decides fast and demands evidence.",
        name="Tomas",
        role="Chief Strategist",
        department="strategy",
        provider=p,
    )
    assert isinstance(res, DraftResult)
    assert res.draft["behavioral_dna"]["disc"]["primary"] == "D"
    assert res.provider_name == "fake"


def test_passes_inputs_into_prompt():
    p = _provider_with_payload(_VALID_PAYLOAD)
    draft_agent(
        "Analytical contrarian with a love for evidence-driven debate.",
        name="Mara",
        role="Research Lead",
        department="strategy",
        provider=p,
    )
    assert "Mara" in (p.last_prompt or "")
    assert "Research Lead" in (p.last_prompt or "")
    assert "strategy" in (p.last_prompt or "")


def test_strips_json_fences():
    p = _FakeProvider("```json\n" + json.dumps(_VALID_PAYLOAD) + "\n```")
    res = draft_agent(
        "Operations specialist who keeps the trains running on time.",
        provider=p,
    )
    assert res.draft["behavioral_dna"]["mbti"] == "ENTJ"


def test_rejects_short_description():
    p = _provider_with_payload(_VALID_PAYLOAD)
    with pytest.raises(DraftError, match="20 characters"):
        draft_agent("too short", provider=p)


def test_rejects_non_json_output():
    p = _FakeProvider("Here is the agent: looks great!")
    with pytest.raises(DraftError, match="non-JSON"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_rejects_non_object_root():
    p = _FakeProvider('["not", "an", "object"]')
    with pytest.raises(DraftError, match="non-object"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_rejects_missing_behavioral_dna():
    payload = {"expertise": {}}
    p = _provider_with_payload(payload)
    with pytest.raises(DraftError, match="behavioral_dna"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_rejects_disc_primary_equal_to_secondary():
    payload = dict(_VALID_PAYLOAD)
    payload["behavioral_dna"] = dict(payload["behavioral_dna"])
    payload["behavioral_dna"]["disc"] = {"primary": "D", "secondary": "D"}
    p = _provider_with_payload(payload)
    with pytest.raises(DraftError, match="must differ"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_rejects_invalid_disc_letter():
    payload = dict(_VALID_PAYLOAD)
    payload["behavioral_dna"] = dict(payload["behavioral_dna"])
    payload["behavioral_dna"]["disc"] = {"primary": "X", "secondary": "C"}
    p = _provider_with_payload(payload)
    with pytest.raises(DraftError, match="invalid DISC"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_rejects_big_five_out_of_range():
    payload = dict(_VALID_PAYLOAD)
    payload["behavioral_dna"] = dict(payload["behavioral_dna"])
    payload["behavioral_dna"]["big_five"] = {"openness": 150}
    p = _provider_with_payload(payload)
    with pytest.raises(DraftError, match="0..100"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_propagates_llm_unavailable_as_draft_error():
    p = _UnavailableProvider("")
    with pytest.raises(DraftError, match="provider down"):
        draft_agent(
            "Operations specialist who keeps the trains running on time.",
            provider=p,
        )


def test_prompt_includes_tier():
    p = _provider_with_payload(_VALID_PAYLOAD)
    draft_agent(
        "Strategic generalist with deep ops chops.",
        tier=1,
        provider=p,
    )
    assert "Tier: 1" in (p.last_prompt or "")


def test_works_without_name_or_role():
    p = _provider_with_payload(_VALID_PAYLOAD)
    res = draft_agent(
        "A wise sage who advises on long-range strategic moves.",
        provider=p,
    )
    assert res.draft["behavioral_dna"]["mbti"] == "ENTJ"
