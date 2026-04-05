"""Agent YAML loader — reads agent definitions from YAML files."""

from pathlib import Path
from typing import Optional

import yaml
from core.agents.schema import Agent


def load_agent(path: str | Path) -> Agent:
    """Load an agent from a YAML file.

    Args:
        path: Path to the agent YAML file.

    Returns:
        Validated Agent instance.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid or doesn't match schema.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Agent file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Empty agent file: {path}")

    return Agent.model_validate(data)


def load_all_agents(
    base_dir: str | Path,
    department: Optional[str] = None,
) -> list[Agent]:
    """Load all agents from a directory tree.

    Scans for YAML files in agents/ subdirectories of each department.

    Args:
        base_dir: Root directory containing department folders.
        department: If set, only load agents from this department.

    Returns:
        List of validated Agent instances.
    """
    base_dir = Path(base_dir)
    agents: list[Agent] = []
    errors: list[str] = []

    if department:
        search_dirs = [base_dir / department / "agents"]
    else:
        search_dirs = list(base_dir.glob("*/agents"))

    for agents_dir in search_dirs:
        if not agents_dir.is_dir():
            continue
        for yaml_file in sorted(agents_dir.glob("*.yaml")):
            try:
                agent = load_agent(yaml_file)
                agents.append(agent)
            except Exception as e:
                errors.append(f"{yaml_file}: {e}")

    if errors:
        import warnings
        for err in errors:
            warnings.warn(f"Failed to load agent: {err}")

    return agents


def agent_to_yaml(agent: Agent) -> str:
    """Serialize an Agent to YAML string.

    Args:
        agent: Agent instance to serialize.

    Returns:
        YAML string representation.
    """
    data = agent.model_dump(mode="json")
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
