"""Fusion CLI — smoke path for the panel → judge pipeline.

Usage::

    python -m core.fusion.cli "your question"
"""

from __future__ import annotations

import sys

from core.fusion.engine import FusionUnavailable, fuse


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m core.fusion.cli \"question\"", file=sys.stderr)
        return 1
    prompt = " ".join(args)
    try:
        result = fuse(prompt)
    except FusionUnavailable as exc:
        print(f"  ✗ {exc}", file=sys.stderr)
        return 1
    seats = ", ".join(
        f"{a.provider}/{a.model}" + (" (failed)" if a.failed else "")
        for a in result.answers
    )
    print(f"\n  Fusion — judge {result.judge_provider}/{result.judge_model} "
          f"| panel: {seats}\n")
    print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
