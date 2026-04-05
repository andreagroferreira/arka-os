#!/usr/bin/env python3
"""Headline Scorer -- rates headlines 0-100 across 6 dimensions.
Part of ArkaOS v2 -- stdlib-only, no pip dependencies.
"""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Tuple

POWER_WORDS = frozenset({
    # urgency / scarcity
    "now", "today", "instantly", "immediately", "urgent", "limited",
    "exclusive", "last", "hurry", "deadline", "expires", "fast",
    # value / benefit
    "free", "save", "proven", "guaranteed", "results", "boost",
    "increase", "grow", "maximize", "unlock", "secret", "revealed",
    "transform", "master", "ultimate", "best", "top", "powerful",
    # curiosity / intrigue
    "discover", "uncover", "surprising", "shocking", "hidden",
    "unknown", "insider", "hack", "trick", "truth",
    # authority
    "experts", "researchers", "scientists", "officially", "certified",
    "award-winning", "world-class",
    # ease
    "easy", "simple", "effortless", "quick", "step-by-step",
    "foolproof", "beginner", "without",
    # negative triggers
    "avoid", "stop", "never", "mistake", "fail", "warning", "danger",
    "worst", "deadly", "risky",
})

EMOTIONAL_TRIGGERS = frozenset({
    "love", "hate", "fear", "hope", "joy", "pain", "anger", "envy",
    "trust", "doubt", "regret", "pride", "shame", "relief", "success",
    "failure", "happiness", "frustration", "excitement", "anxiety",
    "lonely", "powerful", "confident", "inspired",
})

JARGON_WORDS = frozenset({
    "synergy", "leverage", "disruptive", "paradigm", "scalable",
    "bandwidth", "holistic", "ecosystem", "utilize", "facilitate",
    "ideate", "incentivize", "stakeholders", "deliverables",
    "actionable", "bespoke", "granular",
})

WEIGHTS: Dict[str, float] = {"power_words": 0.25, "emotional_triggers": 0.15,
    "numbers": 0.15, "length": 0.20, "specificity": 0.15, "clarity": 0.10}

@dataclass
class DimensionScore:
    score: int
    weight: str
    detail: str

@dataclass
class HeadlineResult:
    headline: str
    overall_score: int = 0
    grade: str = ""
    breakdown: Dict[str, DimensionScore] = field(default_factory=dict)

def _tokenize(headline: str) -> List[str]:
    return re.findall(r"\b\w+(?:[-']\w+)*\b", headline.lower())


def _score_power_words(tokens: List[str]) -> Tuple[int, List[str]]:
    found = [t for t in tokens if t in POWER_WORDS]
    score = min(100, len(found) * 35 + (10 if found else 0))
    return score, found


def _score_emotional(tokens: List[str]) -> Tuple[int, List[str]]:
    found = [t for t in tokens if t in EMOTIONAL_TRIGGERS]
    score = min(100, len(found) * 50)
    return score, found


def _score_numbers(headline: str) -> Tuple[int, List[str]]:
    nums = re.findall(r"\b\d+(?:[,.]\d+)?%?\b", headline)
    return (100 if nums else 0), nums


def _score_length(tokens: List[str]) -> Tuple[int, str]:
    n = len(tokens)
    if 6 <= n <= 12:
        return 100, f"{n} words -- optimal (6-12)"
    if n < 6:
        return max(0, 40 + (n - 1) * 12), f"{n} words -- too short (6-12 optimal)"
    return max(0, 100 - (n - 12) * 10), f"{n} words -- too long (6-12 optimal)"


def _score_specificity(headline: str) -> Tuple[int, List[str]]:
    signals: List[str] = []
    if re.search(r"\b\d+\b", headline):
        signals.append("number")
    if re.search(r"\b(?:in \d+|within \d+|\d+ (?:days?|weeks?|months?|hours?|minutes?))\b", headline, re.I):
        signals.append("timeframe")
    if re.search(r"\b(?:how to|step|guide|checklist|strategy|system|framework|formula)\b", headline, re.I):
        signals.append("concrete format")
    if re.search(r"\b\d+%\b", headline):
        signals.append("percentage")
    return min(100, len(signals) * 34), signals


