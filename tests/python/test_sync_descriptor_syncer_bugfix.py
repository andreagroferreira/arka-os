"""Regression tests for the scalar-stack crash fixed in v2.16.1."""

from __future__ import annotations

from pathlib import Path

from core.sync.descriptor_syncer import sync_descriptor
from core.sync.schema import Project


def _write_scalar_stack_descriptor(tmp_path: Path, project_path: Path) -> Path:
    desc = tmp_path / "proj.md"
    desc.write_text(
        "---\n"
        f"name: proj\n"
        f"path: {project_path}\n"
        "status: active\n"
        "stack: Python 3.8+ (stdlib only)\n"
        "---\n"
        "# proj\n"
    )
    return desc


def test_sync_descriptor_does_not_crash_on_scalar_stack(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    desc_path = _write_scalar_stack_descriptor(tmp_path, project_dir)

    project = Project(
        path=str(project_dir),
        name="proj",
        stack=["python"],
        descriptor_path=str(desc_path),
    )

    result = sync_descriptor(project)

    assert result.status != "error", f"Expected non-error, got: {result.error}"


def test_sync_descriptor_scalar_stack_gets_normalized_to_list(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    desc_path = _write_scalar_stack_descriptor(tmp_path, project_dir)

    project = Project(
        path=str(project_dir),
        name="proj",
        stack=["python"],
        descriptor_path=str(desc_path),
    )

    sync_descriptor(project)

    import yaml

    text = desc_path.read_text()
    raw_fm = text.split("---", 2)[1]
    fm = yaml.safe_load(raw_fm)
    assert isinstance(fm["stack"], list), "stack must be coerced to a list"


def test_normalize_stack_item_handles_whitespace_only(tmp_path: Path) -> None:
    from core.sync.descriptor_syncer import _normalize_stack_item

    assert _normalize_stack_item(" ") == ""
    assert _normalize_stack_item("") == ""
    assert _normalize_stack_item("\t\n") == ""
    assert _normalize_stack_item("Python 3.8") == "python"
