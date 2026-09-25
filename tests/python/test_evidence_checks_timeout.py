"""Issue #570: a tests check killed at its timeout is a FAILURE.

The engine used to report a timeout as ``passed=None``; ``_derive_overall``
then let any other passing check carry ``overall`` to "pass", so a hung
suite could clear the Quality Gate. Every test here drives a REAL child
process that sleeps past a 1 s timeout: no subprocess mock stands between
the engine and the kill.
"""

from __future__ import annotations

import functools
import json
import stat
import sys
from pathlib import Path

import pytest

from core.governance import evidence_checks
from core.governance.evidence_checks import (
    CheckResult,
    EvidenceReport,
    run_evidence_checks,
)

_SLEEP = f"{sys.executable} -c 'import time; time.sleep(5)'"
_PASS = f"{sys.executable} -c 'raise SystemExit(0)'"


def _result(report: EvidenceReport, check: str) -> CheckResult:
    return next(r for r in report.results if r.check == check)


def _fake_venv_pytest(project: Path, body: str) -> None:
    """A project-venv ``pytest`` the final-gate path resolves first."""
    (project / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    script = project / ".venv" / "bin" / "pytest"
    script.parent.mkdir(parents=True)
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)


def _passing_lint(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lint check that PASSES, so only the tests row can fail overall."""
    def lint(*_args: object) -> CheckResult:
        return CheckResult(
            check="lint", ran=True, passed=True, command="lint",
            exit_code=0, summary="clean",
        )
    monkeypatch.setitem(evidence_checks._CHECK_DISPATCH, "lint", lint)


def test_pinned_command_timeout_fails_the_check_and_the_overall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _passing_lint(monkeypatch)
    report = run_evidence_checks(
        tmp_path, checks=["lint", "tests"], test_command=_SLEEP, timeout=1,
    )
    tests = _result(report, "tests")
    assert (tests.ran, tests.passed, tests.exit_code) == (True, False, None)
    assert tests.summary == "timed out after 1 s"
    assert report.overall == "fail"


def test_final_gate_timeout_fails_the_overall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # --final-gate ignores the pinned command and runs the project suite.
    _fake_venv_pytest(tmp_path, "sleep 5")
    _passing_lint(monkeypatch)
    report = run_evidence_checks(
        tmp_path, checks=["lint", "tests"], test_command=_PASS,
        timeout=1, final_gate=True,
    )
    tests = _result(report, "tests")
    assert tests.passed is False
    assert tests.summary == "timed out after 1 s"
    assert "tests(project-venv)" in tests.command
    assert report.overall == "fail"


def test_final_gate_cli_exits_1_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fake_venv_pytest(tmp_path, "sleep 5")
    monkeypatch.setattr(
        evidence_checks, "run_evidence_checks",
        functools.partial(run_evidence_checks, timeout=1),
    )
    code = evidence_checks.main([
        str(tmp_path), "--checks", "tests", "--changed-files", "",
        "--final-gate", "--json",
    ])
    report = json.loads(capsys.readouterr().out)
    assert code == 1
    assert report["overall"] == "fail"
    assert report["results"][0]["summary"] == "timed out after 1 s"


def test_pinned_command_that_finishes_still_passes(tmp_path: Path) -> None:
    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command=_PASS, timeout=30,
    )
    assert _result(report, "tests").passed is True
    assert report.overall == "pass"


def test_scoped_mapping_path_is_unchanged_when_it_finishes(tmp_path: Path) -> None:
    _fake_venv_pytest(tmp_path, 'echo "1 passed $*"')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text("", encoding="utf-8")
    (tmp_path / "mod.py").write_text("", encoding="utf-8")
    report = run_evidence_checks(
        tmp_path, changed_files=["mod.py"], checks=["tests"], timeout=30,
    )
    tests = _result(report, "tests")
    assert tests.passed is True
    assert "diff-scoped" in tests.command
    assert "tests/test_mod.py" in tests.summary


def test_a_timeout_is_never_stored_as_a_reusable_receipt(tmp_path: Path) -> None:
    killed = evidence_checks._timed_out("tests", "pytest", 1)
    evidence_checks._store_tests_receipt(tmp_path, "key", killed)
    assert not evidence_checks._tests_receipt_path(tmp_path).exists()


def test_a_conclusive_failure_is_still_stored(tmp_path: Path) -> None:
    failed = CheckResult(
        check="tests", ran=True, passed=False, command="pytest",
        exit_code=1, summary="1 failed",
    )
    evidence_checks._store_tests_receipt(tmp_path, "key", failed)
    assert evidence_checks._tests_receipt_path(tmp_path).exists()


def test_project_wide_typecheck_timeout_is_reported_and_never_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The advisory keyed its timeout branch on passed=None; with a timeout
    # now a FAIL it must still say "did not finish" and must not cache the
    # kill as the HEAD's debt number.
    monkeypatch.setattr(evidence_checks, "_head_sha", lambda _p: "h" * 40)
    sleeper = [sys.executable, "-c", "import time; time.sleep(5)"]
    note = evidence_checks._project_wide_advisory(tmp_path, sleeper, 1)
    assert note.endswith("did not finish (timeout)")
    assert evidence_checks._cached_advisory(tmp_path, "h" * 40) is None


def test_project_wide_typecheck_that_finishes_is_cached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evidence_checks, "_head_sha", lambda _p: "h" * 40)
    clean = [sys.executable, "-c", "raise SystemExit(0)"]
    note = evidence_checks._project_wide_advisory(tmp_path, clean, 30)
    assert note.endswith("clean")
    assert evidence_checks._cached_advisory(tmp_path, "h" * 40) == f"{note} [cached]"