def _score_clarity(tokens: List[str]) -> Tuple[int, List[str]]:
    found = [t for t in tokens if t in JARGON_WORDS]
    return max(0, 100 - len(found) * 30), found


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def score_headline(headline: str) -> HeadlineResult:
    """Score a single headline across all dimensions."""
    tokens = _tokenize(headline)
    pw_s, pw_f = _score_power_words(tokens)
    et_s, et_f = _score_emotional(tokens)
    nm_s, nm_f = _score_numbers(headline)
    ln_s, ln_n = _score_length(tokens)
    sp_s, sp_f = _score_specificity(headline)
    cl_s, cl_f = _score_clarity(tokens)

    breakdown = {
        "power_words": DimensionScore(pw_s, "25%", f"found: {', '.join(pw_f) or 'none'}"),
        "emotional_triggers": DimensionScore(et_s, "15%", f"found: {', '.join(et_f) or 'none'}"),
        "numbers": DimensionScore(nm_s, "15%", f"found: {', '.join(nm_f) or 'none'}"),
        "length": DimensionScore(ln_s, "20%", ln_n),
        "specificity": DimensionScore(sp_s, "15%", f"signals: {', '.join(sp_f) or 'none'}"),
        "clarity": DimensionScore(cl_s, "10%", f"jargon: {', '.join(cl_f) or 'none'}"),
    }

    overall = round(sum(breakdown[k].score * WEIGHTS[k] for k in WEIGHTS))
    grade = "A" if overall >= 85 else "B" if overall >= 70 else "C" if overall >= 55 else "D" if overall >= 40 else "F"

    return HeadlineResult(headline=headline, overall_score=overall, grade=grade, breakdown=breakdown)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _format_text(results: List[HeadlineResult]) -> str:
    """Human-readable multi-headline report."""
    lines: List[str] = []
    for r in results:
        lines.append("-" * 60)
        lines.append(f"  Headline: {r.headline}")
        lines.append(f"  Score:    {r.overall_score}/100   Grade: {r.grade}")
        lines.append("-" * 60)
        for name, ds in r.breakdown.items():
            bar_len = round(ds.score / 10)
            bar = "#" * bar_len + "." * (10 - bar_len)
            lines.append(f"  {name:<20} [{bar}] {ds.score:>3}/100  {ds.detail}")
        lines.append("")

    if len(results) > 1:
        avg = round(sum(r.overall_score for r in results) / len(results))
        best = max(results, key=lambda r: r.overall_score)
        lines.append("=" * 60)
        lines.append(f"  {len(results)} headlines analyzed  |  Avg score: {avg}/100")
        lines.append(f"  Best: \"{best.headline[:50]}\" ({best.overall_score}/100)")
        lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    """Entry point. Returns 0=success, 1=warnings, 2=errors."""
    parser = argparse.ArgumentParser(
        description="Headline Scorer -- rates headlines 0-100 across 6 dimensions.",
    )
    parser.add_argument("headline", nargs="?", help="Single headline to score")
    parser.add_argument("--file", help="Text file with one headline per line")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.headline:
        headlines = [args.headline]
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as fh:
                headlines = [ln.strip() for ln in fh if ln.strip()]
        except FileNotFoundError:
            print(f"Error: file not found -- {args.file}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
    elif not sys.stdin.isatty():
        headlines = [ln.strip() for ln in sys.stdin if ln.strip()]
    else:
        parser.print_help()
        return 2

    if not headlines:
        print("Error: no headlines provided.", file=sys.stderr)
        return 2

    results = [score_headline(h) for h in headlines]

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print(_format_text(results))

    avg = sum(r.overall_score for r in results) / len(results)
    return 1 if avg < 50 else 0


if __name__ == "__main__":
    sys.exit(main())
