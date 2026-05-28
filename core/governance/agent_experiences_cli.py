"""CLI viewer for agent experiences.

Usage:
    python -m core.governance.agent_experiences_cli list <agent_id> [options]

Options:
    --limit N        Show at most N most-recent experiences (default 10)
    --since DATE     ISO date or datetime (e.g. 2026-05-01)
    --tag TAG        Show only entries with this tag

Examples:
    python -m core.governance.agent_experiences_cli list tech-lead-paulo
    python -m core.governance.agent_experiences_cli list cqo-marta --limit 5
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from core.governance.agent_experiences import query_experiences


def _format_experience(exp, index: int) -> str:
    lines = [
        f"  [{index}] {exp.ts}  {exp.verdict}  {exp.context}",
    ]
    if exp.patterns:
        lines.append(f"        patterns: {', '.join(exp.patterns)}")
    for blocker in (exp.blockers or [])[:5]:
        lines.append(f"        - {blocker}")
    if exp.fix_applied:
        lines.append(f"        fix: {exp.fix_applied}")
    if exp.references:
        refs = ", ".join(exp.references[:3])
        lines.append(f"        refs: {refs}")
    if exp.tags:
        lines.append(f"        tags: {', '.join(exp.tags)}")
    return "\n".join(lines)


def _parse_since(value: str) -> datetime:
    """Accept either an ISO date (YYYY-MM-DD) or full ISO datetime."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"error: invalid --since value: {value}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.agent_experiences_cli",
        description="Inspect Quality Gate experience records for an agent.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    list_p = subparsers.add_parser("list", help="List experiences for an agent.")
    list_p.add_argument("agent_id", help="Agent ID, e.g. tech-lead-paulo")
    list_p.add_argument("--limit", type=int, default=10, help="Max records (default 10)")
    list_p.add_argument("--since", default=None, help="ISO date or datetime cutoff")
    list_p.add_argument("--tag", default=None, help="Filter by tag")
    return parser


def _print_results(agent_id: str, experiences: list) -> int:
    if not experiences:
        print(f"No experiences recorded for {agent_id}.")
        return 0
    print(
        f"Experiences for {agent_id} "
        f"({len(experiences)} record(s), most recent first):\n"
    )
    for i, exp in enumerate(experiences, start=1):
        print(_format_experience(exp, i))
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd != "list":
        parser.print_help()
        return 2
    since = _parse_since(args.since) if args.since else None
    experiences = query_experiences(
        args.agent_id, limit=args.limit, since=since, tag=args.tag
    )
    return _print_results(args.agent_id, experiences)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
