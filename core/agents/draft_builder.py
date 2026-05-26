"""AI-powered agent draft builder (PR82b v3.1.0).

Given a free-text description (and optionally a name/role/department),
produce a full agent draft: behavioural DNA, expertise, mental models,
and communication block — all in one LLM call.

Used by `POST /api/agents/draft` to power the "AI draft from
description" textarea on `/agents/new`. The operator then reviews and
edits the generated draft before clicking Create.

Provider-agnostic: callers can inject a fake `LLMProvider` in tests.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from core.runtime.llm_provider import LLMProvider, LLMUnavailable, get_llm_provider


_SYSTEM = """You design behavioural-DNA profiles for AI agents. Read the
operator's description carefully, then emit a single JSON object that
follows this exact schema. Use ONLY the JSON keys listed — no prose,
no markdown fences, no extra fields.

{
  "behavioral_dna": {
    "disc": {
      "primary": "D|I|S|C",
      "secondary": "D|I|S|C",
      "communication_style": "<one sentence>",
      "under_pressure": "<one sentence>",
      "motivator": "<one sentence>"
    },
    "enneagram": {
      "type": 1-9,
      "wing": 1-9,
      "core_motivation": "<one sentence>",
      "core_fear": "<one sentence>",
      "subtype": "self-preservation|social|sexual"
    },
    "big_five": {
      "openness": 0-100,
      "conscientiousness": 0-100,
      "extraversion": 0-100,
      "agreeableness": 0-100,
      "neuroticism": 0-100
    },
    "mbti": "<4-letter type>"
  },
  "expertise": {
    "domains": ["<domain>", ...],
    "frameworks": ["<framework>", ...],
    "depth": "intermediate|advanced|expert|master",
    "years_equivalent": <int>
  },
  "mental_models": {
    "primary": ["<model>", ...],
    "secondary": ["<model>", ...]
  },
  "communication": {
    "tone": "<adjective list>",
    "vocabulary_level": "lay|specialist|expert",
    "preferred_format": "<format hint>",
    "language": "<two-letter code, e.g. en>",
    "avoid": ["<phrase>", ...]
  }
}

Rules:
- DISC primary MUST differ from secondary.
- Pick concrete frameworks (e.g. "Porter's Five Forces") not abstract verbs.
- Provide 4-8 expertise.domains, 4-8 expertise.frameworks, 3-6 mental_models.primary.
- Keep all string values terse and concrete."""


class DraftError(RuntimeError):
    """LLM produced unusable output or could not be reached."""


@dataclass(frozen=True)
class DraftResult:
    draft: dict
    provider_name: str


def draft_agent(
    description: str,
    *,
    name: str = "",
    role: str = "",
    department: str = "",
    tier: int = 2,
    provider: LLMProvider | None = None,
) -> DraftResult:
    """Return a full agent draft inferred from a free-text description."""
    description = (description or "").strip()
    if len(description) < 20:
        raise DraftError("description must be at least 20 characters")
    llm = provider or get_llm_provider()
    prompt = _build_prompt(description, name, role, department, tier)
    try:
        resp = llm.complete(prompt, max_tokens=2000, system=_SYSTEM)
    except LLMUnavailable as exc:
        raise DraftError(str(exc)) from exc
    draft = _parse(resp.text)
    _validate(draft)
    return DraftResult(draft=draft, provider_name=llm.name())


def _build_prompt(description: str, name: str, role: str, department: str, tier: int) -> str:
    lines = ["Design an agent profile from this description:", "", description.strip(), ""]
    if name:
        lines.append(f"Name: {name}")
    if role:
        lines.append(f"Role: {role}")
    if department:
        lines.append(f"Department: {department}")
    lines.append(f"Tier: {tier}")
    lines.append("")
    lines.append("Return ONLY the JSON object — no prose, no markdown fences.")
    return "\n".join(lines)


def _parse(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        raise DraftError(f"LLM returned non-JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DraftError("LLM returned a non-object JSON value")
    return data


def _validate(draft: dict) -> None:
    """Sanity-check the LLM payload — catches the common failure modes
    before the operator sees a half-broken form."""
    dna = draft.get("behavioral_dna")
    if not isinstance(dna, dict):
        raise DraftError("missing behavioral_dna block")
    disc = dna.get("disc") or {}
    if disc.get("primary") and disc.get("primary") == disc.get("secondary"):
        raise DraftError("DISC primary and secondary must differ")
    valid_disc = {"D", "I", "S", "C"}
    if disc.get("primary") and str(disc["primary"]).upper() not in valid_disc:
        raise DraftError(f"invalid DISC primary: {disc.get('primary')!r}")
    if disc.get("secondary") and str(disc["secondary"]).upper() not in valid_disc:
        raise DraftError(f"invalid DISC secondary: {disc.get('secondary')!r}")
    big_five = dna.get("big_five") or {}
    for axis, value in big_five.items():
        if not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise DraftError(f"big_five.{axis} must be 0..100, got {value!r}")
