"""CLI entry for the MCP usage telemetry summarizer.

Invoked as ``python -m core.runtime.mcp_telemetry_cli <period>`` where
``<period>`` is one of: today, week, month, all (default: today).

Output is plain markdown so it renders cleanly in both the terminal and
the ``/arka status`` skill which concatenates it into its report.
"""

from __future__ import annotations

import sys

from core.runtime.mcp_telemetry import McpUsageSummary, summarise


def _sanitize_md(value: str) -> str:
    """Strip markdown-breaking characters before rendering JSONL strings.

    Telemetry is local-writer-only, but a malformed server/tool value
    (newline, backtick) can still distort the markdown if /arka status
    pipes the output to a UI.
    """
    return value.replace("\n", " ").replace("\r", " ").replace("`", "").strip()


def _render(summary: McpUsageSummary) -> str:
    lines = [
        f"# MCP usage — {summary.period}",
        "",
        f"- Calls: **{summary.total_calls}**",
        f"- Servers in use: **{summary.unique_servers}**",
    ]
    if summary.top_servers:
        lines += ["", "## Top servers"]
        for server, count in summary.top_servers:
            lines.append(f"- `{_sanitize_md(server)}` — {count}")
    if summary.top_tools:
        lines += ["", "## Top tools"]
        for tool, count in summary.top_tools:
            lines.append(f"- `{_sanitize_md(tool)}` — {count}")
    if summary.corrupt_line_count:
        lines += ["", f"_Skipped {summary.corrupt_line_count} corrupt line(s)._"]
    if summary.total_calls == 0:
        lines += ["", "_No MCP calls recorded for this period._"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    period = args[0] if args else "today"
    try:
        summary = summarise(period)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(_render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
