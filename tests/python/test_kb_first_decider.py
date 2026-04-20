"""Tests for core.workflow.kb_first_decider."""

from __future__ import annotations

import math

import pytest

from core.workflow.kb_first_decider import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    decide_confidence,
)


def test_decide_confidence_high():
    # Top-3 avg = (0.9 + 0.8 + 0.7) / 3 = 0.8
    assert decide_confidence([0.9, 0.8, 0.7, 0.3]) == CONFIDENCE_HIGH


def test_decide_confidence_high_boundary():
    # Just above the 0.7 threshold must classify as high (float-safe).
    assert decide_confidence([0.71, 0.71, 0.71]) == CONFIDENCE_HIGH


def test_decide_confidence_medium():
    # Top-3 avg = 0.6
    assert decide_confidence([0.6, 0.6, 0.6]) == CONFIDENCE_MEDIUM


def test_decide_confidence_low():
    # Top-3 avg = 0.4
    assert decide_confidence([0.4, 0.4, 0.4]) == CONFIDENCE_LOW


def test_decide_confidence_low_single_hit():
    # Fewer than 2 hits → low even if the single score is strong.
    assert decide_confidence([0.95]) == CONFIDENCE_LOW


def test_decide_confidence_none():
    assert decide_confidence([]) == CONFIDENCE_NONE


def test_decide_confidence_empty_list():
    # Semantic duplicate of test_decide_confidence_none — explicit contract.
    assert decide_confidence([]) == CONFIDENCE_NONE


def test_decide_confidence_none_on_garbage_input():
    # Completely invalid inputs are coerced to empty → none.
    assert decide_confidence(["x", None, {}]) == CONFIDENCE_NONE  # type: ignore[list-item]


def test_decide_confidence_drops_nan():
    # NaN entries are silently dropped; remaining valid scores decide.
    assert decide_confidence([float("nan"), 0.8, 0.8, 0.8]) == CONFIDENCE_HIGH


def test_decide_confidence_clamps_above_one():
    assert decide_confidence([1.5, 1.2, 1.1]) == CONFIDENCE_HIGH


def test_decide_confidence_clamps_below_zero():
    assert decide_confidence([-0.2, -0.1, 0.3]) == CONFIDENCE_LOW


def test_decide_confidence_uses_only_top_three():
    # Top-3 of [0.9,0.9,0.9,0.1,0.1] is (0.9,0.9,0.9) avg 0.9 → high
    assert decide_confidence([0.9, 0.9, 0.9, 0.1, 0.1]) == CONFIDENCE_HIGH


def test_decide_confidence_rejects_non_list():
    # Non-list inputs are silently treated as empty (never raises).
    assert decide_confidence("not-a-list") == CONFIDENCE_NONE  # type: ignore[arg-type]
    assert decide_confidence(None) == CONFIDENCE_NONE  # type: ignore[arg-type]


def test_decide_confidence_two_hits_medium_boundary():
    # Two hits at 0.5 → avg=0.5 → medium (>=0.5).
    assert decide_confidence([0.5, 0.5]) == CONFIDENCE_MEDIUM


@pytest.mark.parametrize(
    "scores,expected",
    [
        ([0.75, 0.8, 0.85], CONFIDENCE_HIGH),
        ([0.55, 0.6, 0.65], CONFIDENCE_MEDIUM),
        ([0.1, 0.2, 0.3], CONFIDENCE_LOW),
        ([], CONFIDENCE_NONE),
    ],
)
def test_decide_confidence_parametric(scores, expected):
    assert decide_confidence(scores) == expected


def test_decide_confidence_no_float_inf():
    # +inf is coerced safely (clamped to 1.0) and does not crash.
    result = decide_confidence([math.inf, 0.8, 0.8])
    assert result == CONFIDENCE_HIGH
