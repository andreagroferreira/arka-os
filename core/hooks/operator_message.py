"""The operator's latest message in a Claude Code transcript.

A ``"type": "user"`` entry is not necessarily the operator speaking. The
harness writes its own traffic with the same role: tool results, subagent
hand-backs relayed as peer messages, background task notifications, skill
bodies, compact summaries, slash-command echoes. Reading the last user
entry verbatim hands a subagent's report to the learning-signal site as
if the operator had typed it (live defect, JEV PR3).

Structural fields relied on (Claude Code 2.1.2xx transcript shapes):

- ``isMeta`` / ``isCompactSummary`` / ``isVisibleInTranscriptOnly``: set on
  hand-backs, skill bodies, image stubs, caveats and compact summaries;
- ``origin.kind``: ``"human"`` for typed input; ``"peer"`` and
  ``"task-notification"`` for harness relays;
- ``promptSource == "system"``: harness-originated prompts;
- ``isSidechain``: a subagent's own thread, never the operator;
- content blocks of type ``tool_result``: the harness returning a tool call.

Transcripts that predate those fields (and the flat ``role``/``content``
fixtures) fall back to the text prefixes in ``INJECTED_PREFIXES``.

A slash command the operator typed is echoed as ``<command-message>`` /
``<command-name>`` / ``<command-args>``: on a ``human``-origin entry the
``<command-args>`` text is the operator's own words and is kept; the echo
around it, and any command entry without a human origin, is dropped.
"""

from __future__ import annotations

import json
import re
from typing import Any

_META_FLAGS = ("isMeta", "isCompactSummary", "isVisibleInTranscriptOnly", "isSidechain")

INJECTED_PREFIXES = (
    "<system-reminder>",
    "[SYSTEM NOTIFICATION",
    "Another Claude session sent a message:",
    "<agent-message",
    "<task-notification>",
    "<cross-session-message",
    "<command-name>",
    "<command-message>",
    "<local-command-stdout>",
    "<local-command-caveat>",
    "[Request interrupted",
)

_COMMAND_PREFIXES = ("<command-name>", "<command-message>")
_COMMAND_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)


def last_operator_message(raw: str | None) -> str:
    """The newest genuine operator message in raw JSONL text, or ""."""
    if not raw:
        return ""
    for line in reversed(raw.splitlines()):
        record = _record(line)
        if record is None or not _is_operator_entry(record):
            continue
        text = _operator_text(_content(record), human=_human_origin(record))
        if text:
            return text
    return ""


def _record(line: str) -> dict[str, Any] | None:
    if not line.strip():
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    return record if isinstance(record, dict) else None


def _message(record: dict[str, Any]) -> dict[str, Any]:
    message = record.get("message")
    return message if isinstance(message, dict) else {}


def _content(record: dict[str, Any]) -> object:
    content = record.get("content")
    return _message(record).get("content") if content is None else content


def _is_operator_entry(record: dict[str, Any]) -> bool:
    """Structural verdict: a user-role, main-thread, human-origin entry."""
    if (record.get("role") or _message(record).get("role")) != "user":
        return False
    if any(record.get(flag) for flag in _META_FLAGS):
        return False
    origin = record.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return False
    return record.get("promptSource") != "system"


def _human_origin(record: dict[str, Any]) -> bool:
    origin = record.get("origin")
    return isinstance(origin, dict) and origin.get("kind") == "human"


def _operator_text(content: object, *, human: bool = False) -> str:
    """The typed text: tool results carry none; injected blocks are dropped."""
    if isinstance(content, str):
        return _typed(content, human)
    if not isinstance(content, list):
        return ""
    blocks = [b for b in content if isinstance(b, (dict, str))]
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
        return ""
    texts = [b if isinstance(b, str) else str(b.get("text", "")) for b in blocks]
    return "\n".join(t for t in (_typed(t, human) for t in texts) if t)


def _typed(text: str, human: bool) -> str:
    """``text`` itself, a human slash command's arguments, or "" (injected)."""
    if human and text.lstrip().startswith(_COMMAND_PREFIXES):
        match = _COMMAND_ARGS.search(text)
        return match.group(1).strip() if match else ""
    return "" if _injected(text) else text


def _injected(text: str) -> bool:
    return text.lstrip().startswith(INJECTED_PREFIXES)
