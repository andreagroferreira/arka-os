"""CLI viewer for the Pattern Library.

Usage:
    python -m core.knowledge.pattern_cards_cli list [--tag TAG] [--limit N]
    python -m core.knowledge.pattern_cards_cli search <keyword> [--tag TAG] [--limit N]
    python -m core.knowledge.pattern_cards_cli show <id>
"""

from __future__ import annotations

import argparse
import sys

from core.knowledge.pattern_cards import PatternCard, query_patterns


def _format_card(card: PatternCard, index: int | None = None) -> str:
    head = f"  [{index}] " if index is not None else "  "
    lines = [f"{head}{card.id} — {card.name}"]
    if card.stack:
        lines.append(f"      stack: {', '.join(card.stack)}")
    if card.description:
        lines.append(f"      {card.description}")
    if card.files:
        lines.append(f"      files: {', '.join(card.files[:5])}")
    if card.acceptance_criteria:
        lines.append("      AC:")
        for ac in card.acceptance_criteria[:3]:
            lines.append(f"        - {ac}")
    if card.references:
        lines.append(f"      refs: {', '.join(card.references[:3])}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.knowledge.pattern_cards_cli",
        description="Browse the ArkaOS Pattern Library.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    list_p = subparsers.add_parser("list", help="List all patterns by recency.")
    list_p.add_argument("--tag", default=None, help="Filter by stack tag")
    list_p.add_argument("--limit", type=int, default=20, help="Max records")

    search_p = subparsers.add_parser("search", help="Search by keyword.")
    search_p.add_argument("keyword", help="Keyword (case-insensitive substring)")
    search_p.add_argument("--tag", default=None, help="Filter by stack tag")
    search_p.add_argument("--limit", type=int, default=20, help="Max records")

    show_p = subparsers.add_parser("show", help="Show one card by id.")
    show_p.add_argument("id", help="Pattern id slug")
    return parser


def _do_list(args) -> int:
    tags = [args.tag] if args.tag else None
    cards = query_patterns(tags=tags, limit=args.limit)
    return _print_list(cards, scope="all")


def _do_search(args) -> int:
    tags = [args.tag] if args.tag else None
    cards = query_patterns(keywords=[args.keyword], tags=tags, limit=args.limit)
    return _print_list(cards, scope=f"matching '{args.keyword}'")


def _do_show(args) -> int:
    cards = query_patterns()
    for c in cards:
        if c.id == args.id:
            print(_format_card(c))
            return 0
    print(f"No pattern with id '{args.id}'.")
    return 1


def _print_list(cards: list[PatternCard], *, scope: str) -> int:
    if not cards:
        print(f"No patterns {scope}.")
        return 0
    print(f"Patterns {scope} ({len(cards)} record(s), most recent first):\n")
    for i, c in enumerate(cards, start=1):
        print(_format_card(c, index=i))
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "list":
        return _do_list(args)
    if args.cmd == "search":
        return _do_search(args)
    if args.cmd == "show":
        return _do_show(args)
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
