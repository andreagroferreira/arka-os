"""AI-powered persona builder (PR57 v2.74.0).

Generates a draft Persona from already-indexed content in the vector
store. The user ingests sources (YouTube transcripts, articles, PDFs)
via the knowledge dashboard, then the builder:

1. Searches the vector store for chunks about the target person/topic.
2. Sends those chunks to the configured LLM via the multi-backend
   `LLMProvider` (Claude Code subagent / Anthropic API / Ollama local).
3. Parses the LLM's JSON response into a `Persona` draft for the
   operator to review and edit before saving.

The builder NEVER writes to the database — that's the existing
`PersonaManager.create()` path. The builder produces a draft; the
operator owns the persist decision (per the project memory's
"Generated persona presented for review" step).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from core.knowledge.vector_store import VectorStore
from core.personas.schema import (
    Persona,
    PersonaBigFive,
    PersonaCommunication,
    PersonaDISC,
    PersonaEnneagram,
)
from core.runtime.llm_provider import LLMProvider, get_llm_provider


_PERSONA_SYSTEM_PROMPT = """You build behavioural-DNA personas from quotes
and writings of real people. Read the supplied content carefully, then
emit a single JSON object that follows this exact schema. Use ONLY the
JSON keys listed — no prose, no markdown fences, no extra fields.

{
  "title": "<one-line role label>",
  "tagline": "<one-line essence>",
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
  "mbti": "<4-letter type>",
  "mental_models": ["<model>", ...],
  "expertise_domains": ["<domain>", ...],
  "frameworks": ["<framework>", ...],
  "key_quotes": ["<verbatim quote>", ...],
  "communication": {
    "tone": "<adjective>",
    "vocabulary_level": "lay|specialist|expert",
    "preferred_format": "<format hint>",
    "avoid": ["<phrase to avoid>", ...]
  }
}

If the content is insufficient to infer a field, use the closest neutral
default rather than fabricating. NEVER invent quotes — only include
verbatim text that appears in the content."""


@dataclass(frozen=True)
class BuildResult:
    """Output of a persona-builder run."""

    persona: Persona
    chunks_used: int
    provider_name: str
    raw_response: str


class PersonaBuildError(RuntimeError):
    """Raised when the LLM response can't be parsed into a Persona."""


class PersonaBuilder:
    """Generate persona drafts from indexed content."""

    MAX_CONTEXT_CHARS = 18_000

    def __init__(
        self,
        store: VectorStore,
        provider: LLMProvider | None = None,
    ) -> None:
        self._store = store
        self._provider = provider or get_llm_provider()

    def generate(
        self,
        name: str,
        search_query: str = "",
        top_k: int = 20,
        source_label: str = "",
    ) -> BuildResult:
        """Build a persona draft for `name`.

        Searches the vector store for `search_query` (defaults to the
        name), truncates the joined chunks to MAX_CONTEXT_CHARS, sends
        them to the configured LLM, parses the JSON response, and
        returns a draft Persona plus telemetry.
        """
        if not name or not name.strip():
            raise PersonaBuildError("name must not be empty")
        query = (search_query or name).strip()
        chunks = self._store.search(query, top_k=top_k)
        if not chunks:
            raise PersonaBuildError(
                f"no indexed content matches {query!r} — "
                "ingest sources first via /api/knowledge/ingest"
            )
        context = self._compose_context(chunks)
        prompt = f"Person: {name}\n\nContent:\n{context}"
        response = self._provider.complete(
            prompt, system=_PERSONA_SYSTEM_PROMPT, max_tokens=3000,
        )
        persona = self._parse(name, source_label or name, response.text)
        return BuildResult(
            persona=persona,
            chunks_used=len(chunks),
            provider_name=self._provider.name(),
            raw_response=response.text,
        )

    def _compose_context(self, chunks: list[dict]) -> str:
        parts: list[str] = []
        total = 0
        for chunk in chunks:
            text = chunk.get("text") or ""
            if not text:
                continue
            if total + len(text) > self.MAX_CONTEXT_CHARS:
                break
            heading = chunk.get("heading") or ""
            block = f"[{heading}]\n{text}" if heading else text
            parts.append(block)
            total += len(block)
        return "\n\n---\n\n".join(parts)

    def _parse(self, name: str, source_label: str, raw: str) -> Persona:
        data = _extract_json_object(raw)
        if data is None:
            raise PersonaBuildError(
                f"LLM did not return a JSON object; raw response: {raw[:200]!r}"
            )
        now = datetime.now(timezone.utc).isoformat()
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
                mbti=str(data.get("mbti") or "INTJ"),
                mental_models=_as_str_list(data.get("mental_models")),
                expertise_domains=_as_str_list(data.get("expertise_domains")),
                frameworks=_as_str_list(data.get("frameworks")),
                key_quotes=_as_str_list(data.get("key_quotes")),
                communication=PersonaCommunication(
                    **(data.get("communication") or {})
                ),
                created_at=now,
                updated_at=now,
            )
        except (TypeError, ValueError) as exc:
            raise PersonaBuildError(
                f"LLM JSON does not match Persona schema: {exc}"
            ) from exc


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(raw: str) -> dict | None:
    """Parse the first JSON object in `raw`.

    Tolerates models that wrap JSON in markdown fences or add a leading
    explanation. Returns None when no parseable object is found.
    """
    if not raw:
        return None
    candidates = [raw.strip()]
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL,
    )
    if fence_match:
        candidates.insert(0, fence_match.group(1))
    bare_match = _JSON_OBJECT_RE.search(raw)
    if bare_match:
        candidates.append(bare_match.group(0))
    for cand in candidates:
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]
