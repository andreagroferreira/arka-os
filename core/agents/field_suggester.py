"""AI-assisted list-field suggester for agents and personas (PR81).

Generates short lists of `mental_models`, `frameworks`, or
`expertise_domains` for an entity given its existing context.

The LLM is told NOT to duplicate items already present in
`context["current"]`, and to return a strict JSON array of strings.

Used by:
- POST /api/agents/suggest   — ✨ Suggest button in AgentEditDrawer
- POST /api/personas/suggest — ✨ Suggest button in persona edit slideover

The module is provider-agnostic: callers can inject a fake `LLMProvider`
in tests, and production callers fall back to `get_llm_provider()`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from core.runtime.llm_provider import LLMProvider, LLMUnavailable, get_llm_provider


_VALID_FIELDS: tuple[str, ...] = (
    "mental_models",
    "frameworks",
    "expertise_domains",
)
_MAX_COUNT = 12
_DEFAULT_COUNT = 5

_SYSTEM = (
    "You suggest short, concrete items for behavioural agent and persona "
    "profiles. Return ONLY a JSON array of strings. No prose, no fences, no keys."
)

_FIELD_LABELS: dict[str, str] = {
    "mental_models": "mental models",
    "frameworks": "frameworks",
    "expertise_domains": "expertise domains",
}


class SuggestionError(RuntimeError):
    """LLM produced unusable output or could not be reached."""


@dataclass(frozen=True)
class SuggestionResult:
    suggestions: list[str]
    provider_name: str


def suggest_field(
    field: str,
    context: dict,
    *,
    count: int = _DEFAULT_COUNT,
    provider: LLMProvider | None = None,
) -> SuggestionResult:
    """Return up to `count` AI-suggested items for the named field."""
    if field not in _VALID_FIELDS:
        raise SuggestionError(f"unknown field: {field!r}")
    count = max(1, min(_MAX_COUNT, int(count)))
    llm = provider or get_llm_provider()
    prompt = _build_prompt(field, context, count)
    try:
        resp = llm.complete(prompt, max_tokens=600, system=_SYSTEM)
    except LLMUnavailable as exc:
        raise SuggestionError(str(exc)) from exc
    items = _parse(resp.text)
    deduped = _dedupe_against_current(items, context.get("current") or [])
    return SuggestionResult(
        suggestions=deduped[:count],
        provider_name=llm.name(),
    )


def _build_prompt(field: str, context: dict, count: int) -> str:
    name = (context.get("name") or "").strip() or "the entity"
    role = (context.get("role") or context.get("title") or "").strip()
    department = (context.get("department") or "").strip()
    current = list(context.get("current") or [])[:20]
    lines = [f"Suggest {count} new {_FIELD_LABELS[field]} for {name}."]
    if role:
        lines.append(f"Role: {role}.")
    if department:
        lines.append(f"Department: {department}.")
    if current:
        lines.append(
            "Do NOT repeat any of these items already in the profile: "
            + ", ".join(current)
            + "."
        )
    lines.append(
        "Return a JSON array of short strings (2-5 words each). "
        "No explanations, no numbering, no surrounding object."
    )
    return "\n".join(lines)


def _parse(text: str) -> list[str]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return _fallback_lines(cleaned)
    if not isinstance(data, list):
        return _fallback_lines(cleaned)
    return [str(x).strip() for x in data if str(x).strip()]


def _fallback_lines(text: str) -> list[str]:
    items: list[str] = []
    for raw in re.split(r"[\n,]", text):
        line = raw.strip(" \t-*•·0123456789.).\"'`")
        if line and 2 <= len(line) <= 80:
            items.append(line)
    return items


def _dedupe_against_current(items: list[str], current: list) -> list[str]:
    seen = {str(c).strip().lower() for c in current}
    out: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            out.append(item)
            seen.add(key)
    return out
