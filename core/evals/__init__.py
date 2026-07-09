"""Eval harness foundation (E2E audit v4.3.6 P2).

Reference eval tasks per department (config/evals/*.yaml) plus the
QG-verdict label log — the free labeled dataset every future eval run
or local-model distillation consumes.
"""

from core.evals.schema import EvalTask, load_eval_tasks
from core.evals.verdict_labels import (
    load_verdict_labels,
    record_verdict_label,
)

__all__ = [
    "EvalTask",
    "load_eval_tasks",
    "load_verdict_labels",
    "record_verdict_label",
]
