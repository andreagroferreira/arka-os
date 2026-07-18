"""Tool-loop detection over the current turn's transcript (warn-only).

The context monitor's missing signal: an agent stuck re-issuing the
same tool call burns budget without progress, and nothing surfaced it.
Detection runs at the turn boundary (Stop hook) over the transcript, so
it sees EVERY call — including the ones the PostToolUse fast-path shim
short-circuits away from Python, which an in-process ring buffer never
would. Two patterns:

  - ``consecutive`` — the same (tool, input) issued N times in a row,
    the canonical stuck loop;
  - ``repeated`` — the same (tool, input) issued N times across the
    turn with other calls between, the churn variant.

Privacy: tool inputs are compared by digest and never stored — the
verdict carries the tool name and counts only. Reuses the turn-slicing
helpers of ``phantom_action_check`` (same package, same transcript
contract).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass

from core.governance.phantom_action_check import (
    _last_real_user_index,
    _parse_jsonl,
    _record_content,
    _record_role,
)

DEFAULT_THRESHOLD = 4


@dataclass(frozen=True)
class LoopVerdict:
    """Outcome of the tool-loop scan. Never contains tool inputs."""

    detected: bool = False
    tool: str = ""
    repeats: int = 0
    pattern: str = ""  # "consecutive" | "repeated" | ""
    total_tool_uses: int = 0


def _call_key(block: dict) -> tuple[str, str]:
    tool = str(block.get("name") or "")
    try:
        payload = json.dumps(block.get("input"), sort_keys=True, default=str)
    except (TypeError, ValueError):
        payload = "?"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return tool, digest


def _turn_tool_calls(raw_transcript: str) -> list[tuple[str, str]]:
    records = _parse_jsonl(raw_transcript)
    start = _last_real_user_index(records)
    if start < 0:
        return []
    calls: list[tuple[str, str]] = []
    for record in records[start + 1:]:
        if _record_role(record) != "assistant":
            continue
        content = _record_content(record)
        if not isinstance(content, list):
            continue
        calls.extend(
            _call_key(block)
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_use"
        )
    return calls


def _max_consecutive_run(calls: list[tuple[str, str]]) -> tuple[int, str]:
    best, best_tool = 0, ""
    run, prev = 0, None
    for call in calls:
        run = run + 1 if call == prev else 1
        prev = call
        if run > best:
            best, best_tool = run, call[0]
    return best, best_tool


def check_tool_loops(
    raw_transcript: str | None, *, threshold: int = DEFAULT_THRESHOLD,
) -> LoopVerdict:
    """Scan the current turn for stuck or churning tool-call loops."""
    if not raw_transcript or threshold < 2:
        return LoopVerdict()
    calls = _turn_tool_calls(raw_transcript)
    if not calls:
        return LoopVerdict()
    run, run_tool = _max_consecutive_run(calls)
    if run >= threshold:
        return LoopVerdict(
            detected=True, tool=run_tool, repeats=run,
            pattern="consecutive", total_tool_uses=len(calls),
        )
    (top_call, top_count), = Counter(calls).most_common(1)
    if top_count >= threshold:
        return LoopVerdict(
            detected=True, tool=top_call[0], repeats=top_count,
            pattern="repeated", total_tool_uses=len(calls),
        )
    return LoopVerdict(total_tool_uses=len(calls))
