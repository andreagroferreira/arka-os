#!/usr/bin/env python3
"""Brand Voice Analyzer -- score content 0-100 for voice consistency and readability.
Part of ArkaOS v2 -- stdlib-only, no pip dependencies.
"""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List

VOICE_DIMENSIONS: Dict[str, Dict[str, List[str]]] = {
    "formality": {
        "formal": ["hereby", "therefore", "furthermore", "pursuant", "regarding",
                    "accordingly", "henceforth", "notwithstanding", "whereas"],
        "casual": ["hey", "cool", "awesome", "stuff", "yeah", "gonna", "wanna",
                    "kinda", "gotta", "yep"],
    },
    "tone": {
        "professional": ["expertise", "solution", "optimize", "leverage", "strategic",
                         "implement", "framework", "methodology", "deliverable"],
        "friendly": ["happy", "excited", "love", "enjoy", "together", "share",
                      "amazing", "wonderful", "great", "fun"],
    },
    "perspective": {
        "authoritative": ["proven", "research shows", "experts agree", "data indicates",
                          "studies confirm", "evidence suggests"],
        "conversational": ["you might", "let's explore", "we think", "imagine if",
                           "have you ever", "picture this"],
    },
}

@dataclass
class SentenceAnalysis:
    count: int = 0
    average_length: float = 0.0
    variety: str = "low"
    shortest: int = 0
    longest: int = 0

@dataclass
class VoiceDimension:
    dominant: str = ""
    scores: Dict[str, int] = field(default_factory=dict)

@dataclass
class AnalysisResult:
    word_count: int = 0
    readability_score: float = 0.0
    readability_grade: str = ""
    overall_score: int = 0
    voice_profile: Dict[str, VoiceDimension] = field(default_factory=dict)
    sentence_analysis: SentenceAnalysis = field(default_factory=SentenceAnalysis)
    recommendations: List[str] = field(default_factory=list)

def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:'\"")
    count, prev = 0, False
    for ch in word:
        v = ch in "aeiou"
        if v and not prev:
            count += 1
        prev = v
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _flesch_reading_ease(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = text.split()
    if not sentences or not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
    return round(max(0.0, min(100.0, score)), 1)

def _readability_grade(score: float) -> str:
    if score >= 80: return "Easy"
    if score >= 60: return "Standard"
    if score >= 40: return "Fairly Difficult"
    if score >= 20: return "Difficult"
    return "Very Difficult"

def _analyze_sentences(text: str) -> SentenceAnalysis:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return SentenceAnalysis()
    lengths = [len(s.split()) for s in sentences]
    avg = sum(lengths) / len(lengths)
    unique = len(set(lengths))
    variety = "high" if unique >= 5 else ("medium" if unique >= 3 else "low")
    return SentenceAnalysis(count=len(sentences), average_length=round(avg, 1),
                            variety=variety, shortest=min(lengths), longest=max(lengths))

def _score_voice(text: str) -> Dict[str, VoiceDimension]:
    text_lower = text.lower()
    profile: Dict[str, VoiceDimension] = {}
    for dimension, categories in VOICE_DIMENSIONS.items():
        scores = {cat: sum(1 for kw in kws if kw in text_lower) for cat, kws in categories.items()}
        dominant = max(scores, key=scores.get) if sum(scores.values()) > 0 else "neutral"
        profile[dimension] = VoiceDimension(dominant=dominant, scores=scores)
    return profile

def _compute_overall(readability: float, sentence: SentenceAnalysis) -> int:
    variety_map = {"high": 100, "medium": 60, "low": 30}
    return round(readability * 0.50 + variety_map.get(sentence.variety, 30) * 0.25
                 + min(100, sentence.count * 20) * 0.25)

def _generate_recommendations(result: AnalysisResult) -> List[str]:
    recs: List[str] = []
    if result.readability_score < 30:
        recs.append("Simplify language -- shorter words and sentences improve readability.")
    elif result.readability_score > 80:
        recs.append("Content is very easy to read -- verify this matches your audience.")
    if result.sentence_analysis.variety == "low":
        recs.append("Vary sentence length for better rhythm and engagement.")
    if result.sentence_analysis.longest > 35:
        recs.append(f"Longest sentence is {result.sentence_analysis.longest} words -- consider splitting.")
    if result.word_count < 100:
        recs.append("Very short content -- consider expanding for depth.")
    for dim, vd in result.voice_profile.items():
        if sum(vd.scores.values()) == 0:
            recs.append(f"No clear {dim} signals detected -- add stronger voice cues.")
    return recs

def analyze(text: str) -> AnalysisResult:
    """Run the full brand voice analysis on *text*."""
    readability = _flesch_reading_ease(text)
    sentence = _analyze_sentences(text)
    result = AnalysisResult(word_count=len(text.split()), readability_score=readability,
                            readability_grade=_readability_grade(readability),
                            voice_profile=_score_voice(text), sentence_analysis=sentence)
    result.overall_score = _compute_overall(readability, sentence)
    result.recommendations = _generate_recommendations(result)
    return result

def _format_text(result: AnalysisResult) -> str:
    lines = ["=" * 60,
             f"  BRAND VOICE ANALYSIS   Overall Score: {result.overall_score}/100",
             "=" * 60,
             f"  Word Count:       {result.word_count}",
             f"  Readability:      {result.readability_score}/100 ({result.readability_grade})",
             "", "  Voice Profile:"]
    for dim, vd in result.voice_profile.items():
        detail = ", ".join(f"{k}={v}" for k, v in vd.scores.items())
        lines.append(f"    {dim:<16} {vd.dominant:<16} ({detail})")
    lines += ["", "  Sentence Analysis:",
              f"    Count:          {result.sentence_analysis.count}",
              f"    Avg length:     {result.sentence_analysis.average_length} words",
              f"    Variety:        {result.sentence_analysis.variety}",
              f"    Shortest:       {result.sentence_analysis.shortest} words",
              f"    Longest:        {result.sentence_analysis.longest} words",
              "", "  Recommendations:"]
    for rec in result.recommendations:
        lines.append(f"    - {rec}")
    lines.append("=" * 60)
    return "\n".join(lines)

def main() -> int:
    """Entry point. Returns exit code: 0=success, 1=warnings, 2=errors."""
    parser = argparse.ArgumentParser(
        description="Brand Voice Analyzer -- score content 0-100 for voice consistency and readability.")
    parser.add_argument("file", nargs="?", default=None,
                        help="Text file to analyze (reads stdin if omitted)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as fh:
                text = fh.read()
        elif not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            parser.print_help()
            return 2
    except FileNotFoundError:
        print(f"Error: file not found -- {args.file}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if not text.strip():
        print("Error: input is empty.", file=sys.stderr)
        return 2
    result = analyze(text)
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(_format_text(result))
    return 1 if result.overall_score < 40 else 0

if __name__ == "__main__":
    sys.exit(main())
