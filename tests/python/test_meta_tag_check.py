"""Tests for core.governance.meta_tag_check (PR30 v2.49.0).

Response-side classifier for the [arka:meta] one-liner contract
established by the session-start hook (PR12 v2.34.0). Mirrors the
shape of kb_cite_check (PR18 v2.40.0).

Soft block: classifier returns MetaTagResult, hooks decide whether
to surface a suggestion. Never raises.
"""

from __future__ import annotations

import pytest

from core.governance.meta_tag_check import (
    MetaTagResult,
    check_meta_tag,
    parse_reported_kb,
    reconcile_kb_count,
)


# ─── Present (pass cases) ───────────────────────────────────────────────


class TestPresent:
    def test_canonical_one_liner_passes(self):
        text = (
            "Did the work, here is the summary.\n\n"
            "[arka:meta] kb=2 research=none persona=Marta gap=none critic=passed"
        )
        result = check_meta_tag(text)
        assert isinstance(result, MetaTagResult)
        assert result.passed is True
        assert result.reason == "present"

    def test_minimal_tag_passes(self):
        text = "Some response.\n\n[arka:meta] kb=0 research=none persona=orchestrator gap=none critic=skipped"
        result = check_meta_tag(text)
        assert result.passed is True

    def test_case_insensitive_match(self):
        text = "Reply.\n[ARKA:META] kb=1 research=none persona=Paulo gap=none critic=passed"
        result = check_meta_tag(text)
        assert result.passed is True


# ─── Bypass markers (short-circuit pass) ────────────────────────────────


class TestBypass:
    def test_arka_trivial_bypass(self):
        text = "[arka:trivial] one-line typo fix"
        result = check_meta_tag(text)
        assert result.passed is True
        assert result.reason == "trivial"

    def test_short_ack_bypass(self):
        result = check_meta_tag("ok")
        assert result.passed is True
        assert result.reason == "trivial"

    def test_empty_response_bypass(self):
        result = check_meta_tag("")
        assert result.passed is True
        assert result.reason == "trivial"


# ─── Missing (fail with suggestion) ─────────────────────────────────────


class TestMissing:
    def test_substantive_response_without_meta_fails(self):
        text = (
            "Here is the full analysis of the situation. We looked at "
            "several factors and concluded the following: option A is "
            "better than option B because it has clearer trade-offs and "
            "better fits the existing architecture. The implementation "
            "would take about two days and include three tests."
        )
        result = check_meta_tag(text)
        assert result.passed is False
        assert result.reason == "missing"
        assert result.suggestion is not None
        assert "[arka:meta]" in result.suggestion

    def test_suggestion_lists_required_fields(self):
        text = "Long enough substantive response without the meta tag. " * 10
        result = check_meta_tag(text)
        assert result.passed is False
        for cue in ("kb=", "research=", "persona=", "gap=", "critic="):
            assert cue in result.suggestion

    def test_suggestion_is_neutral_factual(self):
        text = "This is a long enough response to qualify as substantive. " * 10
        result = check_meta_tag(text)
        assert result.passed is False
        # No exclamation, no emoji, no AI clichés
        assert "!" not in result.suggestion
        assert "🎯" not in result.suggestion


# ─── Return shape contract ──────────────────────────────────────────────


class TestResultShape:
    def test_result_is_frozen(self):
        result = check_meta_tag("ok")
        assert isinstance(result, MetaTagResult)
        with pytest.raises((AttributeError, Exception)):
            result.passed = False

    def test_passed_results_have_no_suggestion(self):
        result = check_meta_tag("ok")
        assert result.passed is True
        assert result.suggestion is None


# ─── kb=N reconciliation (structural honesty PR-2) ──────────────────────


class TestParseReportedKb:
    def test_extracts_kb_count(self):
        text = "Done.\n[arka:meta] kb=3 research=none persona=Marta gap=none critic=passed"
        assert parse_reported_kb(text) == 3

    def test_zero_is_valid(self):
        text = "[arka:meta] kb=0 research=none persona=orchestrator gap=none critic=skipped"
        assert parse_reported_kb(text) == 0

    def test_case_insensitive(self):
        text = "[ARKA:META] kb=7 research=none persona=Paulo gap=none critic=passed"
        assert parse_reported_kb(text) == 7

    def test_none_when_tag_absent(self):
        assert parse_reported_kb("No meta tag here at all.") is None

    def test_none_when_kb_field_absent(self):
        assert parse_reported_kb("[arka:meta] research=none persona=x") is None

    def test_none_on_empty_input(self):
        assert parse_reported_kb("") is None

    def test_kb_on_other_line_not_matched(self):
        text = "[arka:meta] research=none\nkb=9 unrelated line"
        assert parse_reported_kb(text) is None


class TestReconcileKbCount:
    def test_inflated_when_reported_exceeds_injected(self):
        result = reconcile_kb_count(reported=5, injected=2)
        assert result == {"kb_reported": 5, "kb_injected": 2, "kb_inflated": True}

    def test_not_inflated_when_equal(self):
        result = reconcile_kb_count(reported=2, injected=2)
        assert result["kb_inflated"] is False

    def test_not_inflated_when_reported_below_injected(self):
        result = reconcile_kb_count(reported=1, injected=3)
        assert result["kb_inflated"] is False

    def test_unknown_reported_never_flags(self):
        result = reconcile_kb_count(reported=None, injected=3)
        assert result == {"kb_reported": None, "kb_injected": 3, "kb_inflated": False}

    def test_unknown_injected_never_flags(self):
        result = reconcile_kb_count(reported=5, injected=None)
        assert result == {"kb_reported": 5, "kb_injected": None, "kb_inflated": False}

    def test_both_unknown(self):
        result = reconcile_kb_count(reported=None, injected=None)
        assert result["kb_inflated"] is False

    def test_zero_reported_zero_injected(self):
        result = reconcile_kb_count(reported=0, injected=0)
        assert result["kb_inflated"] is False
