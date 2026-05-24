"""Stale-aware reorganizer scheduler (PR24 v2.46.0).

Cron-less. The trigger is file existence: when today's proposal file
isn't on disk, ``is_stale`` returns True and the session-start hook
fires the reorganizer in background. Multiple sessions per day no-op
because the proposal file now exists.

Read-only — the actual generation lives in
``core.cognition.reorganizer.build_proposal``. This module only
inspects state and renders status.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PROPOSAL_DIR = Path.home() / ".arkaos" / "reorganize-proposals"
_ARTIFACT_COUNT_RE = re.compile(r"Artifacts:\s*\*\*(\d+)\*\*")


@dataclass(frozen=True)
class SchedulerStatus:
    """Snapshot of the reorganizer's daily-proposal state."""
    today_proposal_exists: bool
    today_proposal_path: Path
    last_generated_at: str | None
    artifact_count: int | None


def is_stale(*, output_dir: Path | None = None) -> bool:
    """Return True iff today's proposal file is missing."""
    path = _today_proposal_path(output_dir)
    return not path.is_file()


def status_summary(*, output_dir: Path | None = None) -> SchedulerStatus:
    """Return the current scheduler snapshot for /arka status."""
    path = _today_proposal_path(output_dir)
    if not path.is_file():
        return SchedulerStatus(
            today_proposal_exists=False,
            today_proposal_path=path,
            last_generated_at=None,
            artifact_count=None,
        )
    mtime = _format_mtime(path)
    count = _parse_artifact_count(path)
    return SchedulerStatus(
        today_proposal_exists=True,
        today_proposal_path=path,
        last_generated_at=mtime,
        artifact_count=count,
    )


def render_status_md(status: SchedulerStatus) -> str:
    """Render a SchedulerStatus as a markdown block for /arka status."""
    if not status.today_proposal_exists:
        return (
            "## Reorganization (today)\n\n"
            "No proposal generated yet — will fire on next session start."
        )
    lines = [
        "## Reorganization (today)",
        "",
        f"- Proposal: `{status.today_proposal_path}`",
    ]
    if status.last_generated_at:
        lines.append(f"- Generated: {status.last_generated_at}")
    if status.artifact_count is not None:
        lines.append(f"- Artifacts surfaced: **{status.artifact_count}**")
    return "\n".join(lines)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _today_proposal_path(output_dir: Path | None) -> Path:
    base = Path(output_dir) if output_dir is not None else _DEFAULT_PROPOSAL_DIR
    return base / f"{_today_iso()}.md"


def _format_mtime(path: Path) -> str | None:
    try:
        ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return ts.isoformat(timespec="seconds")
    except OSError:
        return None


def _parse_artifact_count(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _ARTIFACT_COUNT_RE.search(text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None
