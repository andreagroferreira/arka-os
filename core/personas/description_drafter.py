"""AI-powered persona draft from a free-text description (PR83a v3.3.0).

Sibling to `core/personas/builder.PersonaBuilder` but does NOT require
indexed content. Useful when:

- The operator wants to model a persona quickly without ingesting sources
- A YouTuber / author isn't yet in the knowledge base
- The persona is a synthetic archetype rather than a real person

Reuses the same JSON schema and parsing as the vector-driven builder so
the resulting Persona is interchangeable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from core.personas.builder import (
    _PERSONA_SYSTEM_PROMPT,
    _extract_json_object,
)
from core.personas.schema import (
    Persona,
    PersonaBigFive,
    PersonaCommunication,
    PersonaDISC,
    PersonaEnneagram,
)
from core.runtime.llm_provider import LLMProvider, LLMUnavailable, get_llm_provider


_DESCRIPTION_MIN_CHARS = 20


class PersonaDraftError(RuntimeError):
    """LLM produced unusable output or could not be reached."""


@dataclass(frozen=True)
class PersonaDraftResult:
    persona: Persona
    provider_name: str
    raw_response: str


def draft_persona_from_description(
    description: str,
    *,
    name: str,
    source_label: str = "",
    provider: LLMProvider | None = None,
) -> PersonaDraftResult:
    """Generate a Persona draft from a free-text description."""
    description = (description or "").strip()
    if not name or not name.strip():
        raise PersonaDraftError("name must not be empty")
    if len(description) < _DESCRIPTION_MIN_CHARS:
        raise PersonaDraftError(
            f"description must be at least {_DESCRIPTION_MIN_CHARS} characters"
        )
    llm = provider or get_llm_provider()
    prompt = _build_prompt(name.strip(), description)
    try:
        resp = llm.complete(prompt, max_tokens=3000, system=_PERSONA_SYSTEM_PROMPT)
    except LLMUnavailable as exc:
        raise PersonaDraftError(str(exc)) from exc
    persona = _parse(name.strip(), source_label.strip() or name.strip(), resp.text)
    return PersonaDraftResult(
        persona=persona, provider_name=llm.name(), raw_response=resp.text,
    )


def _build_prompt(name: str, description: str) -> str:
    return (
        f"Person: {name}\n\n"
        f"Description provided by the operator:\n{description}\n\n"
        "Build the persona purely from the description above. If a field is "
        "not implied, choose the closest neutral default rather than "
        "fabricating. NEVER invent quotes — leave key_quotes empty if no "
        "quotes are present in the description."
    )


def _parse(name: str, source_label: str, raw: str) -> Persona:
    data = _extract_json_object(raw)
    if data is None:
        raise PersonaDraftError(
            f"LLM did not return a JSON object; raw response: {raw[:200]!r}"
        )
    try:
        return Persona(
            id=str(uuid.uuid4()),
            name=name,
            title=str(data.get("title") or ""),
            tagline=str(data.get("tagline") or ""),
            source=source_label,
            disc=PersonaDISC(**(data.get("disc") or {})),
            enneagram=PersonaEnneagram(**(data.get("enneagram") or {})),
            big_five=PersonaBigFive(**(data.get("big_five") or {})),
            mbti=str(data.get("mbti") or "").upper() or "INTJ",
            mental_models=[str(x) for x in (data.get("mental_models") or [])],
            expertise_domains=[str(x) for x in (data.get("expertise_domains") or [])],
            frameworks=[str(x) for x in (data.get("frameworks") or [])],
            key_quotes=[str(x) for x in (data.get("key_quotes") or [])],
            communication=PersonaCommunication(**(data.get("communication") or {})),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except (TypeError, ValueError) as exc:
        raise PersonaDraftError(f"persona schema mismatch: {exc}") from exc
