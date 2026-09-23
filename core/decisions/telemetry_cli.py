"""CLI for the decisions telemetry summary.

``python -m core.decisions.telemetry_cli [today|week|month|all]``.
Plain markdown, same shape as ``core.runtime.mcp_telemetry_cli`` so
``/arka status`` can concatenate it.
"""

from __future__ import annotations

import sys

from core.decisions.telemetry import DecisionsSummary, SiteSummary, summarise


def _sanitize_md(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ").replace("`", "").replace("|", "/").strip()


def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _fmt_ms(value: int | None) -> str:
    return "—" if value is None else f"{value} ms"


def _site_row(name: str, s: SiteSummary) -> str:
    return (
        f"| `{_sanitize_md(name)}` | {s.calls} | {_fmt_pct(s.agreement_pct)} | "
        f"{_fmt_pct(s.fallback_pct)} | {_fmt_pct(s.acted_jev_pct)} | "
        f"{_fmt_ms(s.p50_latency_ms)} | ${s.cost_usd:.6f} |"
    )


def _render(summary: DecisionsSummary) -> str:
    lines = [
        f"# Decisions — {summary.period}",
        "",
        f"- Decisions: **{summary.calls}**",
        f"- Cost: **${summary.total_cost_usd:.6f}**",
        f"- p50 latency: **{_fmt_ms(summary.p50_latency_ms)}**",
        f"- Cache hits: **{_fmt_pct(summary.cache_hit_pct)}**",
    ]
    if summary.by_site:
        lines += ["", "## By site", "",
                  "| Site | Calls | Agree | Fallback | Acted JEV | p50 | Cost |",
                  "|---|---|---|---|---|---|---|"]
        lines += [_site_row(name, s) for name, s in summary.by_site.items()]
    if summary.top_fallback_reasons:
        lines += ["", "## Top fallback reasons"]
        lines += [f"- `{_sanitize_md(r)}` — {n}" for r, n in summary.top_fallback_reasons]
    if summary.corrupt_line_count:
        lines += ["", f"_Skipped {summary.corrupt_line_count} corrupt line(s)._"]
    if summary.calls == 0:
        lines += ["", "_No decisions recorded for this period._"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the markdown summary; exit 2 on an invalid period."""
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
