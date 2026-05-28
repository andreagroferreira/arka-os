"""Parse Marta (CQO) verdict text and persist Experience records.

When the orchestrator dispatches the `cqo` subagent for a Quality Gate
review, Marta returns a verdict in a stable format (`Quality Gate
Verdict: APPROVED|REJECTED`, with blockers labelled `B1.`, `B2.`,
`M1.`, ...). This module parses that text and, when the verdict is
REJECTED, appends an `Experience` to the failing agent's log so future
dispatches inherit the lesson.

For PR3 v1 the recorder is invoked manually by the orchestrator after a
CQO dispatch. A future PR can wire it into a PostToolUse hook on the
`Agent` tool so the persistence happens automatically.

PR3 of the Squad Intelligence Upgrade.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from core.governance.agent_experiences import (
    Experience,
    record_experience,
)


_VERDICT_RE = re.compile(
    r"Quality Gate Verdict:\s*(APPROVED|REJECTED)", re.IGNORECASE
)

# Blocker headings used by Marta across the codebase. Examples observed:
# `**B1.` `**B2.` `**M1.` (markdown bold + dot/colon)
# `B1.` `B1:` (plain)
# `B1 description` (space-only separator — PR3 v3.74.0 widened per QG B5)
# `B10.` `B11.` (double-digit labels)
#
# Documented limitation: inline blocker references mid-paragraph
# (e.g., "The reviewer noted B1. is problematic") are NOT extracted —
# only line-anchored labels qualify. This is intentional to keep
# false-positive rate low; if we ever need inline capture, add a
# separate pass with a stricter context check.
_BLOCKER_RE = re.compile(
    r"^(?:\*\*)?\s*([BMN])(\d+)[\s\.:](?:\s*\*\*)?\s*(.+?)(?:\*\*)?$",
    re.MULTILINE,
)

# Common pattern hints Marta surfaces. Order matters — first match wins.
_PATTERN_HINTS: tuple[tuple[str, str], ...] = (
    (r"function length|line ceiling|\d+\s+lines?|exceeds.*line", "function-length-violation"),
    (r"command[ -]injection|CWE-77|shell escape", "command-injection-risk"),
    (r"path[ -]traversal|CWE-22", "path-traversal-risk"),
    (r"undocumented|missing.*constitution|not in flow", "governance-gap"),
    (r"missing.*test|zero.*coverage|no pytest", "test-coverage-gap"),
    (r"workaround|hack|shortcut|TODO", "shortcut-applied"),
    (r"client name|leak|confidential", "confidentiality-risk"),
    (r"sycophancy|yes[- ]man|capitulat", "sycophancy-violation"),
)


@dataclass
class ParsedVerdict:
    """Structured view of a Marta verdict string."""

    verdict: str  # "APPROVED" | "REJECTED" | "UNKNOWN"
    blockers: list[str]
    patterns: list[str]


def parse_cqo_verdict(text: str) -> ParsedVerdict:
    """Extract verdict, blocker list, and ALL matching pattern hints."""
    if not text:
        return ParsedVerdict(verdict="UNKNOWN", blockers=[], patterns=[])
    verdict = _extract_verdict(text)
    blockers = _extract_blockers(text) if verdict == "REJECTED" else []
    patterns = _classify_patterns(text) if verdict == "REJECTED" else []
    return ParsedVerdict(verdict=verdict, blockers=blockers, patterns=patterns)


def _extract_verdict(text: str) -> str:
    match = _VERDICT_RE.search(text)
    if not match:
        return "UNKNOWN"
    return match.group(1).upper()


def _extract_blockers(text: str) -> list[str]:
    """Capture lines that start with a blocker label (B/M/N + digits)."""
    blockers: list[str] = []
    for match in _BLOCKER_RE.finditer(text):
        kind, num, headline = match.group(1), match.group(2), match.group(3)
        # Strip markdown markers and trailing whitespace.
        headline = headline.replace("**", "").strip()
        # Cap headline length so a single misformatted line cannot dominate.
        if len(headline) > 200:
            headline = headline[:197] + "..."
        blockers.append(f"{kind}{num}: {headline}")
    return blockers


def _classify_patterns(text: str) -> list[str]:
    """Return ALL matching pattern labels, in registry order.

    First-match-wins was masking secondary patterns (PR3 QG-B6): a
    verdict citing both governance-gap and function-length would be
    classified only as function-length, and the agent would miss the
    structural lesson. Returning all matches lets the dispatched agent
    see every category at once.
    """
    lowered = text.lower()
    matched: list[str] = []
    for pattern, label in _PATTERN_HINTS:
        if re.search(pattern, lowered, re.IGNORECASE):
            matched.append(label)
    return matched


def _build_experience(
    parsed: "ParsedVerdict",
    *,
    agent_id: str,
    session_id: str,
    context: str,
    references: list[str] | None,
    tags: list[str] | None,
    fix_applied: str | None,
) -> Experience:
    """Compose an Experience from a parsed REJECTED verdict + caller metadata."""
    return Experience(
        ts=datetime.now(timezone.utc).isoformat(),
        agent_id=agent_id,
        session_id=session_id,
        context=context,
        verdict="REJECTED",
        blockers=parsed.blockers,
        patterns=parsed.patterns,
        fix_applied=fix_applied,
        references=references or [],
        tags=tags or [],
    )


def record_from_verdict(
    *,
    verdict_text: str,
    agent_id: str,
    session_id: str,
    context: str,
    references: list[str] | None = None,
    tags: list[str] | None = None,
    fix_applied: str | None = None,
) -> Experience | None:
    """Parse `verdict_text` and append one Experience to `agent_id`'s log.

    Returns the persisted Experience, or None when the verdict is not
    REJECTED (APPROVED + UNKNOWN are not lessons worth recording).
    """
    parsed = parse_cqo_verdict(verdict_text)
    if parsed.verdict != "REJECTED":
        return None
    experience = _build_experience(
        parsed,
        agent_id=agent_id,
        session_id=session_id,
        context=context,
        references=references,
        tags=tags,
        fix_applied=fix_applied,
    )
    record_experience(experience)
    return experience
