"""Recover a reviewer's verdict fence from its own transcript (issue #568).

A reviewer that delivers its verdict through ``SubagentHandback`` and then
writes closing prose leaves the SubagentStop payload's
``last_assistant_message`` without the ``arka-qgverdict`` fence: the fence
went out in the handback's tool input, the prose came after it. Filing the
prose as the record produced ``verdict: None`` artifacts, and the guard
then read the reviewer's previous round as if it were current.

This module reads the tail of the subagent's OWN transcript (JSONL, never
the parent's; the caller proves that) and returns the LAST message that
carries a fence, with where it was found:

- ``transcript_assistant``: an assistant ``text`` block;
- ``transcript_handback``: the ``message`` input of a ``SubagentHandback``
  ``tool_use`` block.

The shape is pinned from a real round-7 reviewer transcript: each
assistant line is ``{"type": "assistant", "message": {"role":
"assistant", "content": [<block>]}}`` where a handback block is
``{"type": "tool_use", "name": "SubagentHandback", "input": {"message":
"<report>"}}``; ``user`` lines mark the turn boundary below.

TURN BOUNDARY. A resumed reviewer (``SendMessage``) appends its next
round to the SAME transcript. The newest-first scan therefore stops at
the prompt that opened the current turn: a ``user`` record whose
content is a string, or a list with no ``tool_result`` block (a
coordinator message delivered mid-turn has that shape too). Nothing
older is eligible, so a round that ends in prose never inherits the
previous round's fence.

The read is bounded (the last ``TAIL_BYTES`` of the file) and linear.
Lines are split on ``"\n"`` only (JSON leaves U+2028, U+2029 and U+0085
raw, and ``str.splitlines`` would split on them); a line cut by the tail
boundary, or one that does not parse, is skipped.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

TAIL_BYTES = 8 * 1024 * 1024
HANDBACK_TOOL = "SubagentHandback"
HANDBACK_FIELD = "message"
SOURCE_ASSISTANT = "transcript_assistant"
SOURCE_HANDBACK = "transcript_handback"

_FENCE_RE = re.compile(r"```arka-qgverdict[ \t]*\n")


def has_fence(text: str) -> bool:
    """True when ``text`` opens an ``arka-qgverdict`` fence."""
    return bool(_FENCE_RE.search(text or ""))


def recover_fence(
    transcript_path: str,
    max_bytes: int | None = None,
    accepts: Callable[[str], bool] = has_fence,
) -> tuple[str, str] | None:
    """(message, fence_source) of the LAST fenced message, or None.

    Only the current turn is read (see TURN BOUNDARY). ``accepts``
    decides what counts as a fenced message; the ledger passes the same
    rule its verdict parser applies. ``max_bytes`` defaults to
    ``TAIL_BYTES``, read at call time. Never raises: a missing,
    unreadable or foreign-shaped transcript yields None, and the caller
    records the capture as ``no-fence``.
    """
    bound = max_bytes or TAIL_BYTES
    try:
        for record in _records_newest_first(transcript_path, bound):
            if _opens_turn(record):
                return None
            found = _fenced_in_record(record, accepts)
            if found is not None:
                return found
    except Exception:
        return None
    return None


def _opens_turn(record: Mapping[str, Any]) -> bool:
    """True for the prompt that opened a turn (not a tool result)."""
    if record.get("type") != "user":
        return False
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    return not any(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    )


def _tail_lines(path: str, max_bytes: int) -> list[str]:
    """The complete lines within the last ``max_bytes`` of the file.

    The read starts one byte early: when that byte is a newline the
    first line in the window is complete and kept (the split yields an
    empty leading segment, which is what gets dropped); otherwise the
    first segment starts mid-record and is dropped.
    """
    with Path(path).open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        start = max(0, size - max_bytes - 1) if size > max_bytes else 0
        fh.seek(start)
        data = fh.read()
    lines = data.decode("utf-8", errors="replace").split("\n")
    return lines[1:] if start > 0 else lines


def _records_newest_first(path: str, max_bytes: int) -> Iterator[dict[str, Any]]:
    for line in reversed(_tail_lines(path, max_bytes)):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            continue  # malformed, a huge int, or nested past the limit
        if isinstance(record, dict):
            yield record


def _fenced_in_record(
    record: Mapping[str, Any], accepts: Callable[[str], bool]
) -> tuple[str, str] | None:
    """The last fenced block of one assistant record (newest block last)."""
    if record.get("type") != "assistant":
        return None
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return None
    for block in reversed(content):
        found = _fenced_block(block, accepts)
        if found is not None:
            return found
    return None


def _fenced_block(
    block: object, accepts: Callable[[str], bool]
) -> tuple[str, str] | None:
    if not isinstance(block, dict):
        return None
    if block.get("type") == "text":
        text = block.get("text")
        if isinstance(text, str) and accepts(text):
            return text, SOURCE_ASSISTANT
        return None
    if block.get("type") == "tool_use" and block.get("name") == HANDBACK_TOOL:
        payload = block.get("input")
        text = payload.get(HANDBACK_FIELD) if isinstance(payload, dict) else None
        if isinstance(text, str) and accepts(text):
            return text, SOURCE_HANDBACK
    return None
