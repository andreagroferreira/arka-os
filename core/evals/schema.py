"""Eval task schema and loader.

Reference tasks live in ``config/evals/<department>.yaml`` — one YAML
list per department, versioned with the repo so evals evolve with the
agents they measure. See ADR 2026-07-09-evals-and-distillation.md.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

DEFAULT_EVALS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "config" / "evals"
)


class EvalTask(BaseModel):
    """One reference task an agent/department run is judged against."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    department: str
    prompt: str = Field(min_length=10)
    expected_properties: list[str] = Field(
        min_length=1,
        description="Verifiable properties the deliverable must exhibit",
    )
    rubric: str = Field(
        default="",
        description="Free-text judging guidance beyond the properties",
    )
    tags: list[str] = Field(default_factory=list)


def load_eval_tasks(evals_dir: Path | None = None) -> list[EvalTask]:
    """Load every task from config/evals/*.yaml, validated.

    Raises on schema violations or duplicate ids — a broken eval set
    must fail loudly, not skew results silently.
    """
    base = evals_dir or DEFAULT_EVALS_DIR
    tasks: list[EvalTask] = []
    seen: set[str] = set()
    for path in sorted(base.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for item in raw:
            task = EvalTask.model_validate(item)
            if task.id in seen:
                raise ValueError(f"duplicate eval task id: {task.id}")
            seen.add(task.id)
            tasks.append(task)
    return tasks
