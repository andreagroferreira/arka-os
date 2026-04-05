#!/usr/bin/env python3
"""OKR Cascade Generator -- ArkaOS v2.

Generates cascading OKRs (Company -> Product -> Team) from a strategy type.
Supports strategies: growth, retention, revenue, innovation.
Outputs alignment scores and a visual cascade dashboard.

Usage:
    python okr_cascade.py growth
    python okr_cascade.py retention --teams "Engineering,Design,Data"
    python okr_cascade.py revenue --contribution 0.4 --json
"""
from __future__ import annotations
import argparse, json, sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List

@dataclass
class KeyResult:
    """A single measurable key result."""
    id: str; title: str; target: float = 0.0; parent_id: str = ""

@dataclass
class Objective:
    """An objective containing key results."""
    id: str; title: str; owner: str = ""; parent_id: str = ""
    key_results: List[KeyResult] = field(default_factory=list)

@dataclass
class OKRLevel:
    """A set of objectives at one organisational level."""
    level: str; objectives: List[Objective] = field(default_factory=list)

STRATEGIES: Dict[str, Dict[str, List[str]]] = {
    "growth": {
        "objectives": ["Accelerate user acquisition and market expansion",
                       "Achieve product-market fit in new segments",
                       "Build a sustainable growth engine"],
        "key_results": ["Increase MAU by {pct}%", "Achieve {pct}% MoM growth rate",
                        "Reduce CAC by {pct}%"],
    },
    "retention": {
        "objectives": ["Create lasting customer value and loyalty",
                       "Deliver a superior user experience",
                       "Maximise customer lifetime value"],
        "key_results": ["Improve retention to {pct}%", "Increase NPS by {pct} points",
                        "Reduce churn to below {pct}%"],
    },
    "revenue": {
        "objectives": ["Drive sustainable revenue growth",
                       "Optimise monetisation strategy", "Expand revenue per customer"],
        "key_results": ["Grow ARR by {pct}%", "Increase ARPU by {pct}%",
                        "Achieve {pct}% gross margin"],
    },
    "innovation": {
        "objectives": ["Lead the market through product innovation",
                       "Establish leadership in key capability areas",
                       "Build sustainable competitive differentiation"],
        "key_results": ["Launch {pct} breakthrough features",
                        "Achieve {pct}% revenue from new products",
                        "Reduce time-to-market by {pct}%"],
    },
}
PRODUCT_PREFIX = {"growth": "Build viral product features for",
                  "retention": "Design sticky experiences for",
                  "revenue": "Optimise product monetisation for",
                  "innovation": "Ship innovative features for"}

def _quarter() -> str:
    now = datetime.now()
    return f"Q{(now.month - 1) // 3 + 1} {now.year}"

def generate_cascade(strategy: str, teams: List[str], contribution: float,
                     target: float) -> Dict:
    """Generate the full Company -> Product -> Team cascade."""
    tpl, quarter = STRATEGIES[strategy], _quarter()
    company = OKRLevel(level="Company")
    for i, obj_title in enumerate(tpl["objectives"]):
        obj = Objective(id=f"CO-{i+1}", title=obj_title, owner="CEO")
        for j, kr_tpl in enumerate(tpl["key_results"]):
            obj.key_results.append(KeyResult(
                id=f"CO-{i+1}-KR{j+1}",
                title=kr_tpl.replace("{pct}", str(int(target))), target=target))
        company.objectives.append(obj)
    prefix = PRODUCT_PREFIX.get(strategy, "Product:")
    product = OKRLevel(level="Product")
    for co in company.objectives:
        po = Objective(id=co.id.replace("CO", "PO"),
                       title=f"{prefix} {co.title.lower()}",
                       owner="Head of Product", parent_id=co.id)
        for kr in co.key_results:
            po.key_results.append(KeyResult(
                id=kr.id.replace("CO", "PO"), title=f"[Product] {kr.title}",
                target=round(kr.target * contribution, 1), parent_id=kr.id))
        product.objectives.append(po)
    team_levels: List[OKRLevel] = []
    share = round(1.0 / max(len(teams), 1), 2)
    for team in teams:
        tl = OKRLevel(level=f"Team:{team}")
        for po in product.objectives:
            to = Objective(id=po.id.replace("PO", team[:3].upper()),
                           title=f"[{team}] {po.title}",
                           owner=f"{team} Lead", parent_id=po.id)
            for kr in po.key_results[:2]:
                to.key_results.append(KeyResult(
                    id=kr.id.replace("PO", team[:3].upper()),
                    title=f"[{team}] {kr.title}",
                    target=round(kr.target * share, 1), parent_id=kr.id))
            tl.objectives.append(to)
        team_levels.append(tl)
    return {"quarter": quarter, "strategy": strategy, "company": company,
            "product": product, "teams": team_levels, "contribution": contribution}

