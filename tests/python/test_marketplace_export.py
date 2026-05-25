"""Tests for the marketplace export script (PR51 v2.69.0)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


from marketplace_export import (  # noqa: E402
    EXPORTABLE_SKILLS,
    _convert,
    export_all,
    export_skill,
    write_index,
)


def test_all_ten_skills_declared():
    assert len(EXPORTABLE_SKILLS) == 10
    assert "code-review" in EXPORTABLE_SKILLS
    assert "architecture-design" in EXPORTABLE_SKILLS


def test_convert_strips_kb_first_prefix_block():
    body = (
        "---\nname: dev/code-review\ndescription: x\n"
        "allowed-tools: [Read]\n---\n"
        "<!-- arka:kb-first-prefix begin -->\n"
        "kb-first content\n"
        "<!-- arka:kb-first-prefix end -->\n"
        "\n# Body"
    )
    out = _convert(body)
    assert "kb-first-prefix" not in out
    assert "kb-first content" not in out
    assert "# Body" in out


def test_convert_normalises_name_drops_dev_prefix():
    body = "---\nname: dev/code-review\ndescription: x\n---\nbody"
    assert "name: code-review" in _convert(body)
    assert "name: dev/code-review" not in _convert(body)


def test_convert_keeps_name_unchanged_when_no_prefix():
    body = "---\nname: code-review\ndescription: x\n---\nbody"
    assert "name: code-review" in _convert(body)


def test_convert_normalises_arka_dev_prefix():
    body = "---\nname: arka-dev-spec\ndescription: x\n---\nbody"
    out = _convert(body)
    assert "name: spec" in out
    assert "arka-dev-spec" not in out


def test_convert_normalises_arka_prefix():
    body = "---\nname: arka-runbook\ndescription: x\n---\nbody"
    out = _convert(body)
    assert "name: runbook" in out


def test_convert_drops_allowed_tools_field():
    body = (
        "---\nname: dev/x\ndescription: y\n"
        "allowed-tools: [Read, Write, Edit, Agent]\n---\nbody"
    )
    out = _convert(body)
    assert "allowed-tools" not in out


def test_convert_strips_slash_command_suffix_in_headers():
    body = (
        "---\nname: dev/x\ndescription: y\n---\n"
        "# Code Review — `/dev review <file/pr>`\n"
        "body"
    )
    out = _convert(body)
    assert "/dev review" not in out
    assert "# Code Review" in out


def test_convert_idempotent_on_already_clean_body():
    clean = "---\nname: code-review\ndescription: x\n---\n\n# Body\ncontent"
    assert _convert(clean) == _convert(_convert(clean))


def test_export_skill_creates_output_file(tmp_path, monkeypatch):
    src = tmp_path / "src" / "code-review"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(
        "---\nname: dev/code-review\ndescription: x\n"
        "allowed-tools: [Read]\n---\n# Body",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    import marketplace_export as me
    monkeypatch.setattr(me, "SOURCE_DIR", tmp_path / "src")
    monkeypatch.setattr(me, "EXPORT_DIR", out)
    result = export_skill("code-review")
    assert result.output_path.exists()
    body = result.output_path.read_text(encoding="utf-8")
    assert "name: code-review" in body
    assert "allowed-tools" not in body


def test_export_skill_raises_when_source_missing(tmp_path, monkeypatch):
    import marketplace_export as me
    monkeypatch.setattr(me, "SOURCE_DIR", tmp_path / "no-such-dir")
    monkeypatch.setattr(me, "EXPORT_DIR", tmp_path / "out")
    with pytest.raises(FileNotFoundError):
        export_skill("code-review")


def test_export_all_writes_ten_skills_in_real_tree(tmp_path, monkeypatch):
    out = tmp_path / "out"
    import marketplace_export as me
    monkeypatch.setattr(me, "EXPORT_DIR", out)
    results = export_all()
    assert len(results) == 10
    for r in results:
        assert r.output_path.exists()
        body = r.output_path.read_text(encoding="utf-8")
        # Open-spec compliance gates
        assert "allowed-tools" not in body
        assert "kb-first-prefix" not in body
        assert "name: dev/" not in body


def test_write_index_lists_every_skill(tmp_path, monkeypatch):
    import marketplace_export as me
    monkeypatch.setattr(me, "EXPORT_DIR", tmp_path)
    results = export_all()
    index = write_index(results)
    body = index.read_text(encoding="utf-8")
    for slug in EXPORTABLE_SKILLS:
        assert f"[{slug}]" in body
