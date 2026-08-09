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
At least 13 stamped markers across five installed skills (the audit
record counts 2+3+4+4 and leaves one skill uncounted) survived four
releases (v5.10 → v5.14) with every check reporting clean; they were
normalised by hand on 2026-08-07
(``~/.arkaos/audit/phase4-sync-2026-08-07.json``).

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

import os
import re
from fnmatch import fnmatch
from pathlib import Path

from core.sync.schema import MarkerViolation, ViolationKind

DEFAULT_SKILLS_ROOT = Path.home() / ".claude" / "skills"

# The canonical marker is exactly `<!-- arka:feature:<name>:start -->`:
# one space each side of the payload, nothing else.
_CANONICAL_PAD = " "

# A document larger than this is not scanned; it is REPORTED as unreadable.
# Bounds the worst case on a tree the engine now walks on every sync (the
# largest real skill document is 83 KB).
_MAX_DOCUMENT_BYTES = 1_000_000

_TOKEN = "arka:feature:"
_COMMENT_RE = re.compile(r"<!--(?P<body>.*?)-->", re.DOTALL)
# `(?![A-Za-z0-9._-])` after the side keeps `:startX` out of the stamped
# bucket: a typo in the side is malformed, not a stamp.
_MARKER_RE = re.compile(
    r"(?P<lead>\s*)arka:feature:(?P<name>[A-Za-z0-9._-]+)"
    r":(?P<side>start|end)(?![A-Za-z0-9._-])(?P<trail>[\s\S]*)"
)
# Both patterns are linear: no backreference, no tempered dot. The previous
# pair backtracked superlinearly (8000 backticks took 10.3 s) on a function
# the engine now runs over every file of the installed tree.
_FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
_CODE_SPAN_RE = re.compile(r"`+[^`\n]*`+")

_SWALLOWED = (
    "an unterminated HTML comment swallows this feature marker"
)


def classify_marker(body: str) -> tuple[ViolationKind, str] | None:
    """Classify one HTML-comment body; ``None`` means canonical.

    Whitespace is part of the contract, not cosmetics:
    ``<!--arka:feature:x:start-->`` is invisible to the removal pattern in
    exactly the same way a stamp is, so it is a violation too.
    """
    # Checked before the marker shape: a body holding a second `<!--` means
    # this marker's `-->` closed someone else's comment (seen live in
    # arka-scaffold/SKILL.md), which is the accurate diagnosis even when the
    # remainder happens to look like a stamp.
    if "<!--" in body:
        return ("malformed", _SWALLOWED)
    match = _MARKER_RE.fullmatch(body)
    if match is None:
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
    defect. Anything present but unscannable yields one: the entire defect
    this module exists for was a skip nobody was told about.
    """
    if not root.is_dir():
        return []
    found: list[MarkerViolation] = []
    for document in _walk_documents(root, glob, found):
        try:
            if document.stat().st_size > _MAX_DOCUMENT_BYTES:
                raise OSError(f"exceeds the {_MAX_DOCUMENT_BYTES}-byte scan limit")
            text = document.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            found.append(_unscannable(document, exc))
            continue
        found += scan_text(text, document)
    return sorted(found, key=lambda v: (str(v.path), v.line))


def _walk_documents(root: Path, glob: str, found: list[MarkerViolation]) -> list[Path]:
    """Matching documents under ``root``, following symlinked directories.

    ``rglob`` does not descend into symlinked directories, and said nothing
    about it: on the operator's tree that hid 30 markdown files inside six
    symlinked third-party skills — the same silent skip this module exists
    to abolish, moved from the regex to the walker. Cycles are broken on
    device+inode identity, and a directory that cannot be listed is
    reported rather than dropped.
    """
    documents: list[Path] = []
    visited: set[tuple[int, int]] = set()

    def on_error(exc: OSError) -> None:
        found.append(_unscannable(Path(exc.filename or root), exc))

    walker = os.walk(root, followlinks=True, onerror=on_error)
    for dirpath, dirnames, filenames in walker:
        identity = _identity(dirpath)
        if identity is None or identity in visited:
            dirnames[:] = []
            continue
        visited.add(identity)
        documents += [Path(dirpath) / n for n in filenames if fnmatch(n, glob)]
    return sorted(documents)


def _identity(dirpath: str) -> tuple[int, int] | None:
    """Device+inode of a directory, or None when it cannot be stat'd."""
    try:
        info = os.stat(dirpath)
    except OSError:
        return None
    return (info.st_dev, info.st_ino)


def _unscannable(path: Path, exc: BaseException) -> MarkerViolation:
    """Report a path the scanner could not read, instead of dropping it."""
    return MarkerViolation(
        path=path,
        line=0,
        kind="unreadable",
        marker="",
        reason=f"cannot be scanned for feature markers: {exc}",
    )


def audit_installed_skills(root: Path | None = None) -> list[MarkerViolation]:
    """Self-check the INSTALLED skills tree (default ``~/.claude/skills``).

    This is where the markers actually live. The repo-side lock in
    ``tests/python/test_sync_features_registry.py`` covers ``arka/`` and
    ``departments/``; neither ever contained the markers that drifted.
    """
    return scan_tree(root if root is not None else DEFAULT_SKILLS_ROOT)


def _blank_code(text: str) -> str:
    """Blank fenced blocks and code spans, preserving every byte offset.

    Same-length whitespace rather than deletion, so reported line numbers
    still point at the real line. Line-based on purpose: the regex that
    used to span whole fences backtracked superlinearly, and this runs over
    every file of the installed tree. An UNCLOSED fence blanks nothing —
    a marker below it still reports, because the alternative silently
    swallows the rest of the document.
    """
    lines = text.splitlines(keepends=True)
    blanked: list[str | None] = [None] * len(lines)
    opened_at: int | None = None
    fence = ""
    for index, line in enumerate(lines):
        opener = _FENCE_RE.match(line)
        if opened_at is None:
            if opener is None:
                blanked[index] = _CODE_SPAN_RE.sub(_blank_match, line)
            else:
                opened_at, fence = index, opener.group("fence")
        elif _closes(opener, fence):
            for inner in range(opened_at, index + 1):
                blanked[inner] = _blank_text(lines[inner])
            opened_at = None
    return "".join(
        done if done is not None else _CODE_SPAN_RE.sub(_blank_match, raw)
        for done, raw in zip(blanked, lines, strict=True)
    )


def _closes(opener: re.Match[str] | None, fence: str) -> bool:
    """True when this line closes a fence opened with ``fence``."""
    if opener is None:
        return False
    closing = opener.group("fence")
    return closing[0] == fence[0] and len(closing) >= len(fence)


def _blank_match(match: re.Match[str]) -> str:
    return _blank_text(match.group(0))


def _blank_text(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)
