"""Routing-integrity locks for the TRIGGER/SKIP skill contract.

The 2026-07-09 rollout QG found two defect classes the skill_validator was
blind to: (1) folded-scalar `description: >` blocks that wrap a hyphenated
SKIP slug across a line, so the PARSED target the router consumes is
corrupt (`ecom/cro- optimize`); (2) two sibling skills in one department
sharing a verbatim TRIGGER phrase with no mutual SKIP arm, i.e. an
ambiguous route. These tests resolve every SKIP target against disk and
sweep for unarmed same-department trigger collisions so the classes
cannot silently return.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]

# SKIP targets use department slugs that differ from directory names.
_DEPT_ALIAS = {
    "mkt": "marketing", "strat": "strategy", "fin": "finance",
    "lead": "leadership",
}

# Non-slug tokens that legitimately follow "-> " and must not be resolved
# as skill references (prose arrows, not routing targets).
_NON_SLUG = re.compile(r"^(?:go|no|the|a|an|its?|their)$", re.IGNORECASE)


def _skill_files() -> list[Path]:
    return sorted(
        list(_ROOT.glob("departments/*/skills/*/SKILL.md"))
        + list(_ROOT.glob("arka/skills/*/SKILL.md"))
    )


def _description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    fm = yaml.safe_load(m.group(1)) or {}
    return fm.get("description", "") or ""


def _skill_dir_exists(dept: str, slug: str) -> bool:
    dept = _DEPT_ALIAS.get(dept, dept)
    return (
        (_ROOT / "departments" / dept / "skills" / slug).is_dir()
        or (_ROOT / "arka" / "skills" / slug).is_dir()
    )


def test_all_skip_targets_resolve_to_real_skills():
    """Every `-> dept/slug` in a SKIP arm must resolve to a skill on disk."""
    broken: list[str] = []
    for path in _skill_files():
        desc = _description(path)
        # A folded newline leaves a slug split as 'word- word' — catch it
        # before it masquerades as a valid token.
        for hit in re.findall(r"[a-z0-9]+/[a-z0-9-]+-\s+[a-z0-9-]+", desc):
            broken.append(f"{path.relative_to(_ROOT)}: folded slug '{hit}'")
        for tgt in re.findall(r"->\s*([a-z]+)/([a-z0-9][a-z0-9-]*)", desc):
            dept, slug = tgt
            if _NON_SLUG.match(dept):
                continue
            if not _skill_dir_exists(dept, slug):
                broken.append(f"{path.relative_to(_ROOT)}: -> {dept}/{slug} (no such skill)")
    assert not broken, "Unresolved SKIP targets:\n" + "\n".join(broken)


def _triggers(desc: str) -> set[str]:
    """Quoted trigger phrases from the TRIGGER: clause (before SKIP:)."""
    trigger_part = re.split(r"\bSKIP:", desc)[0]
    trigger_part = re.split(r"\bTRIGGER:", trigger_part)[-1]
    return {q.strip().lower() for q in re.findall(r'"([^"]+)"', trigger_part)}


def test_no_unarmed_same_department_trigger_collisions():
    """Two sibling skills sharing a verbatim trigger must SKIP each other.

    A shared quoted trigger phrase is only allowed when at least one of the
    pair names the other in a SKIP arm — otherwise the route is ambiguous.
    Slash-command tokens ("/kb learn") are excluded: many siblings share a
    department command prefix by design and disambiguate on the argument.
    """
    by_dept: dict[str, list[tuple[str, set[str], str]]] = {}
    for path in _skill_files():
        parts = path.relative_to(_ROOT).parts
        dept = parts[1] if parts[0] == "departments" else "arka"
        desc = _description(path)
        trigs = {t for t in _triggers(desc) if not t.startswith("/")}
        by_dept.setdefault(dept, []).append((path.parent.name, trigs, desc))

    collisions: list[str] = []
    for dept, skills in by_dept.items():
        for i in range(len(skills)):
            for j in range(i + 1, len(skills)):
                name_a, trig_a, desc_a = skills[i]
                name_b, trig_b, desc_b = skills[j]
                shared = trig_a & trig_b
                if not shared:
                    continue
                armed = (f"/{name_b}" in desc_a or f"{dept}/{name_b}" in desc_a
                         or f"/{name_a}" in desc_b or f"{dept}/{name_a}" in desc_b)
                if not armed:
                    collisions.append(
                        f"{dept}: {name_a} <> {name_b} share {sorted(shared)} "
                        f"with no mutual SKIP arm"
                    )
    assert not collisions, "Unarmed trigger collisions:\n" + "\n".join(collisions)
