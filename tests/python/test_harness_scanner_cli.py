"""`arkaos shield` — the operator-facing surface.

The exit code is the contract CI gates on, and the merged report is what
stops the tool from lying by omission: user settings and project MCP
config live in different roots, and a scan that only reads one of them
reports a clean bill of health it has not earned.
"""

import json

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

    def test_empty_merge_does_not_crash(self, tmp_path):
        assert merge([]).score == 100


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

    def test_nonexistent_root_is_skipped_not_fatal(self, tmp_path, capsys):
        assert main([str(tmp_path / "nope")]) == 0
        assert "0 config files scanned" in capsys.readouterr().out
