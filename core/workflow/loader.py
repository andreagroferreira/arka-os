"""Workflow YAML loader."""

from pathlib import Path
import yaml

from core.workflow.schema import Workflow


def load_workflow(path: str | Path) -> Workflow:
    """Load a workflow from a YAML file.

    Args:
        path: Path to the workflow YAML file.

    Returns:
        Validated Workflow instance.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Empty workflow file: {path}")

    return Workflow.model_validate(data)
