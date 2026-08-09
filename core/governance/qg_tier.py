"""Mechanical QG tier — computed from the real diff, never declared
(Gate Economy PR-6, operator-approved 2026-08-09).

The constitution mandated the full trio on every workflow while the
telemetry showed ~950 triad dispatches across 108 sessions with a 68%
rejection rate dominated by minor findings. The tier is derived from
the diff itself:

  - LIGHT — small (<= 3 files, <= 150 changed lines), single-domain
    (pure code or pure prose), and entirely OUTSIDE the sensitive
    surface. One reviewer chosen by content (Francisca for code,
    Eduardo for prose) plus Marta's aggregation.
  - FULL — everything else, and EVERY uncertainty: sensitive paths
    (governance, hooks, workflow, config, CI, installer, release
    tooling), mixed deltas, binary changes, underivable diffs.

The same primitives finally verify ``[arka:trivial]`` — the bypass was
a self-declaration no code ever counted (one file, under 10 lines).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from core.governance.carry_advisor import delta_kind
from core.governance.evidence_checks import _derive_changed_files, _diff_base

FILES_LIGHT_MAX = 3
LINES_LIGHT_MAX = 150
TRIVIAL_MAX_LINES = 10

# The surface where a small diff can still change how EVERYTHING ships:
# gates, hooks, workflows, config, CI, install and release tooling.
SENSITIVE_PREFIXES = (
    "core/governance/",
    "core/hooks/",
    "core/workflow/",
    "config/",
    ".github/",
    "installer/",
    "scripts/",
    "departments/quality/",
    "arka/skills/flow/",
)


def _is_sensitive(name: str) -> bool:
    path = PurePosixPath(name.strip())
    posix = str(path)
    if any(posix.startswith(prefix) for prefix in SENSITIVE_PREFIXES):
        return True
    base = path.name.lower()
    return base.startswith("dockerfile") or base.startswith(".env")


def _changed_line_count(
    project_dir: Path, changed: list[str]
) -> int | None:
    """added + deleted lines for ``changed``, or None (fail closed).

    Tracked changes come from ``git diff --numstat``; untracked files
    count their full line count. Binaries (``-`` in numstat) and any
    unreadable file return None — a diff whose size cannot be proven
    never tiers LIGHT.
    """
    base = _diff_base(project_dir)
    if base is None:
        return None
    try:
        proc = subprocess.run(
            ["git", "diff", "--numstat", base],
            cwd=project_dir, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    counted: dict[str, int] = {}
    for row in proc.stdout.splitlines():
        parts = row.split("\t")
        if len(parts) != 3:
            continue
        added, deleted, name = parts
        if added == "-" or deleted == "-":
            if name.strip() in set(changed):
                return None  # binary change in scope
            continue
        counted[name.strip()] = int(added) + int(deleted)
    total = 0
    for name in changed:
        clean = name.strip()
        if clean in counted:
            total += counted[clean]
            continue
        try:  # untracked new file — its whole content is the change
            content = (project_dir / clean).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        total += len(content.splitlines())
    return total


def _full(reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "tier": "FULL",
        "reviewer": None,
        "reasons": [reason],
        **extra,
    }


def compute_tier(
    project_dir: Path, changed: list[str] | None = None
) -> dict[str, Any]:
    """``{"tier", "reviewer", "reasons", ...}`` for the current diff."""
    project_dir = Path(project_dir)
    if changed is None:
        changed = _derive_changed_files(project_dir)
    if not changed:
        return _full("no derivable diff — the tier fails closed to FULL")
    sensitive = sorted({c for c in changed if _is_sensitive(c)})
    if sensitive:
        return _full(
            "sensitive surface touched: " + ", ".join(sensitive[:5]),
            files=len(changed),
        )
    if len(changed) > FILES_LIGHT_MAX:
        return _full(
            f"{len(changed)} files > {FILES_LIGHT_MAX}", files=len(changed),
        )
    kind = delta_kind(changed)
    if kind == "mixed":
        return _full(
            "mixed/unknown delta — both review domains may be touched",
            files=len(changed),
        )
    lines = _changed_line_count(project_dir, changed)
    if lines is None:
        return _full(
            "changed-line count not derivable (binary or unreadable)",
            files=len(changed),
        )
    if lines > LINES_LIGHT_MAX:
        return _full(
            f"{lines} changed lines > {LINES_LIGHT_MAX}",
            files=len(changed), lines_changed=lines,
        )
    reviewer = "francisca-tech" if kind == "code" else "eduardo-copy"
    return {
        "tier": "LIGHT",
        "reviewer": reviewer,
        "delta_kind": kind,
        "files": len(changed),
        "lines_changed": lines,
        "reasons": [
            f"{len(changed)} file(s), {lines} changed line(s), "
            f"{kind}-only, no sensitive surface"
        ],
    }


def validate_trivial(
    project_dir: Path, changed: list[str] | None = None
) -> dict[str, Any]:
    """Mechanical check behind ``[arka:trivial]`` (one file, <= 10 lines).

    The bypass was a self-declaration no code ever counted; every
    uncertainty answers ``trivial: false``.
    """
    project_dir = Path(project_dir)
    if changed is None:
        changed = _derive_changed_files(project_dir)
    if not changed:
        return {"trivial": False, "reason": "no derivable diff"}
    if len(changed) != 1:
        return {
            "trivial": False,
            "reason": f"{len(changed)} files changed — trivial is ONE file",
        }
    lines = _changed_line_count(project_dir, changed)
    if lines is None:
        return {"trivial": False, "reason": "line count not derivable"}
    if lines > TRIVIAL_MAX_LINES:
        return {
            "trivial": False,
            "reason": f"{lines} changed lines > {TRIVIAL_MAX_LINES}",
        }
    return {
        "trivial": True,
        "reason": f"1 file, {lines} changed line(s)",
        "file": changed[0],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.governance.qg_tier",
        description="Compute the mechanical QG tier for the current diff.",
    )
    parser.add_argument("project_dir", type=Path)
    parser.add_argument(
        "--changed-files", default="",
        help="comma-separated override; derived from git when omitted",
    )
    parser.add_argument(
        "--trivial", action="store_true",
        help="validate the [arka:trivial] claim instead of tiering",
    )
    args = parser.parse_args(argv)
    changed = [
        f for f in (args.changed_files or "").split(",") if f.strip()
    ] or None
    fn = validate_trivial if args.trivial else compute_tier
    print(json.dumps(fn(args.project_dir, changed), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
