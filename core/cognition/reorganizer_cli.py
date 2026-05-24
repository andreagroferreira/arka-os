"""CLI for the propose-only Dreaming reorganizer (PR20 v2.42.0).

Invoked as ``python -m core.cognition.reorganizer_cli [options]``.
Reads recent KB artifacts (pattern / anti-pattern / lesson files),
sanitizes client identifiers, and writes a proposal markdown report.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from core.cognition.reorganizer import build_proposal

# Default KB location — the Obsidian vault subfolder where Dreaming v2
# writes pattern/anti-pattern/lesson artifacts. Overridable via env var
# or --kb-dir for tests and unusual installs.
_DEFAULT_KB_DIR = (
    Path.home()
    / "Documents" / "Personal" / "Projects"
    / "WizardingCode Internal" / "ArkaOS" / "Knowledge Base"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arkaos-reorganize",
        description="Aggregate recent KB artifacts into a propose-only "
                    "markdown report. Never modifies agent YAMLs.",
    )
    parser.add_argument(
        "--since-days", type=int, default=7,
        help="Window in days for first_seen/last_seen filter (default: 7).",
    )
    parser.add_argument(
        "--kb-dir", type=Path, default=None,
        help="Override the KB directory to scan (default: ArkaOS vault).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the report to stdout, do not write to disk.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:])
    kb_dir = args.kb_dir or Path(os.environ.get("ARKAOS_KB_DIR", _DEFAULT_KB_DIR))

    report = build_proposal(
        kb_dir,
        since_days=args.since_days,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(report.report_markdown)
        return 0

    print(f"Artifacts: {report.artifact_count}")
    for cat, count in sorted(report.by_category.items()):
        print(f"  {cat}: {count}")
    if report.report_path is not None:
        print(f"Report: {report.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
