"""KB citation check for ArkaOS responses (PR18 v2.40.0).

Soft-block classifier. Inspects an assistant response for KB
citations (`[[wikilink]]`, `[knowledge:` marker, `file.ext:line`
code references) and reports whether the response honored the
KB-first contract on an ArkaOS topic.

Non-blocking by design — hooks consume CitationResult and decide
whether to surface a nudge to the next turn's additionalContext.
This module never raises; on malformed input it returns a passed
"trivial" verdict so the caller never crashes the hook pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ─── Patterns ───────────────────────────────────────────────────────────

_WIKILINK_PATTERN: re.Pattern[str] = re.compile(r"\[\[([^\[\]]+)\]\]")
_KNOWLEDGE_PATTERN: re.Pattern[str] = re.compile(r"\[knowledge:", re.IGNORECASE)
# File:line — requires at least one path separator. Quantifiers are bounded
# to prevent catastrophic backtracking on pathological input (PR18 security
# review: unbounded variant blew past Stop's 5s budget by ~8x on 100KB of
# `a/a/a/...` with no trailing extension).
_FILE_LINE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:[\w._-]{1,64}/){1,8}[\w._-]{1,64}\.\w{1,8}:\d{1,6}"
)
# Hard upper bound on input scanned for citations. Anything beyond is
# almost certainly a code dump / log paste and not human prose — skip the
# more expensive file-line regex entirely above this threshold.
_MAX_SCAN_CHARS: int = 50_000

# ArkaOS topic keywords. Match is case-insensitive substring.
_ARKAOS_KEYWORDS: frozenset[str] = frozenset({
    "arkaos", "arka", "constitution", "quality gate", "synapse",
    "conclave", "forge", "dreaming", "marta", "eduardo", "francisca",
    "marco", "helena", "sofia", "paulo", "luna", "valentina",
    "tomas", "ricardo", "clara", "daniel", "carolina", "tiago",
    "ines", "rafael", "beatriz", "miguel", "rodrigo",
    "non-negotiable", "tier 0", "squad lead",
    "core/governance", "core/synapse", "core/cognition",
    "core/workflow", "mcp__obsidian", "kb-first",
    "departments/", "agent yaml", "obsidian vault",
})

_BYPASS_DEFAULTS: tuple[str, ...] = ("[arka:trivial]",)
_TRIVIAL_WORD_THRESHOLD: int = 15
_TOPIC_THRESHOLD: float = 0.4
_SUGGESTION_TEXT: str = (
    "KB-first — last response had no citation on ArkaOS topic. "
    "Use @[[note-name]], /kb search, or mcp__obsidian__search_notes "
    "to ground the next answer."
)


# ─── Result ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CitationResult:
    """Verdict of a citation check. Immutable; safe to log as JSON."""
    passed: bool
    reason: str
    suggestion: str | None
    citation_count: int
    topic_score: float


# ─── Public API ─────────────────────────────────────────────────────────


def check_citation(
    response_text: str,
    *,
    topic_keywords: frozenset[str] | None = None,
    bypass_markers: tuple[str, ...] = _BYPASS_DEFAULTS,
) -> CitationResult:
    """Classify an assistant response for KB citation discipline."""
    text = response_text or ""
    citation_count = _count_citations(text)
    topic_score = _compute_topic_score(text, topic_keywords or _ARKAOS_KEYWORDS)

    if _has_bypass_marker(text, bypass_markers):
        return CitationResult(True, "trivial", None, citation_count, topic_score)

    if _is_trivial_length(text):
        return CitationResult(True, "trivial", None, citation_count, topic_score)

    if citation_count > 0:
        return CitationResult(True, "cited", None, citation_count, topic_score)

    if topic_score < _TOPIC_THRESHOLD:
        return CitationResult(True, "off-topic", None, 0, topic_score)

    return CitationResult(False, "missing", _SUGGESTION_TEXT, 0, topic_score)


# ─── Helpers (private) ──────────────────────────────────────────────────


def _has_bypass_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_trivial_length(text: str) -> bool:
    return len(text.split()) < _TRIVIAL_WORD_THRESHOLD


def _count_citations(text: str) -> int:
    # Truncate to _MAX_SCAN_CHARS first; the file-line regex is the only
    # backtracking-prone pattern and the bounded quantifiers (capped at 8
    # segments × 64 chars each) combined with this slice make all three
    # patterns safe to run unconditionally below.
    scan = text if len(text) <= _MAX_SCAN_CHARS else text[:_MAX_SCAN_CHARS]
    wikilinks = len(_WIKILINK_PATTERN.findall(scan))
    knowledge = 1 if _KNOWLEDGE_PATTERN.search(scan) else 0
    files = len(_FILE_LINE_PATTERN.findall(scan))
    return wikilinks + knowledge + files


def _compute_topic_score(text: str, keywords: frozenset[str]) -> float:
    if not keywords:
        return 0.0
    lower = text.lower()
    hits = sum(1 for k in keywords if k.lower() in lower)
    denom = max(1, len(keywords) // 10)
    return min(1.0, hits / denom)
