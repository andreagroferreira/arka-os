"""CLI for the harness manager — ``npx arkaos harness <verb>``.

Verbs: ``status`` (read-only), ``assert`` (apply policies), ``restore``
(assert + re-seed adopted surfaces), ``harden`` (assert + scanner
grade, nonzero exit below B), ``flags`` (read, or set with an explicit
``--set name=value``). Every verb but ``flags`` takes ``--json``.
Exit codes are the contract the Node wrapper propagates verbatim.
"""

from __future__ import annotations

import argparse
import json
import sys

from core.harness.manager import ClaudeConfigManager


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler = {
        "status": _status,
        "assert": _assert,
        "restore": _restore,
        "harden": _harden,
        "flags": _flags,
    }[args.verb]
    try:
        return handler(ClaudeConfigManager(), args)
    except Exception as exc:  # operators get a message, never a traceback
        print(f"harness {args.verb} failed: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.harness.cli",
        description="Assert and report ArkaOS ownership of the harness.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)
    for verb in ("status", "assert", "restore", "harden"):
        sub.add_parser(verb).add_argument(
            "--json", action="store_true", dest="as_json"
        )
    flags = sub.add_parser("flags")
    flags.add_argument(
        "--set", dest="assignment", default=None,
        help=(
            "hardEnforcement|specialistEnforcement: true|false; "
            "frontendGate: off|warn|hard; read-only without it"
        ),
    )
    return parser


def _status(manager: ClaudeConfigManager, args) -> int:
    report = manager.status()
    if getattr(args, "as_json", False):
        print(json.dumps(report, indent=2))
        return 0
    _print_drift(report["drift"])
    return 0


def _print_drift(drift_report: dict) -> None:
    print(f"settings: {drift_report['settings_path']}")
    print(f"ok: {drift_report['ok']}")
    for finding in drift_report["findings"]:
        print(
            f"  [{finding['status']}] {finding['where']} — "
            f"{finding['detail']}"
        )
    if not drift_report["findings"]:
        print("  no drift")


def _assert(manager: ClaudeConfigManager, args) -> int:
    return _print_report(manager.assert_ownership(), args)


def _restore(manager: ClaudeConfigManager, args) -> int:
    return _print_report(manager.restore(), args)


def _harden(manager: ClaudeConfigManager, args) -> int:
    report, grade = manager.harden()
    code = _print_report(report, args, extra={"scan_grade": grade})
    if not getattr(args, "as_json", False):
        print(f"post-assert scan grade: {grade}")
    if code:
        return code
    return 0 if grade in ("A", "B") else 2


def _flags(manager: ClaudeConfigManager, args) -> int:
    if args.assignment:
        name, separator, raw = args.assignment.partition("=")
        if not separator or not raw.strip():
            print("flags --set expects name=value", file=sys.stderr)
            return 1
        try:
            flags = manager.set_flag(name.strip(), _parse_value(raw.strip()))
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        flags = manager.read_flags()
    print(json.dumps(flags, indent=2))
    return 0


def _parse_value(raw: str) -> object:
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    return raw.lower()


def _print_report(report, args=None, extra: dict | None = None) -> int:
    if getattr(args, "as_json", False):
        print(json.dumps({**report.to_dict(), **(extra or {})}, indent=2))
        return 1 if report.refused or _has_refusal(report) else 0
    if report.refused:
        print(f"{report.verb}: refused — {report.refused}", file=sys.stderr)
        print(
            "  nothing was written; fix or remove the file and re-run",
            file=sys.stderr,
        )
        return 1
    print(f"{report.verb}: changed={report.changed}")
    for action in report.actions:
        if action.action == "noop":
            continue
        detail = f" ({action.detail})" if action.detail else ""
        print(f"  {action.action}: {action.surface}{detail}")
    return 1 if _has_refusal(report) else 0


def _has_refusal(report) -> bool:
    return any(a.action == "refused" for a in report.actions)


if __name__ == "__main__":
    raise SystemExit(main())
