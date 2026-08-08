"""Locking test: per-department wiki counts equal the canonical counter.

``test_docs_consistency.py`` locks the HEADLINE totals repo-wide, but its
pattern is ``\\d{3}`` followed by the noun, so two things stayed invisible
to it across the whole of ``wiki/04-Departments/``:

* every per-department count is **fewer than three digits** (``70``,
  ``15``, ``9``),
* half of them are written **noun-then-number** (``**Skills:** 70``), the
  reverse of the order it matches, and
* the rest are **bare table cells** with the noun in a separate header
  row (``| 36 | 70 | 15 |``).

That is 17 departments x 4 count-sites = 68 sites, carrying over 100
individual numbers with no lock at all. This test derives each
department's counts from ``docs_stats.py`` and checks three places on
every page plus the index row in README.md.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_STATS_PATH = _ROOT / "scripts" / "tools" / "docs_stats.py"
_WIKI = _ROOT / "wiki" / "04-Departments"


def _load_docs_stats():
    spec = importlib.util.spec_from_file_location("docs_stats_wiki", _STATS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["docs_stats_wiki"] = module
    spec.loader.exec_module(module)
    return module


_ds = _load_docs_stats()
_SKILLS = _ds.count_skills_by_department(_ROOT)
_AGENTS = _ds.count_agents_by_department(_ROOT)

# Wiki page stems map 1:1 onto department directory names.
_PAGES = sorted(p for p in _WIKI.glob("*.md") if p.name != "README.md")
_DEPTS = sorted(_SKILLS)


def _numbered_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    return list(enumerate(text.splitlines(), 1))


def _fail(path: Path, line: int, found: int, expected: int, what: str) -> str:
    rel = path.relative_to(_ROOT)
    return f"{rel}:{line} says {found} {what}, docs_stats says {expected}"


def test_every_department_has_a_wiki_page_and_vice_versa():
    """The 1:1 mapping is itself a lock: a new department needs a page."""
    assert [p.stem for p in _PAGES] == _DEPTS, (
        "wiki/04-Departments pages and departments/ directories diverged: "
        f"pages={[p.stem for p in _PAGES]} departments={_DEPTS}"
    )


@pytest.mark.parametrize("dept", _DEPTS)
def test_wiki_page_header_carries_canonical_counts(dept: str):
    """The `> **Prefix:** ... **Agents:** N · **Skills:** M` blockquote.

    Noun-then-number order — the shape the repo-wide lock cannot see.
    """
    path = _WIKI / f"{dept}.md"
    errors = []
    seen = set()
    for line, body in _numbered_lines(path):
        for what, expected in (("Agents", _AGENTS[dept]), ("Skills", _SKILLS[dept])):
            m = re.search(rf"\*\*{what}:\*\*\s*(\d+)", body)
            if not m:
                continue
            seen.add(what)
            if int(m.group(1)) != expected:
                errors.append(_fail(path, line, int(m.group(1)), expected, what.lower()))
    assert not errors, "\n  ".join(["header count drift:", *errors])
    # quality.md has no **Skills:** in its header (it is not invocable),
    # so only the agents field is required everywhere.
    assert "Agents" in seen, f"{path.relative_to(_ROOT)} has no '**Agents:** N' header"


@pytest.mark.parametrize("dept", _DEPTS)
def test_wiki_page_summary_table_carries_canonical_counts(dept: str):
    """The `| Commands | Skills | Agents |` table's data row."""
    path = _WIKI / f"{dept}.md"
    rows = _numbered_lines(path)
    header = next(
        (i for i, body in rows
         if re.match(r"\|\s*Commands\s*\|\s*Skills\s*\|\s*Agents\s*\|", body)),
        None,
    )
    assert header is not None, (
        f"{path.relative_to(_ROOT)} lost its '| Commands | Skills | Agents |' table"
    )
    # header row, separator row, then the data row
    line, body = rows[header + 1]
    cells = [c.strip() for c in body.strip().strip("|").split("|")]
    assert len(cells) == 3 and all(c.isdigit() for c in cells), (
        f"{path.relative_to(_ROOT)}:{line} is not a 3-number data row: {body!r}"
    )
    _commands, skills, agents = (int(c) for c in cells)
    errors = []
    if skills != _SKILLS[dept]:
        errors.append(_fail(path, line, skills, _SKILLS[dept], "skills"))
    if agents != _AGENTS[dept]:
        errors.append(_fail(path, line, agents, _AGENTS[dept], "agents"))
    assert not errors, "\n  ".join(["summary table drift:", *errors])


@pytest.mark.parametrize("dept", _DEPTS)
def test_wiki_page_skills_list_header_carries_canonical_counts(dept: str):
    """`**Skills** (N — M sub-skills plus the `/x` hub):`.

    Both numbers are derived: M is N minus the department hub, so a hub
    added or removed without a regen fails here.
    """
    path = _WIKI / f"{dept}.md"
    expected = _SKILLS[dept]
    found = [
        (line, m) for line, body in _numbered_lines(path)
        if (m := re.match(r"\*\*Skills\*\*\s*\((\d+)(?:\s*[—-]\s*(\d+)\s+sub-skills)?", body))
    ]
    assert found, f"{path.relative_to(_ROOT)} lost its '**Skills** (N ...)' list header"
    errors = []
    for line, m in found:
        if int(m.group(1)) != expected:
            errors.append(_fail(path, line, int(m.group(1)), expected, "skills"))
        if m.group(2) and int(m.group(2)) != expected - 1:
            errors.append(
                _fail(path, line, int(m.group(2)), expected - 1, "sub-skills")
            )
    assert not errors, "\n  ".join(["skills list header drift:", *errors])


@pytest.mark.parametrize("dept", _DEPTS)
def test_departments_index_row_carries_canonical_counts(dept: str):
    """The `| [Name](dept.md) | prefix | lead | Agents | Skills | ... |` row."""
    path = _WIKI / "README.md"
    row = next(
        ((line, body) for line, body in _numbered_lines(path)
         if body.startswith("| [") and f"]({dept}.md)" in body),
        None,
    )
    assert row is not None, (
        f"wiki/04-Departments/README.md has no index row linking {dept}.md"
    )
    line, body = row
    cells = [c.strip() for c in body.strip().strip("|").split("|")]
    assert len(cells) == 6, f"unexpected index row shape at line {line}: {body!r}"
    agents, skills = int(cells[3]), int(cells[4])
    errors = []
    if agents != _AGENTS[dept]:
        errors.append(_fail(path, line, agents, _AGENTS[dept], "agents"))
    if skills != _SKILLS[dept]:
        errors.append(_fail(path, line, skills, _SKILLS[dept], "skills"))
    assert not errors, "\n  ".join(["departments index drift:", *errors])


def test_per_department_counts_reconcile_with_the_headline_totals():
    """The breakdown must sum to what the headline locks already assert."""
    stats = _ds.gather(_ROOT)
    assert sum(_SKILLS.values()) == stats["skills"]["departments"]
    assert sum(_AGENTS.values()) == stats["agents"]["files"]
