"""CLI for the evolve engine: ``python -m core.cognition.evolve_cli``.

Mirrors ``reorganizer_cli``: argparse in, one ``build_proposal`` call,
human-readable summary out. ``--dry-run`` prints the proposal to stdout
without writing anything.
"""

from __future__ import annotations

import argparse

from core.cognition.evolve import build_proposal


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.cognition.evolve_cli",
        description=(
            "Ingest accumulated signals into instincts and write a "
            "propose-only evolution proposal."
        ),
    )
    parser.add_argument(
        "--min-projects", type=int, default=2,
        help="distinct projects required for a promotion candidate",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.8,
        help="mean confidence required for a promotion candidate",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the proposal to stdout; write nothing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_proposal(
        dry_run=args.dry_run,
        min_projects=args.min_projects,
        min_confidence=args.min_confidence,
    )
    if not args.dry_run:
        print(
            f"evolve: ingested={report.ingested} "
            f"pending={report.pending_instincts} "
            f"candidates={len(report.candidates)} -> {report.proposal_path}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
