#!/usr/bin/env python3
"""Tech Debt Analyzer -- ArkaOS v2.

Scans a codebase directory for tech debt signals: TODO/FIXME counts,
large files, deep nesting, missing tests, old lock files.
Scores 0-100 with category breakdown and prioritised action list.

Usage:
    python tech_debt_analyzer.py /path/to/project
    python tech_debt_analyzer.py . --json
    python tech_debt_analyzer.py ./src --extensions py,js,ts
"""
from __future__ import annotations
import argparse, json, os, re, sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

DEFAULT_EXT = {"py", "js", "ts", "jsx", "tsx", "php", "rb", "go", "rs", "java"}
LARGE_FILE = 500
NEST_THRESHOLD = 5
TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX|WORKAROUND)\b", re.IGNORECASE)
SKIP = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv",
        "dist", "build", ".next", ".nuxt", "storage", "target"}

@dataclass
class FileIssue:
    """A single issue found in a file."""
    path: str; issue: str; severity: str

@dataclass
class CategoryScore:
    """Score for one debt category."""
    name: str; score: float; weight: float
    issues: List[FileIssue] = field(default_factory=list)

@dataclass
class DebtReport:
    """Full tech debt report."""
    directory: str; timestamp: str; files_scanned: int; total_lines: int
    overall_score: float; level: str
    categories: List[CategoryScore] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)

