"""Synapse v2 — 8-layer context injection engine.

Injects relevant context into every prompt with <100ms target latency
and 65% context reduction through intelligent filtering.
"""

from core.synapse.engine import SynapseEngine
from core.synapse.layers import Layer, LayerResult, ForgeContextLayer
from core.synapse.cache import LayerCache

__all__ = ["SynapseEngine", "Layer", "LayerResult", "LayerCache", "ForgeContextLayer"]
