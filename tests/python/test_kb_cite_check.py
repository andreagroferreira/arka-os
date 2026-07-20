"""Tests for core.governance.kb_cite_check (PR18 v2.40.0).

Citation classifier for assistant responses on ArkaOS topics.
Soft-block contract: classifier returns CitationResult, hooks decide
whether to surface the suggestion. Tests cover detection rules,
bypass markers, off-topic short-circuit, and suggestion shape.

These tests run in TDD red phase before implementation.
"""

from __future__ import annotations

import pytest

from core.governance.kb_cite_check import (
    CitationResult,
    check_citation,
)

# ─── Citation present (pass cases) ──────────────────────────────────────


class TestCitationPresent:
    def test_wikilink_citation_passes(self):
        text = (
            "Per ArkaOS constitution the Quality Gate is mandatory. "
            "See [[ArkaOS v2 Architecture Decisions]] for context. "
            "Synapse layers cover this."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "cited"
        assert result.citation_count >= 1

    def test_knowledge_marker_passes(self):
        text = (
            "Based on [knowledge: 3 chunks] from the vault, "
            "the Synapse L2.5 layer already injects KB context "
            "in user-prompt-submit."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "cited"

    def test_graphify_tool_name_alone_is_not_a_citation(self):
        """Naming the tool is narration, not evidence.

        QG blocker (redo 1): crediting `mcp__graphify__*` let a response
        self-certify by echoing the KB-first pointer, which carries that
        literal in every migrated SKILL.md. Only a returned node counts.
        """
        text = (
            "Consulted the knowledge graph: mcp__graphify__query_graph "
            "surfaced the ArkaOS community and its god nodes. "
            "The Synapse layers connect to Marta's Quality Gate."
        )
        result = check_citation(text)
        assert result.citation_count == 0, "tool name must not earn citation credit"

    def test_graphify_marker_citation_passes(self):
        text = (
            "Per the ArkaOS constitution, [graph: AIOX->LusoLink] shows "
            "the strategy linkage. Quality Gate and Synapse both apply here."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "cited"

    def test_file_line_reference_passes(self):
        text = (
            "The flow enforcer at core/workflow/flow_enforcer.py:232 "
            "defaults hardEnforcement to False, which explains why "
            "the ArkaOS workflow is not blocking."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "cited"

    def test_multiple_wikilinks_counted(self):
        text = (
            "ArkaOS constitution references [[ADR-2026-04-17]], "
            "[[Synapse Architecture]], and [[Quality Gate Spec]] "
            "as the foundational documents for governance."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.citation_count == 3


# ─── Bypass markers (pass via short-circuit) ────────────────────────────


class TestBypass:
    def test_arka_trivial_marker_bypasses(self):
        text = (
            "[arka:trivial] Single-line typo fix in README.\n"
            "Renamed `arkos` to `arkaos` in line 42."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "trivial"

    def test_short_acknowledgement_bypasses(self):
        result = check_citation("ok")
        assert result.passed is True
        assert result.reason == "trivial"

    def test_empty_response_bypasses(self):
        result = check_citation("")
        assert result.passed is True
        assert result.reason == "trivial"


# ─── Off-topic (pass via topic classifier) ──────────────────────────────


class TestOffTopic:
    def test_cooking_question_is_off_topic(self):
        text = (
            "To make sourdough bread, mix flour, water, salt, and "
            "starter culture. Ferment overnight at room temperature. "
            "Bake at 230°C for 35 minutes in a Dutch oven."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "off-topic"
        assert result.topic_score < 0.4

    def test_generic_python_advice_is_off_topic(self):
        text = (
            "When using list comprehensions in Python, prefer them over "
            "explicit for-loops for simple transformations. They are "
            "more readable and slightly faster due to bytecode optimisation."
        )
        result = check_citation(text)
        assert result.passed is True
        assert result.reason == "off-topic"


# ─── Missing citation on ArkaOS topic (fail) ────────────────────────────


class TestMissingCitation:
    def test_arkaos_topic_without_citation_fails(self):
        text = (
            "The ArkaOS constitution defines several NON-NEGOTIABLE "
            "rules. The Quality Gate runs on every workflow with "
            "Marta as CQO. Synapse handles context injection across "
            "eight layers. The Conclave is the strategic advisory board."
        )
        result = check_citation(text)
        assert result.passed is False
        assert result.reason == "missing"
        assert result.suggestion is not None
        assert "KB" in result.suggestion or "knowledge" in result.suggestion.lower()

    def test_suggestion_is_neutral_factual(self):
        text = (
            "ArkaOS Synapse layers handle Dreaming and Forge orchestration "
            "via the Conclave protocol with full Quality Gate review."
        )
        result = check_citation(text)
        assert result.passed is False
        # Must not contain exclamation, emojis, or AI clichés
        assert "!" not in result.suggestion
        assert "🎯" not in result.suggestion
        # Must reference how to fix
        assert any(
            cue in result.suggestion.lower()
            for cue in ("search", "cite", "obsidian", "/kb", "@[[")
        )


# ─── Topic classifier boundaries ────────────────────────────────────────


class TestTopicScore:
    @pytest.mark.parametrize("text,expect_arka", [
        ("Constitution and Quality Gate and Synapse and Conclave and Forge", True),
        ("Just one mention: Synapse.", False),
        ("Pasta carbonara recipe with eggs and pecorino", False),
    ])
    def test_topic_score_classification(self, text: str, expect_arka: bool):
        result = check_citation(text)
        if expect_arka:
            assert result.topic_score >= 0.4
        else:
            assert result.topic_score < 0.4


# ─── Return shape contract ──────────────────────────────────────────────


class TestResultShape:
    def test_result_is_frozen_dataclass(self):
        result = check_citation("ok")
        assert isinstance(result, CitationResult)
        with pytest.raises((AttributeError, Exception)):
            result.passed = False  # frozen → can't mutate

    def test_result_fields_present(self):
        result = check_citation("test")
        assert hasattr(result, "passed")
        assert hasattr(result, "reason")
        assert hasattr(result, "suggestion")
        assert hasattr(result, "citation_count")
        assert hasattr(result, "topic_score")

    def test_passed_responses_have_no_suggestion(self):
        result = check_citation("ok")
        assert result.passed is True
        assert result.suggestion is None


# ─── Security: ReDoS / pathological input ───────────────────────────────


class TestReDoSResistance:
    """Lock the contract from PR18 security audit: pathological input must
    not exceed the Stop hook's 5s budget. Pre-fix the file-line regex took
    ~41s on 100KB of `a/a/a/...`; bounded quantifiers + length guard cap
    runtime far below the hook budget."""

    def test_pathological_slashes_complete_under_budget(self):
        import time
        # 100 KB of slash-separated tokens, no trailing extension —
        # the exact shape that caused catastrophic backtracking before
        # bounding the file-line pattern.
        text = ("a/" * 50_000)[:100_000]
        start = time.perf_counter()
        result = check_citation(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500, (
            f"check_citation took {elapsed_ms:.0f}ms on 100KB pathological "
            f"input; must stay under 500ms to fit Stop's 5s budget."
        )
        assert isinstance(result, CitationResult)

    def test_long_legitimate_response_under_budget(self):
        import time
        # 80 KB of realistic prose mixed with file refs — should still scan
        # fast with the bounded quantifiers + 50KB cap.
        snippet = (
            "The ArkaOS Synapse layer at core/synapse/layers.py:42 handles "
            "context injection. See [[ArkaOS v2 Architecture]] for details. "
        )
        text = snippet * 800
        start = time.perf_counter()
        result = check_citation(text)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 500
        assert result.citation_count > 0
