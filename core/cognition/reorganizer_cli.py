"""CLI for the propose-only Dreaming reorganizer (PR20 v2.42.0).

Invoked as ``python -m core.cognition.reorganizer_cli [options]``.
Reads recent KB artifacts (pattern / anti-pattern / lesson files),
sanitizes client identifiers, and writes a proposal markdown report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from core.cognition.reorganizer import KbDirMissingError, build_proposal
from core.knowledge import vault as knowledge_vault

# Portable default subfolder under the configured vault. The previous
# default hardcoded the author's personal vault layout, which exists on
# no other machine — and a missing dir scanned as an empty one, so every
# fresh install reported zero artifacts with exit 0 (issue #521).
_KB_SUBPATH = Path("Projects") / "ArkaOS" / "Knowledge Base"

_HOW_TO_SET = (
    "Set it with --kb-dir, the ARKAOS_KB_DIR env var, or knowledge.kbDir "
    "in ~/.arkaos/config.json (absolute, or relative to the vault)."
)


def _configured_kb_dir(config_path: Path | None = None) -> Path | None:
    """``knowledge.kbDir`` from config — absolute, or vault-relative."""
    cfg = Path(config_path or knowledge_vault.CONFIG_PATH)
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        raw = str((data.get("knowledge") or {}).get("kbDir") or "").strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        raw = ""
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    vault_path = knowledge_vault.resolve_vault_path(config_path)
    return (vault_path / path) if vault_path else None


def _default_kb_dir(config_path: Path | None = None) -> Path | None:
    """Config ``knowledge.kbDir`` first, else vault + portable subpath."""
    configured = _configured_kb_dir(config_path)
    if configured is not None:
        return configured
    vault_path = knowledge_vault.resolve_vault_path(config_path)
    return (vault_path / _KB_SUBPATH) if vault_path else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arkaos-reorganize",
        description="Aggregate recent KB artifacts into a propose-only "
                    "markdown report. Never modifies agent YAMLs.",
    )
    parser.add_argument(
        "--since-days", type=int, default=7,
        help="Window in days for first_seen/last_seen filter (default: 7).",
    )
    parser.add_argument(
        "--kb-dir", type=Path, default=None,
        help="Override the KB directory to scan (default: ArkaOS vault).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the report to stdout, do not write to disk.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:])
    env_dir = os.environ.get("ARKAOS_KB_DIR", "").strip()
    kb_dir = args.kb_dir or (Path(env_dir) if env_dir else _default_kb_dir())
    if kb_dir is None:
        print(
            "reorganizer: no KB directory is configured and no vault is set, "
            "so there is nothing to scan. " + _HOW_TO_SET,
            file=sys.stderr,
        )
        return 2

    try:
        report = build_proposal(
            kb_dir,
            since_days=args.since_days,
            dry_run=args.dry_run,
        )
    except KbDirMissingError:
        print(
            f"reorganizer: KB directory does not exist: {kb_dir}\n"
            "A missing KB is not an empty KB — refusing to report zero "
            "artifacts for a path that was never scanned. " + _HOW_TO_SET,
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(report.report_markdown)
        return 0

    print(f"Artifacts: {report.artifact_count}")
    for cat, count in sorted(report.by_category.items()):
        print(f"  {cat}: {count}")
    if report.report_path is not None:
        print(f"Report: {report.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
