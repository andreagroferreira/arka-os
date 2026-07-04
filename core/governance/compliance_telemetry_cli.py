"""CLI entry for the behavior-compliance summarizer (PR29 v2.48.0).

Invoked as ``python -m core.governance.compliance_telemetry_cli <period>``.
Renders a markdown report covering the four stop-hook behavior contracts:
closing marker, meta tag, KB cite pass, sycophancy clean.
"""

from __future__ import annotations

import sys

from core.governance.compliance_telemetry import (
    ComplianceSummary,
    summarise,
)


def _fmt_rate(value: float) -> str:
    return f"{value * 100:.2f}%"


def _render(summary: ComplianceSummary) -> str:
    lines = [
        f"# Behavior compliance — {summary.period}",
        "",
        f"- Stop-hook events observed: **{summary.stop_events}**",
        "",
        "| Contract | Compliance rate |",
        "|---|---|",
        f"| `[arka:gate:4]` / `[arka:trivial]` closing marker "
        f"| {_fmt_rate(summary.closing_marker_rate)} |",
        f"| `[arka:meta]` one-liner (PR12 v2.34.0) "
        f"| {_fmt_rate(summary.meta_tag_rate)} |",
        f"| KB citation pass (PR18 v2.40.0) "
        f"| {_fmt_rate(summary.kb_cite_pass_rate)} |",
        f"| Sycophancy clean (inverse of flagged, PR13 v2.35.0) "
        f"| {_fmt_rate(summary.sycophancy_clean_rate)} |",
    ]
    if summary.corrupt_line_count:
        lines += [
            "",
            f"_(skipped {summary.corrupt_line_count} corrupt line(s) in telemetry)_",
        ]
    if summary.stop_events == 0:
        lines += [
            "",
            "_(no stop-hook events in window — open a session and complete "
            "a turn to populate telemetry)_",
        ]
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
