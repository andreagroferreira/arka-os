#!/usr/bin/env python3
"""Convert DTCG colour tokens into shadcn/ui CSS variables (Leo's script).

Reads a DTCG-style ``colors.json`` (as produced by ``extract-colors.py``)
and emits the canonical shadcn/ui CSS variable block plus a matching
``tailwind.config.js`` ``theme.extend.colors`` snippet.

Usage:
    python3 shadcn-tokens.py colors.json
    python3 shadcn-tokens.py colors.json --prefix brand-
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def to_css_var(slug: str, value: str, prefix: str) -> str:
    return f"  --{prefix}{slug}: {value};"


def to_tailwind_entry(slug: str, prefix: str) -> str:
    key = slug.replace("color-", "")
    return f'        "{prefix}{slug}": "var(--{prefix}{slug})",'


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="path to DTCG colors.json")
    parser.add_argument("--prefix", default="", help="CSS variable prefix (e.g. 'brand-')")
    args = parser.parse_args(argv)

    data = json.loads(Path(args.source).read_text(encoding="utf-8"))
    tokens = data.get("colors", {})
    if not tokens:
        print("no colours found in source", file=sys.stderr)
        return 1

    css_vars = [to_css_var(slug, t["$value"], args.prefix) for slug, t in tokens.items()]
    tailwind = [to_tailwind_entry(slug, args.prefix) for slug in tokens]

    print(":root {")
    print("\n".join(css_vars))
    print("}\n")

    print("// tailwind.config.js — theme.extend.colors")
    print("{")
    print('  theme: { extend: { colors: {')
    print("\n".join(tailwind))
    print("  } } }")
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