def alignment_scores(cascade: Dict) -> Dict[str, float]:
    """Calculate vertical alignment, coverage, balance, and overall scores."""
    linked = total = 0
    for lvl in [cascade["product"]] + cascade["teams"]:
        for obj in lvl.objectives:
            total += 1
            linked += 1 if obj.parent_id else 0
    vertical = round((linked / max(total, 1)) * 100, 1)
    co_krs = sum(len(o.key_results) for o in cascade["company"].objectives)
    po_krs = sum(len(o.key_results) for o in cascade["product"].objectives)
    coverage = round((po_krs / max(co_krs, 1)) * 100, 1)
    counts = [len(t.objectives) for t in cascade["teams"]]
    avg = sum(counts) / max(len(counts), 1)
    variance = sum((c - avg) ** 2 for c in counts) / max(len(counts), 1)
    balance = round(max(0, 100 - variance * 10), 1)
    overall = round(vertical * 0.4 + coverage * 0.3 + balance * 0.3, 1)
    return {"vertical": vertical, "coverage": coverage, "balance": balance, "overall": overall}

def format_dashboard(cascade: Dict, scores: Dict[str, float]) -> str:
    """Render a plain-text dashboard."""
    lines = ["=" * 60, "OKR CASCADE DASHBOARD",
             f"Quarter: {cascade['quarter']}  |  Strategy: {cascade['strategy'].upper()}",
             f"Product contribution: {cascade['contribution'] * 100:.0f}%",
             "=" * 60, "", "COMPANY OKRS"]
    for o in cascade["company"].objectives:
        lines.append(f"  {o.id}: {o.title}")
        for kr in o.key_results:
            lines.append(f"    {kr.id}: {kr.title}")
    lines += ["", "PRODUCT OKRS"]
    for o in cascade["product"].objectives:
        lines.append(f"  {o.id}: {o.title}  (supports {o.parent_id})")
        for kr in o.key_results:
            lines.append(f"    {kr.id}: {kr.title}  [target: {kr.target}]")
    lines += ["", "TEAM OKRS"]
    for tl in cascade["teams"]:
        lines.append(f"  --- {tl.level} ---")
        for o in tl.objectives:
            lines.append(f"    {o.id}: {o.title}")
            for kr in o.key_results:
                lines.append(f"      {kr.id}: {kr.title}  [target: {kr.target}]")
    lines += ["", "ALIGNMENT SCORES", "-" * 40]
    for k, v in scores.items():
        tag = "[OK]" if v >= 80 else "[!!]" if v >= 60 else "[XX]"
        lines.append(f"  {tag} {k.title()}: {v}%")
    if scores["overall"] >= 80:
        lines.append("\n  Overall alignment is GOOD (>= 80%)")
    elif scores["overall"] >= 60:
        lines.append("\n  Overall alignment NEEDS ATTENTION (60-80%)")
    else:
        lines.append("\n  Overall alignment is POOR (< 60%)")
    return "\n".join(lines)

def to_json(cascade: Dict, scores: Dict[str, float]) -> str:
    """Serialise the full cascade to JSON."""
    def _level(lvl: OKRLevel) -> Dict:
        return {"level": lvl.level, "objectives": [asdict(o) for o in lvl.objectives]}
    return json.dumps({"quarter": cascade["quarter"], "strategy": cascade["strategy"],
        "contribution": cascade["contribution"], "company": _level(cascade["company"]),
        "product": _level(cascade["product"]),
        "teams": [_level(t) for t in cascade["teams"]],
        "alignment_scores": scores}, indent=2)

def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Generate cascading OKRs (Company -> Product -> Team)")
    parser.add_argument("strategy", choices=list(STRATEGIES.keys()),
                        help="Strategy type for OKR generation")
    parser.add_argument("--teams", "-t", default="Growth,Platform,Mobile,Data",
                        help="Comma-separated team names (default: Growth,Platform,Mobile,Data)")
    parser.add_argument("--contribution", "-c", type=float, default=0.3,
                        help="Product contribution fraction 0-1 (default: 0.3)")
    parser.add_argument("--target", type=float, default=30,
                        help="Numeric target for KR templates (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    if not 0 < args.contribution <= 1:
        print("Error: --contribution must be between 0 and 1", file=sys.stderr)
        return 2
    teams = [t.strip() for t in args.teams.split(",") if t.strip()]
    if not teams:
        print("Error: at least one team is required", file=sys.stderr)
        return 2
    cascade = generate_cascade(args.strategy, teams, args.contribution, args.target)
    scores = alignment_scores(cascade)
    if args.json:
        print(to_json(cascade, scores))
    else:
        print(format_dashboard(cascade, scores))
    return 0 if scores["overall"] >= 60 else 1

if __name__ == "__main__":
    sys.exit(main())
