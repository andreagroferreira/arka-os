"""CLI entry for the enforcement telemetry summarizer (PR19 v2.41.0).

Invoked as ``python -m core.governance.enforcement_telemetry_cli <period>``
where ``<period>`` is one of: today, week, month, all.

Output is plain markdown so it renders cleanly in both the terminal and
the ``/arka status`` skill which concatenates it into its report.
"""

from __future__ import annotations

import sys

from core.governance.enforcement_telemetry import (
    EnforcementSummary,
    summarise,
)


def _fmt_rate(value: float) -> str:
    return f"{value * 100:.2f}%"


def _sanitize_md(value: str) -> str:
    """Strip markdown-breaking characters before rendering JSONL strings.

    Telemetry is local-writer-only, but a malformed tool/reason value (newline,
    backtick) can still distort the markdown if /arka status pipes the output
    to a UI. Belt-and-braces against passive corruption, not active attack.
    """
    return value.replace("\n", " ").replace("\r", " ").replace("`", "").strip()


def _render(summary: EnforcementSummary) -> str:
    lines = [
        f"# Enforcement — {summary.period}",
        "",
        f"- Calls: **{summary.total_calls}**",
        f"- Blocked: **{summary.blocked_calls}** ({_fmt_rate(summary.block_rate)})",
        f"- Bypass used (`ARKA_BYPASS_FLOW=1`): **{summary.bypass_used}**",
    ]
    if summary.top_blocked_tools:
        lines += ["", "## Top blocked tools"]
        for tool, count in summary.top_blocked_tools:
            lines.append(f"- `{_sanitize_md(tool)}` — {count}")
    if summary.top_block_reasons:
        lines += ["", "## Top block reasons"]
        for reason, count in summary.top_block_reasons:
            lines.append(f"- {_sanitize_md(reason)} — {count}")
    if summary.corrupt_line_count:
        lines += ["", f"_(skipped {summary.corrupt_line_count} corrupt line(s))_"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    period = argv[1] if len(argv) > 1 else "today"
    try:
        summary = summarise(period)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(_render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
