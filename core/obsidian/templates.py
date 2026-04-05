"""Obsidian frontmatter templates and conventions."""

from datetime import date, datetime
from typing import Any


def build_frontmatter(
    department: str = "",
    agent: str = "",
    workflow: str = "",
    tags: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Build YAML frontmatter for an Obsidian note.

    Returns:
        String with opening/closing --- delimiters.
    """
    fields: dict[str, Any] = {}
    fields["created"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    fields["source"] = "arkaos"

    if department:
        fields["department"] = department
    if agent:
        fields["agent"] = agent
    if workflow:
        fields["workflow"] = workflow

    all_tags = ["arkaos"]
    if department:
        all_tags.append(f"dept/{department}")
    if tags:
        all_tags.extend(tags)
    fields["tags"] = all_tags

    if extra:
        fields.update(extra)

    lines = ["---"]
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")

    return "\n".join(lines)


def resolve_template_vars(path: str, vars: dict[str, str] | None = None) -> str:
    """Resolve template variables in an Obsidian path.

    Supported variables:
        {project}, {department}, {agent}, {date}, {number}, {name}
    """
    defaults = {
        "date": date.today().isoformat(),
        "project": "Default",
        "department": "general",
        "agent": "unknown",
        "number": "001",
        "name": "untitled",
    }
    if vars:
        defaults.update(vars)

    result = path
    for key, value in defaults.items():
        result = result.replace(f"{{{key}}}", value)

    return result
