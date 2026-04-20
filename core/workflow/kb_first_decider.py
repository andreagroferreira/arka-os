"""Confidence-based routing for KB-first intelligence loop.

Shared helper consumed by `research_gate` (to understand whether the
vault already covers a query) and by the auto-documentor (Task #7, to
tag confidence on the written-back note).

Design: pure function, no I/O, no dependencies beyond stdlib. Scores
are semantic-similarity averages in [0.0, 1.0]; thresholds match the
plan (2026-04-20-intelligence-v2) and ADR 2026-04-20-kb-first-*.
"""

from __future__ import annotations

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_NONE = "none"

_HIGH_THRESHOLD = 0.7
_MEDIUM_THRESHOLD = 0.5
_MIN_HITS_FOR_SIGNAL = 2


def decide_confidence(similarity_scores: list[float]) -> str:
    """Classify KB hit confidence from a list of similarity scores.

    Returns one of: "high" | "medium" | "low" | "none".

    Semantics (aligned with plan 2026-04-20-intelligence-v2):
        - high:   avg of top-3 >= 0.7 — KB is sufficient
        - medium: 0.5 <= avg < 0.7    — KB partial, supplement externally
        - low:    avg < 0.5 OR fewer than 2 hits — KB gap
        - none:   empty / no hits     — KB missing

    Non-numeric entries are silently dropped (never raise on a bad row).
    """
    cleaned = _coerce_scores(similarity_scores)
    if not cleaned:
        return CONFIDENCE_NONE
    if len(cleaned) < _MIN_HITS_FOR_SIGNAL:
        return CONFIDENCE_LOW
    top = sorted(cleaned, reverse=True)[:3]
    avg = sum(top) / len(top)
    if avg >= _HIGH_THRESHOLD:
        return CONFIDENCE_HIGH
    if avg >= _MEDIUM_THRESHOLD:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def _coerce_scores(raw: object) -> list[float]:
    if not isinstance(raw, list):
        return []
    out: list[float] = []
    for item in raw:
        try:
            val = float(item)
        except (TypeError, ValueError):
            continue
        if val != val:  # NaN
            continue
        out.append(max(0.0, min(1.0, val)))
    return out
