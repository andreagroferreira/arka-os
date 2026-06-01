"""Tests for the benchmark harness (scripts/bench/).

Timing values are machine-relative, so these tests assert structural
contracts and the deterministic parts (routing accuracy, handoff size).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


harness = _load("bench_harness", "scripts/bench/harness.py")
bench_run = _load("bench_run", "scripts/bench/run.py")


def test_percentiles_summary():
    summary = harness._percentiles([10.0, 20.0, 30.0])
    assert summary["runs"] == 3
    assert summary["min"] == 10.0
    assert summary["max"] == 30.0
    assert summary["p50"] == 20.0


def test_synapse_latency_contract():
    result = harness.bench_synapse_latency(runs=5)
    assert result["layer_count"] >= 8
    for bucket in ("cold_ms", "warm_ms"):
        assert set(result[bucket]) == {"runs", "min", "p50", "mean", "max"}
        assert result[bucket]["runs"] == 5
        assert result[bucket]["min"] >= 0
    assert "injection_profile" in result


def test_subagent_handoff_is_measured():
    result = harness.bench_subagent_handoff()
    assert result["documented_claim"] == 379
    assert result["measured_tokens"] > 0
    assert result["prompt_chars"] > 0


def test_routing_accuracy_is_deterministic():
    a = harness.bench_routing_accuracy()
    b = harness.bench_routing_accuracy()
    assert a["accuracy_pct"] == b["accuracy_pct"]  # deterministic
    assert a["total"] == len(harness._ROUTING_SET)
    assert 0 <= a["correct"] <= a["total"]
    assert all({"prompt", "expected", "detected", "ok"} <= set(d) for d in a["details"])


def test_run_all_combines_sections():
    result = harness.run_all(runs=3)
    assert set(result) == {"synapse_latency", "subagent_handoff", "routing_accuracy"}


def test_render_markdown_includes_all_sections():
    results = harness.run_all(runs=3)
    md = bench_run.render_markdown(results, {"python": "3.11", "platform": "test"})
    assert "# ArkaOS Benchmarks" in md
    assert "Synapse context injection" in md
    assert "Subagent handoff" in md
    assert "Routing accuracy" in md
