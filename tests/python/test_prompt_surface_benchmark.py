"""Smoke tests for scripts/tools/prompt_surface_benchmark.py.

No git-archive comparison here (needs tags + network-free but slow);
only the current-tree measurement contract, which CI can always run.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "tools" / "prompt_surface_benchmark.py"

spec = importlib.util.spec_from_file_location(
    "prompt_surface_benchmark", SCRIPT
)
bench = importlib.util.module_from_spec(spec)
sys.modules["prompt_surface_benchmark"] = bench
spec.loader.exec_module(bench)


def test_canonical_prompt_set_is_stable():
    assert set(bench.CANONICAL_PROMPTS) == {
        "simple",
        "question",
        "code-modifying",
        "department-routed",
        "slash-command",
    }


def test_measure_current_tree_returns_sane_sizes():
    results = bench.measure(REPO_ROOT)
    assert set(results) == set(bench.CANONICAL_PROMPTS)
    for name, row in results.items():
        assert row["bytes"] > 0, f"{name}: hook injected nothing"
        assert row["tokens_est"] == row["bytes"] // 4


def test_measure_is_deterministic_in_fallback_mode():
    assert bench.measure(REPO_ROOT) == bench.measure(REPO_ROOT)
