"""Eval runner CLI — list tasks, corpus status, dispatch-ready prompts.

Evals reuse the Quality Gate as the judge (ADR 2026-07-09): a run is
the orchestrator dispatching a task prompt through the normal squad
flow, then recording the QGVerdict with the task id via
``core.evals.record_cli``. This CLI is the deterministic half — it
never invokes models itself.

Usage:
    arka-py -m core.evals.runner_cli list [--department dev]
    arka-py -m core.evals.runner_cli status
    arka-py -m core.evals.runner_cli prompt <task-id>
"""

from __future__ import annotations

import argparse
import sys

from core.evals.schema import EvalTask, load_eval_tasks
from core.evals.verdict_labels import load_verdict_labels

DISTILLATION_LABEL_GATE = 500  # ADR 2026-07-09-evals-and-distillation


def _cmd_list(department: str | None) -> int:
    tasks = load_eval_tasks()
    if department:
        tasks = [t for t in tasks if t.department == department]
    for task in tasks:
        print(f"{task.id:35s} {task.department:10s} {task.prompt[:60].strip()}…")
    print(f"\n{len(tasks)} task(s)")
    return 0


def _cmd_status() -> int:
    labels = load_verdict_labels()
    verdicts = [str(entry.get("verdict", "")) for entry in labels]
    by_dept: dict[str, int] = {}
    linked = 0
    for entry in labels:
        dept = str(entry.get("department") or "(none)")
        by_dept[dept] = by_dept.get(dept, 0) + 1
        if entry.get("eval_task_id"):
            linked += 1
    total = len(labels)
    print(f"labels: {total} (gate: {DISTILLATION_LABEL_GATE} — "
          f"{max(0, DISTILLATION_LABEL_GATE - total)} to go)")
    print(f"  APPROVED: {verdicts.count('APPROVED')}  "
          f"REJECTED: {verdicts.count('REJECTED')}")
    print(f"  linked to eval tasks: {linked}")
    for dept, count in sorted(by_dept.items()):
        print(f"  {dept}: {count}")
    print(f"eval tasks defined: {len(load_eval_tasks())}")
    return 0


def _dispatch_prompt(task: EvalTask) -> str:
    properties = "\n".join(f"- {p}" for p in task.expected_properties)
    rubric = f"\nRubrica adicional: {task.rubric}" if task.rubric else ""
    return (
        f"[EVAL RUN — task {task.id}]\n"
        f"Departamento: {task.department}\n\n"
        f"Tarefa: {task.prompt}\n\n"
        f"O deliverable será julgado pelo Quality Gate contra estas "
        f"propriedades verificáveis:\n{properties}{rubric}\n\n"
        f"Após o verdict, regista o label com:\n"
        f"  arka-py -m core.evals.record_cli --eval-task-id {task.id} "
        f"--department {task.department} < verdict.json"
    )


def _cmd_prompt(task_id: str) -> int:
    tasks = {t.id: t for t in load_eval_tasks()}
    task = tasks.get(task_id)
    if task is None:
        print(f"error: unknown eval task {task_id!r}; run `list`",
              file=sys.stderr)
        return 1
    print(_dispatch_prompt(task))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("--department")
    sub.add_parser("status")
    p_prompt = sub.add_parser("prompt")
    p_prompt.add_argument("task_id")
    args = parser.parse_args(argv)

    if args.cmd == "list":
        return _cmd_list(args.department)
    if args.cmd == "status":
        return _cmd_status()
    return _cmd_prompt(args.task_id)


if __name__ == "__main__":
    raise SystemExit(main())
