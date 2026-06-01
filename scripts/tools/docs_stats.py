#!/usr/bin/env python3
"""ArkaOS Docs Stats -- canonical source of truth for documentation numbers.

Counts agents, departments, skills, ADRs, and tests directly from the
repository so that every document (README, wiki, CLAUDE.md) consumes generated
numbers instead of hand-typed ones. This is the antidote to documentation
drift: no number is ever written by hand.

Usage:
    python docs_stats.py                 # human-readable (repo root auto-detected)
    python docs_stats.py --json
    python docs_stats.py --root /path/to/arka-os --json
    python docs_stats.py --with-pytest   # also collect authoritative pytest case count
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

_TEST_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+test_\w+", re.MULTILINE)
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected")


def repo_root(start: Optional[Path] = None) -> Path:
    """Find the repo root by walking up to a dir with VERSION + departments/."""
    cur = (start or Path(__file__).resolve()).resolve()
    candidates = [cur, *cur.parents] if cur.is_dir() else [cur.parent, *cur.parents]
    for p in candidates:
        if (p / "VERSION").is_file() and (p / "departments").is_dir():
            return p
    return Path.cwd()


def read_version(root: Path) -> str:
    """Read the canonical version string from the VERSION file."""
    vf = root / "VERSION"
    return vf.read_text(encoding="utf-8").strip() if vf.is_file() else ""


def count_agents(root: Path) -> dict:
    """Count agent YAML files under departments/*/agents/ (recursive, to
    include sub-squad nesting). Returns total files + unique slugs."""
    dep = root / "departments"
    files = [f for d in dep.glob("*/agents") if d.is_dir()
             for f in d.rglob("*.yaml")] if dep.is_dir() else []
    return {"files": len(files), "unique_slugs": len({f.name for f in files})}


def count_departments(root: Path) -> int:
    """Count department directories under departments/."""
    dep = root / "departments"
    return sum(1 for d in dep.iterdir() if d.is_dir()) if dep.is_dir() else 0


def count_skills(root: Path) -> dict:
    """Count SKILL.md files by area. 'core' = departments + arka."""
    def _n(rel: str) -> int:
        base = root / rel
        return len(list(base.rglob("SKILL.md"))) if base.is_dir() else 0

    dept, arka, market = _n("departments"), _n("arka"), _n("marketplace")
    return {"departments": dept, "arka": arka, "marketplace": market,
            "core": dept + arka}


def count_adrs(root: Path) -> int:
    """Count Architecture Decision Records in docs/adr/."""
    adr = root / "docs" / "adr"
    return len(list(adr.glob("*.md"))) if adr.is_dir() else 0


def count_test_functions(root: Path) -> int:
    """Static count of `def test_` / `async def test_` definitions in tests/."""
    tdir = root / "tests"
    if not tdir.is_dir():
        return 0
    return sum(len(_TEST_DEF_RE.findall(f.read_text(encoding="utf-8", errors="replace")))
               for f in tdir.rglob("test_*.py"))


def collect_pytest_cases(root: Path) -> Optional[int]:
    """Authoritative pytest case count via --collect-only. None on failure."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=root, capture_output=True, text=True, timeout=300, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in reversed(out.stdout.splitlines()):
        m = _COLLECTED_RE.search(line)
        if m:
            return int(m.group(1))
    return None


def gather(root: Path, with_pytest: bool = False) -> dict:
    """Collect all documentation stats into a JSON-serialisable dict."""
    tests = {"functions": count_test_functions(root)}
    if with_pytest:
        tests["collected"] = collect_pytest_cases(root)
    return {
        "version": read_version(root),
        "agents": count_agents(root),
        "departments": count_departments(root),
        "skills": count_skills(root),
        "adrs": count_adrs(root),
        "tests": tests,
        "root": str(root),
    }


def format_text(stats: dict) -> str:
    """Render a human-readable summary."""
    a, s, t = stats["agents"], stats["skills"], stats["tests"]
    lines = [
        "=" * 52,
        "ARKAOS DOCS STATS (canonical)",
        "=" * 52,
        f"Version:        {stats['version']}",
        f"Departments:    {stats['departments']}",
        f"Agents:         {a['files']} files ({a['unique_slugs']} unique slugs)",
        f"Skills (core):  {s['core']}  (departments {s['departments']} + arka {s['arka']})",
        f"  marketplace:  {s['marketplace']}",
        f"ADRs:           {stats['adrs']}",
        f"Test functions: {t['functions']}",
    ]
    if "collected" in t:
        lines.append(f"Test cases:     {t['collected']} (pytest collected)")
    lines.append("=" * 52)
    return "\n".join(lines)


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="ArkaOS docs stats -- canonical documentation counter")
    parser.add_argument("--root", default=None, help="Repo root (default: auto-detect)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--with-pytest", action="store_true",
                        help="Also collect authoritative pytest case count")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else repo_root()
    stats = gather(root, with_pytest=args.with_pytest)
    print(json.dumps(stats, indent=2) if args.json else format_text(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
