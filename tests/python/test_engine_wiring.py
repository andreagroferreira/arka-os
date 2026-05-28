"""Confirm the v3.74.1 wiring of AgentExperiencesLayer into the engine."""

from __future__ import annotations

import pytest

from core.synapse.engine import create_default_engine as build_engine
from core.synapse.agent_experiences_layer import AgentExperiencesLayer


def test_agent_experiences_layer_registered_by_default():
    engine = build_engine(constitution_compressed="", agents_registry={}, commands={})
    layer_ids = [layer.id for layer in engine._layers]
    assert "L2.6" in layer_ids


def test_agent_experiences_layer_instance_present():
    engine = build_engine(constitution_compressed="", agents_registry={}, commands={})
    assert any(isinstance(layer, AgentExperiencesLayer) for layer in engine._layers)


def test_agent_experiences_layer_priority_between_agent_and_kb():
    engine = build_engine(constitution_compressed="", agents_registry={}, commands={})
    layers_by_id = {layer.id: layer for layer in engine._layers}
    # Sanity: L2 (Agent prio 20), L2.6 (Experiences prio 25)
    assert layers_by_id["L2"].priority == 20
    assert layers_by_id["L2.6"].priority == 25
