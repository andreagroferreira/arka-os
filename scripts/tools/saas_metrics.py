#!/usr/bin/env python3
"""SaaS Metrics Calculator -- ArkaOS v2.

Calculates Quick Ratio, net MRR, growth rate, and optional LTV/CAC
from MRR components. Assigns health status: Critical / Watch / Healthy / Excellent.

Adapted from claude-skills/finance/saas-metrics-coach/scripts/quick_ratio_calculator.py

Usage:
    python saas_metrics.py --new-mrr 10000 --churned 3000
    python saas_metrics.py --new-mrr 10000 --expansion 2000 --churned 3000 --contraction 500
    python saas_metrics.py --new-mrr 10000 --churned 2000 --prev-mrr 50000 --ltv 3600 --cac 900 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MRRComponents:
    """Raw MRR inputs."""
    new_mrr: float
    expansion_mrr: float
    churned_mrr: float
    contraction_mrr: float
    previous_mrr: Optional[float] = None

@dataclass
class SaaSMetrics:
    """Calculated SaaS metrics."""
    quick_ratio: Optional[float]
    quick_ratio_display: str
    net_new_mrr: float
    growth_mrr: float
    lost_mrr: float
    current_mrr: Optional[float]
    mrr_growth_rate: Optional[float]
    ltv_cac_ratio: Optional[float]
    status: str
    interpretation: str
    new_mrr_pct: float
    expansion_mrr_pct: float
    churned_mrr_pct: float
    contraction_mrr_pct: float

# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------

def calculate_metrics(
    components: MRRComponents,
    ltv: Optional[float] = None,
    cac: Optional[float] = None,
) -> SaaSMetrics:
    """Calculate all SaaS metrics from MRR components."""
    growth = components.new_mrr + components.expansion_mrr
    lost = components.churned_mrr + components.contraction_mrr
    net_new = growth - lost

    # Quick Ratio
    if lost == 0:
        qr = None if growth == 0 else float("inf")
        qr_display = "0.00" if growth == 0 else "inf"
    else:
        qr = round(growth / lost, 2)
        qr_display = f"{qr:.2f}"

    # Status
    if qr is None or (isinstance(qr, float) and qr < 1):
        status, interp = "Critical", "Losing revenue faster than gaining -- unsustainable"
    elif qr == float("inf") or qr >= 4:
        status, interp = "Excellent", "Strong efficient growth -- gaining 4x+ faster than losing"
    elif qr >= 2:
        status, interp = "Healthy", "Good growth efficiency -- gaining 2x+ faster than losing"
    else:
        status, interp = "Watch", "Marginal growth -- barely gaining more than losing"

    # Breakdown percentages
    new_pct = round((components.new_mrr / growth) * 100, 1) if growth > 0 else 0.0
    exp_pct = round((components.expansion_mrr / growth) * 100, 1) if growth > 0 else 0.0
    churn_pct = round((components.churned_mrr / lost) * 100, 1) if lost > 0 else 0.0
    contr_pct = round((components.contraction_mrr / lost) * 100, 1) if lost > 0 else 0.0

    # Current MRR and growth rate
    current_mrr = (components.previous_mrr + net_new) if components.previous_mrr is not None else None
    mrr_growth = None
    if components.previous_mrr and components.previous_mrr > 0:
        mrr_growth = round((net_new / components.previous_mrr) * 100, 2)

    # LTV/CAC
    ltv_cac = round(ltv / cac, 2) if ltv and cac and cac > 0 else None

    return SaaSMetrics(
        quick_ratio=qr if qr != float("inf") else None,
        quick_ratio_display=qr_display,
        net_new_mrr=round(net_new, 2),
        growth_mrr=round(growth, 2),
        lost_mrr=round(lost, 2),
        current_mrr=round(current_mrr, 2) if current_mrr is not None else None,
        mrr_growth_rate=mrr_growth,
        ltv_cac_ratio=ltv_cac,
        status=status,
        interpretation=interp,
        new_mrr_pct=new_pct,
        expansion_mrr_pct=exp_pct,
        churned_mrr_pct=churn_pct,
        contraction_mrr_pct=contr_pct,
    )

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_report(m: SaaSMetrics, components: MRRComponents) -> str:
    """Render a plain-text report."""
    lines = [
        "=" * 60,
        "SAAS METRICS ANALYSIS",
        "=" * 60,
        "",
        f"QUICK RATIO: {m.quick_ratio_display}",
        f"Status: {m.status}",
        f"{m.interpretation}",
        "",
        "MRR COMPONENTS",
        f"  Growth MRR (New + Expansion): ${m.growth_mrr:,.2f}",
        f"    New MRR:        ${components.new_mrr:,.2f}  ({m.new_mrr_pct:.1f}%)",
        f"    Expansion MRR:  ${components.expansion_mrr:,.2f}  ({m.expansion_mrr_pct:.1f}%)",
        f"  Lost MRR (Churned + Contraction): ${m.lost_mrr:,.2f}",
        f"    Churned MRR:      ${components.churned_mrr:,.2f}  ({m.churned_mrr_pct:.1f}%)",
        f"    Contraction MRR:  ${components.contraction_mrr:,.2f}  ({m.contraction_mrr_pct:.1f}%)",
        "",
        f"  Net new MRR: ${m.net_new_mrr:,.2f}",
    ]

    if m.current_mrr is not None:
        lines.append(f"  Current MRR: ${m.current_mrr:,.2f}")
    if m.mrr_growth_rate is not None:
        lines.append(f"  MRR growth rate: {m.mrr_growth_rate:.2f}%")
    if m.ltv_cac_ratio is not None:
        lines += [
            "",
            "UNIT ECONOMICS",
            f"  LTV/CAC ratio: {m.ltv_cac_ratio:.2f}x",
        ]
        if m.ltv_cac_ratio >= 3:
            lines.append("  Healthy -- LTV/CAC >= 3x")
        elif m.ltv_cac_ratio >= 1:
            lines.append("  Watch -- LTV/CAC between 1x and 3x")
        else:
            lines.append("  Critical -- LTV/CAC below 1x")

    lines += [
        "",
        "BENCHMARKS",
        "  Quick Ratio < 1.0 = Critical (net revenue loss)",
        "  Quick Ratio 1-2   = Watch    (marginal growth)",
        "  Quick Ratio 2-4   = Healthy  (good efficiency)",
        "  Quick Ratio > 4   = Excellent (strong growth)",
        "",
        "=" * 60,
    ]
    return "\n".join(lines)


def to_json(m: SaaSMetrics) -> str:
    """Serialise metrics to JSON."""
    return json.dumps(asdict(m), indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="SaaS Metrics Calculator -- Quick Ratio, net MRR, LTV/CAC",
    )
    parser.add_argument("--new-mrr", type=float, required=True,
                        help="New MRR from new customers")
    parser.add_argument("--expansion", type=float, default=0.0,
                        help="Expansion MRR from upsells (default: 0)")
    parser.add_argument("--churned", type=float, required=True,
                        help="Churned MRR from lost customers")
    parser.add_argument("--contraction", type=float, default=0.0,
                        help="Contraction MRR from downgrades (default: 0)")
    parser.add_argument("--prev-mrr", type=float, default=None,
                        help="Previous month total MRR (for growth rate)")
    parser.add_argument("--ltv", type=float, default=None,
                        help="Customer lifetime value (for LTV/CAC)")
    parser.add_argument("--cac", type=float, default=None,
                        help="Customer acquisition cost (for LTV/CAC)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.new_mrr < 0 or args.churned < 0:
        print("Error: MRR values must be non-negative", file=sys.stderr)
        return 2

    components = MRRComponents(
        new_mrr=args.new_mrr,
        expansion_mrr=args.expansion,
        churned_mrr=args.churned,
        contraction_mrr=args.contraction,
        previous_mrr=args.prev_mrr,
    )

    metrics = calculate_metrics(components, ltv=args.ltv, cac=args.cac)

    if args.json:
        print(to_json(metrics))
    else:
        print(format_report(metrics, components))

    exit_code = 0
    if metrics.status == "Critical":
        exit_code = 2
    elif metrics.status == "Watch":
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
