"""CLI entry for `/arka costs`. Prints a formatted cost summary.

Invoked as `python -m core.runtime.llm_cost_telemetry_cli <period>`
where `<period>` is one of: today, week, month, all, sessions.

Output is plain markdown with pipe tables so it renders cleanly in both
terminal and Obsidian. No external dependencies.
"""

from __future__ import annotations

import sys
from typing import Any

from core.runtime.llm_cost_telemetry import (
    VALID_PERIODS,
    CostSummary,
    list_expensive_sessions,
    summarise,
)


def _fmt_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.4f}"


def _fmt_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _headline(summary: CostSummary) -> list[str]:
    return [
        f"# LLM costs — {summary.period}",
        "",
        f"- Calls: **{summary.call_count}**",
        f"- Total cost: **{_fmt_cost(summary.total_cost_usd)}**",
        f"- Tokens in / out: **{summary.total_tokens_in:,}** / "
        f"**{summary.total_tokens_out:,}**",
        f"- Cached tokens: **{summary.total_cached_tokens:,}** "
        f"(hit rate {_fmt_rate(summary.cache_hit_rate)})",
    ]


def _render_group(title: str, group: dict[str, dict[str, Any]]) -> list[str]:
    if not group:
        return [f"## {title}", "", "_(no data)_", ""]
    lines = [
        f"## {title}",
        "",
        "| Key | Calls | Tokens in | Tokens out | Cache hit | Cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    ordered = sorted(
        group.items(),
        key=lambda kv: (kv[1]["total_cost_usd"] or 0.0),
        reverse=True,
    )
    for key, row in ordered:
        label = key or "<unknown>"
        lines.append(
            f"| {label} | {row['call_count']} | "
            f"{row['total_tokens_in']:,} | {row['total_tokens_out']:,} | "
            f"{_fmt_rate(row['cache_hit_rate'])} | "
            f"{_fmt_cost(row['total_cost_usd'])} |"
        )
    lines.append("")
    return lines


def _render_sessions(rows: list[dict[str, Any]], title: str) -> list[str]:
    if not rows:
        return [f"## {title}", "", "_(no sessions)_", ""]
    lines = [
        f"## {title}",
        "",
        "| Session | Calls | Tokens in | Tokens out | Cost |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        sid = row.get("session_id") or "<unknown>"
        lines.append(
            f"| {sid} | {row['call_count']} | "
            f"{row['total_tokens_in']:,} | {row['total_tokens_out']:,} | "
            f"{_fmt_cost(row['total_cost_usd'])} |"
        )
    lines.append("")
    return lines


def _render_advisories(advisories: list[str]) -> list[str]:
    if not advisories:
        return []
    return ["## Advisories", "", *[f"- {a}" for a in advisories], ""]


def _format_summary(summary: CostSummary) -> str:
    parts: list[str] = []
    parts.extend(_headline(summary))
    parts.append("")
    parts.extend(_render_group("By provider", summary.by_provider))
    parts.extend(_render_group("By model", summary.by_model))
    parts.extend(_render_sessions(summary.by_session, "Top 10 sessions"))
    parts.extend(_render_advisories(summary.advisories))
    if summary.corrupt_line_count:
        parts.append(
            f"_Note: skipped {summary.corrupt_line_count} corrupt JSONL line(s)._"
        )
    return "\n".join(parts).rstrip() + "\n"


def _format_sessions(rows: list[dict[str, Any]]) -> str:
    parts = ["# LLM costs — top expensive sessions", ""]
    parts.extend(_render_sessions(rows, "Top sessions (all time)"))
    return "\n".join(parts).rstrip() + "\n"


def _usage_error() -> str:
    valid = "|".join((*VALID_PERIODS, "sessions"))
    return f"Unknown period. Use: {valid}"


def main(argv: list[str]) -> int:
    args = argv[1:] if len(argv) > 1 else ["today"]
    cmd = (args[0] or "today").strip().lower()
    if cmd in VALID_PERIODS:
        print(_format_summary(summarise(period=cmd)))
        return 0
    if cmd == "sessions":
        print(_format_sessions(list_expensive_sessions(top_n=10)))
        return 0
    print(_usage_error(), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
