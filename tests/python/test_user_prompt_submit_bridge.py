"""`_run_bridge` — the last mile that delivers Synapse output to the model.

This function had no test at all, which is exactly why a defect shipped in
it: the content channel was collected on `content != tag`, so every prompt
gained stray unlabeled lines ("active", "feat/plan-canvas") and nothing
caught it (QG review, B3/B4). These tests cover the contract directly.

The bridge module is stubbed on disk rather than imported for real: the goal
is the hook's assembly logic, not Synapse itself.
"""

from __future__ import annotations

import textwrap

import pytest

from core.hooks.user_prompt_submit import _run_bridge


def _make_root(tmp_path, run_bridge_body: str):
    """A fake repo whose scripts/synapse-bridge.py returns what we choose."""
    scripts = tmp_path / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "synapse-bridge.py").write_text(
        textwrap.dedent(run_bridge_body), encoding="utf-8",
    )
    return str(tmp_path)


def test_returns_context_string_when_no_blocks(tmp_path):
    root = _make_root(tmp_path, """
        def run_bridge(payload, root):
            return {"context_string": "[Constitution] [dept:dev]"}, 0
    """)
    assert _run_bridge(root, "hi", "s1") == "[Constitution] [dept:dev]"


def test_appends_content_blocks_after_the_tag_line(tmp_path):
    root = _make_root(tmp_path, """
        def run_bridge(payload, root):
            return {
                "context_string": "[kb-context:2 +graph]",
                "content_blocks": ["[arka:kb-context]\\nnote body",
                                   "[arka:graph-remote unverified]\\nnode: X"],
            }, 0
    """)
    out = _run_bridge(root, "hi", "s1")
    lines = out.split("\n")
    assert lines[0] == "[kb-context:2 +graph]", "tag line stays first"
    assert "[arka:kb-context]" in out
    assert "[arka:graph-remote unverified]" in out
    assert out.index("[arka:kb-context]") < out.index("[arka:graph-remote")


def test_empty_blocks_are_dropped(tmp_path):
    root = _make_root(tmp_path, """
        def run_bridge(payload, root):
            return {"context_string": "[dept:dev]",
                    "content_blocks": ["", None, "[arka:kb-context]\\nx"]}, 0
    """)
    out = _run_bridge(root, "hi", "s1")
    assert out == "[dept:dev]\n[arka:kb-context]\nx"


@pytest.mark.parametrize("blocks", ["not-a-list", 42, {"a": 1}])
def test_non_list_content_blocks_is_ignored(tmp_path, blocks):
    """A malformed payload must not crash the hook — it degrades to tags."""
    root = _make_root(tmp_path, f"""
        def run_bridge(payload, root):
            return {{"context_string": "[dept:dev]",
                     "content_blocks": {blocks!r}}}, 0
    """)
    assert _run_bridge(root, "hi", "s1") == "[dept:dev]"


def test_non_zero_exit_yields_empty(tmp_path):
    root = _make_root(tmp_path, """
        def run_bridge(payload, root):
            return {"context_string": "ignored"}, 1
    """)
    assert _run_bridge(root, "hi", "s1") == ""


def test_bridge_exception_fails_open(tmp_path):
    root = _make_root(tmp_path, """
        def run_bridge(payload, root):
            raise RuntimeError("bridge exploded")
    """)
    assert _run_bridge(root, "hi", "s1") == ""


def test_missing_bridge_returns_empty(tmp_path):
    assert _run_bridge(str(tmp_path), "hi", "s1") == ""


def test_cwd_is_forwarded_only_when_given(tmp_path):
    """L9.5 scopes cross-session memory by project — an unscoped search leaks."""
    root = _make_root(tmp_path, """
        def run_bridge(payload, root):
            return {"context_string": "cwd=" + str(payload.get("cwd", "absent"))}, 0
    """)
    assert _run_bridge(root, "hi", "s1") == "cwd=absent"
    assert _run_bridge(root, "hi", "s1", cwd="/proj") == "cwd=/proj"
