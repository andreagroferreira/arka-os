#!/usr/bin/env python3
"""RICE Prioritizer -- rank features by Reach, Impact, Confidence, Effort.
RICE = (Reach x Impact x Confidence) / Effort.
Part of ArkaOS v2 -- stdlib-only, no pip dependencies.
"""
from __future__ import annotations
import argparse, json, sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List

IMPACT_MAP: Dict[str, float] = {"massive": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5, "minimal": 0.25}
CONFIDENCE_MAP: Dict[str, int] = {"high": 100, "medium": 80, "low": 50}
EFFORT_MAP: Dict[str, int] = {"xl": 13, "l": 8, "m": 5, "s": 3, "xs": 1}

@dataclass
class Feature:
    name: str
    reach: int = 0
    impact: str = "medium"
    confidence: str = "medium"
    effort: str = "m"
    description: str = ""
    rice_score: float = 0.0
    category: str = ""

@dataclass
class PortfolioAnalysis:
    total_features: int = 0
    total_effort_months: int = 0
    total_reach: int = 0
    average_rice: float = 0.0
    quick_wins: List[str] = field(default_factory=list)
    big_bets: List[str] = field(default_factory=list)

@dataclass
class RICEResult:
    features: List[Feature] = field(default_factory=list)
    analysis: PortfolioAnalysis = field(default_factory=PortfolioAnalysis)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def calculate_rice(reach: int, impact: str, confidence: str, effort: str) -> float:
    """Compute the RICE score for a single feature."""
    i = IMPACT_MAP.get(impact.lower(), 1.0)
    c = CONFIDENCE_MAP.get(confidence.lower(), 50) / 100.0
    e = EFFORT_MAP.get(effort.lower(), 5)
    if e == 0:
        return 0.0
    return round((reach * i * c) / e, 2)


def _categorize(feature: Feature) -> str:
    """Classify a feature as quick-win, big-bet, fill-in, or time-sink."""
    imp = feature.impact.lower()
    eff = feature.effort.lower()
    high_impact = imp in ("massive", "high")
    low_effort = eff in ("xs", "s")
    high_effort = eff in ("l", "xl")
    if high_impact and low_effort:
        return "quick-win"
    if high_impact and high_effort:
        return "big-bet"
    if not high_impact and low_effort:
        return "fill-in"
    return "time-sink"


def prioritize(raw_features: List[Dict]) -> RICEResult:
    """Score, rank, and analyze a list of feature dicts."""
    features: List[Feature] = []
    for raw in raw_features:
        f = Feature(
            name=raw.get("name", "Unnamed"),
            reach=int(raw.get("reach", 0)),
            impact=str(raw.get("impact", "medium")),
            confidence=str(raw.get("confidence", "medium")),
            effort=str(raw.get("effort", "m")),
            description=str(raw.get("description", "")),
        )
        f.rice_score = calculate_rice(f.reach, f.impact, f.confidence, f.effort)
        f.category = _categorize(f)
        features.append(f)

    features.sort(key=lambda f: f.rice_score, reverse=True)

    quick_wins = [f.name for f in features if f.category == "quick-win"]
    big_bets = [f.name for f in features if f.category == "big-bet"]
    total_effort = sum(EFFORT_MAP.get(f.effort.lower(), 5) for f in features)
    total_reach = sum(f.reach for f in features)
    avg_rice = round(sum(f.rice_score for f in features) / len(features), 2) if features else 0.0

    analysis = PortfolioAnalysis(
        total_features=len(features),
        total_effort_months=total_effort,
        total_reach=total_reach,
        average_rice=avg_rice,
        quick_wins=quick_wins[:5],
        big_bets=big_bets[:5],
    )

    return RICEResult(features=features, analysis=analysis)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _format_text(result: RICEResult) -> str:
    """Human-readable RICE report."""
    lines = [
        "=" * 60,
        "  RICE PRIORITIZATION RESULTS",
        "=" * 60,
        "",
        "  Rank  RICE     Category     Feature",
        "  ----  -------  ----------   -------",
    ]
    for i, f in enumerate(result.features, 1):
        lines.append(f"  {i:<4}  {f.rice_score:>7.1f}  {f.category:<12} {f.name}")

    a = result.analysis
    lines += [
        "",
        "-" * 60,
        "  PORTFOLIO ANALYSIS",
        "-" * 60,
        f"  Total features:      {a.total_features}",
        f"  Total effort:        {a.total_effort_months} person-months",
        f"  Total reach:         {a.total_reach:,} users",
        f"  Average RICE score:  {a.average_rice}",
        "",
    ]

    if a.quick_wins:
        lines.append("  Quick Wins (high impact, low effort):")
        for name in a.quick_wins:
            lines.append(f"    - {name}")
    else:
        lines.append("  Quick Wins: none identified")

    lines.append("")
    if a.big_bets:
        lines.append("  Big Bets (high impact, high effort):")
        for name in a.big_bets:
            lines.append(f"    - {name}")
    else:
        lines.append("  Big Bets: none identified")

    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _load_features(source: str) -> List[Dict]:
    """Parse JSON from a string. Expects a list of feature objects."""
    data = json.loads(source)
    if isinstance(data, dict) and "features" in data:
        data = data["features"]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of feature objects.")
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point. Returns 0=success, 1=warnings, 2=errors."""
    parser = argparse.ArgumentParser(
        description="RICE Prioritizer -- rank features by Reach, Impact, Confidence, Effort.",
    )
    parser.add_argument(
        "input", nargs="?", default=None,
        help="JSON file with features, or inline JSON string",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Load input
    raw_json: str = ""
    try:
        if args.input:
            # Try as file first, then as inline JSON
            try:
                with open(args.input, "r", encoding="utf-8") as fh:
                    raw_json = fh.read()
            except (FileNotFoundError, IsADirectoryError):
                raw_json = args.input
        elif not sys.stdin.isatty():
            raw_json = sys.stdin.read()
        else:
            parser.print_help()
            return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not raw_json.strip():
        print("Error: no input provided.", file=sys.stderr)
        return 2

    try:
        features = _load_features(raw_json)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Error: invalid JSON -- {exc}", file=sys.stderr)
        return 2

    if not features:
        print("Error: feature list is empty.", file=sys.stderr)
        return 2

    result = prioritize(features)

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(_format_text(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
