"""CLI for the decisions telemetry summary.

``arka-py -m core.decisions.telemetry_cli [today|week|month|all] [--by-site]``.
Plain markdown, same shape as ``core.runtime.mcp_telemetry_cli`` so
``/arka status`` can concatenate it. Every run ends with the "Cost and
effect" section (``core.decisions.cost_effect``); ``--by-site`` adds the
per-site effect table. A counterfactual is never printed as a saving.
"""

from __future__ import annotations

import sys

from core.decisions.cost_effect import (
    NO_MEASURED_SAVING,
    CostEffect,
    Counterfactual,
    cost_effect,
)
from core.decisions.telemetry import DecisionsSummary, SiteSummary, summarise

BY_SITE_FLAG = "--by-site"


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
                  "| Site | Calls | Agree | Fallback | Acted Jev | p50 | Cost |",
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


def _effect_row(name: str, s: SiteSummary) -> str:
    reasons = ", ".join(f"{_sanitize_md(r)} {n}" for r, n in s.top_fallback_reasons) or "—"
    return (
        f"| `{_sanitize_md(name)}` | ${s.cost_usd:.6f} | {s.acted_jev} | {s.fallback} | "
        f"{s.abstain} | {_fmt_pct(s.abstain_attributable_pct)} | {reasons} |"
    )


def _render_by_site(summary: DecisionsSummary) -> list[str]:
    lines = ["", "## Effect by site", ""]
    if not summary.by_site:
        return [*lines, "_No decisions recorded for this period._"]
    lines += ["| Site | Jev cost (measured) | Acted Jev | Fallback | Abstain | "
              "Abstain (attributable) | Top fallback reasons |",
              "|---|---|---|---|---|---|---|"]
    return lines + [_effect_row(name, s) for name, s in summary.by_site.items()]


def _detail(c: Counterfactual) -> str:
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in c.detail.items())


def _saving(c: Counterfactual) -> str:
    # A ceiling is shown as a ceiling: never summed, never called a saving.
    if c.ceiling_usd is None:
        return c.saving
    return f"{c.saving}: ${c.ceiling_usd:.6f}"


def _counterfactual_row(c: Counterfactual) -> str:
    return (f"| #{c.number} | `{c.site}` | {c.effect}: {c.count} ({_detail(c)}) | "
            f"{_saving(c)} | {c.not_measurable} |")


def _render_cost_effect(view: CostEffect) -> list[str]:
    lines = ["", "## Cost and effect", ""]
    if not view.has_data:
        return [*lines, "_No cost or effect data for this period._"]
    led = view.ledger
    lines += [
        f"- Jev cost, production (ledger `decision`, replay rows excluded): "
        f"**${led.production_usd:.6f}** over {led.production_calls} call(s)",
        f"- Replay runs (ledger `decision-replay` and older session `replay` rows; "
        f"not production spend): ${led.replay_usd:.6f} over {led.replay_calls} call(s)",
        f"- {NO_MEASURED_SAVING}", "",
        "| # | Site | Effect (count) | Saving | Not measurable today |",
        "|---|---|---|---|---|",
    ]
    return lines + [_counterfactual_row(c) for c in view.counterfactuals]


def _parse(args: list[str]) -> tuple[str, bool]:
    flags = [a for a in args if a.startswith("--")]
    unknown = [f for f in flags if f != BY_SITE_FLAG]
    if unknown:
        raise ValueError(f"unknown option: {unknown[0]!r}")
    positional = [a for a in args if not a.startswith("--")]
    if len(positional) > 1:
        raise ValueError(f"unexpected argument: {positional[1]!r}")
    return (positional[0] if positional else "today"), BY_SITE_FLAG in flags


def main(argv: list[str] | None = None) -> int:
    """Print the markdown summary; exit 2 on an invalid period or option."""
    try:
        period, by_site = _parse(argv if argv is not None else sys.argv[1:])
        summary = summarise(period)
        view = cost_effect(period)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    lines = [_render(summary)]
    if by_site:
        lines += _render_by_site(summary)
    lines += _render_cost_effect(view)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
