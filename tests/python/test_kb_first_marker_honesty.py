"""The KB-first marker is evidence, not narration.

Before this split, Synapse L2.5 called ``record_obsidian_query`` on every
prompt — the same marker the research gate reads to decide "KB-first was
respected". The gate was satisfied by the injection mechanism itself and
could never fire (observed live: a marker whose recorded query was the
user's one-word reply "sim", allowing WebSearch as "kb-consulted").

The contract now:
  - L2.5 records kind="injected" (telemetry; gate ignores it)
  - PostToolUse records kind="obsidian" on genuine ``mcp__obsidian__*``
    calls (evidence; gate reads it)
"""

from __future__ import annotations

import pytest

from core.synapse import kb_cache
from core.workflow import research_gate


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKA_KB_QUERY_DIR", str(tmp_path / "kb-query"))
    monkeypatch.setenv("ARKA_KB_VIOLATION_DIR", str(tmp_path / "kb-violation"))
    monkeypatch.setenv("ARKA_BYPASS_KB_FIRST", "")


class TestGateIgnoresInjection:
    def test_injected_kind_does_not_satisfy_gate(self):
        kb_cache.record_injected_context("hon-1", "user prompt text", 5)
        decision = research_gate.evaluate_research_gate(
            "WebSearch", "hon-1", "some query"
        )
        # First violation: nudged, not silently allowed as kb-consulted.
        assert decision.reason == "first-violation-nudge"

    def test_genuine_obsidian_consult_satisfies_gate(self):
        kb_cache.record_obsidian_query("hon-2", "real consult", 3)
        decision = research_gate.evaluate_research_gate(
            "WebSearch", "hon-2", "some query"
        )
        assert decision.allow is True
        assert decision.reason == "kb-consulted"

    def test_kinds_are_separate_files(self):
        kb_cache.record_injected_context("hon-3", "auto", 5)
        assert kb_cache.read_injected_context("hon-3") is not None
        assert kb_cache.read_obsidian_query("hon-3") is None
        kb_cache.record_obsidian_query("hon-3", "manual", 1)
        assert kb_cache.read_obsidian_query("hon-3") is not None

    def test_injected_invalidation_is_independent(self):
        kb_cache.record_injected_context("hon-4", "auto", 5)
        kb_cache.record_obsidian_query("hon-4", "manual", 1)
        kb_cache.invalidate_injected_context("hon-4")
        assert kb_cache.read_injected_context("hon-4") is None
        assert kb_cache.read_obsidian_query("hon-4") is not None


class TestPostToolUseRecordsGenuineConsults:
    def test_obsidian_tool_call_writes_evidence_marker(self):
        from core.hooks import post_tool_use

        post_tool_use.main({
            "tool_name": "mcp__obsidian__search_notes",
            "session_id": "hon-post-1",
            "transcript_path": "",
            "cwd": "/tmp",
            "tool_input": {"query": "testing patterns"},
            "tool_output": "results",
        })
        record = kb_cache.read_obsidian_query("hon-post-1")
        assert record is not None
        assert record["queries"][-1]["query"] == "testing patterns"

    def test_non_obsidian_tool_writes_nothing(self):
        from core.hooks import post_tool_use

        post_tool_use.main({
            "tool_name": "Read",
            "session_id": "hon-post-2",
            "transcript_path": "",
            "cwd": "/tmp",
            "tool_input": {"file_path": "/tmp/x"},
            "tool_output": "",
        })
        assert kb_cache.read_obsidian_query("hon-post-2") is None
