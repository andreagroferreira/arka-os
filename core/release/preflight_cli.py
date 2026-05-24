"""CLI entry for the release preflight gate (PR21 v2.43.0).

Usage:
    python -m core.release.preflight_cli [--expected-npm-user USER]

Exit code: 0 if all blocking checks pass, 1 otherwise. Warnings never
gate the exit code. Output is markdown so it renders cleanly in both
terminal and PR comments.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from core.release.preflight import (
    CheckResult,
    PreflightReport,
    run_preflight,
)


def _glyph(result: CheckResult) -> str:
    if result.passed:
        return "PASS"
    if result.severity == "warning":
        return "WARN"
    return "FAIL"


def _render(report: PreflightReport) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Release Preflight — {today}",
        "",
        "| Check | Status | Notes |",
        "|---|---|---|",
    ]
    for r in report.results:
        notes = r.reason or ""
        if r.remediation and not r.passed:
            notes = f"{notes} | remediation: {r.remediation}"
        lines.append(f"| {r.name} | {_glyph(r)} | {notes} |")
    lines.append("")
    if report.blocking_failures:
        lines.append(f"**BLOCKED — {len(report.blocking_failures)} failure(s).** "
                     "Fix each remediation and rerun before tagging/publishing.")
    elif report.warnings:
        lines.append(f"All blocking checks passed ({len(report.warnings)} "
                     "warning(s) noted, non-blocking).")
    else:
        lines.append("All checks green. Safe to proceed to tag → release → publish.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="arkaos-preflight",
        description="Run release preflight checks. Exit 1 on any blocking failure.",
    )
    parser.add_argument(
        "--expected-npm-user", default=None,
        help="Assert that `npm whoami` returns this user (e.g. wizardingcode).",
    )
    args = parser.parse_args(argv[1:])

    report = run_preflight(expected_npm_user=args.expected_npm_user)
    print(_render(report))
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
