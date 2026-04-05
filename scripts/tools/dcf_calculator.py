#!/usr/bin/env python3
"""DCF Calculator -- ArkaOS v2.

Discounted Cash Flow valuation with projected FCF, terminal value,
enterprise value, equity value, and WACC-vs-terminal-growth sensitivity table.

Usage:
    python dcf_calculator.py --revenue 10000000 --growth 0.15 --margin 0.12 --wacc 0.10
    python dcf_calculator.py --revenue 5e6 --growth 0.20 --margin 0.15 --wacc 0.09 --json
    python dcf_calculator.py --revenue 5e6 --growth 0.20 --margin 0.15 --wacc 0.09 --net-debt 1e6
"""
from __future__ import annotations
import argparse, json, sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

@dataclass
class Projection:
    """Single year projection."""
    year: int; revenue: float; fcf: float; discount_factor: float; pv_fcf: float

@dataclass
class DCFResult:
    """Complete DCF valuation output."""
    wacc: float; terminal_growth: float; years: int
    projections: List[Projection]
    terminal_value: float; pv_terminal: float; pv_fcf_total: float
    enterprise_value: float; net_debt: float; equity_value: float
    shares: Optional[float] = None; value_per_share: Optional[float] = None

def run_dcf(revenue: float, growth: float, margin: float, wacc: float,
            terminal_growth: float = 0.025, years: int = 5,
            net_debt: float = 0.0, shares: Optional[float] = None) -> DCFResult:
    """Run a full DCF valuation and return structured results."""
    projections: List[Projection] = []
    pv_fcf_total, current_revenue = 0.0, revenue
    for yr in range(1, years + 1):
        current_revenue *= 1 + growth
        fcf = current_revenue * margin
        df = (1 + wacc) ** yr
        pv = fcf / df
        pv_fcf_total += pv
        projections.append(Projection(year=yr, revenue=current_revenue, fcf=fcf,
                                      discount_factor=df, pv_fcf=pv))
    terminal_fcf = projections[-1].fcf
    tv = (terminal_fcf * (1 + terminal_growth)) / (wacc - terminal_growth)
    pv_tv = tv / ((1 + wacc) ** years)
    ev = pv_fcf_total + pv_tv
    eq = ev - net_debt
    vps = (eq / shares) if shares and shares > 0 else None
    return DCFResult(wacc=wacc, terminal_growth=terminal_growth, years=years,
        projections=projections, terminal_value=tv, pv_terminal=pv_tv,
        pv_fcf_total=pv_fcf_total, enterprise_value=ev, net_debt=net_debt,
        equity_value=eq, shares=shares, value_per_share=vps)

