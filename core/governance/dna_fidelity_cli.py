"""CLI viewer for DNA fidelity telemetry.

Usage:
    python -m core.governance.dna_fidelity_cli list [--agent AGENT_ID] [--since DAYS] [--limit N]
    python -m core.governance.dna_fidelity_cli summary [--since DAYS]

Examples:
    python -m core.governance.dna_fidelity_cli list --limit 10
    python -m core.governance.dna_fidelity_cli list --agent tech-lead-paulo --since 7
    python -m core.governance.dna_fidelity_cli summary --since 30
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TELEMETRY_PATH: Path = Path.home() / ".arkaos" / "telemetry" / "dna-fidelity.jsonl"


def _load_records(since_dt: datetime | None, agent: str | None) -> list[dict]:
    """Read JSONL, filter by agent and since, skip malformed lines silently."""
    results: list[dict] = []
    try:
        with _TELEMETRY_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if agent and rec.get("agent_id") != agent:
                    continue
                if since_dt is not None:
                    ts = _parse_ts(rec.get("ts", ""))
                    if ts is None or ts < since_dt:
                        continue
                results.append(rec)
    except OSError:
        pass
    results.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return results


def _parse_ts(value: str) -> datetime | None:
    """Parse ISO timestamp; return None on failure."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _since_dt(days: int | None) -> datetime | None:
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _format_record(rec: dict, index: int) -> str:
    """Format a single fidelity record for list output."""
    ts = rec.get("ts", "?")
    agent = rec.get("agent_id", "?")
    vcount = rec.get("violation_count", 0)
    label = "CLEAN" if vcount == 0 else f"VIOLATIONS({vcount})"
    lines = [f"  [{index}] {ts}  {agent}  {label}"]
    for v in (rec.get("violations") or [])[:3]:
        lines.append(f"        - {v.get('kind')} | {v.get('pattern')}")
    return "\n".join(lines)


def _do_list(args: argparse.Namespace) -> int:
    """List fidelity records, most recent first."""
    since = _since_dt(args.since)
    records = _load_records(since, args.agent)
    records = records[: args.limit]
    if not records:
        print("No records found.")
        return 0
    scope = f"agent={args.agent}" if args.agent else "all agents"
    print(f"DNA fidelity ({len(records)} record(s), most recent first) [{scope}]:\n")
    for i, rec in enumerate(records, start=1):
        print(_format_record(rec, i))
        print()
    return 0


def _do_summary(args: argparse.Namespace) -> int:
    """Aggregate by agent_id, show violation rate sorted descending."""
    since = _since_dt(args.since)
    records = _load_records(since, agent=None)
    if not records:
        print("No records found.")
        return 0
    totals: dict[str, int] = {}
    violations: dict[str, int] = {}
    for rec in records:
        aid = rec.get("agent_id", "?")
        totals[aid] = totals.get(aid, 0) + 1
        if rec.get("violation_count", 0) > 0:
            violations[aid] = violations.get(aid, 0) + 1
    rows = sorted(
        totals.keys(),
        key=lambda a: violations.get(a, 0) / totals[a],
        reverse=True,
    )
    print(f"{'agent':<32} {'total':>6} {'violations':>10} {'rate':>8}")
    print("-" * 62)
    for aid in rows:
        total = totals[aid]
        viol = violations.get(aid, 0)
        rate = viol / total * 100
        print(f"{aid:<32} {total:>6} {viol:>10} {rate:>7.1f}%")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.dna_fidelity_cli",
        description="Inspect DNA fidelity telemetry records.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    list_p = subparsers.add_parser("list", help="List fidelity records, most recent first.")
    list_p.add_argument("--agent", default=None, help="Filter by agent_id")
    list_p.add_argument("--since", type=int, default=None, help="Show records from last N days")
    list_p.add_argument("--limit", type=int, default=20, help="Max records (default 20)")

    summary_p = subparsers.add_parser("summary", help="Aggregate violation rate per agent.")
    summary_p.add_argument("--since", type=int, default=None, help="Aggregate last N days only")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "list":
        return _do_list(args)
    if args.cmd == "summary":
        return _do_summary(args)
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
