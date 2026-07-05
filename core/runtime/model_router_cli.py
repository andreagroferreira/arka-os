"""CLI for the Model Fabric router — `npx arkaos models` delegates here.

Usage::

    python -m core.runtime.model_router_cli               # table of roles
    python -m core.runtime.model_router_cli --json        # machine-readable
    python -m core.runtime.model_router_cli init          # create user file
    python -m core.runtime.model_router_cli set review anthropic/best --effort max
"""

from __future__ import annotations

import argparse
import json
import sys

from core.runtime.model_router import (
    USER_CONFIG_PATH,
    ensure_user_config,
    load_config,
    resolve_all,
    set_role,
)


def _print_table() -> None:
    resolved = resolve_all()
    _, source = load_config()
    print()
    print("  ArkaOS Model Fabric — role routing")
    print(f"  config: {USER_CONFIG_PATH if source == 'user' else source}")
    print()
    header = f"  {'ROLE':<14} {'PROVIDER':<12} {'MODEL':<34} EFFORT"
    print(header)
    print("  " + "─" * (len(header) - 2))
    for item in resolved:
        model = item.model or "(unset — configure alias)"
        print(f"  {item.role:<14} {item.provider:<12} {model:<34} {item.effort}")
    print()
    print("  Change: npx arkaos models set <role> <provider>/<model> [--effort max]")
    print()


def _print_json() -> None:
    payload = [item.model_dump() for item in resolve_all()]
    print(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arkaos models")
    parser.add_argument("action", nargs="?", default="list",
                        choices=["list", "init", "set"])
    parser.add_argument("role", nargs="?")
    parser.add_argument("target", nargs="?")
    parser.add_argument("--effort", choices=["low", "medium", "high", "max"])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.action == "init":
        path = ensure_user_config()
        print(f"  ✓ Model Fabric config: {path}")
        return 0
    if args.action == "set":
        if not args.role or not args.target:
            parser.error("set requires: <role> <provider>/<model>")
        try:
            item = set_role(args.role, args.target, effort=args.effort)
        except ValueError as exc:
            print(f"  ✗ {exc}", file=sys.stderr)
            return 1
        print(f"  ✓ {item.role} -> {item.provider}/{item.model} "
              f"(effort {item.effort})")
        return 0
    if args.as_json:
        _print_json()
    else:
        _print_table()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