def sensitivity_table(result: DCFResult, steps: int = 5) -> Dict:
    """Build a WACC vs terminal-growth sensitivity grid for enterprise value."""
    wacc_range = [round(result.wacc + (i - steps // 2) * 0.01, 4) for i in range(steps)]
    growth_range = [round(result.terminal_growth + (i - steps // 2) * 0.005, 4)
                    for i in range(steps)]
    terminal_fcf, years = result.projections[-1].fcf, result.years
    table: List[List[Optional[float]]] = []
    for w in wacc_range:
        row: List[Optional[float]] = []
        for g in growth_range:
            if w <= g or w <= 0:
                row.append(None); continue
            pv_fcf = sum(p.fcf / ((1 + w) ** p.year) for p in result.projections)
            tv = (terminal_fcf * (1 + g)) / (w - g)
            row.append(round(pv_fcf + tv / ((1 + w) ** years), 2))
        table.append(row)
    return {"wacc_values": wacc_range, "growth_values": growth_range, "ev_table": table}

def _fmt(val: float) -> str:
    """Format a monetary value for display."""
    if abs(val) >= 1e9: return f"${val / 1e9:,.2f}B"
    if abs(val) >= 1e6: return f"${val / 1e6:,.2f}M"
    if abs(val) >= 1e3: return f"${val / 1e3:,.1f}K"
    return f"${val:,.2f}"

def format_text(result: DCFResult, sens: Dict) -> str:
    """Render human-readable report."""
    lines = ["=" * 65, "DCF VALUATION ANALYSIS", "=" * 65, "",
        f"WACC: {result.wacc * 100:.2f}%  |  Terminal growth: "
        f"{result.terminal_growth * 100:.2f}%  |  Projection: {result.years} years",
        "", "PROJECTED CASH FLOWS",
        f"  {'Year':>5}  {'Revenue':>14}  {'FCF':>14}  {'PV(FCF)':>14}",
        "  " + "-" * 52]
    for p in result.projections:
        lines.append(f"  {p.year:>5}  {_fmt(p.revenue):>14}  "
                     f"{_fmt(p.fcf):>14}  {_fmt(p.pv_fcf):>14}")
    lines += ["", "VALUATION SUMMARY",
        f"  PV of projected FCFs:  {_fmt(result.pv_fcf_total)}",
        f"  Terminal value:        {_fmt(result.terminal_value)}",
        f"  PV of terminal value:  {_fmt(result.pv_terminal)}",
        f"  Enterprise value:      {_fmt(result.enterprise_value)}",
        f"  Net debt:              {_fmt(result.net_debt)}",
        f"  Equity value:          {_fmt(result.equity_value)}"]
    if result.value_per_share is not None:
        lines.append(f"  Value per share:       ${result.value_per_share:,.2f}")
    lines += ["", "SENSITIVITY: Enterprise Value (WACC vs Terminal Growth)", ""]
    header = f"  {'WACC \\\\ g':>10}"
    for g in sens["growth_values"]:
        header += f"  {g * 100:>7.2f}%"
    lines.append(header)
    lines.append("  " + "-" * (10 + 10 * len(sens["growth_values"])))
    for i, w in enumerate(sens["wacc_values"]):
        row = f"  {w * 100:>9.2f}%"
        for val in sens["ev_table"][i]:
            row += f"  {_fmt(val):>8}" if val is not None else f"  {'N/A':>8}"
        lines.append(row)
    lines += ["", "=" * 65]
    return "\n".join(lines)

def to_json(result: DCFResult, sens: Dict) -> str:
    """Serialise to JSON."""
    payload = asdict(result)
    payload["sensitivity"] = sens
    for p in payload["projections"]:
        for k in ("revenue", "fcf", "pv_fcf", "discount_factor"):
            p[k] = round(p[k], 2)
    for k in ("terminal_value", "pv_terminal", "pv_fcf_total",
              "enterprise_value", "equity_value"):
        payload[k] = round(payload[k], 2)
    if payload["value_per_share"] is not None:
        payload["value_per_share"] = round(payload["value_per_share"], 2)
    return json.dumps(payload, indent=2)

def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="DCF Valuation Calculator -- enterprise and equity valuation")
    parser.add_argument("--revenue", type=float, required=True,
                        help="Base annual revenue (e.g. 10000000 or 1e7)")
    parser.add_argument("--growth", type=float, required=True,
                        help="Annual revenue growth rate as decimal (e.g. 0.15)")
    parser.add_argument("--margin", type=float, required=True,
                        help="Free cash flow margin as decimal (e.g. 0.12)")
    parser.add_argument("--wacc", type=float, required=True,
                        help="Weighted average cost of capital (e.g. 0.10)")
    parser.add_argument("--terminal-growth", type=float, default=0.025,
                        help="Terminal growth rate (default: 0.025)")
    parser.add_argument("--years", type=int, default=5,
                        help="Projection years (default: 5)")
    parser.add_argument("--net-debt", type=float, default=0.0,
                        help="Net debt to subtract for equity value (default: 0)")
    parser.add_argument("--shares", type=float, default=None,
                        help="Shares outstanding for per-share value")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    if args.wacc <= args.terminal_growth:
        print("Error: WACC must be greater than terminal growth rate", file=sys.stderr)
        return 2
    if args.revenue <= 0:
        print("Error: revenue must be positive", file=sys.stderr)
        return 2
    result = run_dcf(revenue=args.revenue, growth=args.growth, margin=args.margin,
                     wacc=args.wacc, terminal_growth=args.terminal_growth,
                     years=args.years, net_debt=args.net_debt, shares=args.shares)
    sens = sensitivity_table(result)
    if args.json:
        print(to_json(result, sens))
    else:
        print(format_text(result, sens))
    return 0

if __name__ == "__main__":
    sys.exit(main())
