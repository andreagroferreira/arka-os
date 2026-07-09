"""Record a QGVerdict as an eval label — the QG-skill wiring point.

Reads the reviewer's QGVerdict JSON from stdin (or --file) and appends
it to the label corpus via ``record_verdict_label``. Invoked by the
orchestrator right after a Quality Gate verdict lands (see the Quality
Gate skill instructions), closing the "labels gratuitos" loop from the
evals ADR.

Unlike the underlying writer (telemetry contract: never raises), this
explicit CLI fails LOUDLY on invalid verdict JSON — a malformed label
recorded silently would poison the corpus.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from core.evals.verdict_labels import record_verdict_label
from core.governance.qg_verdict import QGVerdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="verdict JSON file (default: stdin)")
    parser.add_argument("--deliverable", default="")
    parser.add_argument("--department", default="")
    parser.add_argument("--eval-task-id", default="")
    parser.add_argument("--session-id", default="")
    args = parser.parse_args(argv)

    raw = (
        Path(args.file).read_text(encoding="utf-8")
        if args.file
        else sys.stdin.read()
    )
    try:
        verdict = QGVerdict.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid QGVerdict JSON — {exc}", file=sys.stderr)
        return 1

    record_verdict_label(
        verdict,
        deliverable=args.deliverable,
        department=args.department,
        eval_task_id=args.eval_task_id,
        session_id=args.session_id,
    )
    print(json.dumps({
        "recorded": True,
        "verdict": verdict.verdict,
        "eval_task_id": args.eval_task_id,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
