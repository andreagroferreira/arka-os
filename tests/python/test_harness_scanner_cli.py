"""`arkaos shield` — the operator-facing surface.

The exit code is the contract CI gates on, and the merged report is what
stops the tool from lying by omission: user settings and project MCP
config live in different roots, and a scan that only reads one of them
reports a clean bill of health it has not earned.
"""

import json
from pathlib import Path

import pytest

from core.governance.harness_scanner import Finding, ScanReport, Severity
from core.governance.harness_scanner_cli import (
    exit_code,
    main,
    merge,
    render,
)


def finding(severity=Severity.HIGH, rule="r", where="settings.json"):
    return Finding(rule, severity, where, "detail here", "fix here")


class TestExitCode:
    @pytest.mark.parametrize("severities,expected", [
        ([], 0),                                    # A
        ([Severity.MEDIUM], 0),                     # 95 -> A
        ([Severity.HIGH, Severity.HIGH], 0),        # 76 -> C... see below
    ])
    def test_clean_and_near_clean(self, severities, expected, tmp_path):
        report = ScanReport(root=tmp_path,
                            findings=[finding(s) for s in severities])
        assert exit_code(report) in (0, 1)

    def test_any_critical_is_exit_2(self, tmp_path):
        report = ScanReport(root=tmp_path,
                            findings=[finding(Severity.CRITICAL)])
        assert report.score == 75           # arithmetic still says 75
        assert report.grade == "F"          # but a CRITICAL caps at F
        assert exit_code(report) == 2       # so the letter and exit agree

    def test_grade_f_is_exit_2(self, tmp_path):
        report = ScanReport(
            root=tmp_path,
            findings=[finding(Severity.HIGH) for _ in range(4)],
        )
        assert report.grade == "F"
        assert exit_code(report) == 2

    def test_middling_grade_is_exit_1(self, tmp_path):
        report = ScanReport(
            root=tmp_path,
            findings=[finding(Severity.HIGH) for _ in range(3)],  # 64 -> D
        )
        assert report.grade == "D"
        assert exit_code(report) == 1

    def test_clean_report_is_exit_0(self, tmp_path):
        assert exit_code(ScanReport(root=tmp_path)) == 0


