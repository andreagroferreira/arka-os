"""Tests for scripts/migrate_skills_kb_first.py (PR-3 compact-pointer mode).

All destructive operations run on tmp_path fixtures only — the module's
path-independent helpers are exercised directly.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "migrate_skills_kb_first.py"

_spec = importlib.util.spec_from_file_location("kb_first_lock", _SCRIPT)
_mig = importlib.util.module_from_spec(_spec)
# dataclasses on py3.13 resolve cls.__module__ via sys.modules — register
# before exec or @dataclass raises AttributeError on NoneType.
sys.modules["kb_first_lock"] = _mig
_spec.loader.exec_module(_mig)

_OLD_BLOCK = f"""{_mig.BEGIN_DELIM}
## KB-First Research (non-negotiable)

Before any external research (Context7, WebSearch, WebFetch, Firecrawl):

1. Call `mcp__obsidian__search_notes` on the query first.
{_mig.END_DELIM}
"""


def _skill(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "SKILL.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_injects_compact_block_when_external_ref(tmp_path: Path):
    path = _skill(tmp_path, "---\nname: x\n---\n\n# X\n\nUses WebSearch.\n")
    result = _mig._process_one(path)
    assert result.status == "migrated"
    text = path.read_text(encoding="utf-8")
    assert _mig.BEGIN_DELIM in text
    assert "KB-first:" in text
    assert "Full doctrine: `arka/SKILL.md`" in text


def test_skips_file_without_external_ref(tmp_path: Path):
    path = _skill(tmp_path, "---\nname: x\n---\n\n# X\n\nNo tools here.\n")
    before = path.read_text(encoding="utf-8")
    result = _mig._process_one(path)
    assert result.status == "skipped-no-external-ref"
    assert path.read_text(encoding="utf-8") == before


def test_compacts_old_form_block(tmp_path: Path):
    path = _skill(
        tmp_path,
        f"---\nname: x\n---\n\n{_OLD_BLOCK}\n# X\n\nUses WebFetch.\n",
    )
    result = _mig._process_one(path)
    assert result.status == "compacted"
    text = path.read_text(encoding="utf-8")
    assert "## KB-First Research (non-negotiable)" not in text
    assert "KB-first:" in text
    assert text.count(_mig.BEGIN_DELIM) == 1


def test_compact_is_idempotent_fixed_point(tmp_path: Path):
    path = _skill(
        tmp_path,
        f"---\nname: x\n---\n\n{_OLD_BLOCK}\n# X\n\nUses WebFetch.\n",
    )
    assert _mig._process_one(path).status == "compacted"
    once = path.read_text(encoding="utf-8")
    assert _mig._process_one(path).status == "skipped-already-compact"
    assert path.read_text(encoding="utf-8") == once


def test_body_outside_block_is_preserved(tmp_path: Path):
    body_tail = "# X\n\n## Custom Section\n\nUses firecrawl heavily.\n"
    path = _skill(tmp_path, f"---\nname: x\n---\n\n{_OLD_BLOCK}\n{body_tail}")
    _mig._process_one(path)
    assert body_tail in path.read_text(encoding="utf-8")


def test_discover_excludes_canonical_home(monkeypatch, tmp_path: Path):
    arka = tmp_path / "arka"
    (arka / "skills" / "demo").mkdir(parents=True)
    canonical = arka / "SKILL.md"
    canonical.write_text("# home\nWebSearch\n", encoding="utf-8")
    other = arka / "skills" / "demo" / "SKILL.md"
    other.write_text("# demo\nWebSearch\n", encoding="utf-8")
    monkeypatch.setattr(_mig, "SCAN_ROOTS", [arka])
    monkeypatch.setattr(_mig, "EXCLUDE_FILES", {canonical})
    found = _mig._discover_skill_files()
    assert other in found
    assert canonical not in found


def test_inject_after_h1_when_no_frontmatter(tmp_path: Path):
    path = _skill(tmp_path, "# Título\n\nUses WebSearch.\n")
    assert _mig._process_one(path).status == "migrated"
    text = path.read_text(encoding="utf-8")
    assert text.index("# Título") < text.index(_mig.BEGIN_DELIM)


def test_inject_prepends_when_no_anchor(tmp_path: Path):
    path = _skill(tmp_path, "Uses firecrawl.\n")
    assert _mig._process_one(path).status == "migrated"
    assert path.read_text(encoding="utf-8").startswith(_mig.BEGIN_DELIM)


def _mini_tree(tmp_path: Path) -> Path:
    root = tmp_path / "arka" / "skills"
    for name, body in (
        ("old", f"---\nname: old\n---\n\n{_OLD_BLOCK}\n# O\nWebFetch\n"),
        ("new", "---\nname: new\n---\n\n# N\nWebSearch\n"),
        ("plain", "---\nname: plain\n---\n\n# P\nno tools\n"),
    ):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(body, encoding="utf-8")
    return tmp_path / "arka"


def test_run_dry_run_reports_without_writing(monkeypatch, tmp_path: Path):
    scan = _mini_tree(tmp_path)
    monkeypatch.setattr(_mig, "SCAN_ROOTS", [scan])
    monkeypatch.setattr(_mig, "EXCLUDE_FILES", set())
    before = {
        p: p.read_text(encoding="utf-8") for p in scan.rglob("SKILL.md")
    }
    statuses = sorted(r.status for r in _mig.run(dry_run=True))
    assert statuses == [
        "skipped-no-external-ref", "would-compact", "would-migrate",
    ]
    for p, text in before.items():
        assert p.read_text(encoding="utf-8") == text


def test_run_real_applies_and_is_idempotent(monkeypatch, tmp_path: Path):
    scan = _mini_tree(tmp_path)
    monkeypatch.setattr(_mig, "SCAN_ROOTS", [scan])
    monkeypatch.setattr(_mig, "EXCLUDE_FILES", set())
    first = sorted(r.status for r in _mig.run())
    assert first == ["compacted", "migrated", "skipped-no-external-ref"]
    second = sorted(r.status for r in _mig.run())
    assert second == [
        "skipped-already-compact", "skipped-already-compact",
        "skipped-no-external-ref",
    ]


def test_summarise_prints_counts_and_errors(capsys, tmp_path: Path):
    results = [
        _mig.FileResult(tmp_path / "a", "compacted"),
        _mig.FileResult(tmp_path / "b", "compacted"),
        _mig.FileResult(tmp_path / "c", "error", "disk on fire"),
    ]
    _mig._summarise(results)
    out = capsys.readouterr().out
    assert "Scanned 3 SKILL.md files" in out
    assert "compacted" in out and "2" in out
    assert "disk on fire" in out


def test_unreadable_file_reports_error(tmp_path: Path):
    missing = tmp_path / "nope" / "SKILL.md"
    result = _mig._process_one(missing)
    assert result.status == "error"
    assert result.detail


def test_pointer_has_no_non_negotiable_marker():
    # The prompt-lint ratchet counts the marker case-insensitively; the
    # ~200x pointer must not carry it.
    assert "non-negotiable" not in _mig.PREFIX_BLOCK.lower()
