"""[arka:meta] one-liner soft-block check (PR30 v2.49.0).

Response-side classifier. Inspects an assistant response for the
``[arka:meta] kb=N research=X persona=Y gap=Z critic=W`` one-liner
established by the session-start hook in PR12 v2.34.0.

Soft-block contract — never raises. Hooks consume MetaTagResult and
decide whether to surface a suggestion. Mirrors the shape of
``core.governance.kb_cite_check`` (PR18 v2.40.0).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_META_TAG_RE: re.Pattern[str] = re.compile(r"\[arka:meta\]", re.IGNORECASE)
_BYPASS_DEFAULTS: tuple[str, ...] = ("[arka:trivial]",)
_TRIVIAL_WORD_THRESHOLD: int = 15
_SUGGESTION_TEXT: str = (
    "Meta-tag missing — end substantive responses with a single "
    "`[arka:meta] kb=N research=X persona=Y gap=Z critic=W` line. "
    "Fields: kb=N (notes consulted), research=X (MCPs invoked or "
    "'none'), persona=Y (advisor or 'orchestrator'), gap=Z (KB gap "
    "or 'none'), critic=W (passed|failed|skipped)."
)


@dataclass(frozen=True)
class MetaTagResult:
    """Verdict of a meta-tag check. Immutable; safe to log as JSON."""
    passed: bool
    reason: str
    suggestion: str | None


def check_meta_tag(
    response_text: str,
    *,
    bypass_markers: tuple[str, ...] = _BYPASS_DEFAULTS,
) -> MetaTagResult:
    """Classify whether a response carries the [arka:meta] one-liner.

    Order matters: a SHORT response *with* the tag still counts as
    `present` — the trivial-length bypass only short-circuits when
    the tag genuinely isn't there.
    """
    text = response_text or ""
    if _has_bypass_marker(text, bypass_markers):
        return MetaTagResult(True, "trivial", None)
    if _META_TAG_RE.search(text):
        return MetaTagResult(True, "present", None)
    if _is_trivial_length(text):
        return MetaTagResult(True, "trivial", None)
    return MetaTagResult(False, "missing", _SUGGESTION_TEXT)


def _has_bypass_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_trivial_length(text: str) -> bool:
    return len(text.split()) < _TRIVIAL_WORD_THRESHOLD
