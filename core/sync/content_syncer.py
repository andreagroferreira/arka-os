"""Content syncer for the ArkaOS Sync Engine.

Syncs CLAUDE.md (with intelligent merge), rules, hooks, and a generated
constitution excerpt into each project's .claude/ directory.

Stack conventions deploy as path-scoped rule files
(``.claude/rules/arkaos-stack-<stack>.md``, source
``config/standards/stack-rules/``) instead of being concatenated into
the CLAUDE.md managed block: the ``paths:`` frontmatter makes the
runtime load each convention only when a matching file is read, and the
``arkaos-stack-`` namespace lets the syncer remove stale files when a
project's stack changes. Stack slugs are case-folded and resolved
through ``_STACK_ALIASES`` (project descriptors say ``javascript`` 14x,
``vue`` 9x, ``php`` 9x — none of which matched an overlay filename
under the old exact-name scheme).
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
    except Exception as exc:
        return ContentSyncResult(
            path=project.path, status="error", error=str(exc)
        )


def _do_sync(project: Project) -> ContentSyncResult:
    core = _core_root()
    version = (core / "VERSION").read_text(encoding="utf-8").strip()
    project_claude = Path(project.path) / ".claude"
    project_claude.mkdir(parents=True, exist_ok=True)

    updated: list[str] = []
    unchanged: list[str] = []
    errored: list[str] = []

    _sync_claude_md(core, project, project_claude, version, updated, unchanged, errored)
    _sync_rules(core, project_claude, updated, unchanged, errored)
    _sync_stack_rules(core, project, project_claude, updated, unchanged, errored)
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
    # Stack conventions live in path-scoped rule files (_sync_stack_rules);
    # the managed block carries only the shared base.
    managed_content = (
        (core / "config" / "user-claude.md").read_text(encoding="utf-8").strip()
    )
    target_file = project_claude / "CLAUDE.md"
    target_text = target_file.read_text(encoding="utf-8") if target_file.exists() else ""

    result = merge_managed_content(target_text, managed_content, version)
    if result.status == "error":
        errored.append(f"CLAUDE.md: {result.error}")
        sidecar = target_file.with_suffix(".md.arkaos-new")
        sidecar.write_text(managed_content, encoding="utf-8")
        return
    if result.status == "unchanged":
        unchanged.append("CLAUDE.md")
        return
    target_file.write_text(result.new_text, encoding="utf-8")
    updated.append("CLAUDE.md")


# Descriptor slug -> stack-rules filename. Slugs are case-folded first.
_STACK_ALIASES: dict[str, str] = {
    "js": "node",
    "javascript": "node",
    "ts": "node",
    "typescript": "node",
    "vuejs": "vue",
    "vue3": "vue",
    "next": "react",
    "nextjs": "react",
    "next.js": "react",
    "fastapi": "python",
    "django": "python",
    "flask": "python",
}
_STACK_RULE_PREFIX = "arkaos-stack-"


def _resolve_stacks(stacks: list[str], rules_src: Path) -> list[str]:
    """Case-folded, alias-resolved, deduped stacks that have a rule file."""
    resolved: list[str] = []
    for raw in stacks:
        slug = raw.strip().casefold()
        slug = _STACK_ALIASES.get(slug, slug)
        if slug and slug not in resolved and (rules_src / f"{slug}.md").is_file():
            resolved.append(slug)
    return resolved


def _sync_stack_rules(
    core: Path,
    project: Project,
    project_claude: Path,
    updated: list[str],
    unchanged: list[str],
    errored: list[str],
) -> None:
    """Deploy path-scoped stack rules; remove stale arkaos-stack files."""
    src = core / "config" / "standards" / "stack-rules"
    dst = project_claude / "rules"
    dst.mkdir(parents=True, exist_ok=True)
    stacks = _resolve_stacks(project.stack, src) if src.is_dir() else []
    expected = {f"{_STACK_RULE_PREFIX}{stack}.md" for stack in stacks}
    for stack in stacks:
        name = f"{_STACK_RULE_PREFIX}{stack}.md"
        target = dst / name
        src_text = (src / f"{stack}.md").read_text(encoding="utf-8")
        if target.exists() and target.read_text(encoding="utf-8") == src_text:
            unchanged.append(f"rules/{name}")
            continue
        target.write_text(src_text, encoding="utf-8")
        updated.append(f"rules/{name}")
    # The arkaos-stack- namespace is syncer-owned: files for stacks the
    # project no longer declares are removed (unlike generic rules,
    # which never delete orphans).
    for stale in dst.glob(f"{_STACK_RULE_PREFIX}*.md"):
        if stale.name not in expected:
            stale.unlink(missing_ok=True)
            updated.append(f"rules/{stale.name} (removed)")


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
        src_text = rule.read_text(encoding="utf-8")
        if target.exists() and target.read_text(encoding="utf-8") == src_text:
            unchanged.append(f"rules/{rule.name}")
            continue
        target.write_text(src_text, encoding="utf-8")
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
        src_text = hook.read_text(encoding="utf-8")
        if target.exists() and target.read_text(encoding="utf-8") == src_text:
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
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    rules = data.get("rules", [])
    lines = ["# ArkaOS Constitution — Applicable Rules", ""]
    for rule in rules:
        lines.append(f"- **{rule.get('name', '?')}** — {rule.get('level', '?')}")
    body = "\n".join(lines) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") == body:
        unchanged.append("constitution-applicable.md")
        return
    target.write_text(body, encoding="utf-8")
    updated.append("constitution-applicable.md")


def sync_all_content(projects: list[Project]) -> list[ContentSyncResult]:
    """Sync content artefacts for all projects."""
    return [sync_project_content(p) for p in projects]
