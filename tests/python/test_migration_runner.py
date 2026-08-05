"""Tests for core.sync.migration_runner — propose-only codemods."""

from __future__ import annotations

from pathlib import Path

import yaml

from core.sync.migration_runner import (
    load_migrations,
    pending_migrations,
    run_migrations,
    scan_project,
)
from core.sync.schema import MigrationSpec, Project

SPEC = MigrationSpec(
    name="arka-py-shim",
    added_in="5.10.0",
    description="bare `python -m core` predates the arka-py shim",
    detect=r"\bpython -m core\b",
    paths=["**/*.md"],
    replace="~/.arkaos/bin/arka-py -m core",
    guidance="Use the shim so the pinned venv is honoured.",
)


def _project(tmp_path: Path, name: str = "demo") -> Project:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    return Project(path=str(root), name=name)


# ---------------------------------------------------------------------------
# Version gating
# ---------------------------------------------------------------------------


def test_only_migrations_newer_than_last_sync_run() -> None:
    old = SPEC.model_copy(update={"name": "old", "added_in": "5.0.0"})

    selected = pending_migrations([SPEC, old], "5.9.0", is_first_sync=False)

    assert [s.name for s in selected] == ["arka-py-shim"]


def test_first_sync_runs_no_migrations() -> None:
    assert pending_migrations([SPEC], "pending-sync", is_first_sync=True) == []


def test_unparseable_baseline_selects_nothing() -> None:
    """`unknown` must not be guessed into a version comparison."""
    assert pending_migrations([SPEC], "unknown", is_first_sync=False) == []


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def test_scan_finds_pattern_and_proposes_replacement(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (Path(project.path) / "README.md").write_text(
        "Run `python -m core.sync.engine` to sync.\n", encoding="utf-8"
    )

    hits, truncated = scan_project(project, SPEC)

    assert not truncated
    assert len(hits) == 1
    assert hits[0].line == 1
    assert "python -m core" in hits[0].excerpt
    assert "~/.arkaos/bin/arka-py -m core" in (hits[0].proposed or "")


def test_scan_skips_vendored_trees(tmp_path: Path) -> None:
    project = _project(tmp_path)
    vendored = Path(project.path) / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    (vendored / "README.md").write_text("python -m core\n", encoding="utf-8")

    hits, _ = scan_project(project, SPEC)

    assert hits == []


def test_scan_without_replacement_reports_detection_only(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (Path(project.path) / "a.md").write_text("python -m core\n", encoding="utf-8")
    spec = SPEC.model_copy(update={"replace": None})

    hits, _ = scan_project(project, spec)

    assert hits[0].proposed is None


def test_hit_cap_is_reported_not_silent(tmp_path: Path) -> None:
    project = _project(tmp_path)
    for i in range(30):
        (Path(project.path) / f"f{i}.md").write_text("python -m core\n", encoding="utf-8")

    hits, truncated = scan_project(project, SPEC)

    assert truncated is True
    assert len(hits) == 20


# ---------------------------------------------------------------------------
# Running — propose only
# ---------------------------------------------------------------------------


def test_run_writes_proposal_and_never_touches_project_files(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Path(project.path) / "README.md"
    original = "Run `python -m core.sync.engine`.\n"
    source.write_text(original, encoding="utf-8")
    proposals = tmp_path / "proposals"

    result = run_migrations([project], [SPEC], proposals, "5.10.0")

    assert source.read_text(encoding="utf-8") == original
    assert result.proposal_path is not None
    body = Path(result.proposal_path).read_text(encoding="utf-8")
    assert "arka-py-shim" in body
    assert "Use the shim so the pinned venv is honoured." in body
    assert "proposed:" in body
    assert "Nothing here has been applied" in body


def test_run_with_no_hits_writes_no_proposal(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (Path(project.path) / "README.md").write_text("all good\n", encoding="utf-8")
    proposals = tmp_path / "proposals"

    result = run_migrations([project], [SPEC], proposals, "5.10.0")

    assert result.hits == []
    assert result.proposal_path is None
    assert not proposals.exists()


def test_run_with_no_specs_is_a_noop(tmp_path: Path) -> None:
    result = run_migrations([_project(tmp_path)], [], tmp_path / "p", "5.10.0")

    assert result.migrations_run == []
    assert result.hits == []


def test_missing_project_path_does_not_raise(tmp_path: Path) -> None:
    ghost = Project(path=str(tmp_path / "gone"), name="ghost")

    hits, truncated = scan_project(ghost, SPEC)

    assert hits == []
    assert not truncated


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_load_migrations_from_yaml(tmp_path: Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "shim.yaml").write_text(
        yaml.safe_dump(SPEC.model_dump()), encoding="utf-8"
    )

    loaded = load_migrations(d)

    assert [s.name for s in loaded] == ["arka-py-shim"]


def test_load_migrations_missing_dir_is_empty(tmp_path: Path) -> None:
    assert load_migrations(tmp_path / "nope") == []
