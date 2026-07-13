"""Scope-aware transcript reading — the sidechain guard (specialist P0.2).

The specialist gate's 20-message window was counted over EVERY assistant
record in the JSONL. Two scope leaks follow:

- where a harness interleaves subagent (sidechain) records into the same
  transcript, a burst of subagent activity evicts the routing marker and
  reopens the fail-open the persisted-persona fix exists to close;
- the persisted persona itself must never cross scopes — a dispatched
  specialist evaluated under the PARENT's persisted persona would be
  blocked from the very files it was dispatched to write.

This module splits a transcript into main-scope and sidechain-scope
assistant messages and reports which scope is ACTIVE (the scope of the
most recent assistant record — at PreToolUse time, the agent whose tool
call is being judged). Parsing mirrors
``flow_enforcer._load_last_assistant_messages`` exactly; records without
an ``isSidechain`` field are main-scope, so a transcript that predates
the field behaves as before.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from core.workflow.flow_enforcer import _extract_text


@dataclass
class ScopeSplit:
    """Assistant messages of a transcript, separated by scope."""

    main: list[str] = field(default_factory=list)
    sidechain: list[str] = field(default_factory=list)
    active_sidechain: bool = False


def split_by_scope(raw_text: str) -> ScopeSplit:
    """Split raw JSONL transcript text into main/sidechain scopes."""
    split = ScopeSplit()
    for line in raw_text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = record.get("role") or record.get("message", {}).get("role")
        if role != "assistant":
            continue
        content = record.get("content")
        if content is None:
            content = record.get("message", {}).get("content")
        text = _extract_text(content)
        if not text:
            continue
        side = bool(record.get("isSidechain", False))
        (split.sidechain if side else split.main).append(text)
        split.active_sidechain = side
    return split


def split_from_path(transcript_path: str) -> ScopeSplit:
    """Read and split a transcript file; any failure is an empty split."""
    path = Path(transcript_path) if transcript_path else None
    if path is None or not path.exists():
        return ScopeSplit()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ScopeSplit()
    return split_by_scope(raw)
