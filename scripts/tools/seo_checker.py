#!/usr/bin/env python3
"""SEO Checker -- scores an HTML page 0-100 across 8 on-page factors.
Part of ArkaOS v2 -- stdlib-only, no pip dependencies.
"""
from __future__ import annotations
import argparse, json, re, sys
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

class _SEOParser(HTMLParser):
    """Extract SEO-relevant elements from HTML."""
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta_description = ""
        self.viewport_meta = False
        self.h_tags: List[Tuple[int, str]] = []
        self._cur_h: Optional[int] = None
        self._cur_h_text: List[str] = []
        self.images: List[Dict[str, Optional[str]]] = []
        self.links: List[Dict[str, str]] = []
        self._in_link = False
        self._link_href = ""
        self._link_text: List[str] = []
        self.body_parts: List[str] = []
        self._in_body = self._in_script = self._in_style = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        t = tag.lower()
        if t == "title":
            self._in_title = True
        elif t == "meta":
            name, prop = a.get("name", "").lower(), a.get("property", "").lower()
            if name == "description": self.meta_description = a.get("content", "")
            if name == "viewport": self.viewport_meta = True
            if prop == "og:description" and not self.meta_description:
                self.meta_description = a.get("content", "")
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._cur_h, self._cur_h_text = int(t[1]), []
        elif t == "img":
            self.images.append({"src": a.get("src", ""), "alt": a.get("alt")})
        elif t == "a":
            self._in_link, self._link_href, self._link_text = True, a.get("href", ""), []
        elif t == "body": self._in_body = True
        elif t == "script": self._in_script = True
        elif t == "style": self._in_style = True

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title": self._in_title = False
        elif t in ("h1", "h2", "h3", "h4", "h5", "h6") and self._cur_h is not None:
            self.h_tags.append((self._cur_h, " ".join(self._cur_h_text).strip()))
            self._cur_h = None
        elif t == "a" and self._in_link:
            self.links.append({"href": self._link_href, "text": " ".join(self._link_text).strip()})
            self._in_link = False
        elif t == "script": self._in_script = False
        elif t == "style": self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_title: self.title += data
        if self._cur_h is not None: self._cur_h_text.append(data)
        if self._in_link: self._link_text.append(data)
        if self._in_body and not self._in_script and not self._in_style:
            self.body_parts.append(data)

@dataclass
class Check:
    name: str
    score: int
    passed: bool
    note: str
    details: Dict = field(default_factory=dict)

@dataclass
class SEOResult:
    overall_score: int = 0
    grade: str = ""
    checks: List[Check] = field(default_factory=list)

WEIGHTS: Dict[str, int] = {"title": 20, "meta_description": 15, "h1": 15,
    "heading_hierarchy": 10, "image_alt_text": 10, "link_ratio": 10,
    "word_count": 15, "viewport_meta": 5}

