"""
ARKA OS — MCP Prompts Server.

Exposes all ARKA OS department commands as MCP prompts so they work in
both Claude Code and Claude Desktop.

Usage:
    uv run server.py
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import Prompt, PromptArgument

from commands import COMMANDS

mcp = FastMCP(
    "arka-prompts",
    instructions="ARKA OS department commands. Select a prompt to run an ARKA OS command.",
)


def _find_skills_dir() -> Path:
    """Resolve the base skills directory where SKILL.md files live.

    Resolution order:
    1. ARKA_OS env var  ->  parent dir is the skills root
    2. ~/.claude/skills/arka/.repo-path  ->  dev mode (read repo path from file)
    3. Fallback to ~/.claude/skills/
    """
    arka_os = os.environ.get("ARKA_OS")
    if arka_os:
        arka_path = Path(arka_os)
        if arka_path.is_dir():
            return arka_path.parent  # e.g. ~/.claude/skills/

    # Dev mode: .repo-path points to the repo checkout
    repo_path_file = Path.home() / ".claude" / "skills" / "arka" / ".repo-path"
    if repo_path_file.exists():
        repo_path = Path(repo_path_file.read_text().strip())
        if repo_path.is_dir():
            return repo_path  # Return repo root for dev mode resolution

    return Path.home() / ".claude" / "skills"


def _load_skill(skill_dir: str) -> str | None:
    """Load SKILL.md content for the given skill directory name.

    Tries installed location first, then falls back to dev repo layout.
    """
    skills_base = _find_skills_dir()

    # Installed layout: ~/.claude/skills/<skill_dir>/SKILL.md
    installed = skills_base / skill_dir / "SKILL.md"
    if installed.is_file():
        return installed.read_text(encoding="utf-8")

    # Dev repo layout: <repo>/departments/<dept>/SKILL.md
    # Map skill_dir names to department directories
    dept_map = {
        "arka": "arka",
        "arka-dev": "departments/dev",
        "arka-marketing": "departments/marketing",
        "arka-ecommerce": "departments/ecommerce",
        "arka-finance": "departments/finance",
        "arka-operations": "departments/operations",
        "arka-strategy": "departments/strategy",
        "arka-knowledge": "departments/knowledge",
        "arka-scaffold": "departments/dev/skills/scaffold",
    }
    if skill_dir in dept_map:
        dev_path = skills_base / dept_map[skill_dir] / "SKILL.md"
        if dev_path.is_file():
            return dev_path.read_text(encoding="utf-8")

    return None


def _build_instruction(cmd_key: str, cmd: dict, user_args: dict[str, str]) -> str:
    """Build the prompt message returned to the LLM."""
    parts: list[str] = []

    # Header with command context
    parts.append(f"# ARKA OS — {cmd['title']}")
    parts.append("")
    parts.append(f"**Command:** `{cmd['slash_command']}`")

    # Include user-provided arguments
    if user_args:
        parts.append("")
        parts.append("**User input:**")
        for arg_name, arg_value in user_args.items():
            if arg_value:
                parts.append(f"- **{arg_name}:** {arg_value}")

    parts.append("")
    parts.append("---")
    parts.append("")

    # Load and append the full SKILL.md
    skill_content = _load_skill(cmd["skill_dir"])
    if skill_content:
        parts.append(skill_content)
    else:
        parts.append(
            f"*SKILL.md not found for `{cmd['skill_dir']}`. "
            f"Ensure ARKA OS is installed (`bash install.sh`).*"
        )

    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(
        f"Now execute the `{cmd['slash_command']}` command "
        f"with the user input provided above."
    )

    return "\n".join(parts)


def _make_prompt_fn(cmd_key: str, cmd: dict):
    """Create a prompt handler function for a command."""
    arg_names = [a["name"] for a in cmd["arguments"]]

    def handler(**kwargs: str) -> str:
        user_args = {name: kwargs.get(name, "") for name in arg_names}
        return _build_instruction(cmd_key, cmd, user_args)

    return handler


# Register all commands as prompts
for cmd_key, cmd_data in COMMANDS.items():
    prompt_args = [
        PromptArgument(
            name=a["name"],
            description=a["description"],
            required=a["required"],
        )
        for a in cmd_data["arguments"]
    ]

    prompt = Prompt(
        name=cmd_key,
        description=f"{cmd_data['title']}: {cmd_data['description']}",
        arguments=prompt_args or None,
        fn=_make_prompt_fn(cmd_key, cmd_data),
    )
    mcp.add_prompt(prompt)


if __name__ == "__main__":
    mcp.run(transport="stdio")
