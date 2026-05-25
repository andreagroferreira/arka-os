"""[arka:phase:13] / [arka:trivial] closing-marker soft-block (PR59 v2.76.0).

Response-side classifier. Inspects the closing assistant message of a
flow-required turn for the mandatory closure marker — either
``[arka:phase:13]`` (full flow completed) or ``[arka:trivial]``
(trivial bypass). Mirrors the contract of
``core.governance.meta_tag_check`` (PR30 v2.49.0) and
``core.governance.kb_cite_check`` (PR18 v2.40.0).

Telemetry analysis from the May 24-25 continuous-build session showed
**0% closing-marker rate** on every flow-required turn (5/5 rows
without ``[arka:phase:13]`` or ``[arka:trivial]``). PR59 surfaces the
gap to the next-turn nudge layer so the model is reminded to close
each flow-required turn with an explicit marker.

Soft-block contract — never raises. Hooks consume ClosingMarkerResult
and decide whether to surface a suggestion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_PHASE13_RE: re.Pattern[str] = re.compile(r"\[arka:phase:13\]", re.IGNORECASE)
_TRIVIAL_RE: re.Pattern[str] = re.compile(r"\[arka:trivial\]", re.IGNORECASE)
_TRIVIAL_WORD_THRESHOLD: int = 15
_SUGGESTION_TEXT: str = (
    "Closing marker missing — end every flow-required turn with "
    "`[arka:phase:13] <label>` (full canonical flow) or "
    "`[arka:trivial] <reason>` (single-file edit < 10 lines, "
    "imperative verb). Without the marker, telemetry can't confirm "
    "the turn closed cleanly."
)


@dataclass(frozen=True)
class ClosingMarkerResult:
    """Verdict of a closing-marker check. Immutable; safe to log as JSON."""

    passed: bool
    reason: str
    suggestion: str | None


def check_closing_marker(response_text: str) -> ClosingMarkerResult:
    """Classify whether a response carries a closing flow marker.

    Order matters: a SHORT response *with* a marker still counts as
    `present` — the trivial-length bypass only short-circuits when no
    marker is found.
    """
    text = response_text or ""
    if _PHASE13_RE.search(text):
        return ClosingMarkerResult(True, "phase13", None)
    if _TRIVIAL_RE.search(text):
        return ClosingMarkerResult(True, "trivial", None)
    if _is_trivial_length(text):
        return ClosingMarkerResult(True, "trivial-length", None)
    return ClosingMarkerResult(False, "missing", _SUGGESTION_TEXT)


def _is_trivial_length(text: str) -> bool:
    return len(text.split()) < _TRIVIAL_WORD_THRESHOLD
