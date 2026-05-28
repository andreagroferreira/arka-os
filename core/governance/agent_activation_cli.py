"""CLI viewer for agent activation telemetry.

Usage:
    python -m core.governance.agent_activation_cli top [--since DAYS] [--limit N]
    python -m core.governance.agent_activation_cli dead [--since-days N]

Examples:
    python -m core.governance.agent_activation_cli top --limit 10
    python -m core.governance.agent_activation_cli dead --since-days 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from core.governance.activation_tracker import query_dead_agents, query_top_callers


def _since_dt(days: int | None) -> datetime | None:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _print_top(rows: list[tuple[str, int]]) -> int:
    """Print rank | subagent_type | call_count table."""
    if not rows:
        print("No activation records found.")
        return 0
    print(f"{'rank':>4}  {'subagent_type':<36} {'calls':>6}")
    print("-" * 50)
    for rank, (agent, count) in enumerate(rows, start=1):
        print(f"{rank:>4}  {agent:<36} {count:>6}")
    return 0


def _parse_ts_for_display(iso: str) -> tuple[str, int]:
    """Return (formatted_ts, days_since) from an ISO string."""
    try:
        ts = datetime.fromisoformat(iso)
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        days_since = (now - ts).days
        return ts.strftime("%Y-%m-%d %H:%M UTC"), days_since
    except (TypeError, ValueError):
        return iso, -1


def _print_dead(rows: list[tuple[str, str]]) -> int:
    """Print subagent_type | last_seen | days_since table."""
    if not rows:
        print("No dormant agents found.")
        return 0
    print(f"{'subagent_type':<36} {'last_seen':<22} {'days_since':>10}")
    print("-" * 72)
    for agent, last_ts in rows:
        last_seen, days_since = _parse_ts_for_display(last_ts)
        print(f"{agent:<36} {last_seen:<22} {days_since:>10}")
    return 0


def _do_top(args: argparse.Namespace) -> int:
    since = _since_dt(args.since)
    rows = query_top_callers(limit=args.limit, since=since)
    return _print_top(rows)


def _do_dead(args: argparse.Namespace) -> int:
    rows = query_dead_agents(since_days=args.since_days)
    return _print_dead(rows)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.agent_activation_cli",
        description="Inspect agent activation telemetry.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    top_p = subparsers.add_parser("top", help="Show most-dispatched agents by call count.")
    top_p.add_argument("--since", type=int, default=None, help="Limit to last N days")
    top_p.add_argument("--limit", type=int, default=10, help="Max records (default 10)")

    dead_p = subparsers.add_parser("dead", help="Show agents with no activation in N days.")
    dead_p.add_argument(
        "--since-days", type=int, default=30, dest="since_days",
        help="Dormancy threshold in days (default 30)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "top":
        return _do_top(args)
    if args.cmd == "dead":
        return _do_dead(args)
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
