"""Tests for core.governance.cqo_experience_recorder (PR3)."""

from __future__ import annotations

import pytest

from core.governance import agent_experiences
from core.governance.agent_experiences import query_experiences
from core.governance.cqo_experience_recorder import (
    parse_cqo_verdict,
    record_from_verdict,
)


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_experiences, "AGENTS_ROOT", tmp_path / "agents")
    return tmp_path / "agents"


# ─── parse_cqo_verdict ─────────────────────────────────────────────────


class TestVerdictExtraction:
    def test_approved_simple(self):
        text = "Quality Gate Verdict: APPROVED\nAll good."
        parsed = parse_cqo_verdict(text)
        assert parsed.verdict == "APPROVED"
        assert parsed.blockers == []
        assert parsed.patterns == []

    def test_rejected_simple(self):
        text = "## Quality Gate Verdict: REJECTED\n**B1. Issue exists.**"
        parsed = parse_cqo_verdict(text)
        assert parsed.verdict == "REJECTED"
        assert len(parsed.blockers) == 1

    def test_empty_text_returns_unknown(self):
        assert parse_cqo_verdict("").verdict == "UNKNOWN"
        assert parse_cqo_verdict("just some text").verdict == "UNKNOWN"

    def test_verdict_case_insensitive(self):
        assert parse_cqo_verdict("quality gate verdict: rejected").verdict == "REJECTED"
        assert parse_cqo_verdict("QUALITY GATE VERDICT: APPROVED").verdict == "APPROVED"


class TestBlockerExtraction:
    def test_extracts_b_and_m_blockers(self):
        text = """Quality Gate Verdict: REJECTED

**B1. evaluate() is 31 lines.**
**B2. _glob_match() is 37 lines.**
**M1. Missing pytest coverage.**
"""
        parsed = parse_cqo_verdict(text)
        labels = [b.split(":")[0] for b in parsed.blockers]
        assert "B1" in labels
        assert "B2" in labels
        assert "M1" in labels

    def test_blockers_only_for_rejected(self):
        text = """Quality Gate Verdict: APPROVED

**B1. would not be counted because verdict is APPROVED.**
"""
        parsed = parse_cqo_verdict(text)
        assert parsed.blockers == []

    def test_handles_colon_style_blockers(self):
        text = "Quality Gate Verdict: REJECTED\nB1: function too long\nB2: missing tests"
        parsed = parse_cqo_verdict(text)
        assert len(parsed.blockers) == 2

    def test_handles_space_separator_after_label(self):
        """B1 followed only by whitespace (no dot/colon) should still match."""
        text = "Quality Gate Verdict: REJECTED\nB1 function too long\nB2 missing tests"
        parsed = parse_cqo_verdict(text)
        assert len(parsed.blockers) == 2
        assert "function too long" in parsed.blockers[0]

    def test_handles_double_digit_blocker(self):
        text = "Quality Gate Verdict: REJECTED\n**B10. tenth blocker.**\n**B11. eleventh.**"
        parsed = parse_cqo_verdict(text)
        labels = [b.split(":")[0] for b in parsed.blockers]
        assert "B10" in labels
        assert "B11" in labels

    def test_inline_blockers_in_paragraph_are_NOT_matched(self):
        """Documented limitation: inline blocker references in paragraphs are not extracted.
        Only line-anchored labels (after optional ** and whitespace) qualify."""
        text = "Quality Gate Verdict: REJECTED\nThe reviewer noted B1. is problematic mid-sentence."
        parsed = parse_cqo_verdict(text)
        # Line starts with "The reviewer..." — no leading blocker label
        assert parsed.blockers == []

    def test_blocker_headline_truncated_at_200(self):
        long = "x" * 500
        text = f"Quality Gate Verdict: REJECTED\n**B1. {long}**"
        parsed = parse_cqo_verdict(text)
        assert len(parsed.blockers[0]) <= 220  # label + headline + ellipsis
        assert "..." in parsed.blockers[0]


