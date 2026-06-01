"""Semantic agent attribution for a knowledge source (PR3).

Given the knowledge text of a source, suggest WHICH agents should learn
from it by comparing the source text against each agent's expertise
profile via local embeddings (``core.knowledge.embedder``).

Pure and propose-only: this module reads agent dicts passed in by the
caller and NEVER writes agent YAMLs. It degrades gracefully — when the
embedder is unavailable (fastembed missing) or the source text is empty
it returns an empty list, and the caller surfaces a reason.

The registry stores ``expertise_domains`` and ``frameworks`` as flat
list keys on each agent dict (not nested under an ``expertise`` object).
"""

from __future__ import annotations

import math

from core.knowledge import embedder

_PROFILE_FIELDS = ("expertise_domains", "frameworks")
_MAX_MATCHED_TERMS = 5


def agent_profile_text(agent: dict) -> str:
    """Build one searchable string from an agent's role + expertise.

    Concatenates role, expertise domains, frameworks, and (optionally)
    name into a single space-joined string suitable for embedding. Empty
    fields are skipped so a sparse agent still yields a clean profile.
    """
    parts: list[str] = []
    name = str(agent.get("name") or "").strip()
    role = str(agent.get("role") or "").strip()
    if role:
        parts.append(role)
    for field in _PROFILE_FIELDS:
        parts.extend(str(v).strip() for v in agent.get(field) or [] if str(v).strip())
    if name:
        parts.append(name)
    return " ".join(parts)


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors; 0.0 if either is empty/zero-norm."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _profile_texts(agents: list[dict]) -> list[str]:
    """Profile text for each agent, preserving order."""
    return [agent_profile_text(agent) for agent in agents]


def _explain_match(source_text: str, agent: dict) -> list[str]:
    """Up to 5 expertise/framework terms that textually appear in source.

    A cheap, case-insensitive substring "why" explanation — independent of
    the embedding similarity — so the proposal can show concrete overlap.
    """
    haystack = source_text.lower()
    matched: list[str] = []
    for field in _PROFILE_FIELDS:
        for term in agent.get(field) or []:
            clean = str(term).strip()
            if clean and clean.lower() in haystack and clean not in matched:
                matched.append(clean)
                if len(matched) >= _MAX_MATCHED_TERMS:
                    return matched
    return matched


def _build_result(source_text: str, agent: dict, score: float) -> dict:
    """Shape one ranked match for the API response."""
    return {
        "id": agent.get("id", ""),
        "name": agent.get("name", ""),
        "department": agent.get("department", ""),
        "role": agent.get("role", ""),
        "score": round(score, 3),
        "matched_terms": _explain_match(source_text, agent),
    }


def match_agents(source_text: str, agents: list[dict], top_n: int = 5) -> list[dict]:
    """Rank agents by semantic similarity of their expertise to the source.

    Returns ``[]`` when ``source_text`` is empty or the embedder is
    unavailable (caller surfaces a reason). Embeds the source once and the
    agent profiles in a single batch, then sorts by cosine descending and
    returns the top ``top_n`` results, each with id/name/department/role/
    score (0..1, 3dp) and matched_terms. Never writes anything.
    """
    if not source_text.strip() or not agents:
        return []
    source_vec = embedder.embed(source_text)
    if source_vec is None:
        return []
    agent_vecs = embedder.embed_batch(_profile_texts(agents))
    if agent_vecs is None:
        return []
    scored = [
        _build_result(source_text, agent, cosine(source_vec, vec))
        for agent, vec in zip(agents, agent_vecs)
    ]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[: max(top_n, 0)]
