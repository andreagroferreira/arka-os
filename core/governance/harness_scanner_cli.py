"""`npx arkaos shield` — the operator-facing surface of the harness scanner.

Two roots matter and both are scanned by default: the user config
(``~/.claude``) and the project the operator is standing in. Splitting
them would be a footgun — the MCP servers that run with the agent's
permissions usually live in the project's ``.mcp.json``, while the
permissions themselves live in the user settings. A tool that reports a
clean bill of health because it only looked at one of them is worse than
no tool.

Exit codes: 0 = grade A/B, 1 = grade C/D, 2 = grade F, a CRITICAL
finding, or a REFUSAL. A refusal is a root we could not read: any root
the operator NAMED, every root when none was readable, or ANY root —
the defaults included — that raised while we scanned it (mode 000, a
root-owned config, a container uid mismatch). Only a MISSING default
root is exempt: a fresh machine has no ``~/.claude``, so it is noted on
stderr and the readable roots set the code; failing there would break
every CI container. CI can gate on the exit code. A refusal is never a
pass: a config we never opened cannot be graded, and saying "nothing to
report" about it would be the clean-looking run this tool exists to
prevent.
"""

from __future__ import annotations

import argparse
import json
import stat
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
    """One grade for the operator, not one per file they must add up.

    Merging nothing raises. An empty list produced a grade-A 100/100
    report, so every caller that forgot to check got a clean bill of
    health for a scan that never happened — twice in this module, and
    the next caller would inherit it (QG C3 r7, Francisca M1). Grading
    nothing is a programming error, not a passing grade.
    """
    if not reports:
        raise ValueError("merge() of no reports: nothing was scanned")
    merged = ScanReport(root=reports[0].root)
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


def _partition_roots(
    args: argparse.Namespace,
) -> tuple[list[Path], list[Path], bool]:
    """Split the requested roots, and say whether the OPERATOR named them.

    Provenance travels with the partition rather than being re-derived
    from ``args.path`` at each use: the wording and the exit code both
    depend on it, and two derivations five lines apart is the structural
    precondition of every defect this module produced across six rounds
    (QG C3 r7, Francisca M3).
    """
    requested = _roots(args)
    readable = [root for root in requested if _looks_like_dir(root)]
    unreadable = [root for root in requested if root not in readable]
    return readable, unreadable, bool(args.path)


def _looks_like_dir(root: Path) -> bool:
    """Is `root` a directory we should try to scan?

    "We could not tell" must answer YES, so the root reaches `_safe_scan`
    and comes back as a REFUSAL. Answering NO would file it under
    "skipped", which for a DEFAULT root exits 0 — a clean run over a
    config nobody read. `Path.is_dir()` cannot express that: it raises on
    3.13 (an unhandled traceback out of `main`) and swallows on 3.14
    (silently skipped), so neither interpreter produced the refusal
    (QG C3 r9, Francisca B1, sibling of the scan() probe).
    """
    try:
        return stat.S_ISDIR(root.stat().st_mode)
    except (FileNotFoundError, NotADirectoryError):
        return False  # genuinely absent — the exemption case
    except OSError:
        return True  # cannot tell: let _safe_scan refuse it by name


def _skipped_notice(readable: list[Path], skipped: list[Path],
                    named: bool) -> str:
    """Name every requested root that was never opened.

    A root the operator NAMED and we silently dropped is a clean bill of
    health for something we never read: `shield ~/.claude/settings.json`
    — the file rather than its directory, a normal invocation — was
    answered with "Grade A (100/100) — nothing to report." on the read-only
    path and with a bare exit 2 on --fix (QG C3 r5, Francisca B2).

    REFUSED is used exactly when the run will exit 2 for this reason, so
    the word and the exit code never disagree (QG C3 r6, Francisca B1).
    A missing DEFAULT root is a note instead: a fresh machine has no
    ~/.claude and must not fail CI over it. Written to stderr so
    `--json` stdout stays parseable.
    """
    paths = ", ".join(str(root) for root in skipped)
    subject = ("a readable directory" if len(skipped) == 1
               else "readable directories")
    if not readable:
        return f"REFUSED: no readable config root — {paths}"
    if named:
        return f"REFUSED: not {subject} — {paths}"
    return f"note: skipped, not {subject} — {paths}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arkaos shield",
        description=(
            "Scan the agent harness configuration for vulnerabilities: "
            "over-permissive allow rules, secrets in config, hook command "
            "injection, unpinned MCP servers, prompt injection in "
            "instruction files."
        ),
        epilog=(
            "Exit: 0 = A/B, 1 = C/D, 2 = F, any CRITICAL finding, or a "
            "root we could not read — any root YOU named, every root "
            "when none was readable, or any root that raised while we "
            "scanned it. Only a MISSING default root (~/.claude on a "
            "fresh machine) is noted on stderr instead of failing the run."
        ),
    )
    parser.add_argument(
        "path", nargs="*",
        help="Config roots to scan. Default: ~/.claude and the cwd.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Machine-readable output.",
    )
    _add_fix_arguments(parser)
    return parser


