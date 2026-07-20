"""Synapse v2 engine — orchestrates all 8 layers with caching and filtering.

Design goals:
- <100ms total latency for all layers
- 65% context reduction vs injecting everything
- Pluggable layers (add/remove/reorder)
- TTL-based caching per layer
- Relevance filtering (skip irrelevant layers)
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from core.synapse.cache import LayerCache
from core.synapse.layers import Layer, LayerResult, PromptContext


@dataclass
class SynapseResult:
    """Complete result of Synapse context injection."""

    context_string: str  # The combined context to inject
    layers: list[LayerResult]  # Individual layer results
    total_ms: int  # Total computation time
    total_tokens_est: int  # Estimated total tokens injected
    cache_stats: dict  # Cache hit/miss statistics
    layers_skipped: int  # Layers that returned empty results
    # Full-text blocks from layers whose content is richer than their tag
    # (L2.5 KB context, graph context). Kept separate from context_string so
    # the compact tag line stays compact; the hook appends these after it.
    # Before this existed, LayerResult.content had NO consumer — every block a
    # layer built was discarded while its tag still advertised the injection.
    content_blocks: list[str] = field(default_factory=list)


class SynapseEngine:
    """9-layer context injection engine.

    Computes all registered layers, caches results per TTL,
    filters empty results, and combines into a compact context string.
    """

    def __init__(self) -> None:
        self._layers: list[Layer] = []
        self._cache = LayerCache()
        self._metrics: list[dict] = []

    def register_layer(self, layer: Layer) -> None:
        """Register a context layer. Layers execute in priority order."""
        self._layers.append(layer)
        self._layers.sort(key=lambda x: x.priority)

    def remove_layer(self, layer_id: str) -> None:
        """Remove a layer by ID."""
        self._layers = [x for x in self._layers if x.id != layer_id]

    def get_layer(self, layer_id: str) -> Layer | None:
        """Get a layer by ID."""
        for layer in self._layers:
            if layer.id == layer_id:
                return layer
        return None

    def inject(self, ctx: PromptContext) -> SynapseResult:
        """Compute all layers and return combined context.

        Args:
            ctx: The prompt context (user input, environment).

        Returns:
            SynapseResult with the combined context string.
        """
        start = time.time()
        results: list[LayerResult] = []
        skipped = 0

        block_layers: set[str] = set()
        for layer in self._layers:
            result = self._compute_layer(layer, ctx)
            if result.tag or result.content:
                results.append(result)
                if layer.emits_block:
                    block_layers.add(layer.id)
            else:
                skipped += 1

        # Combine all layer tags into a single context string
        tags = [r.tag for r in results if r.tag]
        context_string = " ".join(tags)

        # Full-text blocks — OPT-IN via Layer.emits_block. Collecting on
        # `content != tag` instead swept up every layer whose content is its
        # tag's value ("dev", "active", "feat/plan-canvas"), injecting stray
        # unlabeled lines into every prompt for zero added information.
        content_blocks = [
            r.content for r in results
            if r.content and r.layer_id in block_layers
        ]

        total_tokens = sum(r.tokens_est for r in results)
        total_ms = int((time.time() - start) * 1000)

        # Record metrics
        self._metrics.append(
            {
                "timestamp": time.time(),
                "total_ms": total_ms,
                "layers_computed": len(results),
                "layers_skipped": skipped,
                "tokens_injected": total_tokens,
            }
        )
        # Keep only last 500 metrics
        if len(self._metrics) > 500:
            self._metrics = self._metrics[-500:]

        return SynapseResult(
            context_string=context_string,
            layers=results,
            total_ms=total_ms,
            total_tokens_est=total_tokens,
            cache_stats=self._cache.stats,
            layers_skipped=skipped,
            content_blocks=content_blocks,
        )

    def _compute_layer(self, layer: Layer, ctx: PromptContext) -> LayerResult:
        """Compute a single layer with caching."""
        cache_key = f"{layer.id}:{ctx.cwd}:{ctx.active_agent}"
        if layer.input_sensitive:
            # Input-dependent layers (hints, department, KB retrieval)
            # must not serve one prompt's result to a different prompt
            # within the TTL window.
            digest = hashlib.sha1(
                (ctx.user_input or "").encode("utf-8", "replace")
            ).hexdigest()[:12]
            cache_key += f":{digest}"
        if getattr(layer, "session_sensitive", False):
            # Session-sensitive layers (KB retrieval) must recompute per
            # session: a cross-session cache hit would skip their
            # per-session side effects (KBSessionCache.store).
            session_id = (ctx.extra or {}).get("session_id", "default")
            cache_key += f":{session_id}"

        # Check cache. The stored value is `tag` alone, or `tag\x00content`
        # whenever content differs from tag: replaying the tag as the content
        # would feed a marker to the model in place of what it advertises.
        # This condition is deliberately WIDER than `emits_block` — the cache
        # round-trips content faithfully for every layer (AgentLayer stores
        # `[agent:x disc:y]\x00x` and is no block at all); only the block
        # channel in inject() is opt-in.
        if layer.cache_ttl > 0:
            cached = self._cache.get(cache_key)
            if cached is not None:
                tag, _, content = cached.partition("\x00")
                content = content or tag
                return LayerResult(
                    layer_id=layer.id,
                    tag=tag,
                    content=content,
                    tokens_est=len(content.split()),
                    compute_ms=0,
                    cached=True,
                )

        # Compute fresh
        result = layer.compute(ctx)

        # Cache if TTL > 0 and result is non-empty
        if layer.cache_ttl > 0 and result.tag:
            stored = result.tag
            if result.content and result.content != result.tag:
                stored = f"{result.tag}\x00{result.content}"
            self._cache.set(cache_key, stored, layer.cache_ttl)

        return result

    def clear_cache(self) -> None:
        """Clear all cached layer results."""
        self._cache.clear()

    @property
    def metrics(self) -> list[dict]:
        """Get computation metrics history."""
        return self._metrics

    @property
    def layer_count(self) -> int:
        """Number of registered layers."""
        return len(self._layers)

    @property
    def cache_stats(self) -> dict:
        """Cache hit/miss statistics."""
        return self._cache.stats


def create_default_engine(
    constitution_compressed: str = "",
    commands: list[dict] | None = None,
    agents_registry: dict[str, dict] | None = None,
    vector_store: Any = None,
    kb_vault_path: str | None = None,
    kb_max_notes: int = 5,
) -> SynapseEngine:
    """Create a SynapseEngine with all default layers.

    Args:
        constitution_compressed: Compressed Constitution string for L0.
        commands: Command registry for L5 hints.
        agents_registry: Agent registry for L2 context.
        vector_store: Optional vector store (enables L2.5 + L3.5).
        kb_vault_path: Optional Obsidian vault path for L2.5 Jaccard fallback.
        kb_max_notes: Max Obsidian notes to inject at L2.5 (default 5).

    Returns:
        Configured SynapseEngine ready to use.
    """
    from core.synapse.agent_experiences_layer import AgentExperiencesLayer
    from core.synapse.graph_context_layer import GraphContextLayer
    from core.synapse.layers import (
        AgentLayer,
        BranchLayer,
        CommandHintsLayer,
        ConstitutionLayer,
        DepartmentLayer,
        ForgeContextLayer,
        KBContextLayer,
        KnowledgeRetrievalLayer,
        ProjectLayer,
        QualityGateLayer,
        SessionContextLayer,
    )
    from core.synapse.pattern_library_layer import PatternLibraryLayer
    from core.synapse.recipe_layer import RecipeLayer
    from core.synapse.routing_feedback_layer import RoutingFeedbackLayer
    from core.synapse.session_memory_layer import SessionMemoryLayer

    engine = SynapseEngine()

    l0 = ConstitutionLayer(compressed=constitution_compressed)
    engine.register_layer(l0)
    engine.register_layer(DepartmentLayer())
    engine.register_layer(AgentLayer(agents_registry=agents_registry))
    # L2.6 (PR3.5 v3.74.1) — injects past Quality Gate experiences for the
    # specialist named in `[arka:dispatch]`, so dispatched agents inherit
    # prior REJECTED lessons across sessions. Closes the PR3 loop.
    engine.register_layer(AgentExperiencesLayer())
    if vector_store is not None or kb_vault_path:
        engine.register_layer(
            KBContextLayer(
                vector_store=vector_store,
                vault_path=kb_vault_path,
                max_notes=kb_max_notes,
            )
        )
    # L2.7 (PR-3 v4.1) — Graphify grounding. Injects code-graph nodes
    # (EXTRACTED confidence + source_location) matching the prompt so
    # answers about a codebase cite real structure. Registered
    # unconditionally: without a graphify-out/graph.json the layer is
    # inert and contributes zero tokens.
    engine.register_layer(GraphContextLayer())
    engine.register_layer(ProjectLayer())
    if vector_store is not None:
        engine.register_layer(KnowledgeRetrievalLayer(vector_store=vector_store))
    engine.register_layer(BranchLayer())
    engine.register_layer(CommandHintsLayer(commands=commands))
    engine.register_layer(QualityGateLayer())
    # L5.5 (F1-B2) — routing feedback. When the detected department has a
    # poor recent QG record (routing-scores.json, F1-B1), injects
    # [arka:redo-risk] with citable counts. Silent below 5 samples or at
    # healthy approval — warnings only, never noise. Closes the second
    # learning loop of the memory reform.
    engine.register_layer(RoutingFeedbackLayer())
    # L7 TimeLayer removed (prompt-surface P0 2026-07-08): the time-of-day tag
    # had no consumer rule and invalidated the prompt cache at every
    # 5h/12h/18h boundary — same rationale as the session-start hook's
    # time-of-day removal.
    engine.register_layer(ForgeContextLayer())
    # L7.5 (PR4 v3.75.0) — Pattern Library injection. Surfaces prior
    # `PatternCard`s when the user prompt has matching keywords, so
    # specs and dispatched specialists start from prior art rather than
    # reinventing.
    engine.register_layer(PatternLibraryLayer())
    # L7.6 (Interaction Reform PR8) — validated Recipe injection.
    # Sibling of L7.5: surfaces QG-approved prior BUILDS (reference files
    # on disk) when the prompt matches, so the build loop reuses proven
    # work. Inert when no recipes are captured.
    engine.register_layer(RecipeLayer())
    engine.register_layer(SessionContextLayer())
    # L9.5 (F1-A3) — cross-session semantic turn memory. Reads the cache
    # the detached turn-capture worker precomputed (labeled ranked@HH:MMZ
    # / pre-ranked) plus a live keyword LIKE; NEVER embeds on the prompt
    # path. Registered unconditionally: inert when the store is empty.
    engine.register_layer(SessionMemoryLayer())

    return engine