def analyze_html(html: str) -> SEOResult:
    """Parse *html* and return an SEOResult with per-check scores."""
    p = _SEOParser()
    p.feed(html)
    checks: List[Check] = []
    # Title
    title, tl = p.title.strip(), len(p.title.strip())
    t_ok = 50 <= tl <= 60
    checks.append(Check("title", 100 if t_ok else (50 if title else 0), t_ok,
        "Good length" if t_ok else (f"Too {'short' if tl < 50 else 'long'} ({tl} chars)" if title else "Missing title tag"),
        {"value": title, "length": tl, "optimal": "50-60 chars"}))
    # Meta description
    desc, dl = p.meta_description.strip(), len(p.meta_description.strip())
    d_ok = 150 <= dl <= 160
    d_score = 100 if d_ok else (50 if 100 <= dl < 150 or 160 < dl <= 200 else (30 if desc else 0))
    checks.append(Check("meta_description", d_score, d_ok,
        "Good length" if d_ok else (f"Too {'short' if dl < 150 else 'long'} ({dl} chars)" if desc else "Missing meta description"),
        {"length": dl, "optimal": "150-160 chars"}))
    # H1
    h1s = [t for lvl, t in p.h_tags if lvl == 1]
    h1_ok = len(h1s) == 1
    checks.append(Check("h1", 100 if h1_ok else (50 if len(h1s) > 1 else 0), h1_ok,
        "Exactly one H1" if h1_ok else (f"Multiple H1s ({len(h1s)})" if h1s else "No H1 found"),
        {"count": len(h1s), "values": h1s}))
    # Heading hierarchy
    issues, prev = [], 0
    for lvl, _ in p.h_tags:
        if prev and lvl > prev + 1:
            issues.append(f"H{prev} -> H{lvl} skips a level")
        prev = lvl
    checks.append(Check("heading_hierarchy", max(0, 100 - len(issues) * 25), not issues,
        "Hierarchy OK" if not issues else f"{len(issues)} level-skip issue(s)",
        {"headings": [f"H{l}: {t[:60]}" for l, t in p.h_tags], "issues": issues}))
    # Image alt text
    total_imgs = len(p.images)
    with_alt = sum(1 for img in p.images if img.get("alt") is not None and img["alt"].strip())
    alt_pct = (with_alt / total_imgs * 100) if total_imgs else 100.0
    checks.append(Check("image_alt_text", round(alt_pct), alt_pct == 100,
        "All images have alt text" if alt_pct == 100 else f"{total_imgs - with_alt} image(s) missing alt",
        {"total": total_imgs, "with_alt": with_alt}))
    # Link ratio
    total_links = len(p.links)
    ext = sum(1 for lk in p.links if lk["href"].startswith(("http://", "https://")))
    internal = total_links - ext
    ratio = (internal / total_links) if total_links else 1.0
    lr_ok = ratio >= 0.5 or total_links == 0
    checks.append(Check("link_ratio", 100 if lr_ok else round(ratio * 100), lr_ok,
        "Good internal/external balance" if lr_ok else "More external than internal links",
        {"total": total_links, "internal": internal, "external": ext}))
    # Word count
    wc = len(re.findall(r"\b\w+\b", " ".join(p.body_parts)))
    wc_ok = wc >= 300
    checks.append(Check("word_count", 100 if wc_ok else min(100, round(wc / 300 * 100)), wc_ok,
        f"{wc} words (good)" if wc_ok else f"Only {wc} words -- need 300+", {"count": wc}))
    # Viewport meta
    checks.append(Check("viewport_meta", 100 if p.viewport_meta else 0, p.viewport_meta,
        "Viewport tag present" if p.viewport_meta else "Missing viewport meta tag"))
    # Overall
    check_map = {c.name: c.score for c in checks}
    total_w = sum(WEIGHTS.values())
    overall = round(sum(check_map.get(k, 0) * w for k, w in WEIGHTS.items()) / total_w)
    grade = "A" if overall >= 90 else "B" if overall >= 75 else "C" if overall >= 60 else "D" if overall >= 40 else "F"
    return SEOResult(overall_score=overall, grade=grade, checks=checks)

def _format_text(result: SEOResult) -> str:
    icons = {True: "[PASS]", False: "[FAIL]"}
    lines = ["=" * 60,
             f"  SEO AUDIT RESULTS   Overall Score: {result.overall_score}/100  Grade: {result.grade}",
             "=" * 60]
    for c in result.checks:
        lines.append(f"  {icons[c.passed]}  {c.name:<22} [{c.score:>3}/100]  {c.note}")
    lines.append("=" * 60)
    return "\n".join(lines)

def main() -> int:
    """Entry point. Returns 0=success, 1=warnings, 2=errors."""
    parser = argparse.ArgumentParser(
        description="SEO Checker -- scores an HTML page 0-100 across 8 on-page factors.")
    parser.add_argument("file", nargs="?", default=None,
                        help="HTML file to analyze (reads stdin if omitted)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8", errors="replace") as fh:
                html = fh.read()
        elif not sys.stdin.isatty():
            html = sys.stdin.read()
        else:
            parser.print_help()
            return 2
    except FileNotFoundError:
        print(f"Error: file not found -- {args.file}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if not html.strip():
        print("Error: input is empty.", file=sys.stderr)
        return 2
    result = analyze_html(html)
    if args.json:
        print(json.dumps({"overall_score": result.overall_score, "grade": result.grade,
                          "checks": [asdict(c) for c in result.checks]}, indent=2))
    else:
        print(_format_text(result))
    return 1 if result.overall_score < 50 else 0

if __name__ == "__main__":
    sys.exit(main())
