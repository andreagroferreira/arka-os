"""Tests for Synapse L2.7 — Graphify grounding context injection.

Covers:
- graph.json discovery (cwd + parent walk, missing file → inert)
- keyword matching against node labels, degree tiebreak
- confidence honesty: EXTRACTED as-is, INFERRED suffixed, AMBIGUOUS excluded
- source_location never truncated
- ~400-token output cap
- feature flag (synapse.graphContext) + env bypass
- oversized graph (>10MB) skipped with an explicit metrics tag
- engine registration (L2.7, priority 26)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.synapse.engine import create_default_engine
from core.synapse.graph_context_layer import GraphContextLayer, _locate_graph
from core.synapse.layers import PromptContext


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    """Redirect HOME so the flag reader never touches the real ~/.arkaos."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ARKA_BYPASS_L27", raising=False)
    return home


def _write_graph(project: Path, nodes: list[dict], edges: list[dict] | None = None) -> Path:
    out = project / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    graph = out / "graph.json"
    graph.write_text(json.dumps({"nodes": nodes, "edges": edges or []}), encoding="utf-8")
    return graph


def _node(node_id: str, label: str, confidence: str, location: str) -> dict:
    return {
        "id": node_id,
        "label": label,
        "confidence": confidence,
        "source_location": location,
    }


def _ctx(cwd: Path, prompt: str = "explain the OrderService payment flow") -> PromptContext:
    return PromptContext(user_input=prompt, cwd=str(cwd))


# --- Discovery ---------------------------------------------------------------


def test_missing_graph_is_inert(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    result = GraphContextLayer().compute(_ctx(project))
    assert result.tag == ""
    assert result.content == ""
    assert result.tokens_est == 0


def test_graph_found_in_parent_directory(tmp_path):
    project = tmp_path / "project"
    nested = project / "src" / "services"
    nested.mkdir(parents=True)
    _write_graph(project, [_node("n1", "OrderService", "EXTRACTED", "src/services/order.py:12")])

    result = GraphContextLayer().compute(_ctx(nested))
    assert result.tag == "[graph-context:1]"
    assert "OrderService [EXTRACTED] — src/services/order.py:12" in result.content


def test_graph_beyond_three_parents_not_found(tmp_path):
    root = tmp_path / "project"
    deep = root / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    _write_graph(root, [_node("n1", "OrderService", "EXTRACTED", "x.py:1")])
    assert _locate_graph(str(deep)) is None


# --- Matching + honesty ------------------------------------------------------


def test_matches_prompt_keywords_against_labels(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _write_graph(project, [
        _node("n1", "OrderService.create", "EXTRACTED", "app/order.py:10"),
        _node("n2", "UnrelatedWidget", "EXTRACTED", "app/widget.py:5"),
    ])

    result = GraphContextLayer().compute(_ctx(project, "how does OrderService create orders"))
    assert "[graph-context:1]" == result.tag
    assert "OrderService.create" in result.content
    assert "UnrelatedWidget" not in result.content


def test_inferred_nodes_carry_suffix_and_ambiguous_excluded(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _write_graph(project, [
        _node("n1", "PaymentGateway", "EXTRACTED", "pay.py:1"),
        _node("n2", "PaymentRetry", "INFERRED", "pay.py:44"),
        _node("n3", "PaymentGhost", "AMBIGUOUS", "pay.py:99"),
    ])

    result = GraphContextLayer().compute(_ctx(project, "payment handling"))
    assert "PaymentGateway [EXTRACTED] — pay.py:1" in result.content
    assert "PaymentRetry [INFERRED] — pay.py:44 (inferred)" in result.content
    assert "PaymentGhost" not in result.content


def test_source_location_never_truncated(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    long_location = "/".join(["deeply-nested-package"] * 30) + "/order_service.py:1234"
    _write_graph(project, [_node("n1", "OrderService", "EXTRACTED", long_location)])

    result = GraphContextLayer().compute(_ctx(project, "OrderService"))
    assert long_location in result.content


def test_degree_breaks_keyword_ties(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    edges = [{"source": "hub", "target": f"n{i}"} for i in range(5)]
    _write_graph(
        project,
        [
            _node("leaf", "InvoiceLeaf", "EXTRACTED", "leaf.py:1"),
            _node("hub", "InvoiceHub", "EXTRACTED", "hub.py:1"),
        ],
        edges,
    )

    result = GraphContextLayer(max_nodes=1).compute(_ctx(project, "invoice"))
    assert "InvoiceHub" in result.content
    assert "InvoiceLeaf" not in result.content


def test_output_capped_at_400_tokens(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    filler = "very-long-module-path-" * 40  # ~880 chars per location
    nodes = [
        _node(f"n{i}", f"InvoiceProcessor{i}", "EXTRACTED", f"{filler}{i}.py:1")
        for i in range(5)
    ]
    _write_graph(project, nodes)

    result = GraphContextLayer().compute(_ctx(project, "invoiceprocessor"))
    assert result.tag.startswith("[graph-context:")
    # Budget: ~400 tokens estimated at 4 chars/token. One oversize line is
    # allowed through (locations are never truncated), so the assertion
    # bounds at budget + one filler line, not more.
    assert result.tokens_est <= 400 + len(filler) // 4 + 32
    assert len(result.content.splitlines()) < 6


# --- Flags + oversized graph -------------------------------------------------


def test_flag_off_disables_layer(tmp_path, _isolated_home):
    project = tmp_path / "project"
    project.mkdir()
    _write_graph(project, [_node("n1", "OrderService", "EXTRACTED", "o.py:1")])
    arkaos = _isolated_home / ".arkaos"
    arkaos.mkdir()
    (arkaos / "config.json").write_text(
        json.dumps({"synapse": {"graphContext": False}}), encoding="utf-8"
    )

    result = GraphContextLayer().compute(_ctx(project, "OrderService"))
    assert result.tag == ""
    assert result.content == ""


def test_env_bypass_disables_layer(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    _write_graph(project, [_node("n1", "OrderService", "EXTRACTED", "o.py:1")])
    monkeypatch.setenv("ARKA_BYPASS_L27", "1")

    result = GraphContextLayer().compute(_ctx(project, "OrderService"))
    assert result.tag == ""


def test_flag_defaults_true_when_config_missing(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _write_graph(project, [_node("n1", "OrderService", "EXTRACTED", "o.py:1")])

    result = GraphContextLayer().compute(_ctx(project, "OrderService"))
    assert result.tag == "[graph-context:1]"


def test_oversized_graph_skipped_with_metrics_tag(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    out = project / "graphify-out"
    out.mkdir()
    big = out / "graph.json"
    with big.open("wb") as fh:
        fh.seek(10 * 1024 * 1024)
        fh.write(b"x")

    result = GraphContextLayer().compute(_ctx(project, "OrderService"))
    assert result.tag == "[graph-context:skipped size>10MB]"
    assert result.content == ""


def test_corrupt_graph_json_is_inert(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    out = project / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text("{ not json", encoding="utf-8")

    result = GraphContextLayer().compute(_ctx(project, "OrderService"))
    assert result.tag == ""


# --- Engine wiring -----------------------------------------------------------


def test_layer_registered_in_default_engine():
    engine = create_default_engine()
    layer = engine.get_layer("L2.7")
    assert layer is not None
    assert layer.name == "GraphContext"
    assert layer.priority == 26
    assert layer.cache_ttl == 30
