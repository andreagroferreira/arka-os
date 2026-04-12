"""AI-backed decider for MCPs the policy could not classify.

Falls back to deterministic heuristic (defer all unknowns) when the AI
is unavailable or a call fails. Decisions are cached on disk keyed by
(stack, ecosystem, mcp_name) to guarantee idempotence across runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable


class AIUnavailable(RuntimeError):
    pass


AiCaller = Callable[[str, list[str], str | None], str]


def decide_ambiguous(
    ambiguous: list[str],
    stack: list[str],
    ecosystem: str | None,
    cache_path: Path,
    call_ai: AiCaller | None,
) -> dict[str, str]:
    if not ambiguous:
        return {}

    cache = _load_cache(cache_path)
    result: dict[str, str] = {}

    for mcp in ambiguous:
        key = _cache_key(mcp, stack, ecosystem)
        cached = cache.get(key)
        if cached in {"active", "deferred"}:
            result[mcp] = cached
            continue

        decision = _resolve(mcp, stack, ecosystem, call_ai)
        result[mcp] = decision
        cache[key] = decision

    _save_cache(cache_path, cache)
    return result


def _resolve(
    mcp: str,
    stack: list[str],
    ecosystem: str | None,
    call_ai: AiCaller | None,
) -> str:
    if call_ai is None:
        return "deferred"
    try:
        raw = call_ai(mcp, stack, ecosystem)
    except AIUnavailable:
        return "deferred"
    return raw if raw in {"active", "deferred"} else "deferred"


def _cache_key(mcp: str, stack: list[str], ecosystem: str | None) -> str:
    raw = f"{mcp}|{','.join(sorted(stack))}|{ecosystem or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(path: Path, data: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True))
