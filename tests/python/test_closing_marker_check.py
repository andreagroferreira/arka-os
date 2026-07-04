"""Tests for core.governance.closing_marker_check (PR59 v2.76.0).

Response-side classifier for the [arka:phase:13] / [arka:trivial]
closing markers. Mirrors the shape of meta_tag_check (PR30 v2.49.0).

Soft block: classifier returns ClosingMarkerResult, hooks decide
whether to surface a suggestion. Never raises.
"""

from __future__ import annotations

import pytest

from core.governance.closing_marker_check import (
    ClosingMarkerResult,
    check_closing_marker,
)


# ─── Present (pass cases) ───────────────────────────────────────────────


class TestPresent:
    def test_gate4_marker_passes(self):
        text = (
            "Shipped v4.1.0. Lint, type-check, and coverage all green.\n\n"
            "[arka:gate:4] review complete — evidence attached above"
        )
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "gate4"
        assert result.suggestion is None

    def test_gate4_case_insensitive(self):
        text = "[ARKA:GATE:4] done with " + ("more text " * 20)
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "gate4"

    def test_phase13_marker_passes(self):
        text = (
            "Shipped v2.76.0 to npm. Tests green, preflight passed.\n\n"
            "[arka:phase:13] Done — v2.76.0 live on npm"
        )
        result = check_closing_marker(text)
        assert isinstance(result, ClosingMarkerResult)
        assert result.passed is True
        assert result.reason == "phase13"
        assert result.suggestion is None

    def test_trivial_marker_passes(self):
        text = "[arka:trivial] single-line typo fix in README"
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "trivial"

    def test_phase13_case_insensitive(self):
        text = "[ARKA:PHASE:13] done with " + ("more text " * 20)
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "phase13"

    def test_phase13_anywhere_in_text(self):
        """Marker can appear anywhere in the closing message, not just last line."""
        text = (
            "Started work...\n"
            "Now finishing.\n\n"
            "[arka:phase:13] Done — v2.76.0\n\n"
            "Final notes here, more prose follows."
        )
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "phase13"


# ─── Trivial-length bypass (also pass) ──────────────────────────────────


class TestTrivialLength:
    def test_short_response_passes(self):
        text = "Yes."
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "trivial-length"

    def test_one_sentence_passes(self):
        text = "Confirmed — looks good."
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "trivial-length"

    def test_exactly_14_words_passes(self):
        text = " ".join(["w"] * 14)
        assert check_closing_marker(text).passed is True

    def test_exactly_15_words_fails(self):
        text = " ".join(["w"] * 15)
        result = check_closing_marker(text)
        assert result.passed is False
        assert result.reason == "missing"


# ─── Missing (fail cases) ───────────────────────────────────────────────


class TestMissing:
    def test_long_response_without_marker_fails(self):
        text = (
            "Did a long batch of work today. Shipped four PRs, ran tests, "
            "updated documentation, and merged everything to master. "
            "Total of 15 new tests passed. Preflight green. No client "
            "name leaks. Coffee was also good."
        )
        result = check_closing_marker(text)
        assert result.passed is False
        assert result.reason == "missing"
        assert result.suggestion is not None
        assert "[arka:gate:4]" in result.suggestion
        assert "[arka:trivial]" in result.suggestion

    def test_partial_marker_does_not_pass(self):
        """A response that mentions phase:13 in prose but not as a tag
        must NOT pass — we need the exact bracketed marker."""
        text = (
            "Following the phase 13 of the canonical flow, I did the work "
            "and shipped to npm with proper testing throughout. " * 3
        )
        result = check_closing_marker(text)
        assert result.passed is False

    def test_arka_phase_with_other_number_does_not_pass(self):
        """[arka:phase:5] must NOT count as a closing marker — only :13."""
        text = (
            "[arka:phase:5] starting phase 5\n\n"
            "Doing the work now and continuing through the steps "
            "but not yet at phase 13 of the canonical flow."
        )
        result = check_closing_marker(text)
        assert result.passed is False
        assert result.reason == "missing"


# ─── Defensive edges ────────────────────────────────────────────────────


class TestDefensive:
    def test_none_input_does_not_raise(self):
        # Hooks may pass empty / None text on edge cases. Must not raise.
        result = check_closing_marker(None)  # type: ignore[arg-type]
        assert result.passed is True
        assert result.reason == "trivial-length"

    def test_empty_string_passes_as_trivial(self):
        result = check_closing_marker("")
        assert result.passed is True
        assert result.reason == "trivial-length"

    def test_both_markers_present_picks_phase13(self):
        """If both markers somehow appear, phase13 wins (full flow > bypass)."""
        text = "[arka:phase:13] full flow\n[arka:trivial] also trivial"
        result = check_closing_marker(text)
        assert result.passed is True
        assert result.reason == "phase13"


# ─── Result shape ───────────────────────────────────────────────────────


def test_result_is_immutable():
    result = check_closing_marker("[arka:phase:13] done with the work " + "x" * 50)
    with pytest.raises(Exception):
        result.passed = False  # type: ignore[misc]
