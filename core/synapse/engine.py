"""Synapse v2 engine — orchestrates all 8 layers with caching and filtering.

Design goals:
- <100ms total latency for all layers
- 65% context reduction vs injecting everything
- Pluggable layers (add/remove/reorder)
- TTL-based caching per layer
- Relevance filtering (skip irrelevant layers)
"""

import time
from dataclasses import dataclass, field
from typing import Any

from core.synapse.layers import Layer, LayerResult, PromptContext
from core.synapse.cache import LayerCache


@dataclass
class SynapseResult:
    """Complete result of Synapse context injection."""

    context_string: str  # The combined context to inject
    layers: list[LayerResult]  # Individual layer results
    total_ms: int  # Total computation time
    total_tokens_est: int  # Estimated total tokens injected
    cache_stats: dict  # Cache hit/miss statistics
    layers_skipped: int  # Layers that returned empty results


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
        self._layers.sort(key=lambda l: l.priority)

    def remove_layer(self, layer_id: str) -> None:
        """Remove a layer by ID."""
        self._layers = [l for l in self._layers if l.id != layer_id]

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

        for layer in self._layers:
            result = self._compute_layer(layer, ctx)
            if result.tag or result.content:
                results.append(result)
            else:
                skipped += 1

        # Combine all layer tags into a single context string
        tags = [r.tag for r in results if r.tag]
        context_string = " ".join(tags)

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
        )

    def _compute_layer(self, layer: Layer, ctx: PromptContext) -> LayerResult:
        """Compute a single layer with caching."""
        cache_key = f"{layer.id}:{ctx.cwd}:{ctx.active_agent}"

        # Check cache
        if layer.cache_ttl > 0:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return LayerResult(
                    layer_id=layer.id,
                    tag=cached,
                    content=cached,
                    tokens_est=len(cached.split()),
                    compute_ms=0,
                    cached=True,
                )

        # Compute fresh
        result = layer.compute(ctx)

        # Cache if TTL > 0 and result is non-empty
        if layer.cache_ttl > 0 and result.tag:
            self._cache.set(cache_key, result.tag, layer.cache_ttl)

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
    from core.synapse.layers import (
        ConstitutionLayer,
        DepartmentLayer,
        AgentLayer,
        ProjectLayer,
        BranchLayer,
        CommandHintsLayer,
        QualityGateLayer,
        TimeLayer,
        KnowledgeRetrievalLayer,
        KBContextLayer,
        ForgeContextLayer,
        SessionContextLayer,
    )

    engine = SynapseEngine()

    l0 = ConstitutionLayer(compressed=constitution_compressed)
    engine.register_layer(l0)
    engine.register_layer(DepartmentLayer())
    engine.register_layer(AgentLayer(agents_registry=agents_registry))
    if vector_store is not None or kb_vault_path:
        engine.register_layer(
            KBContextLayer(
                vector_store=vector_store,
                vault_path=kb_vault_path,
                max_notes=kb_max_notes,
            )
        )
    engine.register_layer(ProjectLayer())
    if vector_store is not None:
        engine.register_layer(KnowledgeRetrievalLayer(vector_store=vector_store))
    engine.register_layer(BranchLayer())
    engine.register_layer(CommandHintsLayer(commands=commands))
    engine.register_layer(QualityGateLayer())
    engine.register_layer(TimeLayer())
    engine.register_layer(ForgeContextLayer())
    engine.register_layer(SessionContextLayer())

    return engine
