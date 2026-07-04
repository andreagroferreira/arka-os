"""Runtime capabilities matrix CLI (PR-6 v4.1.0 — multi-runtime honesty).

Single source of truth for what each runtime adapter actually supports.
Prints the static ``capabilities()`` matrix of all registered adapters,
plus live binary detection for the headless CLIs.

Usage:
    python -m core.runtime.capabilities_cli          # table
    python -m core.runtime.capabilities_cli --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys

from core.runtime.registry import RUNTIME_ADAPTERS

_CAP_KEYS = ("agent_dispatch", "headless", "file_ops", "hooks")


def build_matrix() -> dict[str, dict]:
    """Collect capabilities + live headless availability per runtime."""
    matrix: dict[str, dict] = {}
    for runtime_id, adapter_cls in RUNTIME_ADAPTERS.items():
        adapter = adapter_cls()
        caps = adapter.capabilities()
        row = {key: bool(caps.get(key, False)) for key in _CAP_KEYS}
        try:
            row["headless_available"] = bool(adapter.headless_supported())
        except Exception:  # noqa: BLE001 — detection must never crash
            row["headless_available"] = False
        row["name"] = adapter.get_config().name
        matrix[runtime_id] = row
    return matrix


def _render_table(matrix: dict[str, dict]) -> str:
    header = (
        f"{'runtime':<14}{'agent_dispatch':<16}{'headless':<10}"
        f"{'file_ops':<10}{'hooks':<7}{'binary on PATH'}"
    )
    lines = [header, "-" * len(header)]
    for runtime_id, row in matrix.items():
        def mark(key: str) -> str:
            return "yes" if row.get(key) else "no"
        lines.append(
            f"{runtime_id:<14}{mark('agent_dispatch'):<16}"
            f"{mark('headless'):<10}{mark('file_ops'):<10}"
            f"{mark('hooks'):<7}{mark('headless_available')}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.runtime.capabilities_cli",
        description="Print the multi-runtime support matrix.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON instead of a table"
    )
    args = parser.parse_args(argv)
    matrix = build_matrix()
    if args.json:
        print(json.dumps(matrix, indent=2))
    else:
        print(_render_table(matrix))
    return 0


if __name__ == "__main__":
    sys.exit(main())