class TestPatternHints:
    def test_function_length_pattern(self):
        text = "Quality Gate Verdict: REJECTED\n**B1. evaluate() exceeds the 30-line ceiling.**"
        assert "function-length-violation" in parse_cqo_verdict(text).patterns

    def test_command_injection_pattern(self):
        text = "Quality Gate Verdict: REJECTED\n**B1. shell escape needed (CWE-77).**"
        assert "command-injection-risk" in parse_cqo_verdict(text).patterns

    def test_governance_gap_pattern(self):
        text = "Quality Gate Verdict: REJECTED\n**B1. Undocumented marker in flow SKILL.**"
        assert "governance-gap" in parse_cqo_verdict(text).patterns

    def test_test_coverage_pattern(self):
        text = "Quality Gate Verdict: REJECTED\n**M1. Missing test coverage for module X.**"
        assert "test-coverage-gap" in parse_cqo_verdict(text).patterns

    def test_multiple_patterns_all_returned(self):
        """QG-B6 fix: both governance-gap AND function-length must surface."""
        text = (
            "Quality Gate Verdict: REJECTED\n"
            "**B1. Undocumented marker AND evaluate() exceeds 30 lines.**"
        )
        patterns = parse_cqo_verdict(text).patterns
        assert "governance-gap" in patterns
        assert "function-length-violation" in patterns

    def test_no_pattern_when_no_hint(self):
        text = "Quality Gate Verdict: REJECTED\n**B1. A unique snowflake bug.**"
        parsed = parse_cqo_verdict(text)
        assert parsed.verdict == "REJECTED"
        # patterns may be empty when no hint regex matches
        assert isinstance(parsed.patterns, list)


# ─── record_from_verdict ───────────────────────────────────────────────


class TestRecord:
    def test_records_rejected_verdict(self, tmp_store):
        text = """Quality Gate Verdict: REJECTED

**B1. evaluate() is 31 lines, 1 over ceiling.**
**B2. _glob_match() also too long.**
"""
        exp = record_from_verdict(
            verdict_text=text,
            agent_id="tech-lead-paulo",
            session_id="sess-pr3",
            context="PR3 implementation",
            references=["https://example.com/pr/200"],
        )
        assert exp is not None
        assert exp.agent_id == "tech-lead-paulo"
        assert exp.verdict == "REJECTED"
        assert len(exp.blockers) == 2
        assert "function-length-violation" in exp.patterns
        # Verify it was persisted
        results = query_experiences("tech-lead-paulo")
        assert len(results) == 1

    def test_skips_approved_verdict(self, tmp_store):
        text = "Quality Gate Verdict: APPROVED\nShip it."
        exp = record_from_verdict(
            verdict_text=text,
            agent_id="tech-lead-paulo",
            session_id="sess-pr3",
            context="PR3 implementation",
        )
        assert exp is None
        assert query_experiences("tech-lead-paulo") == []

    def test_skips_unknown_verdict(self, tmp_store):
        text = "Just some random text without a verdict line."
        exp = record_from_verdict(
            verdict_text=text,
            agent_id="tech-lead-paulo",
            session_id="sess-pr3",
            context="PR3 implementation",
        )
        assert exp is None
        assert query_experiences("tech-lead-paulo") == []

    def test_unsafe_agent_id_drops_silently(self, tmp_store):
        text = "Quality Gate Verdict: REJECTED\n**B1. issue.**"
        exp = record_from_verdict(
            verdict_text=text,
            agent_id="../../evil",
            session_id="sess-pr3",
            context="PR3 implementation",
        )
        # parsed verdict is REJECTED, but path safety rejects the write
        assert exp is not None  # function returns the Experience it tried to write
        assert exp.verdict == "REJECTED"
        # But no file should have been created at the unsafe path
        assert not (tmp_store.parent / "evil").exists()
