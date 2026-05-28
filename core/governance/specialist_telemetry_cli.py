"""CLI front-end for specialist-dispatch telemetry.

Usage:
    python -m core.governance.specialist_telemetry_cli today
    python -m core.governance.specialist_telemetry_cli week
    python -m core.governance.specialist_telemetry_cli month
    python -m core.governance.specialist_telemetry_cli all
"""

from __future__ import annotations

import sys

from core.governance.specialist_telemetry import summarise


def _format_human(summary) -> str:
    pct = f"{summary.block_rate * 100:.1f}%"
    lines = [
        f"Specialist Dispatch Telemetry — {summary.period}",
        f"  Total calls:       {summary.total_calls}",
        f"  Blocked:           {summary.blocked_calls} ({pct})",
        f"  Bypasses used:     {summary.bypass_used}",
    ]
    if summary.top_blocked_personas:
        lines.append("  Top blocked personas:")
        for persona, count in summary.top_blocked_personas:
            lines.append(f"    - {persona}: {count}")
    if summary.top_owners_required:
        lines.append("  Top owners required:")
        for owner, count in summary.top_owners_required:
            lines.append(f"    - {owner}: {count}")
    if summary.corrupt_line_count:
        lines.append(f"  Corrupt lines:     {summary.corrupt_line_count}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    period = args[0] if args else "today"
    try:
        summary = summarise(period)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(_format_human(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