def _iter_files(root: str, extensions: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for f in filenames:
            ext = f.rsplit(".", 1)[-1] if "." in f else ""
            if ext in extensions:
                full = os.path.join(dirpath, f)
                yield os.path.relpath(full, root), full

def _read(path: str) -> List[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.readlines()
    except (OSError, PermissionError):
        return []

def _max_nesting(lines: List[str]) -> int:
    depth = mx = 0
    for ln in lines:
        for ch in ln:
            if ch in "({[":
                depth += 1; mx = max(mx, depth)
            elif ch in ")}]":
                depth = max(depth - 1, 0)
    return mx

def _has_tests(root: str) -> bool:
    return any(os.path.isdir(os.path.join(root, d))
               for d in ("tests", "test", "spec", "__tests__"))

def _lock_age(root: str) -> Optional[int]:
    locks = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml",
             "composer.lock", "Pipfile.lock", "poetry.lock", "Cargo.lock"]
    mt = max((os.path.getmtime(os.path.join(root, f))
              for f in locks if os.path.isfile(os.path.join(root, f))), default=0.0)
    return int((datetime.now().timestamp() - mt) / 86400) if mt else None

def analyze(root: str, extensions: set[str]) -> DebtReport:
    """Scan directory and produce a debt report."""
    root = os.path.abspath(root)
    cats = {n: CategoryScore(name=n, score=0, weight=0.20) for n in
            ("TODO/FIXME markers", "Large files", "Deep nesting",
             "Test coverage signals", "Dependency freshness")}
    total_files = total_lines = todo_count = large_count = deep_count = 0

    for rel, full in _iter_files(root, extensions):
        lines = _read(full)
        lc = len(lines); total_files += 1; total_lines += lc
        ft = sum(1 for ln in lines if TODO_RE.search(ln))
        if ft:
            todo_count += ft
            cats["TODO/FIXME markers"].issues.append(
                FileIssue(rel, f"{ft} markers", "high" if ft > 10 else "medium" if ft > 3 else "low"))
        if lc > LARGE_FILE:
            large_count += 1
            cats["Large files"].issues.append(
                FileIssue(rel, f"{lc} lines", "high" if lc > 1000 else "medium"))
        nest = _max_nesting(lines)
        if nest > NEST_THRESHOLD:
            deep_count += 1
            cats["Deep nesting"].issues.append(
                FileIssue(rel, f"depth {nest}", "high" if nest > 8 else "medium"))

    if total_lines > 0:
        cats["TODO/FIXME markers"].score = min(100, round((todo_count / total_lines) * 10000, 1))
    if total_files > 0:
        cats["Large files"].score = min(100, round((large_count / total_files) * 200, 1))
        cats["Deep nesting"].score = min(100, round((deep_count / total_files) * 200, 1))

    ct = cats["Test coverage signals"]
    if not _has_tests(root):
        ct.score = 80.0; ct.issues.append(FileIssue(".", "No test directory found", "high"))
    else:
        test_n = sum(1 for r, _ in _iter_files(root, extensions)
                     if "test" in r.lower() or "spec" in r.lower())
        ct.score = max(0, round((1 - min((test_n / max(total_files, 1)) * 4, 1)) * 100, 1))

    cd = cats["Dependency freshness"]
    age = _lock_age(root)
    if age is None:
        cd.score = 40.0; cd.issues.append(FileIssue(".", "No lock file found", "medium"))
    else:
        cd.score = min(100, round(age / 3.6, 1))
        if age > 90:
            cd.issues.append(FileIssue(".", f"Lock file {age} days old",
                                       "high" if age > 180 else "medium"))

    cat_list = list(cats.values())
    overall = round(sum(c.score * c.weight for c in cat_list), 1)
    level = ("Low" if overall < 20 else "Moderate" if overall < 40 else
             "Elevated" if overall < 60 else "High" if overall < 80 else "Critical")

    actions: List[str] = []
    if overall >= 60:
        actions.append("[URGENT] Dedicate 30%+ capacity to debt reduction")
    elif overall >= 40:
        actions.append("[PLAN] Allocate 20% of sprints to debt reduction")
    for c in sorted(cat_list, key=lambda x: x.score, reverse=True):
        if c.score > 50:
            actions.append(f"[HIGH] Address {c.name} (score: {c.score})")
        elif c.score > 25:
            actions.append(f"[MED]  Improve {c.name} (score: {c.score})")

    return DebtReport(directory=root, timestamp=datetime.now().isoformat(timespec="seconds"),
        files_scanned=total_files, total_lines=total_lines, overall_score=overall,
        level=level, categories=cat_list, actions=actions)

def format_report(r: DebtReport) -> str:
    """Render plain-text report."""
    lines = ["=" * 60, "TECH DEBT ANALYSIS REPORT", "=" * 60,
             f"Directory:    {r.directory}",
             f"Scanned:      {r.files_scanned} files, {r.total_lines:,} lines",
             f"Timestamp:    {r.timestamp}", "",
             f"OVERALL SCORE: {r.overall_score}/100  ({r.level})", "",
             "CATEGORY BREAKDOWN",
             f"  {'Category':<28} {'Score':>6}  {'Weight':>6}  Issues",
             "  " + "-" * 55]
    for c in r.categories:
        lines.append(f"  {c.name:<28} {c.score:>5.1f}  {c.weight * 100:>5.0f}%  {len(c.issues)}")
    lines += ["", "TOP ISSUES"]
    sev_order = {"high": 0, "medium": 1, "low": 2}
    for c in sorted(r.categories, key=lambda x: x.score, reverse=True):
        if not c.issues: continue
        lines.append(f"  {c.name}:")
        for iss in sorted(c.issues, key=lambda i: sev_order[i.severity])[:5]:
            lines.append(f"    [{iss.severity.upper()}] {iss.path}: {iss.issue}")
    lines += ["", "PRIORITISED ACTIONS"]
    for i, a in enumerate(r.actions, 1):
        lines.append(f"  {i}. {a}")
    lines += ["", "=" * 60]
    return "\n".join(lines)

def to_json(r: DebtReport) -> str:
    return json.dumps(asdict(r), indent=2)

def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Tech Debt Analyzer -- scan a codebase for debt signals")
    parser.add_argument("directory", nargs="?", default=".",
                        help="Directory to scan (default: current directory)")
    parser.add_argument("--extensions", "-e", default=None,
                        help="Comma-separated file extensions (default: py,js,ts,...)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory", file=sys.stderr)
        return 2
    extensions = DEFAULT_EXT
    if args.extensions:
        extensions = {e.strip().lstrip(".") for e in args.extensions.split(",") if e.strip()}
    report = analyze(args.directory, extensions)
    if args.json:
        print(to_json(report))
    else:
        print(format_report(report))
    if report.overall_score >= 60: return 2
    if report.overall_score >= 40: return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
