"""Skills catalog generator — every SKILL.md in the system, one page.

Documents the complete skill surface: 318 department skills plus the 15
``/arka`` meta skills (333 total). Single source of truth: the SKILL.md
files themselves (``departments/*/skills/*/SKILL.md`` and
``arka/skills/*/SKILL.md``), never hand-typed counts. This script
GENERATES:

- ``docs/SKILLS-CATALOG.md`` — per-department catalog with slug, path,
  and description for every skill.

Regenerate + commit after touching any SKILL.md set, department
layout, or VERSION:

    python scripts/skills_catalog_gen.py

``tests/python/test_skills_catalog_gen.py`` drift-gates the committed
file against a fresh in-memory run, byte for byte.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - venv-only dependency
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "docs" / "SKILLS-CATALOG.md"

# Canonical department order — mirrors scripts/tools/docs_stats.py
DEPARTMENT_ORDER = [
    "dev",
    "marketing",
    "brand",
    "finance",
    "strategy",
    "ecom",
    "kb",
    "ops",
    "pm",
    "saas",
    "landing",
    "content",
    "community",
    "sales",
    "leadership",
    "org",
]

DEPT_TITLES = {
    "dev": "Development",
    "marketing": "Marketing",
    "brand": "Brand & Design",
    "finance": "Finance",
    "strategy": "Strategy",
    "ecom": "E-Commerce",
    "kb": "Knowledge",
    "ops": "Operations",
    "pm": "Project Management",
    "saas": "SaaS",
    "landing": "Landing Pages",
    "content": "Content",
    "community": "Communities",
    "sales": "Sales",
    "leadership": "Leadership",
    "org": "Organization",
}


def _clean_description(raw: str | None, fallback: str) -> str:
    """First sentence(s) of the description, single line, truncated."""
    if not raw:
        return fallback
    text = raw.replace("TRIGGER:", ". TRIGGER:").split("TRIGGER:")[0]
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+\.", ".", text)
    if len(text) > 180:
        head = text[:177]
        # Cut on a word boundary: a mid-word slice emits fragments that read
        # as typos to spellcheckers ("CLEAN" -> "CLEA", "with" -> "wit").
        boundary = head.rfind(" ")
        text = (head[:boundary] if boundary > 0 else head).rstrip(" ,;:—-") + "..."
    return text or fallback


def _skill_entry(path: Path) -> dict:
    """slug, name, description from a SKILL.md frontmatter."""
    text = path.read_text(encoding="utf-8", errors="replace")
    name = path.parent.name
    description = path.stem
    if yaml is not None and text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                name = meta.get("name", name)
                description = _clean_description(meta.get("description"), name)
            except Exception:
                pass
    if description == name:
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                description = _clean_description(line, name)
                break
    return {"slug": path.parent.name, "name": name, "description": description}


def _dept_skills() -> dict[str, list[dict]]:
    """department slug -> hub entry first, then sorted sub-skill entries.

    Matches docs_stats.py semantics: the department hub
    (``departments/<dept>/SKILL.md``) IS counted as a skill, so the
    grand total reconciles with the canonical 333 headline.
    """
    result: dict[str, list[dict]] = {}
    for dept_dir in (REPO_ROOT / "departments").iterdir():
        if not dept_dir.is_dir() or "vendor" in dept_dir.parts:
            continue
        entries = []
        hub = dept_dir / "SKILL.md"
        if hub.is_file():
            entry = _skill_entry(hub)
            entry["slug"] = f"{dept_dir.name}-hub"
            entry["name"] = f"{dept_dir.name} (hub)"
            entries.append(entry)
        skills_dir = dept_dir / "skills"
        if skills_dir.is_dir():
            for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
                if "vendor" in skill_md.parts:
                    continue
                entries.append(_skill_entry(skill_md))
        if entries:
            result[dept_dir.name] = entries
    return result


def _arka_skills() -> list[dict]:
    """The 15 /arka meta skills: the master orchestrator plus the 14
    sub-skills under arka/skills/*/SKILL.md."""
    master = REPO_ROOT / "arka" / "SKILL.md"
    entries = []
    if master.is_file():
        entry = _skill_entry(master)
        entry["slug"] = "arka"
        entry["name"] = "arka (master orchestrator)"
        entries.append(entry)
    skills_dir = REPO_ROOT / "arka" / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            if "vendor" in skill_md.parts:
                continue
            entries.append(_skill_entry(skill_md))
    return entries


def generate() -> str:
    """Return the full SKILLS-CATALOG.md content."""
    dept_skills = _dept_skills()
    arka_skills = _arka_skills()
    dept_total = sum(len(v) for v in dept_skills.values())
    total = dept_total + len(arka_skills)

    lines = [
        "# ArkaOS Skills Catalog",
        "",
        "> Generated by `scripts/skills_catalog_gen.py`; do not edit. Regenerate after",
        "> touching any SKILL.md, department layout, or VERSION.",
        "",
        f"**{total} skills** — {dept_total} department skills across "
        f"{len(dept_skills)} departments, plus {len(arka_skills)} `/arka` meta skills.",
        "",
        "## Summary",
        "",
        "| Department | Skills |",
        "| --- | --- |",
    ]
    for slug in DEPARTMENT_ORDER:
        if slug in dept_skills:
            lines.append(f"| {DEPT_TITLES[slug]} (`{slug}`) | {len(dept_skills[slug])} |")
    for slug in sorted(set(dept_skills) - set(DEPARTMENT_ORDER)):
        lines.append(f"| {slug} | {len(dept_skills[slug])} |")
    lines.append(f"| **Total departments** | **{dept_total}** |")
    lines.append(f"| `/arka` meta skills | {len(arka_skills)} |")
    lines.append(f"| **Grand total** | **{total}** |")
    lines.append("")

    lines.append("## Department skills")
    lines.append("")
    for slug in DEPARTMENT_ORDER:
        entries = dept_skills.get(slug)
        if not entries:
            continue
        lines.append(f"### {DEPT_TITLES[slug]} (`{slug}`)")
        lines.append("")
        lines.append("| Skill | Name | Description |")
        lines.append("| --- | --- | --- |")
        for entry in entries:
            lines.append(
                f"| `{entry['slug']}` | {entry['name']} | {entry['description']} |"
            )
        lines.append("")

    lines.append("## `/arka` meta skills")
    lines.append("")
    lines.append("| Skill | Name | Description |")
    lines.append("| --- | --- | --- |")
    for entry in arka_skills:
        lines.append(
            f"| `{entry['slug']}` | {entry['name']} | {entry['description']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    content = generate()
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"skills catalog generated: {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
