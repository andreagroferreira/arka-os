"""CLI front-end for frontend-gate telemetry (WARN→hard flip evidence).

Usage:
    python -m core.workflow.frontend_gate_telemetry_cli today
    python -m core.workflow.frontend_gate_telemetry_cli week
    python -m core.workflow.frontend_gate_telemetry_cli month
    python -m core.workflow.frontend_gate_telemetry_cli all
"""

from __future__ import annotations

import sys

from core.workflow.frontend_gate_telemetry import summarise


def _format_human(summary) -> str:
    pct = f"{summary.would_deny_rate * 100:.1f}%"
    lines = [
        f"Frontend Gate Telemetry — {summary.period}",
        f"  Gated UI events:   {summary.total_events}",
        f"  Would-have-denied: {summary.would_deny_events} ({pct}) "
        f"[suffix scope, hard-flip evidence]",
    ]
    for label, pairs in (
        ("By reason", summary.by_reason),
        ("By marker kind", summary.by_marker_kind),
        ("By mode", summary.by_mode),
        ("By UI scope", summary.by_ui_scope),
    ):
        if pairs:
            lines.append(f"  {label}:")
            for key, count in pairs:
                lines.append(f"    - {key}: {count}")
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
