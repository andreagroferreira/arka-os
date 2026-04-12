"""Agent provisioner — copies baseline agents into each project's .claude/agents/.

Resolves stack-based allowlists (plus the _base allowlist applied to every
project), locates source agent files under departments/**/agents/, and
materializes them as flat markdown files with YAML frontmatter the project's
Claude Code can consume.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from core.sync.schema import AgentProvisionResult, Project


def _core_root() -> Path:
    env = os.environ.get("ARKAOS_CORE_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def resolve_allowlist(stack: list[str]) -> list[str]:
    """Return the union of baseline agent names for the given stack tokens."""
    core = _core_root()
    allowlist_dir = core / "config" / "agent-allowlists"
    agents: set[str] = set()

    _extend_from_file(allowlist_dir / "_base.yaml", agents)
    for stack_name in stack:
        _extend_from_file(allowlist_dir / f"{stack_name.lower()}.yaml", agents)

    return sorted(agents)


def sync_project_agents(project: Project) -> AgentProvisionResult:
    """Materialize baseline agent markdown files in <project>/.claude/agents/."""
    try:
        return _do_sync(project)
    except Exception as exc:  # noqa: BLE001
        return AgentProvisionResult(
            path=project.path, status="error", error=str(exc)
        )


def sync_all_agents(projects: list[Project]) -> list[AgentProvisionResult]:
    return [sync_project_agents(p) for p in projects]


def _extend_from_file(path: Path, agents: set[str]) -> None:
    if not path.exists():
        return
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return
    for name in data.get("baseline", []) or []:
        if isinstance(name, str):
            agents.add(name)


def _do_sync(project: Project) -> AgentProvisionResult:
    core = _core_root()
    agents_dir = Path(project.path) / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    allowlist = resolve_allowlist(project.stack)
    added: list[str] = []
    unchanged: list[str] = []
    errored: list[str] = []

    for name in allowlist:
        rendered = _render_agent(core, name)
        if rendered is None:
            errored.append(name)
            continue

        target = agents_dir / f"{name}.md"
        if target.exists() and target.read_text() == rendered:
            unchanged.append(name)
            continue
        target.write_text(rendered)
        added.append(name)

    status = "error" if errored and not added and not unchanged else (
        "updated" if added else "unchanged"
    )
    return AgentProvisionResult(
        path=project.path,
        status=status,
        agents_added=added,
        agents_unchanged=unchanged,
        agents_errored=errored,
    )


def _render_agent(core: Path, name: str) -> str | None:
    yaml_path = _find_agent_file(core, name, ".yaml")
    md_path = _find_agent_file(core, name, ".md")

    if yaml_path is None and md_path is None:
        return None

    parts: list[str] = []
    if yaml_path is not None:
        parts.append("---")
        parts.append(yaml_path.read_text().strip())
        parts.append("---")
    if md_path is not None:
        parts.append(md_path.read_text().rstrip())

    return "\n".join(parts) + "\n"


def _find_agent_file(core: Path, name: str, suffix: str) -> Path | None:
    for dept in (core / "departments").iterdir() if (core / "departments").exists() else []:
        candidate = dept / "agents" / f"{name}{suffix}"
        if candidate.exists():
            return candidate
    return None
