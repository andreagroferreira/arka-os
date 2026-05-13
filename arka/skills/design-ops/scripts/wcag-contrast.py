#!/usr/bin/env python3
"""WCAG 2.2 contrast ratio checker (Oren's reference script).

Compares foreground / background colours and reports whether the pair
passes WCAG 2.2 Level AA (4.5 : 1 normal text, 3 : 1 large text and UI
components) and AAA (7 : 1 normal, 4.5 : 1 large).

Usage:
    python3 wcag-contrast.py "#1a1a1a" "#ffffff"
    python3 wcag-contrast.py --json "#0f172a" "#ffffff" "#3b82f6" "#ffffff"

Outputs a single-line verdict or, with --json, a structured report.
"""

from __future__ import annotations

import argparse
import json
import sys


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance formula."""
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    lf, lb = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(lf, lb), min(lf, lb)
    return (lighter + 0.05) / (darker + 0.05)


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"Invalid hex colour: {hex_color}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def verdict(ratio: float) -> dict[str, bool]:
    return {
        "AA_normal": ratio >= 4.5,
        "AA_large": ratio >= 3.0,
        "AAA_normal": ratio >= 7.0,
        "AAA_large": ratio >= 4.5,
    }


def check_pair(fg_hex: str, bg_hex: str) -> dict[str, object]:
    fg = hex_to_rgb(fg_hex)
    bg = hex_to_rgb(bg_hex)
    ratio = round(contrast_ratio(fg, bg), 2)
    return {
        "fg": fg_hex,
        "bg": bg_hex,
        "ratio": ratio,
        **verdict(ratio),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("colors", nargs="*", help="alternating fg bg pairs")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)

    if len(args.colors) < 2 or len(args.colors) % 2 != 0:
        parser.error("provide pairs of hex colours: <fg> <bg> [<fg> <bg> ...]")

    pairs = list(zip(args.colors[::2], args.colors[1::2]))
    results = [check_pair(fg, bg) for fg, bg in pairs]

    if args.json:
        print(json.dumps({"results": results}, indent=2))
        return 0

    for r in results:
        flags = [k for k, v in r.items() if k.startswith("AA") and v]
        flag_str = "+".join(flags) if flags else "FAILS_ALL"
        print(f"{r['fg']} on {r['bg']}: {r['ratio']}:1  → {flag_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
