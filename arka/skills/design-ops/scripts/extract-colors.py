#!/usr/bin/env python3
"""Extract colour tokens from CSS / HTML / JSON (Nia's reference script).

Scans the input for hex colours and named CSS variables, normalises to
lower-case 6-digit hex, deduplicates, and emits a DTCG-compliant
``colors.json`` token list.

Usage:
    python3 extract-colors.py path/to/styles.css
    python3 extract-colors.py --stdin < styles.css
    cat styles.css | python3 extract-colors.py --stdin
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
RGB = re.compile(r"rgb(?:a)?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def normalise(hex_value: str) -> str | None:
    h = hex_value.lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h[:3])
    elif len(h) == 8:
        h = h[:6]
    if len(h) != 6:
        return None
    return f"#{h}"


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def extract(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in HEX.finditer(text):
        norm = normalise(m.group(1))
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    for r, g, b in RGB.findall(text):
        norm = rgb_to_hex(int(r), int(g), int(b))
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def to_dtcg(colors: list[str]) -> dict:
    tokens = {}
    for i, c in enumerate(colors):
        slug = f"color-{i:03d}"
        tokens[slug] = {"$value": c, "$type": "color"}
    return {"$schema": "https://design-tokens.org/draft", "colors": tokens}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", help="path to CSS / HTML file")
    parser.add_argument("--stdin", action="store_true", help="read from stdin")
    args = parser.parse_args(argv)

    if args.stdin or args.source == "-":
        text = sys.stdin.read()
    elif args.source:
        text = Path(args.source).read_text(encoding="utf-8")
    else:
        parser.error("provide a source path or use --stdin")

    colors = extract(text)
    print(json.dumps(to_dtcg(colors), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
