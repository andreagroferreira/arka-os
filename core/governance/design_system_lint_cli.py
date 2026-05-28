"""CLI for the Design System Linter (PR6 Squad Intelligence Upgrade v3.77.0).

Usage:
    python -m core.governance.design_system_lint_cli <project_path> [--format text|json] [--exit-on-violations]

Examples:
    python -m core.governance.design_system_lint_cli /path/to/project
    python -m core.governance.design_system_lint_cli /path/to/project --format json --exit-on-violations
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from core.governance.design_system_lint import (
    DesignViolation,
    lint_project,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.design_system_lint_cli",
        description="Scan a project for design-system violations.",
    )
    parser.add_argument("project_path", help="Path to the project root containing design-system.yaml.")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--exit-on-violations",
        action="store_true",
        help="Exit with code 1 when violations are found.",
    )
    return parser


def _print_text(violations: list[DesignViolation]) -> None:
    """Group violations by file, sorted by file then line, and pretty-print."""
    print(f"{len(violations)} design-system violation(s) found:")
    by_file: dict[str, list[DesignViolation]] = defaultdict(list)
    for v in violations:
        by_file[v.file].append(v)
    for file in sorted(by_file):
        for v in sorted(by_file[file], key=lambda x: x.line):
            truncated = v.matched_text[:60] + ("..." if len(v.matched_text) > 60 else "")
            print(f"  {v.file}:{v.line}  {truncated}")
            print(f"    → {v.suggestion}")


def _print_json(violations: list[DesignViolation]) -> None:
    """Emit one JSON line per violation followed by a summary line (jsonl)."""
    for v in violations:
        print(json.dumps({
            "file": v.file,
            "line": v.line,
            "pattern": v.pattern,
            "suggestion": v.suggestion,
            "matched_text": v.matched_text,
        }))
    print(json.dumps({"summary": True, "count": len(violations)}))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    violations = lint_project(Path(args.project_path))

    if not violations:
        if args.format == "json":
            print(json.dumps({"violations": [], "count": 0}))
        else:
            print("No design-system violations.")
        return 0

    if args.format == "json":
        _print_json(violations)
    else:
        _print_text(violations)

    return 1 if args.exit_on_violations else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
