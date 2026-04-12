"""Descriptor syncer for the ArkaOS Sync Engine.

Syncs project descriptor YAML frontmatter: auto-pauses inactive projects,
archives missing paths, and updates detected stacks.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.sync.schema import DescriptorSyncResult, Project

_PAUSE_THRESHOLD_DAYS = 30
_REACTIVATE_THRESHOLD_DAYS = 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_descriptor(project: Project) -> DescriptorSyncResult:
    """Sync a single project's descriptor file.

    Reads the descriptor, checks if the project path exists, compares the
    detected stack, checks git activity, and writes any updates back.
    """
    if not project.descriptor_path:
        return DescriptorSyncResult(path=project.path, status="unchanged")

    desc_path = Path(project.descriptor_path)
    if not desc_path.exists():
        return DescriptorSyncResult(path=project.path, status="unchanged")

    try:
        return _do_sync(project)
    except Exception as exc:  # noqa: BLE001
        return DescriptorSyncResult(
            path=project.path, status="error", error=str(exc)
        )


def _do_sync(project: Project) -> DescriptorSyncResult:
    """Execute the descriptor sync logic for a single project."""
    desc_path = Path(project.descriptor_path)  # type: ignore[arg-type]
    text = desc_path.read_text()
    frontmatter, body = _split_frontmatter(text)
    changes: list[str] = []

    if not Path(project.path).exists():
        frontmatter["status"] = "archived"
        changes.append("status: archived (path not found)")
        _write_descriptor(desc_path, frontmatter, body)
        return DescriptorSyncResult(
            path=project.path, status="updated", changes=changes
        )

    _check_stack(frontmatter, project.stack, changes)
    _check_activity(frontmatter, project.path, changes)

    if not changes:
        return DescriptorSyncResult(path=project.path, status="unchanged")

    _write_descriptor(desc_path, frontmatter, body)
    return DescriptorSyncResult(
        path=project.path, status="updated", changes=changes
    )


def sync_all_descriptors(projects: list[Project]) -> list[DescriptorSyncResult]:
    """Sync descriptor files for all projects."""
    return [sync_descriptor(p) for p in projects]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into its YAML frontmatter dict and body string.

    Expects the file to start with '---' and have a closing '---' marker.
    Returns ({}, full_text) if frontmatter markers are not found.
    """
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_yaml = parts[1]
    body = parts[2]
    parsed = yaml.safe_load(raw_yaml) or {}
    return parsed, body


def _normalize_stack_item(item: str) -> str:
    """Normalize a stack item to lowercase first word for comparison.

    Returns an empty string for empty or whitespace-only input so that
    iteration over malformed stacks (e.g., a scalar YAML string) does not
    crash with IndexError.
    """
    parts = item.strip().lower().split()
    return parts[0] if parts else ""


def _check_stack(
    frontmatter: dict, detected_stack: list[str], changes: list[str]
) -> None:
    """Compare frontmatter stack with detected stack and update if different.

    Tolerates malformed frontmatter where ``stack`` is a scalar string or
    ``None`` by coercing it to a list first. A scalar value is always
    rewritten as a list even when the normalized tokens match. Empty or
    whitespace-only items are dropped during normalization.
    """
    raw_fm_stack = frontmatter.get("stack")
    needs_type_coercion = not isinstance(raw_fm_stack, list)

    if raw_fm_stack is None:
        fm_stack: list[str] = []
    elif isinstance(raw_fm_stack, str):
        fm_stack = [raw_fm_stack]
    elif isinstance(raw_fm_stack, list):
        fm_stack = [s for s in raw_fm_stack if isinstance(s, str)]
    else:
        fm_stack = []

    fm_normalized = {
        token for s in fm_stack if (token := _normalize_stack_item(s))
    }
    detected_normalized = {
        token for s in detected_stack if (token := _normalize_stack_item(s))
    }

    if fm_normalized != detected_normalized and detected_stack:
        frontmatter["stack"] = detected_stack
        changes.append(f"stack updated: {fm_stack} -> {detected_stack}")
    elif needs_type_coercion and detected_stack:
        frontmatter["stack"] = detected_stack
        changes.append(f"stack coerced to list: {raw_fm_stack!r} -> {detected_stack}")


def _check_activity(
    frontmatter: dict, project_path: str, changes: list[str]
) -> None:
    """Check git activity and auto-pause or auto-reactivate the project."""
    days = _get_last_commit_days(project_path)
    if days is None:
        return

    current_status = frontmatter.get("status", "active")

    if days > _PAUSE_THRESHOLD_DAYS and current_status == "active":
        frontmatter["status"] = "paused"
        changes.append(f"status: active -> paused ({days}d since last commit)")
    elif days < _REACTIVATE_THRESHOLD_DAYS and current_status == "paused":
        frontmatter["status"] = "active"
        changes.append(f"status: paused -> active ({days}d since last commit)")


def _get_last_commit_days(project_path: str) -> int | None:
    """Return days since the last git commit in project_path, or None."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw = result.stdout.strip()
        if not raw:
            return None

        commit_dt = datetime.fromisoformat(raw)
        if commit_dt.tzinfo is None:
            commit_dt = commit_dt.replace(tzinfo=timezone.utc)

        now = datetime.now(tz=timezone.utc)
        return (now - commit_dt).days
    except Exception:  # noqa: BLE001
        return None


def _write_descriptor(desc_path: Path, frontmatter: dict, body: str) -> None:
    """Write updated frontmatter and preserved body back to the descriptor file."""
    fm_text = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    desc_path.write_text(f"---\n{fm_text}---{body}")
