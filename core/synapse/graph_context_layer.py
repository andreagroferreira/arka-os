"""Synapse layer L2.7 — Graphify grounding context injection.

When the working project has a Graphify code knowledge graph
(``graphify-out/graph.json``, generated locally by the ``graphify`` CLI
via tree-sitter), this layer matches the user's prompt keywords against
graph node labels and injects the top matches as grounded context:
node label, confidence tag and the exact ``source_location``. The model
then cites real code structure instead of inventing it.

Honesty contract (PR-3 v4.1 — Graphify grounding):
  - Only ``EXTRACTED`` nodes are injected as-is. ``INFERRED`` nodes are
    included with an explicit ``(inferred)`` suffix. ``AMBIGUOUS`` nodes
    are never injected.
  - ``source_location`` is NEVER truncated — a clipped citation is worse
    than no citation.
  - No graph → the layer contributes nothing (inert, zero tokens).

Feature flag: ``synapse.graphContext`` in ``~/.arkaos/config.json``
(default ``true`` — mirrors how L2.5 reads ``synapse.l25KbContext``).
``ARKA_BYPASS_L27=1`` env disables for debugging.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from core.synapse.layers import Layer, LayerResult, PromptContext
from core.synapse.pattern_library_layer import _extract_keywords

# graph.json can grow to many MB on large repos. Loading it inside a
# per-prompt hook with a <100ms Synapse budget would blow both latency
# and memory, so beyond this cap we skip with an explicit metrics tag
# instead of parsing. (`graphify . --update` keeps graphs incremental;
# a >10MB graph is a signal the project should shard extraction, not
# that the hook should pay for it.)
_MAX_GRAPH_BYTES = 10 * 1024 * 1024

_MAX_NODES = 5
_MAX_PARENT_WALK = 3  # cwd + up to 3 parent dirs
_MAX_TOKENS_EST = 400  # ~4 chars/token budget cap for the whole block


def _graph_flag_on() -> bool:
    if os.environ.get("ARKA_BYPASS_L27", "").strip() == "1":
        return False
    config_path = Path.home() / ".arkaos" / "config.json"
    if not config_path.exists():
        return True
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    synapse_cfg = data.get("synapse") or {}
    return bool(synapse_cfg.get("graphContext", True))


def _locate_graph(cwd: str) -> Optional[Path]:
    """Find ``graphify-out/graph.json`` in cwd or up to 3 parent dirs."""
    if not cwd:
        return None
    current = Path(cwd)
    if not current.is_dir():
        return None
    for candidate in [current, *current.parents[:_MAX_PARENT_WALK]]:
        graph = candidate / "graphify-out" / "graph.json"
        if graph.is_file():
            return graph
    return None


def _node_degrees(edges: list) -> dict[str, int]:
    degrees: dict[str, int] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        for key in ("source", "target"):
            node_id = edge.get(key)
            if isinstance(node_id, str) and node_id:
                degrees[node_id] = degrees.get(node_id, 0) + 1
    return degrees


def _score_nodes(
    nodes: list, keywords: list[str], degrees: dict[str, int]
) -> list[tuple[int, int, dict]]:
    """Rank nodes by keyword-match count, then degree. Drops non-matches."""
    scored: list[tuple[int, int, dict]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        confidence = str(node.get("confidence", "")).upper()
        if confidence not in ("EXTRACTED", "INFERRED"):
            continue  # AMBIGUOUS (or untagged) nodes are never injected
        label = str(node.get("label") or node.get("id") or "").strip()
        if not label:
            continue
        haystack = label.lower()
        matches = sum(1 for kw in keywords if kw in haystack)
        if matches == 0:
            continue
        degree = degrees.get(str(node.get("id", "")), 0)
        scored.append((matches, degree, node))
    scored.sort(key=lambda row: (-row[0], -row[1]))
    return scored


def _format_node_line(node: dict) -> str:
    confidence = str(node.get("confidence", "")).upper()
    label = str(node.get("label") or node.get("id") or "").strip()
    # source_location is the citation — NEVER truncate it.
    location = str(node.get("source_location", "")).strip() or "(no source_location)"
    line = f"- {label} [{confidence}] — {location}"
    if confidence == "INFERRED":
        line += " (inferred)"
    return line


def _format_graph_block(lines: list[str]) -> str:
    header = (
        f"[arka:graph-context:{len(lines)}] Graphify grounded nodes for this "
        f"prompt (cite source_location; EXTRACTED = verified from code):"
    )
    return "\n".join([header, *lines])


class GraphContextLayer(Layer):
    """L2.7 — inject Graphify graph nodes matching the user prompt."""

    def __init__(self, max_nodes: int = _MAX_NODES) -> None:
        self._max_nodes = max_nodes

    @property
    def id(self) -> str:
        return "L2.7"

    @property
    def name(self) -> str:
        return "GraphContext"

    @property
    def input_sensitive(self) -> bool:
        return True

    @property
    def cache_ttl(self) -> int:
        return 30

    @property
    def priority(self) -> int:
        return 26  # right after L2.5 KBContext (25), before ProjectLayer (30)

    def compute(self, ctx: PromptContext) -> LayerResult:
        start = time.time()
        if not ctx.user_input or not _graph_flag_on():
            return self._empty(start)
        graph_path = _locate_graph(ctx.cwd)
        if graph_path is None:
            return self._empty(start)
        try:
            if graph_path.stat().st_size > _MAX_GRAPH_BYTES:
                # See _MAX_GRAPH_BYTES: too big to parse inside the hook
                # budget — surface a metrics note instead of silence.
                return self._empty(start, tag="[graph-context:skipped size>10MB]")
            data = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return self._empty(start)
        return self._build_result(ctx, data, start)

    def _build_result(self, ctx: PromptContext, data: Any, start: float) -> LayerResult:
        if not isinstance(data, dict):
            return self._empty(start)
        keywords = _extract_keywords(ctx.user_input)
        if not keywords:
            return self._empty(start)
        nodes = data.get("nodes") or []
        edges = data.get("edges") or []
        scored = _score_nodes(nodes, keywords, _node_degrees(edges))
        lines = self._capped_lines(scored)
        if not lines:
            return self._empty(start)
        content = _format_graph_block(lines)
        return LayerResult(
            layer_id=self.id,
            tag=f"[graph-context:{len(lines)}]",
            content=content,
            tokens_est=max(1, len(content) // 4),
            compute_ms=int((time.time() - start) * 1000),
            cached=False,
        )

    def _capped_lines(self, scored: list[tuple[int, int, dict]]) -> list[str]:
        """Top-N node lines, kept under the ~400-token block budget."""
        lines: list[str] = []
        budget_chars = _MAX_TOKENS_EST * 4
        used = 0
        for _, _, node in scored[: self._max_nodes]:
            line = _format_node_line(node)
            if lines and used + len(line) > budget_chars:
                break
            lines.append(line)
            used += len(line)
        return lines

    def _empty(self, start: float, tag: str = "") -> LayerResult:
        return LayerResult(
            layer_id=self.id,
            tag=tag,
            content="",
            tokens_est=0,
            compute_ms=int((time.time() - start) * 1000),
            cached=False,
        )
