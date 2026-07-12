"""Skill-budget linter — the curated default must stay small (F2-7c).

Measures the ALWAYS-ON context surface of the default skill install:
the frontmatter descriptions of every skill the curated cut deploys
(main /arka + 17 hubs + 14 meta + curated sub-skills, resolved from
``knowledge/skills-manifest.json`` — the generated classification the
marketplace generator emits). Skill bodies are invoke-only and do not
count; descriptions are what the runtime can inject per session.

Honesty note, printed with every report: live sessions currently
observe a smaller footprint (~2.3k tokens) because the runtime
truncates most entries to name-only — but that truncation is
NON-CONTRACTUAL runtime behavior. This budget sizes the GUARANTEED
surface (chars of description; tokens estimated at chars/4).

Thresholds (calibrated against the measured 2026-07-12 baseline:
69 skills, 34,929 chars):

    skills   WARN > 72 (90% of cap)   FAIL > 80
    total    WARN > 36,000 chars      FAIL > 40,000 (~10k tokens)
    per-skill WARN > 800 chars        FAIL > 1,024
    structural completeness           FAIL (flow & co. must be default)
    curated slug in a collision set   FAIL

CI gate: ``tests/python/test_skill_budget.py`` (repo-only, no install
needed). CLI: ``python scripts/tools/skill_budget.py [--json]`` —
exit 1 when any FAIL finding exists. stdlib only (docs_stats pattern).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "knowledge" / "skills-manifest.json"

MAX_SKILLS_FAIL = 80
MAX_SKILLS_WARN = 72
TOTAL_CHARS_FAIL = 40_000
TOTAL_CHARS_WARN = 36_000
PER_SKILL_FAIL = 1_024
PER_SKILL_WARN = 800

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.*)$", re.MULTILINE)
_ROOT_KEY_RE = re.compile(r"^[A-Za-z_-]+:")


@dataclass(frozen=True)
class Finding:
    level: str  # "FAIL" | "WARN"
    check: str
    detail: str


def frontmatter_description(skill_md: Path) -> str:
    """Extract the description value, including folded (>) blocks."""
    match = _FRONTMATTER_RE.match(skill_md.read_text(encoding="utf-8"))
    if not match:
        return ""
    frontmatter = match.group(1)
    desc = _DESCRIPTION_RE.search(frontmatter)
    if not desc:
        return ""
    value = desc.group(1).strip()
    if value not in (">", "|", ">-", "|-"):
        return value
    folded: list[str] = []
    for line in frontmatter[desc.end():].split("\n"):
        if line.startswith((" ", "\t")):
            folded.append(line.strip())
        elif _ROOT_KEY_RE.match(line):
            break
    return " ".join(folded).strip()


def default_surface(manifest: dict) -> dict[str, Path]:
    """Deployed-name -> source SKILL.md for the curated default install."""
    surface: dict[str, Path] = {"arka": REPO_ROOT / "arka" / "SKILL.md"}
    for hub in manifest["structural"]["hubs"]:
        dept = hub.removeprefix("arka-")
        surface[hub] = REPO_ROOT / "departments" / dept / "SKILL.md"
    for meta in manifest["structural"]["meta"]:
        slug = meta.removeprefix("arka-")
        surface[meta] = REPO_ROOT / "arka" / "skills" / slug / "SKILL.md"
    for slug, entry in manifest["skills"].items():
        if entry["curated"]:
            dept = entry["depts"][0]
            surface[f"arka-{slug}"] = (
                REPO_ROOT / "departments" / dept / "skills" / slug / "SKILL.md"
            )
    return surface


def _threshold_findings(count: int, total: int) -> list[Finding]:
    findings: list[Finding] = []
    if count > MAX_SKILLS_FAIL:
        findings.append(Finding(
            "FAIL", "skill-count",
            f"default install carries {count} skills (cap {MAX_SKILLS_FAIL})"))
    elif count > MAX_SKILLS_WARN:
        findings.append(Finding(
            "WARN", "skill-count",
            f"{count} skills — approaching the {MAX_SKILLS_FAIL} cap"))
    if total > TOTAL_CHARS_FAIL:
        findings.append(Finding(
            "FAIL", "total-description-chars",
            f"{total} chars of always-on descriptions "
            f"(cap {TOTAL_CHARS_FAIL} ~= {TOTAL_CHARS_FAIL // 4} tokens)"))
    elif total > TOTAL_CHARS_WARN:
        findings.append(Finding(
            "WARN", "total-description-chars",
            f"{total} chars — approaching the {TOTAL_CHARS_FAIL} cap"))
    return findings


def _structural_findings(manifest: dict) -> list[Finding]:
    findings: list[Finding] = []
    meta = set(manifest["structural"]["meta"])
    for required in ("arka-flow", "arka-forge", "arka-fusion"):
        if required not in meta:
            findings.append(Finding(
                "FAIL", "structural-completeness",
                f"{required} missing from the structural default — "
                f"evidence-flow and planning are NON-NEGOTIABLE"))
    for slug, entry in manifest["skills"].items():
        if entry["curated"] and entry["collision"]:
            findings.append(Finding(
                "FAIL", "curated-collision",
                f"curated slug {slug!r} is a later-wins collision — it "
                f"must live only in plugins"))
    return findings


def audit(manifest_path: Path | None = None) -> dict:
    """Full audit. Returns {summary, findings, note}.

    ``manifest_path`` resolves the module attribute at CALL time so
    tests can monkeypatch ``MANIFEST_PATH`` (a def-time default would
    freeze the original binding).
    """
    manifest_path = manifest_path or MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    surface = default_surface(manifest)
    sizes = {
        name: len(frontmatter_description(path))
        for name, path in surface.items() if path.is_file()
    }
    missing = sorted(set(surface) - set(sizes))
    total = sum(sizes.values())
    findings = _threshold_findings(len(surface), total)
    findings.extend(_structural_findings(manifest))
    for name in missing:
        findings.append(Finding(
            "FAIL", "missing-source", f"{name}: source SKILL.md not found"))
    for name, size in sorted(sizes.items(), key=lambda kv: -kv[1]):
        if size > PER_SKILL_FAIL:
            findings.append(Finding(
                "FAIL", "per-skill-description",
                f"{name}: {size} chars (cap {PER_SKILL_FAIL})"))
        elif size > PER_SKILL_WARN:
            findings.append(Finding(
                "WARN", "per-skill-description",
                f"{name}: {size} chars (warn over {PER_SKILL_WARN})"))
    return {
        "summary": {
            "skills": len(surface),
            "total_description_chars": total,
            "estimated_tokens": total // 4,
            "fails": sum(1 for f in findings if f.level == "FAIL"),
            "warns": sum(1 for f in findings if f.level == "WARN"),
        },
        "findings": [asdict(f) for f in findings],
        "note": (
            "Budget sizes the GUARANTEED always-on surface (description "
            "chars). Live sessions may observe less (~2.3k tokens) because "
            "the runtime truncates entries to name-only — that truncation "
            "is non-contractual and not relied upon."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/tools/skill_budget.py",
        description="Audit the curated default skill surface. Exit 1 on FAIL.",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = audit()
    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        s = report["summary"]
        print(f"skills: {s['skills']} | always-on description chars: "
              f"{s['total_description_chars']} (~{s['estimated_tokens']} tokens)")
        for f in report["findings"]:
            print(f"  [{f['level']}] {f['check']}: {f['detail']}")
        print(report["note"])
    return 1 if report["summary"]["fails"] else 0


if __name__ == "__main__":
    sys.exit(main())
