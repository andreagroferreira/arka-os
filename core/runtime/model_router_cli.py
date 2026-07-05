"""CLI for the Model Fabric router — `npx arkaos models` delegates here.

Usage::

    python -m core.runtime.model_router_cli               # table of roles
    python -m core.runtime.model_router_cli --json        # machine-readable
    python -m core.runtime.model_router_cli init          # create user file
    python -m core.runtime.model_router_cli set review anthropic/best --effort max
    python -m core.runtime.model_router_cli usage --period week
"""

from __future__ import annotations

import argparse
import json
import sys

from core.runtime.llm_cost_telemetry import VALID_PERIODS, summarise
from core.runtime.model_router import (
    USER_CONFIG_PATH,
    ensure_user_config,
    load_config,
    resolve_all,
    set_role,
)
from core.runtime.ollama_discovery import discover


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
    _print_ollama_line()
    print("  Change: npx arkaos models set <role> <provider>/<model> [--effort max]")
    print("  Usage:  npx arkaos models usage [--period today|week|month|all]")
    print()


def _print_ollama_line() -> None:
    status = discover()
    if status.running and status.models:
        names = ", ".join(m.name for m in status.models[:5])
        extra = f" (+{len(status.models) - 5} more)" if len(status.models) > 5 else ""
        print(f"  Ollama: running — {len(status.models)} local models: {names}{extra}")
        print("          use them: npx arkaos models set mechanical ollama/<model>")
    elif status.installed:
        print("  Ollama: installed but not running — start it to unlock local models")
    else:
        print("  Ollama: not detected — https://ollama.com for free local models")
    print()


def _print_usage(period: str) -> None:
    summary = summarise(period=period)
    total = summary.total_cost_usd
    total_s = f"${total:.4f}" if total is not None else "—"
    print()
    print(f"  Model Fabric — usage ({period})")
    print(f"  calls: {summary.call_count}  tokens in/out: "
          f"{summary.total_tokens_in}/{summary.total_tokens_out}  "
          f"cached: {summary.total_cached_tokens}  est. cost: {total_s}")
    for title, group in (("BY MODEL", summary.by_model),
                         ("BY PROVIDER", summary.by_provider)):
        if not group:
            continue
        print()
        print(f"  {title:<28} {'CALLS':>6} {'IN':>10} {'OUT':>10} {'COST':>10}")
        print("  " + "─" * 68)
        ranked = sorted(group.items(),
                        key=lambda kv: kv[1].get("total_cost_usd") or 0,
                        reverse=True)
        for name, bucket in ranked:
            cost = bucket.get("total_cost_usd")
            cost_s = f"${cost:.4f}" if cost is not None else "—"
            print(f"  {(name or '(unknown)'):<28} "
                  f"{bucket.get('call_count', 0):>6} "
                  f"{bucket.get('total_tokens_in', 0):>10} "
                  f"{bucket.get('total_tokens_out', 0):>10} {cost_s:>10}")
    print()


def _print_json() -> None:
    payload = [item.model_dump() for item in resolve_all()]
    print(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arkaos models")
    parser.add_argument("action", nargs="?", default="list",
                        choices=["list", "init", "set", "usage", "discover"])
    parser.add_argument("role", nargs="?")
    parser.add_argument("target", nargs="?")
    parser.add_argument("--effort", choices=["low", "medium", "high", "max"])
    parser.add_argument("--period", choices=list(VALID_PERIODS), default="today")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.action == "usage":
        if args.as_json:
            summary = summarise(period=args.period)
            print(json.dumps({
                "period": summary.period,
                "call_count": summary.call_count,
                "total_cost_usd": summary.total_cost_usd,
                "total_tokens_in": summary.total_tokens_in,
                "total_tokens_out": summary.total_tokens_out,
                "total_cached_tokens": summary.total_cached_tokens,
                "by_model": summary.by_model,
                "by_provider": summary.by_provider,
                "by_category": summary.by_category,
            }, indent=2))
        else:
            _print_usage(args.period)
        return 0
    if args.action == "discover":
        print(json.dumps(discover().to_dict(), indent=2))
        return 0
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
