"""Tests for core.sync.migration_runner — propose-only codemods."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from core.sync.migration_runner import (
    _SPEC_TIME_BUDGET_SECONDS,
    compile_specs,
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

    loaded, errors = load_migrations(d)

    assert [s.name for s in loaded] == ["arka-py-shim"]
    assert errors == []


def test_load_migrations_missing_dir_is_empty(tmp_path: Path) -> None:
    assert load_migrations(tmp_path / "nope") == ([], [])


# ---------------------------------------------------------------------------
# Robustness — one bad spec must never abort a sync that already wrote to disk
# ---------------------------------------------------------------------------


def test_malformed_yaml_is_recorded_not_raised(tmp_path: Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "broken.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    (d / "good.yaml").write_text(yaml.safe_dump(SPEC.model_dump()), encoding="utf-8")

    specs, errors = load_migrations(d)

    assert [s.name for s in specs] == ["arka-py-shim"]
    assert any("broken.yaml" in e for e in errors)


def test_incomplete_spec_is_recorded_not_raised(tmp_path: Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    (d / "partial.yaml").write_text("name: only-a-name\n", encoding="utf-8")

    specs, errors = load_migrations(d)

    assert specs == []
    assert any("invalid spec" in e for e in errors)


def test_bad_detect_regex_is_recorded_not_raised(tmp_path: Path) -> None:
    bad = SPEC.model_copy(update={"name": "bad", "detect": "foo("})

    result = run_migrations([_project(tmp_path)], [bad], tmp_path / "p", "5.10.0")

    assert result.hits == []
    assert any("bad pattern" in e for e in result.errors)


def test_bad_replace_backreference_is_recorded_not_raised(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (Path(project.path) / "a.md").write_text("python -m core\n", encoding="utf-8")
    bad = SPEC.model_copy(update={"name": "bad", "replace": r"\9"})

    result = run_migrations([project], [bad], tmp_path / "p", "5.10.0")

    assert result.hits == []
    assert any("bad pattern" in e for e in result.errors)


def test_file_cap_is_reported_not_silent(tmp_path: Path) -> None:
    """The 2000-file cap used to `return` bare, so a partial scan read as complete."""
    project = _project(tmp_path)
    root = Path(project.path)
    for i in range(2010):
        (root / f"f{i:05d}.md").write_text("nothing here\n", encoding="utf-8")

    _, truncated = scan_project(project, SPEC)

    assert truncated is True


def test_overlong_lines_are_skipped(tmp_path: Path) -> None:
    """No regex timeout exists in Python; the only ceiling is subject length."""
    project = _project(tmp_path)
    (Path(project.path) / "min.md").write_text(
        "x" * 5000 + " python -m core\n", encoding="utf-8"
    )

    hits, _ = scan_project(project, SPEC)

    assert hits == []


def test_each_file_is_read_once_for_all_specs(tmp_path: Path, monkeypatch) -> None:
    """Re-globbing and re-reading per spec dominated the run on many projects."""
    project = _project(tmp_path)
    (Path(project.path) / "a.md").write_text("python -m core\n", encoding="utf-8")
    specs = [SPEC.model_copy(update={"name": f"m{i}"}) for i in range(4)]

    reads: list[str] = []
    original = Path.read_text

    def counting_read(self, *args, **kwargs):
        if self.suffix == ".md":
            reads.append(str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read)
    result = run_migrations([project], specs, tmp_path / "p", "5.10.0")

    assert len(result.hits) == 4
    assert len(reads) == 1


# ---------------------------------------------------------------------------
# Catastrophic patterns (QG round 3)
#
# A shape heuristic shipped here with no tests. It refused ordinary patterns
# like `import (\w+)` — `"" in "+*{"` is True — while accepting `(a|a)*`,
# which hangs for over eight seconds on forty characters. The heuristic is
# gone; the wall-clock budget is the control, and it is tested in both
# directions.
# ---------------------------------------------------------------------------

ORDINARY_PATTERNS = [
    r"import (\w+)",
    r"import (\w+)$",
    r"const (\w+)",
    r"(https?://\S+)",
    r"v(\d+\.\d+\.\d+)",
    r"from (\S+) import (\w+)",
    r"(\d{4})+",
    r"(v\d+\.\d+)*",
    r"(x|y)*z",
    r"(ab)+c",
    r"\bpython -m core\b",
    r"^## (.+)$",
    r"\(\d+\)+",
    r"([+*])+",
    r"(a+)+b",
]


@pytest.mark.parametrize("pattern", ORDINARY_PATTERNS)
def test_no_pattern_is_refused_on_shape_alone(pattern: str) -> None:
    """Every valid regex compiles. Only real slowness is acted on."""
    compiled, errors = compile_specs(
        [SPEC.model_copy(update={"detect": pattern, "replace": None})]
    )
    assert errors == []
    assert len(compiled) == 1


# ---------------------------------------------------------------------------
# Containment and crash-safety (QG round 3)
# ---------------------------------------------------------------------------


def test_paths_cannot_escape_the_project_root(tmp_path: Path) -> None:
    """`../**` would read outside the project and copy it into a proposal."""
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.md").write_text(
        "TOKEN placeholder-value\n", encoding="utf-8"
    )
    project = _project(tmp_path, "project")
    (Path(project.path) / "own.md").write_text("nothing\n", encoding="utf-8")
    spec = SPEC.model_copy(update={"detect": "TOKEN", "paths": ["../**/*.md"]})

    result = run_migrations([project], [spec], tmp_path / "out", "5.10.0")

    assert result.hits == []
    assert any("escaped the project root" in e for e in result.errors)


def test_absolute_path_pattern_does_not_abort_the_run(tmp_path: Path) -> None:
    """pathlib raises NotImplementedError, which is not an OSError."""
    project = _project(tmp_path)
    spec = SPEC.model_copy(update={"paths": ["/etc/**/*.md", "**/*.md"]})

    result = run_migrations([project], [spec], tmp_path / "out", "5.10.0")

    assert any("NotImplementedError" in e for e in result.errors)


def test_odd_glob_never_costs_the_other_patterns(tmp_path: Path) -> None:
    """A pattern that matches nothing must not silence the ones that do."""
    project = _project(tmp_path)
    (Path(project.path) / "a.md").write_text("python -m core\n", encoding="utf-8")
    spec = SPEC.model_copy(update={"paths": ["**/[", "**/*.md"]})

    result = run_migrations([project], [spec], tmp_path / "out", "5.10.0")

    assert len(result.hits) == 1


# ---------------------------------------------------------------------------
# Errors must reach the operator (QG round 3: they were dropped at zero hits)
# ---------------------------------------------------------------------------


def test_a_run_that_could_not_scan_still_writes_a_record(tmp_path: Path) -> None:
    """Errors matter most in the run that found nothing."""
    project = _project(tmp_path)
    bad = SPEC.model_copy(update={"name": "bad", "detect": "foo("})

    result = run_migrations([project], [bad], tmp_path / "out", "5.10.0")

    assert result.hits == []
    assert result.proposal_path is not None
    body = Path(result.proposal_path).read_text(encoding="utf-8")
    assert "could not run" in body
    assert "bad" in body


def test_catastrophic_pattern_is_abandoned_not_hung(tmp_path: Path) -> None:
    """An ambiguous alternation passes the shape guard and must still stop."""
    project = _project(tmp_path)
    (Path(project.path) / "x.md").write_text("a" * 40 + "b\n", encoding="utf-8")
    evil = SPEC.model_copy(
        update={"name": "evil", "detect": r"(a|a)*$", "replace": None}
    )

    started = time.monotonic()
    result = run_migrations([project], [evil], tmp_path / "out", "5.10.0")
    elapsed = time.monotonic() - started

    assert elapsed < _SPEC_TIME_BUDGET_SECONDS * 3
    assert any("abandoned" in e or "backtracking" in e for e in result.errors)


# ---------------------------------------------------------------------------
# QG round 4 — class tests, written BEFORE the fixes.
#
# Four rounds produced the same pattern: each fix closed the reported
# instance and left a sibling open. These tests cover the classes.
# ---------------------------------------------------------------------------


def test_budget_expiry_during_glob_abandons_the_scan(tmp_path: Path, monkeypatch) -> None:
    """ScanBudgetError must never be swallowed by a generic handler.

    _glob catches bare Exception; the deadline IS an Exception, and the
    timer is one-shot — swallowed there, the rest of the scan runs with no
    deadline and the error surfaces as a meaningless 'ScanBudgetError' path
    note instead of 'scan abandoned'.
    """
    from core.sync import migration_runner as mr

    project = _project(tmp_path)
    (Path(project.path) / "a.md").write_text("python -m core\n", encoding="utf-8")

    def exploding_glob(self, pattern):
        raise mr.ScanBudgetError

    monkeypatch.setattr(Path, "glob", exploding_glob)
    result = run_migrations([project], [SPEC], tmp_path / "out", "5.10.0")

    assert any("abandoned" in e for e in result.errors)
    assert not any("ScanBudgetError" in e for e in result.errors)


def test_escaped_candidate_does_not_cost_later_candidates(tmp_path: Path) -> None:
    """_take used to return on the first escaped candidate, silently
    abandoning every candidate after it with nothing in truncated."""
    from core.sync.migration_runner import _take

    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.md"
    secret.write_text("python -m core\n", encoding="utf-8")
    root = tmp_path / "project"
    root.mkdir()
    link = root / "a_link.md"
    link.symlink_to(secret)
    real = root / "z_real.md"
    real.write_text("python -m core\n", encoding="utf-8")

    files: list[Path] = []
    errors: list[str] = []
    capped = _take([link, real], root.resolve(), files, set(), errors, "**/*.md")

    assert capped is False
    assert real in files
    assert any("escaped" in e for e in errors)


def test_real_hits_survive_an_escaping_symlink(tmp_path: Path) -> None:
    """End-to-end: one escaping symlink must not cost the real findings."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("python -m core\n", encoding="utf-8")
    project = _project(tmp_path, "project")
    (Path(project.path) / "link.md").symlink_to(outside / "secret.md")
    (Path(project.path) / "real.md").write_text("python -m core\n", encoding="utf-8")

    result = run_migrations([project], [SPEC], tmp_path / "out", "5.10.0")

    assert [Path(h.file).name for h in result.hits] == ["real.md"]
    assert any("escaped" in e for e in result.errors)


def test_load_errors_reach_the_run_record(tmp_path: Path) -> None:
    """Load-time failures used to be folded in AFTER the proposal decision,
    so an all-specs-unreadable run left no record anywhere."""
    result = run_migrations(
        [], [], tmp_path / "out", "5.10.0",
        pre_errors=["broken.yaml: unreadable (ScannerError)"],
    )

    assert result.errors == ["broken.yaml: unreadable (ScannerError)"]
    assert result.proposal_path is not None
