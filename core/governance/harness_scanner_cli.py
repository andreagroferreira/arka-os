"""`npx arkaos shield` — the operator-facing surface of the harness scanner.

Two roots matter and both are scanned by default: the user config
(``~/.claude``) and the project the operator is standing in. Splitting
them would be a footgun — the MCP servers that run with the agent's
permissions usually live in the project's ``.mcp.json``, while the
permissions themselves live in the user settings. A tool that reports a
clean bill of health because it only looked at one of them is worse than
no tool.

Exit codes: 0 = grade A/B, 1 = grade C/D, 2 = grade F or a CRITICAL
finding. CI can gate on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.governance.harness_scanner import (
    PENALTY,
    Finding,
    ScanReport,
    Severity,
    scan,
)

_ICON = {
    Severity.CRITICAL: "✗",
    Severity.HIGH: "✗",
    Severity.MEDIUM: "⚠",
    Severity.LOW: "·",
}


def merge(reports: list[ScanReport]) -> ScanReport:
    """One grade for the operator, not one per file they must add up."""
    merged = ScanReport(root=reports[0].root if reports else Path("."))
    for report in reports:
        merged.files_scanned += report.files_scanned
        for finding in report.findings:
            merged.findings.append(_qualify(finding, report.root))
    merged.findings.sort(key=lambda f: (-PENALTY[f.severity], f.rule))
    return merged


def _qualify(finding: Finding, root: Path) -> Finding:
    """Name the root in `where` so two scans cannot be confused."""
    return Finding(
        rule=finding.rule,
        severity=finding.severity,
        where=f"{root}/{finding.where}",
        detail=finding.detail,
        fix=finding.fix,
    )


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def render(report: ScanReport) -> str:
    scanned = _plural(report.files_scanned, "config file")
    lines = ["", f"  ArkaOS Shield — {scanned} scanned", ""]
    if not report.findings:
        lines += [f"  Grade {report.grade} ({report.score}/100) — nothing "
                  f"to report.", ""]
        return "\n".join(lines)
    for severity in Severity:
        found = report.by_severity(severity)
        if not found:
            continue
        lines.append(f"  {severity.value.upper()}")
        for finding in found:
            lines.append(f"    {_ICON[severity]} {finding.rule}  "
                         f"({finding.where})")
            lines.append(f"      {finding.detail}")
            lines.append(f"      fix: {finding.fix}")
        lines.append("")
    summary = _plural(len(report.findings), "finding")
    lines += [f"  Grade {report.grade} ({report.score}/100) — {summary}.", ""]
    return "\n".join(lines)


def exit_code(report: ScanReport) -> int:
    # grade already collapses to F on any CRITICAL, so the letter is the
    # single source of the exit contract.
    if report.grade == "F":
        return 2
    return 1 if report.grade in ("C", "D") else 0


def _roots(args: argparse.Namespace) -> list[Path]:
    if args.path:
        return [Path(p).expanduser() for p in args.path]
    return [Path.home() / ".claude", Path.cwd()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arkaos shield",
        description=(
            "Scan the agent harness configuration for vulnerabilities: "
            "over-permissive allow rules, secrets in config, hook command "
            "injection, unpinned MCP servers, prompt injection in "
            "instruction files."
        ),
        epilog="Exit: 0 = A/B, 1 = C/D, 2 = F or any CRITICAL finding.",
    )
    parser.add_argument(
        "path", nargs="*",
        help="Config roots to scan. Default: ~/.claude and the cwd.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Machine-readable output.",
    )
    args = parser.parse_args(argv)

    report = merge([scan(root) for root in _roots(args) if root.is_dir()])
    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render(report))
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
