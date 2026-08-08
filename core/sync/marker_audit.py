"""Feature-marker self-check for the ArkaOS Sync Engine.

Phase 4 of ``/arka update`` injects each feature section wrapped in
``<!-- arka:feature:<name>:start -->`` / ``:end`` markers. That marker pair
is the detection anchor, the removal anchor AND the drift anchor, and every
consumer — the sync workflow, the deprecation step, the repo drift lock —
matches it **literally**.

Why this module exists (issue #492): a run once stamped those markers with
the attributes that belong to the ``arkaos:managed`` block
(``version=… hash=…``). Literal matchers stopped matching, and a non-match
was read as "no marker in this file" rather than "this marker is broken".
Eight stamped markers across five installed skills survived two releases
(v5.10 → v5.14) with every check reporting clean; they were normalised by
hand on 2026-08-07 (``~/.arkaos/audit/phase4-sync-2026-08-07.json``).

Two design choices follow directly from that failure:

1. **Classification is total.** One regex recognises a marker by its
   ``arka:feature:<name>:<side>`` core regardless of what trails it, then
   sorts the result into bare (the contract), stamped, or malformed. There
   is no path where a recognisable marker is silently dropped — that path
   *was* the bug.
2. **The scan reaches the installed tree.** The markers live in
   ``~/.claude/skills``, not in the repo. A lock that only reads the repo
   cannot see the files that drifted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_SKILLS_ROOT = Path.home() / ".claude" / "skills"

ViolationKind = Literal["stamped", "malformed", "unreadable"]

# The canonical marker is exactly `<!-- arka:feature:<name>:start -->`:
# one space each side of the payload, nothing else.
_CANONICAL_PAD = " "

_TOKEN = "arka:feature:"
_COMMENT_RE = re.compile(r"<!--(?P<body>.*?)-->", re.DOTALL)
_MARKER_RE = re.compile(
    r"(?P<lead>\s*)arka:feature:(?P<name>[A-Za-z0-9._-]+)"
    r":(?P<side>start|end)(?P<trail>[\s\S]*)"
)
_FENCE_RE = re.compile(
    r"^ {0,3}(?P<fence>`{3,}|~{3,})[^\n]*$.*?^ {0,3}(?P=fence)[^\n]*$",
    re.DOTALL | re.MULTILINE,
)
_CODE_SPAN_RE = re.compile(r"(?P<ticks>`+)(?:(?!(?P=ticks)).)*?(?P=ticks)")


@dataclass(frozen=True)
class MarkerViolation:
    """One feature marker that no literal consumer would ever match."""

    path: Path
    line: int
    kind: ViolationKind
    marker: str
    reason: str

    def describe(self) -> str:
        """Phase-prefixed, linter-style ``path:line: reason`` line.

        Carries the offending marker text verbatim: "a marker is wrong
        somewhere" is what let this rot for two releases.
        """
        tail = f" — {self.marker}" if self.marker else ""
        return f"Markers: {self.path}:{self.line}: {self.reason}{tail}"


def classify_marker(body: str) -> tuple[ViolationKind, str] | None:
    """Classify one HTML-comment body; ``None`` means canonical.

    Whitespace is part of the contract, not cosmetics:
    ``<!--arka:feature:x:start-->`` is invisible to the removal pattern in
    exactly the same way a stamp is, so it is a violation too.
    """
    match = _MARKER_RE.fullmatch(body)
    if match is None:
        if "<!--" in body:
            # Seen live in arka-scaffold/SKILL.md: an unterminated comment
            # opened above the injection point, so the first marker closes
            # THAT comment instead of standing on its own — and the real
            # comment's tail renders as visible garbage further down.
            return (
                "malformed",
                "an unterminated HTML comment above it swallows this feature "
                "marker",
            )
        return ("malformed", "not a well-formed arka:feature marker")
    trail = match.group("trail")
    if trail.strip():
        return (
            "stamped",
            f"feature marker carries a stamp ({trail.strip()}); every literal "
            "consumer skips it",
        )
    if match.group("lead") != _CANONICAL_PAD or trail != _CANONICAL_PAD:
        return ("malformed", "non-canonical whitespace inside the marker")
    return None


def scan_text(text: str, path: Path) -> list[MarkerViolation]:
    """Every non-canonical feature marker in one document, in file order.

    Code spans and fenced blocks are blanked first: the reference docs
    describe the contract with a ``<name>`` placeholder inside backticks,
    and a lock that cries wolf on its own documentation gets muted.
    """
    scannable = _blank_code(text)
    violations: list[MarkerViolation] = []
    for match in _COMMENT_RE.finditer(scannable):
        if _TOKEN not in match.group("body"):
            continue
        verdict = classify_marker(match.group("body"))
        if verdict is None:
            continue
        kind, reason = verdict
        violations.append(
            MarkerViolation(
                path=path,
                line=text.count("\n", 0, match.start()) + 1,
                kind=kind,
                marker=match.group(0).strip(),
                reason=reason,
            )
        )
    return violations


def scan_tree(root: Path, *, glob: str = "*.md") -> list[MarkerViolation]:
    """Every marker violation under ``root``, ordered by path then line.

    A missing root yields no violations — "not installed" is not a marker
    defect. A file that cannot be decoded yields one: the entire defect this
    module exists for was a skip nobody was told about.
    """
    if not root.is_dir():
        return []
    found: list[MarkerViolation] = []
    for document in sorted(root.rglob(glob)):
        try:
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            found.append(
                MarkerViolation(
                    path=document,
                    line=0,
                    kind="unreadable",
                    marker="",
                    reason=f"cannot be scanned for feature markers: {exc}",
                )
            )
            continue
        found += scan_text(text, document)
    return found


def audit_installed_skills(root: Path | None = None) -> list[MarkerViolation]:
    """Self-check the INSTALLED skills tree (default ``~/.claude/skills``).

    This is where the markers actually live. The repo-side lock in
    ``tests/python/test_sync_features_registry.py`` covers ``arka/`` and
    ``departments/``; neither ever contained the eight markers that drifted.
    """
    return scan_tree(root if root is not None else DEFAULT_SKILLS_ROOT)


def _blank_code(text: str) -> str:
    """Blank fenced blocks and code spans, preserving every byte offset.

    Same-length whitespace rather than deletion, so reported line numbers
    still point at the real line in the original file.
    """
    return _CODE_SPAN_RE.sub(_blank_match, _FENCE_RE.sub(_blank_match, text))


def _blank_match(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))