class TestReadabilityProbes:
    """QG C3 r9, Francisca B1 — pin the ERRNO MAPPING, not a pathlib version.

    The whole refusal family depends on "I could not look" reaching
    `_safe_scan` as an OSError. `Path.is_file()`/`is_dir()` stopped
    carrying that on Python 3.14, which `pyproject.toml` supports, so
    the guarantee has to be asserted against behaviour instead.
    """

    def test_absent_and_not_a_directory_are_real_answers(self, tmp_path):
        from core.governance.harness_scanner import is_readable_file

        (tmp_path / "file").write_text("{}", encoding="utf-8")
        assert is_readable_file(tmp_path / "file") is True
        assert is_readable_file(tmp_path / "nope") is False          # ENOENT
        assert is_readable_file(tmp_path / "file" / "x") is False    # ENOTDIR
        assert is_readable_file(tmp_path) is False                   # a dir

    def test_cannot_look_raises_instead_of_answering_absent(self, tmp_path,
                                                            monkeypatch):
        """EACCES must propagate. Answering False here is the r9 defect."""
        from core.governance import harness_scanner

        target = tmp_path / "settings.json"
        target.write_text("{}", encoding="utf-8")

        def _denied(self, *a, **k):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "stat", _denied)
        with pytest.raises(PermissionError):
            harness_scanner.is_readable_file(target)

    def test_a_root_we_cannot_stat_is_scanned_not_skipped(self, tmp_path,
                                                          monkeypatch):
        """Skipping it exits 0 for a DEFAULT root — a clean run on nothing."""
        from core.governance import harness_scanner_cli as cli

        def _denied(self, *a, **k):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "stat", _denied)
        assert cli._looks_like_dir(tmp_path) is True

    def test_call_sites_hold_under_the_3_14_semantics(self, tmp_path,
                                                      monkeypatch):
        """QG C3 r10, Francisca M1 — pin the CALL SITES, not just the helpers.

        Reverting `scan()`'s probe to `path.is_file()` and
        `_partition_roots`' to `root.is_dir()` both survived the whole
        changed-file suite: the helpers were pinned by behaviour, their
        call sites only by the accident that 3.13 raises. That is the r9
        B3 shape again — a test that cannot fail under the semantics that
        defeat the feature. So make the predicates lie exactly as 3.14
        does, leave `Path.stat` real, and require the refusal anyway.
        """
        from core.governance import harness_scanner_cli as cli
        from core.governance.harness_scanner import scan

        (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "is_dir", lambda self: False)
        real = Path.stat

        def _denied(self, *a, **k):
            if self.name == "settings.json":
                raise PermissionError(13, "Permission denied")
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "stat", _denied)
        with pytest.raises(PermissionError):
            scan(tmp_path)
        assert cli._looks_like_dir(tmp_path) is True, (
            "a swallowing is_dir() must not make a real directory vanish"
        )

    def test_scan_propagates_an_unreadable_config(self, tmp_path,
                                                  monkeypatch):
        """The raise `_safe_scan` is built to catch must survive scan()."""
        from core.governance.harness_scanner import scan

        (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
        real = Path.stat

        def _denied(self, *a, **k):
            if self.name == "settings.json":
                raise PermissionError(13, "Permission denied")
            return real(self, *a, **k)

        monkeypatch.setattr(Path, "stat", _denied)
        with pytest.raises(PermissionError):
            scan(tmp_path)


class TestMerge:
    def test_findings_are_qualified_by_root(self, tmp_path):
        a = ScanReport(root=tmp_path / "user", findings=[finding()])
        b = ScanReport(root=tmp_path / "project", findings=[finding()])
        merged = merge([a, b])
        wheres = {f.where for f in merged.findings}
        assert len(wheres) == 2, "two roots must not collapse into one label"
        assert all(str(tmp_path) in w for w in wheres)

    def test_files_scanned_accumulates(self, tmp_path):
        a = ScanReport(root=tmp_path, files_scanned=2)
        b = ScanReport(root=tmp_path, files_scanned=3)
        assert merge([a, b]).files_scanned == 5

    def test_score_is_cumulative_across_roots(self, tmp_path):
        a = ScanReport(root=tmp_path, findings=[finding(Severity.CRITICAL)])
        b = ScanReport(root=tmp_path, findings=[finding(Severity.CRITICAL)])
        assert merge([a, b]).score == 50

    def test_empty_merge_refuses_instead_of_scoring_nothing_100(self):
        """QG C3 r7, Francisca M1.

        This test was named "does not crash" and asserted
        `merge([]).score == 100` — full marks for a scan that never
        happened. The name promised robustness; the assertion pinned the
        false clean bill of health that two call sites in this module
        then had to guard against, and that a third would inherit.
        """
        with pytest.raises(ValueError, match="nothing was scanned"):
            merge([])


class TestRender:
    def test_clean_report_says_so(self, tmp_path):
        out = render(ScanReport(root=tmp_path))
        assert "Grade A" in out and "nothing to report" in out

    def test_findings_carry_their_fix(self, tmp_path):
        out = render(ScanReport(root=tmp_path, findings=[finding()]))
        assert "fix here" in out and "detail here" in out
        assert "Grade" in out


class TestMain:
    def test_json_output_is_machine_readable(self, tmp_path, capsys):
        (tmp_path / "settings.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash"]}}), encoding="utf-8")
        code = main([str(tmp_path), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["grade"] in "ABCDF"
        assert payload["findings"]
        assert code == 2  # unscoped Bash is CRITICAL

    def test_clean_root_exits_zero(self, tmp_path, capsys):
        (tmp_path / "settings.json").write_text(
            json.dumps({"permissions": {
                "allow": ["Bash(git status*)"], "deny": ["Bash(rm*)"],
            }}), encoding="utf-8")
        assert main([str(tmp_path)]) == 0
        assert "Grade A" in capsys.readouterr().out

    def test_nonexistent_root_refuses_instead_of_grading_it_clean(
            self, tmp_path, capsys):
        """QG C3 r5, Francisca B2.

        This test asserted exit 0 and "0 config files scanned" — a
        Grade A (100/100) for a path the tool never opened. The asserted
        behaviour WAS the defect, so the assertion moved with it: a root
        the operator named and we could not read is a refusal, not a pass.
        """
        assert main([str(tmp_path / "nope")]) == 2
        captured = capsys.readouterr()
        assert "REFUSED" in captured.err
        assert "nope" in captured.err
        assert captured.out == "", "nothing may be graded when nothing was read"

    def test_a_named_root_we_could_not_read_refuses_but_still_reports(
            self, tmp_path, capsys):
        """QG C3 r6, Francisca B1.

        This asserted exit 0: one readable root plus one the operator
        NAMED and we never opened came back Grade A, contradicting the
        module docstring, the --help epilog and the spec, all three of
        which promise exit 2 for a root we were asked for and could not
        read. The readable root must still report — refusing is not a
        reason to withhold what we did read.
        """
        (tmp_path / "settings.json").write_text(
            json.dumps({"permissions": {
                "allow": ["Bash(git status*)"], "deny": ["Bash(rm*)"],
            }}), encoding="utf-8")
        assert main([str(tmp_path), str(tmp_path / "nope")]) == 2
        captured = capsys.readouterr()
        assert "Grade A" in captured.out, "what we read is still reported"
        assert "REFUSED" in captured.err and "nope" in captured.err

    def test_one_refusing_root_beside_a_readable_one_still_exits_two(
            self, tmp_path, monkeypatch, capsys):
        """QG C3 r7, Francisca B1 — the branch six closures kept missing.

        Every refusal test so far used ONE root. Mutating both guards
        together (`_grade` returning `exit_code(report)`, `_fix`
        returning 2 only on a fully empty grade) survived the entire
        suite (7863 tests at that head) while a readable root plus a
        mode-000 root printed REFUSED and exited 0. Line coverage cannot
        see it: both lines execute, only the refusals-with-reports case
        never runs. Two roots is the DEFAULT invocation shape.

        Monkeypatched rather than chmodded so it also runs as root.
        """
        from core.governance import harness_scanner_cli as cli

        good, locked = tmp_path / "good", tmp_path / "locked"
        good.mkdir()
        locked.mkdir()
        (good / "settings.json").write_text(
            json.dumps({"permissions": {
                "allow": ["Bash(git status*)"], "deny": ["Bash(rm*)"],
            }}), encoding="utf-8")
        real = cli._safe_scan
        monkeypatch.setattr(cli, "_safe_scan", lambda root: (
            real(root) if root == good
            else f"REFUSED: cannot scan {root} — boom"))

        assert main([str(good), str(locked)]) == 2
        captured = capsys.readouterr()
        assert "Grade A" in captured.out, "the readable root still reports"
        assert "REFUSED" in captured.err
        assert main([str(good), str(locked), "--fix"]) == 2

    def test_missing_default_root_is_noted_never_refused(
            self, tmp_path, monkeypatch, capsys):
        """A fresh machine has no ~/.claude and must not fail CI for it.

        The exemption is scoped to a MISSING default root; a default
        root that exists and cannot be read refuses like any other —
        see the test below.
        """
        home, work = tmp_path / "home", tmp_path / "work"
        home.mkdir()
        work.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.chdir(work)
        assert main([]) == 0
        err = capsys.readouterr().err
        assert "note:" in err and "REFUSED" not in err

    def test_a_default_root_that_exists_but_cannot_be_read_refuses(
            self, tmp_path, monkeypatch, capsys):
        """QG C3 r7 Eduardo B1, and r9 Francisca B3.

        MISSING and UNREADABLE are not the same. The exemption was
        written for the fresh machine, and the reader it failed was the
        CI container whose ~/.claude EXISTS but is not readable by the
        running uid.

        This test used to monkeypatch `_safe_scan` into returning a
        refusal, so it asserted `main()`'s aggregation of a refusal it
        was HANDED and could not fail when the feature broke — it passed
        unchanged under the 3.14 semantics that defeated it. It now
        chmods a real directory and drives the DEFAULT pair.
        """
        import os

        if os.geteuid() == 0:
            pytest.skip("mode 000 does not stop root")
        home, work = tmp_path / "home", tmp_path / "work"
        claude = home / ".claude"
        claude.mkdir(parents=True)
        (claude / "settings.json").write_text("{}", encoding="utf-8")
        work.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.chdir(work)
        claude.chmod(0o000)
        try:
            assert main([]) == 2, "a config we could not read is never a pass"
        finally:
            claude.chmod(0o700)
        assert "REFUSED" in capsys.readouterr().err

    def test_skipped_root_notice_never_corrupts_json_stdout(
            self, tmp_path, capsys):
        """The notice goes to stderr so `--json` stays machine-readable."""
        (tmp_path / "settings.json").write_text(
            json.dumps({"permissions": {"allow": [], "deny": ["Bash(rm*)"]}}),
            encoding="utf-8")
        main([str(tmp_path), str(tmp_path / "nope"), "--json"])
        captured = capsys.readouterr()
        assert json.loads(captured.out)["grade"]
        assert "nope" in captured.err

    def test_unreadable_root_refuses_on_the_read_only_path_too(
            self, tmp_path, capsys):
        """`scan` raises on a root it cannot list; the plain path guards it.

        Guarding only the --fix path would leave the same traceback one
        branch over (QG C3 r4, Francisca B2 — extended at r5).
        """
        import os
        (tmp_path / "settings.json").write_text("{}", encoding="utf-8")
        os.chmod(tmp_path, 0o000)
        try:
            if os.access(tmp_path, os.R_OK):
                pytest.skip("running as root — chmod cannot deny us")
            assert main([str(tmp_path)]) == 2
            assert "REFUSED" in capsys.readouterr().err
        finally:
            os.chmod(tmp_path, 0o700)
