#!/usr/bin/env python3
"""ArkaOS v2 Skill Validator — validates SKILL.md files against project standards.

Exit codes: 0 = all passed, 1 = warnings only, 2 = failures found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

WEIGHTS = {
    "skill_md_exists": 20, "frontmatter_present": 15, "required_fields": 15,
    "name_format": 10, "allowed_tools_list": 5, "has_h1": 10, "has_h2": 5,
    "line_count": 5, "agent_attribution": 10, "output_section": 5,
}


@dataclass
class SkillResult:
    """Validation result for a single skill."""
    name: str
    score: int = 100
    level: str = "EXCELLENT"
    issues: list[str] = field(default_factory=list)

    def deduct(self, points: int, reason: str) -> None:
        self.score = max(0, self.score - points)
        self.issues.append(reason)

    def finalize(self) -> None:
        if self.score >= 90:
            self.level = "EXCELLENT"
        elif self.score >= 70:
            self.level = "GOOD"
        elif self.score >= 50:
            self.level = "WARN"
        else:
            self.level = "FAIL"

    @property
    def passed(self) -> bool:
        return self.level in ("EXCELLENT", "GOOD")

    @property
    def is_warning(self) -> bool:
        return self.level == "WARN"

    @property
    def is_failure(self) -> bool:
        return self.level == "FAIL"

    def to_dict(self) -> dict:
        return {"name": self.name, "score": self.score, "level": self.level, "issues": self.issues}


def parse_frontmatter(content: str) -> dict[str, str | list[str]] | None:
    """Extract YAML frontmatter between --- markers (no PyYAML needed)."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    data: dict[str, str | list[str]] = {}
    for line in match.group(1).split("\n"):
        key_match = re.match(r"^(\w[\w-]*)\s*:\s*(.*)", line)
        if key_match:
            key, value = key_match.group(1), key_match.group(2).strip()
            list_match = re.match(r"^\[(.+)]$", value)
            if list_match:
                data[key] = [v.strip() for v in list_match.group(1).split(",")]
            elif value in (">", "|"):
                data[key] = ""
            else:
                data[key] = value
        elif line.startswith("  ") and data:
            last_key = list(data.keys())[-1]
            if isinstance(data[last_key], str):
                data[last_key] = (data[last_key] + " " + line.strip()).strip()
    return data


def validate_skill(skill_dir: Path) -> SkillResult:
    """Validate a single skill directory against ArkaOS v2 standards."""
    parts = skill_dir.resolve().parts
    try:
        dept = parts[parts.index("departments") + 1]
    except (ValueError, IndexError):
        dept = "unknown"
    result = SkillResult(name=f"{dept}/{skill_dir.name}")
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.is_file():
        result.deduct(WEIGHTS["skill_md_exists"], "missing SKILL.md")
        result.finalize()
        return result

    content = skill_md.read_text(encoding="utf-8")
    line_count = content.count("\n") + 1

    # Frontmatter checks
    fm = parse_frontmatter(content)
    if fm is None:
        for key in ("frontmatter_present", "required_fields", "name_format", "allowed_tools_list"):
            result.deduct(WEIGHTS[key], f"no {key.replace('_', ' ')} (no frontmatter)")
    else:
        missing = [f for f in ("name", "description", "allowed-tools") if f not in fm]
        if missing:
            result.deduct(WEIGHTS["required_fields"], f"missing fields: {', '.join(missing)}")
        name_val = fm.get("name", "")
        if isinstance(name_val, str) and not re.match(r"^[a-z][\w-]*/[\w-]+$", name_val):
            result.deduct(WEIGHTS["name_format"], f"name '{name_val}' does not match dept/slug format")
        tools = fm.get("allowed-tools")
        if tools is not None and not isinstance(tools, list):
            result.deduct(WEIGHTS["allowed_tools_list"], "allowed-tools is not a list")

    # Content checks (strip frontmatter)
    body = re.sub(r"^---.*?---\s*", "", content, count=1, flags=re.DOTALL)
    if not re.search(r"^# ", body, re.MULTILINE):
        result.deduct(WEIGHTS["has_h1"], "no H1 heading found")
    if not re.search(r"^## ", body, re.MULTILINE):
        result.deduct(WEIGHTS["has_h2"], "no H2 heading found")

    # Line count: error if outside 30-200, soft warn if outside 60-120
    if line_count < 30 or line_count > 200:
        result.deduct(WEIGHTS["line_count"], f"line count {line_count} outside 30-200 range")
    elif line_count < 60 or line_count > 120:
        result.deduct(WEIGHTS["line_count"] // 2, f"line count {line_count} outside ideal 60-120 range")

    if not re.search(r"^>\s*\*\*Agent:", body, re.MULTILINE):
        result.deduct(WEIGHTS["agent_attribution"], "missing agent attribution (> **Agent:** line)")
    if not re.search(r"^##\s+Output", body, re.MULTILINE):
        result.deduct(WEIGHTS["output_section"], "missing ## Output section")

    result.finalize()
    return result


def discover_skills(root: Path) -> list[Path]:
    """Recursively find all directories containing SKILL.md."""
    skills = [Path(dp) for dp, _, fns in os.walk(root) if "SKILL.md" in fns]
    skills.sort(key=lambda p: str(p))
    return skills


def _counts(results: list[SkillResult]) -> tuple[int, int, int]:
    passed = sum(1 for r in results if r.passed)
    warnings = sum(1 for r in results if r.is_warning)
    failures = sum(1 for r in results if r.is_failure)
    return passed, warnings, failures


def print_text(results: list[SkillResult], summary_only: bool = False) -> None:
    """Print human-readable validation output."""
    if not summary_only:
        for r in results:
            icon = "\u2713" if r.passed else ("\u26A0" if r.is_warning else "\u2717")
            suffix = f" ({', '.join(r.issues)})" if r.issues else ""
            print(f"{icon} {r.name} \u2014 {r.score}/100 {r.level}{suffix}")
        print()
    passed, warnings, failures = _counts(results)
    print(f"Summary: {len(results)} skills validated, {passed} passed, {warnings} warnings, {failures} failures")


def print_json(results: list[SkillResult]) -> None:
    """Print JSON validation output."""
    passed, warnings, failures = _counts(results)
    output = {
        "total": len(results), "passed": passed, "warnings": warnings,
        "failures": failures, "skills": [r.to_dict() for r in results],
    }
    print(json.dumps(output, indent=2))


def main() -> int:
    """Entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="ArkaOS v2 Skill Validator — validate SKILL.md files against project standards.",
        epilog="Exit codes: 0 = all passed, 1 = warnings only, 2 = failures found.",
    )
    parser.add_argument("path", type=Path, help="Skill directory or parent to scan recursively.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON.")
    parser.add_argument("--summary", action="store_true", help="Print only summary totals.")
    args = parser.parse_args()
    target: Path = args.path.resolve()

    if not target.exists():
        print(f"Error: path does not exist: {target}", file=sys.stderr)
        return 2

    if (target / "SKILL.md").is_file():
        skill_dirs = [target]
    elif target.is_dir():
        skill_dirs = discover_skills(target)
    else:
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return 2

    if not skill_dirs:
        print("No SKILL.md files found.", file=sys.stderr)
        return 2

    results = [validate_skill(d) for d in skill_dirs]
    if args.json_output:
        print_json(results)
    else:
        print_text(results, summary_only=args.summary)

    if any(r.is_failure for r in results):
        return 2
    if any(r.is_warning for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
