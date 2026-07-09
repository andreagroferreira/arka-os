"""Recipe capture/list/show CLI (Interaction Reform PR7).

The QG skill (step 7) proposes promoting an APPROVED reusable feature
to a recipe; on operator confirmation it calls `capture` here. Capture
is fail-closed: no redaction config → refused (SanitizerConfigMissing),
because a client identifier reaching the recipe corpus is the exact
confidentiality breach the sanitizer exists to prevent.

Usage:
    arka-py -m core.knowledge.recipes_cli capture --spec <recipe.json>
    arka-py -m core.knowledge.recipes_cli list
    arka-py -m core.knowledge.recipes_cli show <slug>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from core.evals.sanitizer import SanitizerConfigMissing
from core.knowledge.recipes import (
    Recipe,
    RecipeCaptureRefused,
    capture_recipe,
    list_recipes,
    load_recipe,
)


def _cmd_capture(args: argparse.Namespace) -> int:
    """Capture from a spec JSON: {recipe, narrative, files:{path:content}}."""
    raw = (
        Path(args.spec).read_text(encoding="utf-8")
        if args.spec
        else sys.stdin.read()
    )
    try:
        payload = json.loads(raw)
        recipe = Recipe.model_validate(payload["recipe"])
    except (json.JSONDecodeError, KeyError, ValidationError) as exc:
        print(f"error: invalid recipe spec — {exc}", file=sys.stderr)
        return 1
    try:
        target = capture_recipe(
            recipe,
            narrative=payload.get("narrative", ""),
            reference_files=payload.get("files", {}),
        )
    except SanitizerConfigMissing as exc:
        print(f"error: capture refused — {exc}", file=sys.stderr)
        return 2
    except RecipeCaptureRefused as exc:
        print(f"error: capture refused — {exc}", file=sys.stderr)
        return 3
    print(json.dumps({"captured": True, "slug": recipe.slug,
                      "path": str(target)}))
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    recipes = list_recipes()
    for recipe in recipes:
        print(f"{recipe.slug:30s} {', '.join(recipe.stack):20s} {recipe.name}")
    print(f"\n{len(recipes)} recipe(s)")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    recipe = load_recipe(args.slug)
    if recipe is None:
        print(f"error: no recipe {args.slug!r}", file=sys.stderr)
        return 1
    print(recipe.model_dump_json(indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_capture = sub.add_parser("capture")
    p_capture.add_argument("--spec", help="spec JSON file (default: stdin)")
    sub.add_parser("list")
    p_show = sub.add_parser("show")
    p_show.add_argument("slug")
    args = parser.parse_args(argv)

    return {
        "capture": _cmd_capture,
        "list": _cmd_list,
        "show": _cmd_show,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
