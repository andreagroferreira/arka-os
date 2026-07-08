"""MCP usage telemetry (audit E2E v4.3.6, P1).

Writer + summarizer for ``~/.arkaos/telemetry/mcp-usage.jsonl``. The
PostToolUse hook calls :func:`record` on every tool event; MCP tool
names (``mcp__<server>__<tool>``) are parsed and appended as one JSONL
line, everything else is ignored. Before this module the only usage
signal was grepping session transcripts.

Mirrors ``core.governance.enforcement_telemetry`` so periods,
malformed-line tolerance, and zero-division safety behave the same way
across telemetry surfaces. :func:`summarise` is read-only.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "mcp-usage.jsonl"
_VALID_PERIODS: frozenset[str] = frozenset({"today", "week", "month", "all"})
_TOP_SERVERS: int = 10
_TOP_TOOLS: int = 5
_MCP_PREFIX = "mcp__"


@dataclass(frozen=True)
class McpUsageSummary:
    """Aggregated MCP usage over a time slice."""
    period: str
    total_calls: int
    unique_servers: int
    top_servers: list[tuple[str, int]] = field(default_factory=list)
    top_tools: list[tuple[str, int]] = field(default_factory=list)
    corrupt_line_count: int = 0


def parse_mcp_tool(tool_name: str) -> tuple[str, str] | None:
    """Split ``mcp__<server>__<tool>`` into (server, tool).

    Returns None for non-MCP tool names. Handles servers whose slug
    contains single underscores (``claude_ai_Canva``, plugin servers
    like ``plugin_claude-mem_mcp-search``) by splitting on the FIRST
    double underscore after the prefix.
    """
    if not tool_name.startswith(_MCP_PREFIX):
        return None
    rest = tool_name[len(_MCP_PREFIX):]
    server, sep, tool = rest.partition("__")
    if not sep or not server or not tool:
        return None
    return server, tool


def record(
    tool_name: str,
    *,
    session_id: str = "",
    path: Path | None = None,
) -> bool:
    """Append one usage line when tool_name is an MCP tool.

    Never raises — the caller is a hook that must not block on
    telemetry. Returns True when a line was written.
    """
    parsed = parse_mcp_tool(tool_name)
    if parsed is None:
        return False
    server, tool = parsed
    dest = path or DEFAULT_PATH
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "server": server,
        "tool": tool,
        "session": session_id,
    }
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return False
    return True


def summarise(period: str, *, path: Path | None = None) -> McpUsageSummary:
    """Return a McpUsageSummary for the requested period.

    period: one of "today", "week", "month", "all".
    path:   override telemetry source (used by tests; defaults to DEFAULT_PATH).
    """
    if period not in _VALID_PERIODS:
        raise ValueError(f"invalid period: {period!r}")
    src = path or DEFAULT_PATH
    cutoff = _period_cutoff(period)
    entries, corrupt = _read_jsonl(src, cutoff)
    return _build_summary(period, entries, corrupt)


def _period_cutoff(period: str, now: datetime | None = None) -> datetime | None:
    ref = now or datetime.now(timezone.utc)
    if period == "today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return ref - timedelta(days=7)
    if period == "month":
        return ref - timedelta(days=30)
    return None


def _read_jsonl(src: Path, cutoff: datetime | None) -> tuple[list[dict[str, Any]], int]:
    if not src.exists():
        return [], 0
    entries: list[dict[str, Any]] = []
    corrupt = 0
    # Line-stream to keep memory O(1) — this file grows on every MCP call.
    try:
        with src.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    corrupt += 1
                    continue
                if not isinstance(entry, dict):
                    corrupt += 1
                    continue
                if cutoff is not None and not _within_cutoff(entry, cutoff):
                    continue
                entries.append(entry)
    except OSError:
        return entries, corrupt
    return entries, corrupt


def _within_cutoff(entry: dict[str, Any], cutoff: datetime) -> bool:
    ts = _parse_ts(entry.get("ts"))
    if ts is None:
        return False
    return ts >= cutoff


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_summary(
    period: str,
    entries: Iterable[dict[str, Any]],
    corrupt: int,
) -> McpUsageSummary:
    total = 0
    servers: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    for entry in entries:
        server = str(entry.get("server", ""))
        tool = str(entry.get("tool", ""))
        if not server:
            continue
        total += 1
        servers[server] += 1
        if tool:
            tools[f"{server}/{tool}"] += 1
    return McpUsageSummary(
        period=period,
        total_calls=total,
        unique_servers=len(servers),
        top_servers=servers.most_common(_TOP_SERVERS),
        top_tools=tools.most_common(_TOP_TOOLS),
        corrupt_line_count=corrupt,
    )
