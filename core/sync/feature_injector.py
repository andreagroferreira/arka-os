"""Feature-section injector for ``/arka update`` Phase 4.

Phase 4 adds a registry feature to an ecosystem SKILL.md by writing its
marker-wrapped ``content`` at a chosen point in the document. Choosing
that point needs judgement about the host's own material, so it stays with
the Phase-4 consumer; performing the write does not, and that is what this
module owns.

Why it exists (issue #509). A run picked an insertion point that sat
INSIDE an unterminated HTML comment: line 20 of an installed SKILL.md
opened ``<!-- Column convention: …`` and its ``-->`` only arrived at line
74. Four marker blocks landed at lines 23-73, between the two. Two things
broke at once — the first feature marker's own ``-->`` closed the OUTER
comment instead of itself, so that marker became invisible to every
literal consumer, and the outer comment's tail spilled out as visible
garbage above the skill's commands table.

``marker_audit`` already NAMES that state ("an unterminated HTML comment
swallows this feature marker"), but naming it is a post-mortem: by then
``~/.claude/skills`` — not a git repository — is already wrong.

Two properties of the offset are therefore checked before anything is
written, and both answer with refusal, never repair and never relocation:

1. **Position.** The offset must sit on a line boundary. An offset in the
   middle of a table row splices the block between the row's two halves,
   and because the markers it writes are perfectly canonical, the audit
   reports the result CLEAN — blind in the same way it was blind to the
   original incident.
2. **Enclosure.** The offset must not sit inside an unterminated
   ``<!--``.

Either way the document comes back byte-identical with an
``InjectionRefusal`` attached. Relocating would guess where the operator
wanted the section; refusing states the problem and leaves the file
intact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from core.sync.marker_audit import blank_code
from core.sync.schema import FeatureSpec, InjectionRefusal

_COMMENT_OPEN = "<!--"
_COMMENT_CLOSE = "-->"

_OPEN_COMMENT_REASON = (
    "an HTML comment opens here and is still unterminated at the insertion "
    "point; the feature markers would be swallowed by it"
)
_SPLIT_LINE_REASON = (
    "the insertion point splits this line; the block would be spliced "
    "between its two halves"
)

InjectionStatus = Literal["injected", "present", "refused"]


@dataclass(frozen=True)
class InjectionResult:
    """Outcome of one feature injection attempt.

    ``text`` is the document to persist. On "present" and "refused" it is
    the input unchanged, so a caller that always writes ``result.text``
    still cannot corrupt the file.
    """

    status: InjectionStatus
    text: str
    refusal: InjectionRefusal | None = None


def split_line_at(text: str, offset: int) -> int | None:
    """1-based line the offset would cut in two, or ``None`` at a boundary.

    A boundary has nothing before the offset on its line or nothing after
    it — line start, end of line and EOF all qualify, which covers the
    documented insertion points (a line of its own, or straight after an
    existing `:end -->`). Anything else lands between two populated halves
    and splices the block through the middle of a table row or a sentence.

    Position, not just range, because position is the parameter that
    caused issue #509 and the caller choosing it is an LLM. Worse than the
    comment case: the markers it writes are canonical, so `marker_audit`
    reports the wreckage clean and nothing ever notices.
    """
    before = text[:offset].rpartition("\n")[2]
    after = text[offset:].partition("\n")[0]
    if before.strip() and after.strip():
        return text.count("\n", 0, offset) + 1
    return None


def open_comment_line(text: str, offset: int) -> int | None:
    """1-based line of the ``<!--`` still open at ``offset``, else ``None``.

    Fenced blocks and code spans are blanked over the WHOLE document first
    (``blank_code`` preserves every byte offset), so a comment shown as an
    EXAMPLE inside a fence is read as documentation rather than as an open
    comment — the same view ``marker_audit`` takes of the same bytes.
    """
    prefix = blank_code(text)[:offset]
    cursor = 0
    while True:
        opened = prefix.find(_COMMENT_OPEN, cursor)
        if opened == -1:
            return None
        closed = prefix.find(_COMMENT_CLOSE, opened + len(_COMMENT_OPEN))
        if closed == -1:
            return text.count("\n", 0, opened) + 1
        cursor = closed + len(_COMMENT_CLOSE)


def inject_feature(
    text: str,
    spec: FeatureSpec,
    *,
    path: Path,
    at: int | None = None,
) -> InjectionResult:
    """Insert ``spec.content`` at ``at``, unless detection or the guard says no.

    ``at`` is an offset into ``text``, defaulting to the end of the
    document, and it MUST sit on a line boundary: nothing before it on its
    line, or nothing after it. ``path`` names the file in any refusal; it
    is not read or written here — persisting ``result.text`` is the
    caller's step.

    Order matters twice over. Detection runs first, so a host that already
    carries the section (under any of the shapes ``detection_pattern``
    accepts) is never touched and only a genuine injection is put to the
    guards. Position runs before the comment scan, because an offset that
    splits a line is malformed whatever else is true of the prefix.
    """
    offset = len(text) if at is None else at
    if not 0 <= offset <= len(text):
        raise ValueError(f"insertion offset {offset} outside 0..{len(text)}")

    if re.search(spec.detection_pattern, text):
        return InjectionResult(status="present", text=text)

    split = split_line_at(text, offset)
    if split is not None:
        return _refuse(text, path, spec.name, split, _SPLIT_LINE_REASON)

    opened = open_comment_line(text, offset)
    if opened is not None:
        return _refuse(text, path, spec.name, opened, _OPEN_COMMENT_REASON)

    return InjectionResult(status="injected", text=_splice(text, spec.content, offset))


def _refuse(
    text: str, path: Path, feature: str, line: int, reason: str
) -> InjectionResult:
    """Decline the injection, handing back the document untouched."""
    return InjectionResult(
        status="refused",
        text=text,
        refusal=InjectionRefusal(
            path=path, feature=feature, line=line, reason=reason
        ),
    )


def _splice(text: str, content: str, offset: int) -> str:
    """Put ``content`` on its own lines at ``offset``.

    The document's own halves are trimmed of newlines ONLY: stripping
    general whitespace there would eat the indentation that carries
    meaning in a markdown list or a code block. ``content`` comes from the
    registry marker-wrapped, so it is stripped whole.
    """
    head = text[:offset].rstrip("\n")
    tail = text[offset:].lstrip("\n")
    body = "\n\n".join(part for part in (head, content.strip(), tail) if part)
    return body if body.endswith("\n") else body + "\n"
