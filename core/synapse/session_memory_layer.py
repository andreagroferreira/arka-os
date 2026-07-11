"""Synapse L9.5 — session semantic memory retrieval (F1-A3).

Closes the memory loop opened by F1-A2: reads the per-session cache the
detached turn-capture worker precomputed (semantic neighbours, labeled
``asof-last-turn`` because they were ranked at the END of the previous
turn) plus a live keyword LIKE over the store for the current prompt.

Honesty contract (identical to L2.5 / vector_store.py): semantic hits
carry their cosine score; keyword hits carry ``score=None`` and are
labeled ``keyword — NOT semantic similarity``. The layer NEVER embeds —
zero embedding cost on the prompt hot path, ever.

Flag: ``synapse.l95SessionMemory`` (default ON) + env ``ARKA_BYPASS_L95``.
Inert (zero tokens) when the store is empty or the flag is off.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from core.synapse.layers import Layer, LayerResult, PromptContext

_MAX_ITEMS = 5
_SUMMARY_CHARS = 160
_LIVE_KEYWORD_K = 2
_CACHE_SEMANTIC_K = 3
_CONFIG_PATH = Path.home() / ".arkaos" / "config.json"


def _l95_feature_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L95", "").strip() == "1":
        return False
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    synapse_cfg = data.get("synapse") or {}
    return bool(synapse_cfg.get("l95SessionMemory", True))


def _read_session_cache(session_id: str) -> list[dict]:
    """Precomputed neighbours from the last turn's worker (version 1)."""
    if not session_id:
        return []
    path = Path.home() / ".arkaos" / "context-cache" / f"session-memory-{session_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if payload.get("version") != 1:
        return []
    items = payload.get("items")
    return items[:_CACHE_SEMANTIC_K] if isinstance(items, list) else []


def _format_item(item: dict, asof: bool) -> str:
    summary = str(item.get("summary") or "")[:_SUMMARY_CHARS]
    if not summary:
        return ""
    score = item.get("score")
    if item.get("retrieval") == "semantic" and isinstance(score, (int, float)):
        label = f"semantic {score:.2f}" + (" asof-last-turn" if asof else "")
    else:
        label = "keyword — NOT semantic similarity"
    project = str(item.get("project_name") or "")
    suffix = f" ({project})" if project else ""
    return f"- [{label}] {summary}{suffix}"


class SessionMemoryLayer(Layer):
    """L9.5: cross-session turn memory — cache read + live keyword only."""

    @property
    def id(self) -> str:
        return "L9.5"

    @property
    def name(self) -> str:
        return "SessionSemanticMemory"

    @property
    def cache_ttl(self) -> int:
        return 0  # cache file is per-turn fresh; store query is indexed

    @property
    def priority(self) -> int:
        return 91  # right after L9 SessionContext (90)

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        content = ""
        try:
            if ctx.user_input and _l95_feature_flag_on():
                content = self._retrieve(ctx)
        except Exception:  # noqa: BLE001 — layer must never break the prompt
            content = ""
        elapsed = int((time.time() - start) * 1000)
        if not content:
            return LayerResult(layer_id=self.id, tag="", content="",
                               tokens_est=0, compute_ms=elapsed, cached=False)
        count = content.count("\n- ") + (1 if content.startswith("- ") else 0)
        return LayerResult(
            layer_id=self.id,
            tag=f"[session-memory:{count}]",
            content=content,
            tokens_est=len(content.split()),
            compute_ms=elapsed,
            cached=False,
        )

    def _retrieve(self, ctx: PromptContext) -> str:
        session_id = str((ctx.extra or {}).get("session_id") or "")
        lines: list[str] = []
        seen: set[str] = set()
        for item in _read_session_cache(session_id):
            line = _format_item(item, asof=True)
            if line and item.get("summary") not in seen:
                seen.add(item.get("summary"))
                lines.append(line)
        from core.memory.semantic_store import SessionMemoryStore, default_db_path
        if default_db_path().is_file():
            hits = SessionMemoryStore().keyword_search(
                ctx.user_input, ctx.project_name or None, top_k=_LIVE_KEYWORD_K
            )
            for hit in hits:
                line = _format_item(hit, asof=False)
                if line and hit.get("summary") not in seen:
                    seen.add(hit.get("summary"))
                    lines.append(line)
        return "\n".join(lines[:_MAX_ITEMS])