def _add_fix_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--fix", action="store_true",
        help=(
            "Plan the mechanical fixes (dangerous-command allow rules, "
            "missing deny list). Prints every finding it cannot fix and "
            "why — unscoped rules need your pattern, so they are named, "
            "never dropped. Writes nothing without --apply."
        ),
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="With --fix: write the changes, after a timestamped backup.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.apply and not args.fix:
        # Silently degrading a destructive flag into a read-only scan is
        # a trap: the operator believes they wrote (QG C3 r1, Francisca M1).
        parser.error("--apply requires --fix")

    roots, skipped, named = _partition_roots(args)
    if skipped:
        print(_skipped_notice(roots, skipped, named), file=sys.stderr)
    if not roots:
        return 2  # nothing was read, so nothing can be graded
    code = _fix(roots, args) if args.fix else _grade(roots, args)
    if skipped and named:
        # A root the OPERATOR NAMED and we never opened is a refusal
        # even when the others reported: the run cannot claim to have
        # graded what it was asked for (QG C3 r6, Francisca B1). Only a
        # MISSING default root is exempt — a fresh machine has no
        # ~/.claude. A default root that EXISTS and cannot be read is
        # refused by _grade/_fix, not here (QG C3 r7, Eduardo B1).
        return 2
    return code


def _grade(roots: list[Path], args: argparse.Namespace) -> int:
    """Read-only path: grade what we could read, refuse the rest.

    Guarded for the same reason the fix path is: `scan` raises on a root
    it cannot list, and leaving one call site bare only moves the
    traceback (QG C3 r4, Francisca B2).
    """
    reports, refusals = [], []
    for root in roots:
        result = _safe_scan(root)
        if isinstance(result, str):
            refusals.append(result)
        else:
            reports.append(result)
    for refusal in refusals:
        print(refusal, file=sys.stderr)
    if not reports:
        return 2
    report = merge(reports)
    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render(report))
    return 2 if refusals else exit_code(report)


def _safe_scan(root: Path) -> ScanReport | str:
    """Scan a root, or say why it could not be scanned.

    ``scan`` is not never-raises: an unreadable ROOT (mode 000, a
    root-owned config, a container uid mismatch) passes the is_dir()
    filter and then raises PermissionError from the first is_file()
    (QG C3 r4, Francisca B2, reproduced end to end). A security tool
    that answers a locked directory with a traceback has told the
    operator nothing.
    """
    try:
        return scan(root)
    except OSError as exc:
        return f"REFUSED: cannot scan {root} — {exc}"


def _fix(roots: list[Path], args: argparse.Namespace) -> int:
    """Remediate each root, then grade what is left.

    The exit code stays the scanner's contract and is computed from the
    RE-SCAN: a fix run that leaves criticals still exits 2.
    """
    payloads, rendered, graded = [], [], []
    for root in roots:
        payload, text, after = _fix_one(root, args)
        payloads.append(payload)
        rendered.append(text)
        if after is not None:
            graded.append(after)
    if args.as_json:
        print(json.dumps(payloads, indent=2))
    else:
        print("\n\n".join(rendered))
    if not graded or len(graded) < len(roots):
        # `not graded` is not redundant with the caller's guard: without
        # it, exit_code(merge([])) grades an empty read as A and returns
        # 0 — the r5 B2 defect surviving one level down, where the two
        # guards above only masked it (QG C3 r6).
        return 2
    return exit_code(merge(graded))


def _fix_one(root: Path,
             args: argparse.Namespace) -> tuple[dict, str, ScanReport | None]:
    """Remediate one root and re-grade it; None means the re-scan refused.

    The re-scan happens ONCE and its report is what both the printed
    grade and the exit code are computed from. Scanning a second time to
    derive the exit code graded a different read than the one on screen
    (QG C3 r5, Francisca M1), and dropped what `fix` itself planned when
    the re-scan refused (her M3).
    """
    from core.harness import remediation

    fix_report = remediation.fix(root, apply=args.apply)
    after = _safe_scan(root)
    if isinstance(after, str):
        return ({"root": str(root), **fix_report.to_dict(), "refused": after},
                f"{root}\n{remediation.render(fix_report)}\n{after}", None)
    return ({"root": str(root), **fix_report.to_dict(),
             "grade_after": after.grade},
            f"{root}\n{remediation.render(fix_report, after)}", after)


if __name__ == "__main__":
    sys.exit(main())
