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
    # post_tool_use.main() also appends mcp-usage telemetry under $HOME —
    # keep the operator's real ~/.arkaos out of the test (QG 2026-09-03, m8).
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))


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

    def test_graphify_tool_call_writes_graphify_marker(self):
        # Runtime Sync PR0: the graphify kind had no writer at all before.
        from core.hooks import post_tool_use

        post_tool_use.main({
            "tool_name": "mcp__graphify__query_graph",
            "session_id": "hon-post-3",
            "transcript_path": "",
            "cwd": "/tmp",
            "tool_input": {"question": "hooks adapter version"},
            "tool_output": "nodes",
        })
        record = kb_cache.read_graphify_query("hon-post-3")
        assert record is not None
        assert record["queries"][-1]["query"] == "hooks adapter version"
        # kinds stay separate: a graphify consult never forges obsidian evidence
        assert kb_cache.read_obsidian_query("hon-post-3") is None

    def test_vault_write_is_not_a_consult(self):
        # QG 2026-09-03 M1: saving one's own deliverable must not unlock
        # the gate that exists to prove a READ.
        from core.hooks import post_tool_use

        for tool in ("write_note", "patch_note", "update_frontmatter", "delete_note"):
            post_tool_use.main({
                "tool_name": f"mcp__obsidian__{tool}",
                "session_id": "hon-post-w",
                "transcript_path": "",
                "cwd": "/tmp",
                "tool_input": {"path": "Projects/out.md", "content": "my own deliverable"},
                "tool_output": "ok",
            })
        assert kb_cache.read_obsidian_query("hon-post-w") is None
        decision = research_gate.evaluate_research_gate(
            "WebSearch", session_id="hon-post-w", query="how to do X")
        assert decision.reason != "kb-consulted"

    def test_unknown_kind_writes_nothing_and_is_reported(self, monkeypatch):
        # QG 2026-09-03 M2: a third kind must never fall back onto graphify.
        from core.hooks import post_tool_use

        monkeypatch.setattr(post_tool_use, "KB_MARKER_TOOL_PREFIXES",
                            {**post_tool_use.KB_MARKER_TOOL_PREFIXES, "mcp__zettel__": "zettel"})
        monkeypatch.setattr(post_tool_use, "KB_CONSULT_TOOLS",
                            {**post_tool_use.KB_CONSULT_TOOLS, "zettel": frozenset({"search"})})
        degraded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(post_tool_use, "record_degraded",
                            lambda hook, reason, detail="": degraded.append((hook, reason, detail)))
        post_tool_use._record_kb_marker(
            "mcp__zettel__search", "hon-post-z", {"tool_input": {"query": "q"}})
        assert kb_cache.read_graphify_query("hon-post-z") is None
        assert kb_cache.read_obsidian_query("hon-post-z") is None
        assert degraded == [("post-tool-use", "kb-marker-no-writer", "zettel")]

    def test_writer_failure_reaches_the_degraded_channel(self, monkeypatch):
        # QG 2026-09-03 m7: a broken writer must not deny for weeks in silence.
        from core.hooks import post_tool_use

        def boom(*_a, **_k):
            raise OSError("disk full")

        monkeypatch.setattr(kb_cache, "record_obsidian_query", boom)
        degraded: list[tuple[str, str, str]] = []
        monkeypatch.setattr(post_tool_use, "record_degraded",
                            lambda hook, reason, detail="": degraded.append((hook, reason, detail)))
        post_tool_use._record_kb_marker(
            "mcp__obsidian__read_note", "hon-post-f", {"tool_input": {"path": "a.md"}})
        assert degraded and degraded[0][1] == "kb-marker-write-failed"
        assert "disk full" in degraded[0][2]

    def test_new_turn_resets_every_marker_kind(self):
        # QG 2026-09-03 M3: graphify gained a writer; it must reset per turn.
        from core.hooks.user_prompt_submit import _invalidate_turn_caches

        kb_cache.record_obsidian_query("hon-turn-1", "q", 1)
        kb_cache.record_graphify_query("hon-turn-1", "g", 1)
        kb_cache.record_injected_context("hon-turn-1", "i", 1)
        assert kb_cache.obsidian_queried_this_turn("hon-turn-1")
        assert kb_cache.graphify_queried_this_turn("hon-turn-1")
        _invalidate_turn_caches("hon-turn-1")
        assert not kb_cache.obsidian_queried_this_turn("hon-turn-1")
        assert not kb_cache.graphify_queried_this_turn("hon-turn-1")
        assert kb_cache.read_injected_context("hon-turn-1") is None

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
