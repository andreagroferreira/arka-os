"""Project discovery for the ArkaOS Sync Engine.

Discovers projects from 3 sources: descriptors, filesystem, and ecosystems.
Detects tech stacks and deduplicates across sources.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from core.sync.schema import Project


# --- Stack detection helpers ---

def _detect_from_composer(project_path: Path) -> list[str]:
    composer = project_path / "composer.json"
    if not composer.exists():
        return []
    try:
        data = json.loads(composer.read_text())
        require = data.get("require", {})
        if "laravel/framework" in require:
            return ["php", "laravel"]
        return ["php"]
    except (json.JSONDecodeError, OSError):
        return []


def _detect_from_package_json(project_path: Path) -> list[str]:
    pkg = project_path / "package.json"
    if not pkg.exists():
        return []
    try:
        data = json.loads(pkg.read_text())
        deps = {
            **data.get("dependencies", {}),
            **data.get("devDependencies", {}),
        }
        stack: list[str] = []
        if "nuxt" in deps:
            stack.extend(["javascript", "nuxt", "vue"])
        elif "vue" in deps:
            stack.extend(["javascript", "vue"])
        elif "next" in deps:
            stack.extend(["javascript", "next", "react"])
        elif "react" in deps:
            stack.extend(["javascript", "react"])
        else:
            stack.append("javascript")
        return stack
    except (json.JSONDecodeError, OSError):
        return []


def _detect_from_pyproject(project_path: Path) -> list[str]:
    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return []
    return ["python"]


def detect_stack(project_path: Path) -> list[str]:
    """Detect tech stack from project files.

    Checks composer.json, package.json, and pyproject.toml in order.
    Returns a deduplicated list of detected technologies.
    """
    stack: list[str] = []
    stack.extend(_detect_from_composer(project_path))
    stack.extend(_detect_from_package_json(project_path))
    stack.extend(_detect_from_pyproject(project_path))
    seen: set[str] = set()
    result: list[str] = []
    for item in stack:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# --- Descriptor discovery helpers ---

def _parse_descriptor_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _read_descriptor_item(item: Path) -> dict:
    """Read a descriptor file and return its frontmatter as a dict."""
    try:
        return _parse_descriptor_frontmatter(item.read_text())
    except OSError:
        return {}


def _process_descriptor_item(item: Path, descriptor_dir: Path) -> "Project | None":
    """Parse a single descriptor file and return a Project or None."""
    fm = _read_descriptor_item(item)
    raw_path = fm.get("path", "")
    if not raw_path:
        return None
    project_path = Path(raw_path)
    if not project_path.exists():
        return None
    name = fm.get("name", project_path.name)
    stack = detect_stack(project_path)
    return Project(
        path=str(project_path),
        name=name,
        ecosystem=fm.get("ecosystem") or None,
        stack=stack,
        descriptor_path=str(item),
        has_mcp_json=(project_path / ".mcp.json").exists(),
        has_settings=(project_path / ".claude").is_dir(),
    )


def discover_from_descriptors(descriptor_dir: Path) -> list[Project]:
    """Discover projects from .md descriptor files with YAML frontmatter.

    Reads .md files in descriptor_dir and PROJECT.md in subdirectories.
    Skips entries whose paths don't exist on the filesystem.
    """
    if not descriptor_dir.exists():
        return []

    candidates: list[Path] = list(descriptor_dir.glob("*.md"))
    for subdir in descriptor_dir.iterdir():
        if subdir.is_dir():
            project_md = subdir / "PROJECT.md"
            if project_md.exists():
                candidates.append(project_md)

    projects: list[Project] = []
    for item in candidates:
        project = _process_descriptor_item(item, descriptor_dir)
        if project is not None:
            projects.append(project)

    return projects


# --- Filesystem discovery ---

def discover_from_filesystem(scan_dirs: list[Path]) -> list[Project]:
    """Discover projects by scanning directories for .mcp.json or .claude/ markers."""
    projects: list[Project] = []
    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for subdir in scan_dir.iterdir():
            if not subdir.is_dir():
                continue
            has_mcp = (subdir / ".mcp.json").is_file()
            has_claude = (subdir / ".claude").is_dir()
            has_claude_md = (subdir / "CLAUDE.md").is_file()
            if not has_mcp and not has_claude and not has_claude_md:
                continue
            stack = detect_stack(subdir)
            projects.append(Project(
                path=str(subdir),
                name=subdir.name,
                stack=stack,
                has_mcp_json=has_mcp,
                has_settings=has_claude,
            ))

    return projects


# --- Ecosystem discovery ---

def discover_from_ecosystems(ecosystems_file: Path) -> list[Project]:
    """Discover projects from an ecosystems.json registry file."""
    if not ecosystems_file.exists():
        return []
    try:
        data = json.loads(ecosystems_file.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    projects: list[Project] = []
    for eco_key, eco_data in data.get("ecosystems", {}).items():
        for proj_name, proj_path_str in eco_data.get("project_paths", {}).items():
            proj_path = Path(proj_path_str)
            if not proj_path.exists():
                continue
            stack = detect_stack(proj_path)
            projects.append(Project(
                path=str(proj_path),
                name=proj_name,
                ecosystem=eco_key,
                stack=stack,
                has_mcp_json=(proj_path / ".mcp.json").exists(),
                has_settings=(proj_path / ".claude").is_dir(),
            ))

    return projects


# --- Merge and deduplication helpers ---

def _merge_project(primary: Project, secondary: Project) -> Project:
    """Merge two Project records — primary data wins over secondary."""
    return Project(
        path=primary.path,
        name=primary.name,
        ecosystem=primary.ecosystem or secondary.ecosystem,
        stack=primary.stack if primary.stack else secondary.stack,
        descriptor_path=primary.descriptor_path or secondary.descriptor_path,
        has_mcp_json=primary.has_mcp_json or secondary.has_mcp_json,
        has_settings=primary.has_settings or secondary.has_settings,
    )


def _deduplicate(projects: list[Project]) -> list[Project]:
    """Deduplicate projects by resolved absolute path. First entry wins."""
    seen: dict[str, Project] = {}
    for project in projects:
        key = str(Path(project.path).resolve())
        if key not in seen:
            seen[key] = project
        else:
            seen[key] = _merge_project(seen[key], project)
    return list(seen.values())


def discover_all_projects(
    descriptor_dir: Path,
    scan_dirs: list[Path],
    ecosystems_file: Path,
) -> list[Project]:
    """Discover all projects from all sources, deduplicate, and sort by name.

    Descriptor data wins over filesystem/ecosystem data during merging.
    """
    descriptor_projects = discover_from_descriptors(descriptor_dir)
    filesystem_projects = discover_from_filesystem(scan_dirs)
    ecosystem_projects = discover_from_ecosystems(ecosystems_file)

    all_projects = descriptor_projects + ecosystem_projects + filesystem_projects
    deduplicated = _deduplicate(all_projects)

    return sorted(deduplicated, key=lambda p: p.name)
