"""Content syncer for the ArkaOS Sync Engine.

Syncs CLAUDE.md (with intelligent merge), rules, hooks, and a generated
constitution excerpt into each project's .claude/ directory.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from core.sync.content_merger import merge_managed_content
from core.sync.schema import ContentSyncResult, Project


def _core_root() -> Path:
    # Honors ARKAOS_CORE_ROOT env var for tests; falls back to repo root.
    env = os.environ.get("ARKAOS_CORE_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def sync_project_content(project: Project) -> ContentSyncResult:
    """Sync CLAUDE.md, rules, hooks, and constitution excerpt for a project."""
    try:
        return _do_sync(project)
    except Exception as exc:  # noqa: BLE001
        return ContentSyncResult(
            path=project.path, status="error", error=str(exc)
        )


def _do_sync(project: Project) -> ContentSyncResult:
    core = _core_root()
    version = (core / "VERSION").read_text().strip()
    project_claude = Path(project.path) / ".claude"
    project_claude.mkdir(parents=True, exist_ok=True)

    updated: list[str] = []
    unchanged: list[str] = []
    errored: list[str] = []

    _sync_claude_md(core, project, project_claude, version, updated, unchanged, errored)
    _sync_rules(core, project_claude, updated, unchanged, errored)
    _sync_hooks(core, project_claude, updated, unchanged, errored)
    _sync_constitution(core, project_claude, updated, unchanged, errored)

    if errored:
        status = "error"
    elif updated:
        status = "updated"
    else:
        status = "unchanged"
    return ContentSyncResult(
        path=project.path,
        status=status,
        artefacts_updated=updated,
        artefacts_unchanged=unchanged,
        artefacts_errored=errored,
    )


def _sync_claude_md(
    core: Path,
    project: Project,
    project_claude: Path,
    version: str,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    base = (core / "config" / "user-claude.md").read_text()
    overlays_dir = core / "config" / "standards" / "claude-md-overlays"
    overlays: list[str] = []
    for stack in project.stack:
        overlay = overlays_dir / f"{stack}.md"
        if overlay.exists():
            overlays.append(overlay.read_text())

    managed_content = "\n\n".join([base, *overlays]).strip()
    target_file = project_claude / "CLAUDE.md"
    target_text = target_file.read_text() if target_file.exists() else ""

    result = merge_managed_content(target_text, managed_content, version)
    if result.status == "error":
        errored.append(f"CLAUDE.md: {result.error}")
        sidecar = target_file.with_suffix(".md.arkaos-new")
        sidecar.write_text(managed_content)
        return
    if result.status == "unchanged":
        unchanged.append("CLAUDE.md")
        return
    target_file.write_text(result.new_text)
    updated.append("CLAUDE.md")


def _sync_rules(
    core: Path,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    # Copies/updates rules from core standards; does not delete orphan files.
    src = core / "config" / "standards"
    dst = project_claude / "rules"
    dst.mkdir(parents=True, exist_ok=True)
    for rule in src.glob("*.md"):
        target = dst / rule.name
        src_text = rule.read_text()
        if target.exists() and target.read_text() == src_text:
            unchanged.append(f"rules/{rule.name}")
            continue
        target.write_text(src_text)
        updated.append(f"rules/{rule.name}")


def _sync_hooks(
    core: Path,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    src = core / "config" / "hooks"
    dst = project_claude / "hooks"
    dst.mkdir(parents=True, exist_ok=True)
    for hook in src.glob("*.sh"):
        target = dst / hook.name
        src_text = hook.read_text()
        if target.exists() and target.read_text() == src_text:
            unchanged.append(f"hooks/{hook.name}")
            continue
        shutil.copy2(hook, target)
        target.chmod(0o755)
        updated.append(f"hooks/{hook.name}")


def _sync_constitution(
    core: Path,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    src = core / "config" / "constitution.yaml"
    target = project_claude / "constitution-applicable.md"
    data = yaml.safe_load(src.read_text()) or {}
    rules = data.get("rules", [])
    lines = ["# ArkaOS Constitution — Applicable Rules", ""]
    for rule in rules:
        lines.append(f"- **{rule.get('name', '?')}** — {rule.get('level', '?')}")
    body = "\n".join(lines) + "\n"
    if target.exists() and target.read_text() == body:
        unchanged.append("constitution-applicable.md")
        return
    target.write_text(body)
    updated.append("constitution-applicable.md")


def sync_all_content(projects: list[Project]) -> list[ContentSyncResult]:
    """Sync content artefacts for all projects."""
    return [sync_project_content(p) for p in projects]
