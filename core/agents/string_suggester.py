"""AI-assisted single-string suggester (PR83c v3.5.0).

Sibling to `core/agents/field_suggester` but for fields that hold ONE
string value (not a list). Used by the ✨ Generate button next to
fields like `communication.tone`, `communication.preferred_format`,
and `communication.language`.

Where the list suggester APPENDS, this one REPLACES. The caller is
expected to swap the field's existing value with the result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.runtime.llm_provider import LLMProvider, LLMUnavailable, get_llm_provider


_VALID_FIELDS: tuple[str, ...] = ("tone", "preferred_format", "language")

_SYSTEM = (
    "You suggest concise single-string values for behavioural agent and "
    "persona profile fields. Return ONLY the value as plain text — no "
    "JSON, no fences, no quotes, no explanations."
)

_FIELD_HINTS: dict[str, str] = {
    "tone": (
        "Return 2-4 adjectives separated by commas describing the "
        "profile's voice (e.g. 'Direct, analytical, crisp'). "
        "Max 60 characters."
    ),
    "preferred_format": (
        "Return a short noun phrase listing the formats this profile "
        "prefers (e.g. 'Briefs, tables, ASCII diagrams'). Max 80 characters."
    ),
    "language": (
        "Return a comma-separated list of IETF language tags this profile "
        "writes in (e.g. 'en' or 'en, pt-PT'). Max 20 characters."
    ),
}

_MAX_LEN: dict[str, int] = {"tone": 60, "preferred_format": 80, "language": 20}


class StringSuggestionError(RuntimeError):
    """LLM produced unusable output or could not be reached."""


@dataclass(frozen=True)
class StringSuggestionResult:
    value: str
    provider_name: str


def suggest_string_field(
    field: str,
    context: dict,
    *,
    provider: LLMProvider | None = None,
) -> StringSuggestionResult:
    """Return an AI-suggested single-string value for `field`."""
    if field not in _VALID_FIELDS:
        raise StringSuggestionError(f"unknown field: {field!r}")
    llm = provider or get_llm_provider()
    prompt = _build_prompt(field, context)
    try:
        resp = llm.complete(prompt, max_tokens=200, system=_SYSTEM)
    except LLMUnavailable as exc:
        raise StringSuggestionError(str(exc)) from exc
    value = _clean(resp.text, field)
    if not value:
        raise StringSuggestionError("LLM returned an empty value")
    return StringSuggestionResult(value=value, provider_name=llm.name())


def _build_prompt(field: str, context: dict) -> str:
    name = (context.get("name") or "").strip() or "the entity"
    role = (context.get("role") or context.get("title") or "").strip()
    department = (context.get("department") or "").strip()
    current = (context.get("current") or "").strip()
    lines = [f"Suggest a {field.replace('_', ' ')} for {name}."]
    if role:
        lines.append(f"Role: {role}.")
    if department:
        lines.append(f"Department: {department}.")
    if current:
        lines.append(f"Current value (to be replaced, do not repeat verbatim): {current}.")
    lines.append(_FIELD_HINTS[field])
    return "\n".join(lines)


def _clean(text: str, field: str) -> str:
    """Strip fences, quotes, leading bullets and trim to the field's max."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:\w+)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    # Remove surrounding quotes the LLM may add.
    if len(cleaned) >= 2 and cleaned[0] in '"\'`' and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1].strip()
    # Drop a leading bullet/numbering.
    cleaned = re.sub(r"^[-*•·]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
    # Single-line: collapse internal whitespace, drop trailing punctuation.
    cleaned = " ".join(cleaned.split())
    cleaned = cleaned.rstrip(".")
    max_len = _MAX_LEN[field]
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(", ").rstrip()
    return cleaned
